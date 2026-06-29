"""
Key Lineage and Rotation tracking for advanced security (Phase 5).
"""
import json
from dataclasses import dataclass
from typing import Any
import base64

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.serialization import load_pem_public_key


@dataclass
class KeyLineageRecord:
    old_pubkey_pem: str
    new_pubkey_pem: str
    signature: str  # Signed by old_pubkey_pem proving authorization
    timestamp: str


def verify_key_rotation(record: KeyLineageRecord) -> bool:
    """Verify that the old key authorized the rotation to the new key."""
    # Serialize payload to guarantee deterministic bytes for signature
    payload = json.dumps({
        "old_pubkey": record.old_pubkey_pem,
        "new_pubkey": record.new_pubkey_pem,
        "timestamp": record.timestamp
    }, sort_keys=True).encode("utf-8")
    
    # Load old key and verify
    try:
        pubkey = load_pem_public_key(record.old_pubkey_pem.encode("utf-8"))
        if not isinstance(pubkey, ed25519.Ed25519PublicKey):
            return False
            
        sig_bytes = base64.b64decode(record.signature)
        pubkey.verify(sig_bytes, payload)
        return True
    except Exception:
        return False
