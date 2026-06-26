"""
PKI for Agent Skills — signed manifest creation and validation.

Each skill gets a manifest that bundles:
- SHA-256 of the skill file (byte integrity)
- SKILLS Checksum value (semantic integrity)
- Author identity (ed25519 public key)
- Cryptographic signature over the manifest
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric import ed25519

from .crypto import (
    compute_sha256,
    load_private_key,
    load_public_key,
    sign_data_b64,
    verify_signature,
    KeyPair,
)


MANIFEST_VERSION = "1.0"


@dataclass
class SkillInfo:
    """Information about the skill being signed."""
    name: str
    version: str = "0.1.0"
    description: str = ""
    sha256: str = ""
    checksum: dict | None = None
    dependencies: list[dict] = field(default_factory=list)


@dataclass
class Manifest:
    """A signed manifest for a skill artifact."""
    manifest_version: str = MANIFEST_VERSION
    skill: SkillInfo = field(default_factory=lambda: SkillInfo(name=""))
    author: dict = field(default_factory=dict)
    timestamp: str = ""
    signature: str = ""

    def to_dict(self) -> dict:
        return {
            "manifest_version": self.manifest_version,
            "skill": {
                "name": self.skill.name,
                "version": self.skill.version,
                "description": self.skill.description,
                "sha256": self.skill.sha256,
                "checksum": self.skill.checksum or {},
                "dependencies": self.skill.dependencies,
            },
            "author": self.author,
            "timestamp": self.timestamp,
            "signature": self.signature,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "Manifest":
        skill_data = data.get("skill", {})
        return cls(
            manifest_version=data.get("manifest_version", MANIFEST_VERSION),
            skill=SkillInfo(
                name=skill_data.get("name", ""),
                version=skill_data.get("version", "0.1.0"),
                description=skill_data.get("description", ""),
                sha256=skill_data.get("sha256", ""),
                checksum=skill_data.get("checksum"),
                dependencies=skill_data.get("dependencies", []),
            ),
            author=data.get("author", {}),
            timestamp=data.get("timestamp", ""),
            signature=data.get("signature", ""),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "Manifest":
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def from_file(cls, path: str | Path) -> "Manifest":
        return cls.from_json(Path(path).read_text())

    def save(self, path: str | Path) -> None:
        Path(path).write_text(self.to_json())


def create_manifest(
    skill_path: str | Path,
    skill_name: str,
    private_key: ed25519.Ed25519PrivateKey,
    public_key: ed25519.Ed25519PublicKey,
    version: str = "0.1.0",
    description: str = "",
    checksum_value: float | None = None,
    checksum_model: str = "",
    dependencies: list[dict] | None = None,
) -> Manifest:
    """Create and sign a manifest for a skill file."""
    skill_path = Path(skill_path)
    skill_bytes = skill_path.read_bytes()

    sha256_hash = compute_sha256(skill_bytes)

    skill_info = SkillInfo(
        name=skill_name,
        version=version,
        description=description,
        sha256=sha256_hash,
        checksum={
            "algorithm": "SKILLS_CHECKSUM_V1",
            "model": checksum_model or "all-MiniLM-L6-v2",
            "seed": 42,
            "value": checksum_value,
        } if checksum_value is not None else {},
        dependencies=dependencies or [],
    )

    pubkey_b64 = KeyPair(
        private_key=private_key,
        public_key=public_key,
        created_at=datetime.now(timezone.utc),
    ).public_key_b64

    manifest = Manifest(
        skill=skill_info,
        author={
            "pubkey": f"ed25519:{pubkey_b64}",
            "identity_proof": "",
        },
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    # Sign the JSON without the signature field
    unsigned_json = json.dumps({
        "manifest_version": manifest.manifest_version,
        "skill": {
            "name": manifest.skill.name,
            "version": manifest.skill.version,
            "sha256": manifest.skill.sha256,
            "checksum": manifest.skill.checksum,
            "dependencies": manifest.skill.dependencies,
        },
        "author": manifest.author,
        "timestamp": manifest.timestamp,
    }, sort_keys=True)

    signature = sign_data_b64(unsigned_json.encode("utf-8"), private_key)
    manifest.signature = signature

    return manifest


def verify_manifest(manifest: Manifest, public_key: ed25519.Ed25519PublicKey) -> bool:
    """Verify the cryptographic signature of a manifest."""
    unsigned_json = json.dumps({
        "manifest_version": manifest.manifest_version,
        "skill": {
            "name": manifest.skill.name,
            "version": manifest.skill.version,
            "sha256": manifest.skill.sha256,
            "checksum": manifest.skill.checksum,
            "dependencies": manifest.skill.dependencies,
        },
        "author": manifest.author,
        "timestamp": manifest.timestamp,
    }, sort_keys=True)

    return verify_signature(
        unsigned_json.encode("utf-8"), manifest.signature, public_key
    )


def verify_manifest_file(
    manifest_path: str | Path, public_key_pem: str
) -> tuple[bool, Manifest]:
    """Load and verify a manifest file against a public key.
    
    Returns:
        Tuple of (is_valid, manifest).
    """
    manifest = Manifest.from_file(manifest_path)
    pubkey = load_public_key(public_key_pem)
    is_valid = verify_manifest(manifest, pubkey)
    return is_valid, manifest
