"""
PKI for Agent Skills — SQLite trust registry.

Manages author identities, skill records, trust scores,
and the transparency log (Merkle tree of all operations).
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class TrustRegistry:
    """SQLite-based trust registry for skill PKI.
    
    Maintains:
    - Author identities with trust scores
    - Skill records (published versions, checksums, manifests)
    - Dependency graph
    - Transparency log (append-only Merkle tree)
    - Revocation list
    """

    def __init__(self, db_path: str | Path = "pki-registry.db"):
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def init(self) -> None:
        """Create all tables if they don't exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS authors (
                id TEXT PRIMARY KEY,
                pubkey TEXT NOT NULL UNIQUE,
                display_name TEXT,
                verified_identity TEXT,
                trust_score REAL DEFAULT 0.5,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS skills (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                author_id TEXT REFERENCES authors(id),
                version TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                checksum_value REAL,
                checksum_model TEXT,
                manifest_json TEXT NOT NULL,
                trust_score REAL DEFAULT 0.5,
                status TEXT DEFAULT 'active',
                published_at TEXT NOT NULL,
                UNIQUE(name, version)
            );

            CREATE TABLE IF NOT EXISTS dependencies (
                skill_id TEXT REFERENCES skills(id),
                dependency_name TEXT NOT NULL,
                min_version TEXT,
                PRIMARY KEY (skill_id, dependency_name)
            );

            CREATE TABLE IF NOT EXISTS transparency_log (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                operation TEXT NOT NULL,
                skill_id TEXT,
                entry_hash TEXT NOT NULL,
                merkle_root TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS revocations (
                skill_id TEXT PRIMARY KEY REFERENCES skills(id),
                reason TEXT,
                revocation_signature TEXT NOT NULL,
                revoked_at TEXT NOT NULL
            );
        """)
        self.conn.commit()

    # ── Author operations ──

    def register_author(
        self,
        pubkey: str,
        display_name: str = "",
        verified_identity: str = "",
    ) -> str:
        """Register a new author or return existing author ID."""
        now = datetime.now(timezone.utc).isoformat()
        author_id = hashlib.sha256(pubkey.encode()).hexdigest()[:16]

        self.conn.execute(
            """INSERT OR IGNORE INTO authors (id, pubkey, display_name,
               verified_identity, trust_score, created_at, updated_at)
               VALUES (?, ?, ?, ?, 0.5, ?, ?)""",
            (author_id, pubkey, display_name, verified_identity, now, now),
        )
        self.conn.commit()
        return author_id

    def compute_author_trust(self, pubkey: str) -> float:
        """Dynamically compute the trust score for an author based on the architectural algorithm."""
        author = self.conn.execute(
            "SELECT * FROM authors WHERE pubkey = ?", (pubkey,)
        ).fetchone()
        if not author:
            return 0.0

        import math
        
        # 1. Identity verification (0.30)
        identity_score = 1.0 if author["verified_identity"] else 0.0
        
        # 2. Account age normalized (0.20)
        created_at = datetime.fromisoformat(author["created_at"])
        now = datetime.now(timezone.utc)
        age_days = (now - created_at).days
        age_score = min(1.0, age_days / 365.0)
        
        # 3. Skills published count (0.15)
        count_row = self.conn.execute(
            "SELECT COUNT(*) as c FROM skills WHERE author_id = ?", (author["id"],)
        ).fetchone()
        skills_count = count_row["c"] if count_row else 0
        count_score = min(1.0, math.log10(skills_count + 1) / 2.0)
        
        # 4. Incident free ratio (0.15)
        if skills_count == 0:
            incident_free_score = 1.0
        else:
            rev_row = self.conn.execute(
                """SELECT COUNT(*) as c FROM revocations r 
                   JOIN skills s ON r.skill_id = s.id 
                   WHERE s.author_id = ?""", (author["id"],)
            ).fetchone()
            revocations = rev_row["c"] if rev_row else 0
            incident_free_score = max(0.0, 1.0 - (revocations / skills_count))
            
        # 5. Community reviews (0.10) - MVP default 0.5
        reviews_score = 0.5
        
        # 6. Dependency graph centrality (0.10) - MVP default 0.5
        centrality_score = 0.5
        
        trust_score = (
            0.30 * identity_score +
            0.20 * age_score +
            0.15 * count_score +
            0.15 * incident_free_score +
            0.10 * reviews_score +
            0.10 * centrality_score
        )
        
        return trust_score

    def get_author_trust(self, pubkey: str) -> float:
        """Get dynamically computed trust score for an author (0.0-1.0), or 0.0 if not found."""
        author = self.conn.execute(
            "SELECT id FROM authors WHERE pubkey = ?", (pubkey,)
        ).fetchone()
        if not author:
            return 0.0
            
        score = self.compute_author_trust(pubkey)
        self.update_author_trust(pubkey, score)
        return score

    def update_author_trust(self, pubkey: str, score: float) -> None:
        """Update an author's trust score."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "UPDATE authors SET trust_score = ?, updated_at = ? WHERE pubkey = ?",
            (max(0.0, min(1.0, score)), now, pubkey),
        )
        self.conn.commit()

    # ── Skill operations ──

    def publish_skill(
        self,
        name: str,
        author_pubkey: str,
        version: str,
        sha256: str,
        checksum_value: float | None,
        checksum_model: str,
        manifest_json: str,
        dependencies: list[dict] | None = None,
    ) -> str:
        """Publish a new skill version. Returns skill ID."""
        now = datetime.now(timezone.utc).isoformat()
        author_id = self.register_author(author_pubkey)
        skill_id = hashlib.sha256(f"{name}:{version}:{sha256}".encode()).hexdigest()[:16]

        self.conn.execute(
            """INSERT OR REPLACE INTO skills
               (id, name, author_id, version, sha256, checksum_value,
                checksum_model, manifest_json, status, published_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)""",
            (skill_id, name, author_id, version, sha256, checksum_value,
             checksum_model, manifest_json, now),
        )

        if dependencies:
            for dep in dependencies:
                self.conn.execute(
                    """INSERT OR REPLACE INTO dependencies
                       (skill_id, dependency_name, min_version)
                       VALUES (?, ?, ?)""",
                    (skill_id, dep.get("name", ""), dep.get("min_version", "*")),
                )

        self._log_operation("publish", skill_id)
        self.conn.commit()
        return skill_id

    def get_skill(self, name: str, version: str | None = None) -> dict | None:
        """Get a skill record by name and optionally version."""
        if version:
            row = self.conn.execute(
                "SELECT * FROM skills WHERE name = ? AND version = ? AND status = 'active'",
                (name, version),
            ).fetchone()
        else:
            row = self.conn.execute(
                """SELECT * FROM skills
                   WHERE name = ? AND status = 'active'
                   ORDER BY published_at DESC LIMIT 1""",
                (name,),
            ).fetchone()
        return dict(row) if row else None

    def list_skills(self, author_pubkey: str | None = None) -> list[dict]:
        """List skills, optionally filtered by author."""
        if author_pubkey:
            rows = self.conn.execute(
                """SELECT s.* FROM skills s
                   JOIN authors a ON s.author_id = a.id
                   WHERE a.pubkey = ? AND s.status = 'active'
                   ORDER BY s.published_at DESC""",
                (author_pubkey,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM skills WHERE status = 'active' ORDER BY published_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Revocation ──

    def revoke_skill(self, name: str, version: str, reason: str) -> bool:
        """Revoke a skill version. Returns True if revoked."""
        now = datetime.now(timezone.utc).isoformat()
        skill = self.get_skill(name, version)
        if not skill:
            return False

        self.conn.execute(
            "UPDATE skills SET status = 'revoked' WHERE id = ?",
            (skill["id"],),
        )
        self.conn.execute(
            """INSERT OR REPLACE INTO revocations
               (skill_id, reason, revocation_signature, revoked_at)
               VALUES (?, ?, 'registry-admin', ?)""",
            (skill["id"], reason, now),
        )
        self._log_operation("revoke", skill["id"])
        self.conn.commit()
        return True

    def is_revoked(self, name: str, version: str) -> bool:
        """Check if a skill version is revoked."""
        row = self.conn.execute(
            "SELECT status FROM skills WHERE name = ? AND version = ?",
            (name, version),
        ).fetchone()
        return row is not None and row["status"] == "revoked"

    # ── Transparency log ──

    def _log_operation(self, operation: str, skill_id: str) -> None:
        """Append to transparency log with Merkle tree update."""
        now = datetime.now(timezone.utc).isoformat()
        entry_data = f"{operation}:{skill_id}:{now}"
        entry_hash = hashlib.sha256(entry_data.encode()).hexdigest()

        prev = self.conn.execute(
            "SELECT merkle_root FROM transparency_log ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        prev_root = prev["merkle_root"] if prev else "0" * 64

        merkle_root = hashlib.sha256(
            (prev_root + entry_hash).encode()
        ).hexdigest()

        self.conn.execute(
            """INSERT INTO transparency_log
               (operation, skill_id, entry_hash, merkle_root, timestamp)
               VALUES (?, ?, ?, ?, ?)""",
            (operation, skill_id, entry_hash, merkle_root, now),
        )

    def get_transparency_log(self, limit: int = 50) -> list[dict]:
        """Get recent transparency log entries."""
        rows = self.conn.execute(
            "SELECT * FROM transparency_log ORDER BY sequence DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_merkle_root(self) -> str:
        """Get the current Merkle tree root."""
        row = self.conn.execute(
            "SELECT merkle_root FROM transparency_log ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        return row["merkle_root"] if row else "0" * 64

    # ── Stats ──

    def stats(self) -> dict:
        """Get registry statistics."""
        return {
            "total_authors": self.conn.execute(
                "SELECT COUNT(*) as c FROM authors"
            ).fetchone()["c"],
            "total_skills": self.conn.execute(
                "SELECT COUNT(*) as c FROM skills WHERE status='active'"
            ).fetchone()["c"],
            "total_revocations": self.conn.execute(
                "SELECT COUNT(*) as c FROM revocations"
            ).fetchone()["c"],
            "total_operations": self.conn.execute(
                "SELECT COUNT(*) as c FROM transparency_log"
            ).fetchone()["c"],
            "merkle_root": self.get_merkle_root(),
        }

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
