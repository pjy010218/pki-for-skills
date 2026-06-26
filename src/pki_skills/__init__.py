"""
PKI for Agent Skills — Cryptographic trust infrastructure
for AI agent skill supply chains.
"""

__version__ = "0.1.0"

from .crypto import generate_keypair, KeyPair
from .manifest import Manifest, create_manifest, verify_manifest

__all__ = [
    "generate_keypair",
    "KeyPair",
    "Manifest",
    "create_manifest",
    "verify_manifest",
]
