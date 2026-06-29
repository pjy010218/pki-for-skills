"""
PKI for Agent Skills — Cryptographic trust infrastructure
for AI agent skill supply chains.
"""

__version__ = "0.1.0"

from .core import (
    generate_keypair,
    KeyPair,
    Manifest,
    create_manifest,
    verify_manifest,
    VerificationResult,
    SkillVerifier,
)
from .registry import TrustRegistry

__all__ = [
    "generate_keypair",
    "KeyPair",
    "Manifest",
    "create_manifest",
    "verify_manifest",
    "VerificationResult",
    "SkillVerifier",
    "TrustRegistry",
]
