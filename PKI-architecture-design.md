---
title: "PKI for Agent Skills — Architecture Design"
author: "Junyeong Park (박준영)"
date: 2026-06-17
version: "v0.1 — Initial Architecture"
status: "Draft for Discussion"
---

# PKI for Agent Skills: Architecture Design

## 1. Executive Summary

SKILLS Checksum verifies **what** a skill claims to be. PKI for Agent Skills verifies **who** published it and **whether they should be trusted**. Together they form a complete integrity infrastructure for the agent skill supply chain.

This document defines:
- The **trust model** — who trusts whom, and on what basis
- The **protocol** — the lifecycle of a skill from author publication to consumer verification
- The **threat model** — what attacks exist and how PKI defends against them
- The **architecture** — components, interfaces, and deployment topology

## 2. Trust Model

### 2.1 Trust Relationships

```
┌─────────────┐     publishes     ┌──────────────┐
│   Author    │ ──────────────────▶│   Registry   │
│  (Signer)   │   signed skill    │ (Trust Anchor)│
└─────────────┘                   └──────┬───────┘
                                         │
                                    look up trust
                                         │
┌─────────────┐  verify signature  ┌─────▼───────┐
│  Consumer   │ ◀───────────────── │   Verifier  │
│  (Agent)    │   trusted/blocked  │             │
└─────────────┘                    └─────────────┘
```

**Three types of trust:**

| Trust Type | Mechanism | Example |
|-----------|-----------|---------|
| **Cryptographic** | ed25519 signature verification | "This skill was signed by key X" |
| **Reputational** | Registry trust score (multi-signal) | "Key X belongs to a verified Google engineer" |
| **Transitive** | Merkle-DAG of skill dependencies | "Skill A trusts B, B trusts C → A trusts C" |

### 2.2 Trust is NOT Binary

Unlike traditional PKI (valid/invalid certificate), skill trust is **continuous**:

```
Trust Score = f(crypto_sig, author_reputation, skill_age,
                incident_history, community_reviews, checksum_stability)
```

A skill with a valid signature but from a new author might get `trust=0.3` ("load with caution"). A skill from a verified organization with clean history gets `trust=0.95` ("load with confidence").

### 2.3 Consumer Authority

