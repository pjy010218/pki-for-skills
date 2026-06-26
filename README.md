# PKI for Agent Skills

Public Key Infrastructure for cryptographic verification and trust management of AI agent skills.

## Overview

PKI for Agent Skills provides a complete trust infrastructure for the agent skill supply chain:

- **Cryptographic signing** — ed25519 signatures for skill manifests
- **Identity verification** — Author authentication via public keys
- **Trust registry** — SQLite-based reputation tracking
- **Transparency log** — Merkle tree audit trail for all operations
- **Revocation system** — Invalidate compromised skills

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PKI for Agent Skills                       │
├─────────────────────────────────────────────────────────────┤
│  Author                                                      │
│  ├── Generate ed25519 keypair                               │
│  ├── Sign skill manifest (SHA-256 + checksum + identity)    │
│  └── Publish to registry                                    │
├─────────────────────────────────────────────────────────────┤
│  Registry                                                    │
│  ├── Verify signature                                       │
│  ├── Track author reputation (trust score)                  │
│  ├── Maintain transparency log (Merkle tree)                │
│  └── Handle revocations                                     │
├─────────────────────────────────────────────────────────────┤
│  Consumer                                                    │
│  ├── Verify manifest signature                              │
│  ├── Check author trust score                               │
│  ├── Verify revocation status                               │
│  └── Load skill if trusted                                  │
└─────────────────────────────────────────────────────────────┘
```

## Installation

```bash
pip install -e .
```

## Quick Start

### Generate Keys

```bash
pki-skills keygen --output ~/.pki-skills/keys
```

This creates:
- `private.pem` — Keep secret, used for signing
- `public.pem` — Share publicly, used for verification

### Sign a Skill

```bash
pki-skills sign \
  --skill-path ./my-skill/SKILL.md \
  --private-key ~/.pki-skills/keys/private.pem \
  --output ./my-skill/manifest.json
```

The manifest includes:
- Skill metadata (name, version, description)
- SHA-256 hash of SKILL.md
- SKILLS Checksum value (semantic integrity)
- Author public key
- ed25519 signature

### Verify a Skill

```bash
pki-skills verify \
  --manifest ./my-skill/manifest.json \
  --skill-path ./my-skill/SKILL.md
```

Checks:
1. Signature validity (authenticity)
2. SHA-256 match (byte integrity)
3. SKILLS Checksum match (semantic integrity)
4. Revocation status
5. Author trust score

### Registry Operations

```bash
# Initialize registry
pki-skills registry init --db ~/.pki-skills/registry.db

# Register author
pki-skills registry register-author \
  --public-key ~/.pki-skills/keys/public.pem \
  --name "Alice" \
  --db ~/.pki-skills/registry.db

# Publish skill
pki-skills registry publish \
  --manifest ./my-skill/manifest.json \
  --db ~/.pki-skills/registry.db

# Check trust score
pki-skills registry trust-score \
  --public-key ~/.pki-skills/keys/public.pem \
  --db ~/.pki-skills/registry.db

# Revoke skill
pki-skills registry revoke \
  --skill-name "my-skill" \
  --reason "Security vulnerability" \
  --db ~/.pki-skills/registry.db
```

## Manifest Format

```json
{
  "version": "1.0",
  "skill": {
    "name": "my-skill",
    "version": "1.0.0",
    "description": "Does something useful",
    "sha256": "a1b2c3d4e5f6...",
    "checksum": 0.95
  },
  "author": {
    "public_key": "-----BEGIN PUBLIC KEY-----\n...",
    "name": "Alice",
    "timestamp": "2026-01-20T10:30:00Z"
  },
  "signature": "ed25519:..."
}
```

## Trust Model

### Trust Score Calculation

```python
trust_score = (
    0.4 * reputation_score +      # Community ratings
    0.3 * verification_level +    # Identity verification depth
    0.2 * skill_quality +         # Average checksum stability
    0.1 * tenure                  # Time since first publish
)
```

### Verification Levels

- **Level 0** — Anonymous (no identity verification)
- **Level 1** — Email verified
- **Level 2** — GitHub/GitLab linked
- **Level 3** — Domain ownership verified
- **Level 4** — Organization affiliation verified

## Security Considerations

### Threat Model

| Threat | Mitigation |
|--------|-----------|
| **Skill tampering** | SHA-256 + signature verification |
| **Identity spoofing** | ed25519 signatures, identity verification levels |
| **Replay attacks** | Timestamps in manifests, registry tracking |
| **Compromised author** | Revocation system, community reporting |
| **Registry compromise** | Merkle tree transparency log, distributed verification |

### Key Management

- **Private keys** — Store securely (hardware security module recommended for production)
- **Key rotation** — Generate new keypair, re-sign all skills, update registry
- **Key compromise** — Immediately revoke, publish new public key, re-sign skills

## Integration with SKILLS Checksum

PKI for Agent Skills works alongside [SKILLS Checksum](../skills-checksum/):

```python
from skills_checksum import SkillsChecksum
from pki_skills import ManifestVerifier

# Compute semantic checksum
checksum = SkillsChecksum()
checksum_value = checksum.compute(skill_path)

# Verify PKI manifest
verifier = ManifestVerifier(registry_db="~/.pki-skills/registry.db")
result = verifier.verify(manifest_path, skill_path)

if result.valid and result.trust_score >= 0.7:
    # Skill is authentic and from trusted author
    load_skill(skill_path)
```

## Testing

```bash
pytest tests/ -v
```

## License

MIT

## Related

- [SKILLS Checksum](../skills-checksum/) — Semantic integrity verification
- [Paper: SKILLS Checksum](../skills-checksum/paper/skills-checksum-ieee.tex) — Research foundation
