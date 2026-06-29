"""
PKI for Agent Skills — verification integration for agent frameworks.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .manifest import Manifest, verify_manifest_file
from ..registry import TrustRegistry


@dataclass
class VerificationResult:
    trusted: bool
    trust_score: float
    signature_valid: bool
    checksum_match: bool
    manifest: Manifest | None = None
    warnings: list[str] | None = None


class SkillVerifier:
    def __init__(self, registry_db: str | Path, trust_threshold: float = 0.7):
        self.registry_db = str(registry_db)
        self.trust_threshold = trust_threshold

    def verify_and_load(
        self,
        skill_path: str | Path,
        manifest_path: str | Path,
        public_key_pem: str,
        expected_checksum: float | None = None,
        checksum_tolerance: float = 1e-4,
    ) -> VerificationResult:
        warnings = []
        
        # 1. Verify cryptographic signature
        try:
            sig_valid, manifest = verify_manifest_file(manifest_path, public_key_pem)
        except Exception as e:
            sig_valid = False
            manifest = None
            warnings.append(f"Signature verification failed: {e}")

        # 2. Check registry trust
        trust_score = 0.0
        if manifest:
            pubkey = manifest.author.get("pubkey", "")
            try:
                registry = TrustRegistry(self.registry_db)
                registry.init()
                trust_score = registry.get_author_trust(pubkey)
                
                if registry.is_revoked(manifest.skill.name, manifest.skill.version):
                    warnings.append("SKILL IS REVOKED")
                    sig_valid = False  # Treat revoked as untrusted
                registry.close()
            except Exception as e:
                warnings.append(f"Registry query failed: {e}")

        # 3. Check checksum
        checksum_match = True
        if expected_checksum is not None and manifest and manifest.skill.checksum:
            actual = manifest.skill.checksum.get("value")
            if actual is not None:
                if abs(expected_checksum - float(actual)) > checksum_tolerance:
                    checksum_match = False
                    warnings.append(f"Checksum mismatch: expected {expected_checksum}, got {actual}")
            else:
                checksum_match = False
                warnings.append("Manifest does not contain a checksum value")

        trusted = (
            sig_valid
            and checksum_match
            and trust_score >= self.trust_threshold
            and "SKILL IS REVOKED" not in warnings
        )

        return VerificationResult(
            trusted=trusted,
            trust_score=trust_score,
            signature_valid=sig_valid,
            checksum_match=checksum_match,
            manifest=manifest,
            warnings=warnings,
        )
