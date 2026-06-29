"""
PKI for Agent Skills — ed25519 cryptographic operations.

Key generation, signing, and verification for skill manifests.
Uses the `cryptography` library for ed25519 operations.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


@dataclass
class KeyPair:
    """An ed25519 keypair for skill signing."""

    private_key: ed25519.Ed25519PrivateKey
    public_key: ed25519.Ed25519PublicKey
    created_at: datetime

    @property
    def public_key_b64(self) -> str:
        """Base64-encoded public key (raw bytes, no PEM)."""
        raw = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return base64.b64encode(raw).decode("ascii")

    @property
    def public_key_pem(self) -> str:
        """PEM-encoded public key."""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")


def generate_keypair() -> KeyPair:
    """Generate a new ed25519 keypair."""
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return KeyPair(
        private_key=private_key,
        public_key=public_key,
        created_at=datetime.now(timezone.utc),
    )


def save_keypair(keypair: KeyPair, output_dir: str | Path = ".") -> tuple[Path, Path]:
    """Save a keypair to disk.
    
    Returns:
        Tuple of (private_key_path, public_key_path).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    priv_path = output_dir / "pki-skills-private.key"
    priv_pem = keypair.private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    priv_path.write_bytes(priv_pem)
    priv_path.chmod(0o600)

    pub_path = output_dir / "pki-skills-public.key"
    pub_path.write_text(keypair.public_key_pem)

    return priv_path, pub_path


def load_private_key(path: str | Path) -> ed25519.Ed25519PrivateKey:
    """Load a private key from a PEM file."""
    pem_data = Path(path).read_bytes()
    key = serialization.load_pem_private_key(pem_data, password=None)
    if not isinstance(key, ed25519.Ed25519PrivateKey):
        raise ValueError(f"Expected Ed25519 private key, got {type(key)}")
    return key


def load_public_key(path_or_pem: str | Path) -> ed25519.Ed25519PublicKey:
    """Load a public key from a PEM file or PEM string."""
    path_or_pem_str = str(path_or_pem)
    if "-----BEGIN" in path_or_pem_str:
        pem_data = path_or_pem_str.encode("ascii")
    else:
        pem_data = Path(path_or_pem_str).read_bytes()
    key = serialization.load_pem_public_key(pem_data)
    if not isinstance(key, ed25519.Ed25519PublicKey):
        raise ValueError(f"Expected Ed25519 public key, got {type(key)}")
    return key


def load_public_key_from_b64(b64_str: str) -> ed25519.Ed25519PublicKey:
    """Load a public key from a base64-encoded raw key."""
    raw = base64.b64decode(b64_str)
    return ed25519.Ed25519PublicKey.from_public_bytes(raw)


def sign_data(data: bytes, private_key: ed25519.Ed25519PrivateKey) -> bytes:
    """Sign data with an ed25519 private key."""
    return private_key.sign(data)


def sign_data_b64(data: bytes, private_key: ed25519.Ed25519PrivateKey) -> str:
    """Sign data and return base64-encoded signature."""
    sig = sign_data(data, private_key)
    return base64.b64encode(sig).decode("ascii")


def verify_signature(
    data: bytes, signature: bytes | str, public_key: ed25519.Ed25519PublicKey
) -> bool:
    """Verify an ed25519 signature."""
    if isinstance(signature, str):
        signature = base64.b64decode(signature)
    try:
        public_key.verify(signature, data)
        return True
    except InvalidSignature:
        return False


def compute_sha256(data: bytes) -> str:
    """Compute SHA-256 hash of data. Returns hex digest."""
    return hashlib.sha256(data).hexdigest()