Following the **Consumer-Driven Integrity** principle (Haunting Idea #3 from SKILLS Checksum): consumers define their own trust thresholds. An enterprise security team might require `trust ≥ 0.9` + `SKILLS Checksum match`. An individual developer might accept `trust ≥ 0.3`.

## 3. Protocol Specification

### 3.1 Skill Lifecycle

```
PHASE 1: PUBLISH (Author)
  1. Author generates ed25519 keypair
  2. Author writes skill SKILL.md
  3. Author computes SKILLS Checksum χ(S)
  4. Author creates signed manifest:
     {
       skill_hash: SHA-256(SKILL.md)
       checksum: χ(S)
       author_pubkey: <ed25519 public key>
       timestamp: ISO8601
       signature: ed25519_sign(privkey, manifest)
     }
  5. Author publishes (SKILL.md, manifest) to registry

PHASE 2: REGISTER (Registry)
  6. Registry verifies signature against pubkey
  7. Registry verifies SKILLS Checksum matches skill content
  8. Registry assigns initial trust score based on author identity
  9. Registry appends to transparency log (Merkle tree)
  10. Registry returns receipt (Merkle proof of inclusion)

PHASE 3: VERIFY (Consumer)
  11. Agent downloads (SKILL.md, manifest)
  12. Agent verifies ed25519 signature
  13. Agent recomputes SKILLS Checksum, compares to manifest
  14. Agent queries registry for author trust score
  15. Agent computes composite trust decision
  16. Agent loads skill if trust ≥ policy threshold

PHASE 4: REVOKE (Author or Registry)
  17. Author signs revocation statement
  18. Registry appends revocation to transparency log
  19. Consumers detect revocation on next verification
```

### 3.2 Manifest Format

```json
{
  "manifest_version": "1.0",
  "skill": {
    "name": "example-skill",
    "version": "1.2.0",
    "checksum": {
      "algorithm": "SKILLS_CHECKSUM_V1",
      "model": "all-MiniLM-L6-v2",
      "seed": 42,
      "value": 0.984721
    },
    "sha256": "a1b2c3d4e5f6...",
    "dependencies": [
      {"name": "base-security-skill", "min_version": "2.0.0"}
    ]
  },
  "author": {
    "pubkey": "ed25519:abc123...",
    "identity_proof": "https://github.com/author-proof"
  },
  "timestamp": "2026-06-17T12:00:00Z",
  "signature": "ed25519_sig:xyz789..."
}
```

## 4. Threat Model

### 4.1 Attacks and Defenses

| Attack | SKILLS Checksum Alone | + PKI |
|--------|----------------------|-------|
| **Malicious author** publishes evil skill with honest intent description | ❌ Missed (intent matches content) | ❌ Missed (author is real, just malicious) — requires behavioral analysis layer |
| **Impersonation** — attacker poses as trusted author | ✅ Checksum passes but wrong author | ✅ Prevented: signature verification fails |
| **Registry compromise** — attacker modifies skill in registry | ✅ Detected: checksum mismatch | ✅ Detected: signature + checksum both fail |
| **Key compromise** — author's private key stolen | ❌ Not addressed | ⚠️ Detected via key revocation, but window of vulnerability exists |
| **Dependency hijack** — trusted skill depends on malicious sub-skill | ❌ Not addressed | ✅ Transitive trust chain: verify entire dependency tree |
| **Rollback attack** — attacker serves old, vulnerable version | ❌ Not addressed | ✅ Version pinning + registry transparency log |
| **Skill drift** — author silently updates skill with backdoor | ✅ Checksum detects semantic change | ✅ Signature + versioning prevent silent updates |

### 4.2 PKI-Specific Threat Mitigations

**Key Rotation:** Authors rotate keys periodically. Old key signs a delegation to new key. Registry maintains key lineage. Consumers verify chain of delegations.

**Transparency Log:** All registry operations (publish, update, revoke) are logged in an append-only Merkle tree. Consumers can verify their view is consistent with everyone else's. Prevents split-world attacks where registry shows different content to different consumers.

**Revocation Checking:** Consumers MUST check revocation status before loading. Two mechanisms: (1) CRL-style — registry publishes signed revocation list; (2) OCSP-style — consumer queries registry for specific skill status.

## 5. System Architecture

### 5.1 Components

```
┌─────────────────────────────────────────────────────┐
│                   PKI for Skills                      │
├───────────────┬──────────────┬──────────────────────┤
│  skill-sign   │  skill-verify│  trust-registry       │
│  (CLI)        │  (CLI/Lib)   │  (Server + DB)        │
│               │              │                       │
│  • Key gen    │  • Sig check │  • Identity mgmt      │
│  • Manifest   │  • Checksum  │  • Reputation score   │
│    creation   │    verify    │  • Transparency log   │
│  • Signing    │  • Trust     │  • Revocation list    │
│               │    query     │  • Dependency graph   │
├───────────────┴──────────────┴──────────────────────┤
│              SKILLS Checksum Pipeline                 │
│         (frozen embedding + cosine similarity)        │
└─────────────────────────────────────────────────────┘
```

### 5.2 CLI Commands

```bash
# Author operations
pki-skills keygen              # Generate ed25519 keypair
pki-skills sign SKILL.md       # Create signed manifest
pki-skills publish SKILL.md    # Sign + push to registry

# Consumer operations
pki-skills verify SKILL.md     # Verify signature + checksum
pki-skills trust SKILL.md      # Query registry trust score
pki-skills audit SKILL.md      # Full transparency verification

# Registry operations (admin)
pki-skills registry init       # Initialize local registry
pki-skills registry trust <id> # Set trust score
pki-skills registry revoke <id># Revoke a skill
```

### 5.3 Integration with Agent Frameworks

The verification library (`libpki-skills`) is designed to be embedded in agent frameworks:

```python
# In Claude Code / Codex / Cursor / Hermes skill loader:
from pki_skills import SkillVerifier

verifier = SkillVerifier(trust_threshold=0.7)
result = verifier.verify_and_load("path/to/SKILL.md")

if result.trusted:
    agent.load_skill(result.skill_content)
else:
    agent.warn(f"Skill trust={result.trust_score} < threshold")
```

## 6. Registry Design

### 6.1 Schema (SQLite MVP → PostgreSQL production)

```sql
-- Authors table
CREATE TABLE authors (
    id TEXT PRIMARY KEY,
    pubkey TEXT NOT NULL UNIQUE,
    display_name TEXT,
    verified_identity TEXT,  -- URL to GitHub/LinkedIn proof
    trust_score REAL DEFAULT 0.5,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Skills table
CREATE TABLE skills (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    author_id TEXT REFERENCES authors(id),
    version TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    checksum_value REAL NOT NULL,
    checksum_model TEXT,
    manifest_json TEXT NOT NULL,  -- Full signed manifest
    trust_score REAL DEFAULT 0.5,
    status TEXT DEFAULT 'active',  -- active, revoked, superseded
    published_at TIMESTAMP,
    UNIQUE(name, version)
);

-- Dependencies table
CREATE TABLE dependencies (
    skill_id TEXT REFERENCES skills(id),
    dependency_id TEXT REFERENCES skills(id),
    min_version TEXT,
    PRIMARY KEY (skill_id, dependency_id)
);

-- Transparency log (Merkle tree)
CREATE TABLE transparency_log (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    operation TEXT NOT NULL,        -- publish, update, revoke
    skill_id TEXT,
    entry_hash TEXT NOT NULL,       -- SHA-256 of entry
    merkle_root TEXT NOT NULL,      -- Root after this entry
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Revocations
CREATE TABLE revocations (
    skill_id TEXT PRIMARY KEY REFERENCES skills(id),
    reason TEXT,
    revocation_signature TEXT NOT NULL,
    revoked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 6.2 Trust Score Computation

```
TRUST_SCORE = 
    0.30 × identity_verification (0 or 1)
  + 0.20 × account_age_normalized (days/365, capped at 1)
  + 0.15 × skills_published_count (log scale)
  + 0.15 × incident_free_ratio (1 - revocations/published)
  + 0.10 × community_reviews (normalized rating)
  + 0.10 × dependency_graph_centrality (bootstrapping penalty)
```

## 7. Integration with SKILLS Checksum

### 7.1 Layered Defense Architecture

```
                    ┌──────────────────────┐
                    │  BEHAVIORAL ANALYSIS  │  ← Layer 3: Agent Behavioral Checksum
                    │  (Future: ABC paper)  │     Runtime sandbox traces
                    ├──────────────────────┤
                    │    PKI + REGISTRY     │  ← Layer 2: PKI for Agent Skills
                    │  (This project)       │     Who published? Are they trusted?
                    ├──────────────────────┤
                    │  SKILLS CHECKSUM      │  ← Layer 1: Semantic integrity
                    │  (Paper complete)     │     Does intent match content?
                    ├──────────────────────┤
                    │     SHA-256           │  ← Layer 0: Byte integrity
                    │                       │     Did the bytes change?
                    └──────────────────────┘
```

Each layer catches what the layers below cannot. PKI catches impersonation and unauthorized updates that SKILLS Checksum alone cannot.

### 7.2 Verification Pipeline (Integrated)

```python
def verify_skill(skill_path, trust_threshold=0.7):
    # Layer 0: Byte integrity
    file_hash = sha256(skill_path)
    
    # Layer 1: Semantic integrity
    checksum = compute_skills_checksum(skill_path)
    
    # Layer 2: PKI
    manifest = load_manifest(skill_path)
    sig_valid = ed25519_verify(manifest.signature, manifest.author_pubkey)
    author_trust = registry.get_trust(manifest.author_pubkey)
    checksum_match = abs(checksum - manifest.checksum_value) < THRESHOLD
    
    # Composite decision
    trusted = (sig_valid and checksum_match and author_trust >= trust_threshold)
    
    return VerificationResult(
        trusted=trusted,
        trust_score=author_trust,
        checksum_match=checksum_match,
        signature_valid=sig_valid,
        warnings=generate_warnings(...)
    )
```

## 8. Roadmap

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| **Phase 1: MVP** | Week 1-2 | CLI (sign, verify) + SQLite registry + integration with SKILLS Checksum |
| **Phase 2: Security** | Week 3-4 | Transparency log, key rotation, revocation, threat model validation |
| **Phase 3: Ecosystem** | Week 5-6 | Open-source registry server, agent framework plugins (Hermes, Claude Code) |
| **Phase 4: Paper + Patent** | Week 7-8 | PKI for Agent Skills whitepaper, CIP patent filing |
| **Phase 5: Business** | Week 9+ | Customer interviews, managed registry SaaS, enterprise compliance |

## 9. Open Questions for Discussion

1. **Trust anchor**: Who runs the root registry? A foundation (like Let's Encrypt)? A company (CLEAR)? Decentralized (blockchain)?
2. **Identity binding**: How do we bind a pubkey to a real-world identity? OIDC? GitHub verification? Web of Trust?
3. **Federation**: Should there be one global registry or many federated registries (like package registries: npm, PyPI, crates.io)?
4. **Privacy**: Does the transparency log expose author identities? Should there be pseudonymous publishing?
5. **Business model**: Managed registry SaaS vs. open-source self-hosted? Which drives CLEAR integration?
