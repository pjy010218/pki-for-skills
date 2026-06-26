"""
Tests for pki_skills package.
"""

import json
import tempfile
from pathlib import Path

import pytest


class TestCrypto:
    """Test ed25519 cryptographic operations."""

    def test_generate_keypair(self):
        from pki_skills.crypto import generate_keypair

        kp = generate_keypair()
        assert kp.private_key is not None
        assert kp.public_key is not None
        assert kp.created_at is not None

    def test_public_key_b64(self):
        from pki_skills.crypto import generate_keypair

        kp = generate_keypair()
        b64 = kp.public_key_b64
        assert len(b64) > 0
        # ed25519 raw public key is 32 bytes → 44 chars base64
        assert len(b64) == 44

    def test_sign_and_verify(self):
        from pki_skills.crypto import generate_keypair, sign_data, verify_signature

        kp = generate_keypair()
        data = b"test data to sign"
        sig = sign_data(data, kp.private_key)
        assert verify_signature(data, sig, kp.public_key)

    def test_verify_wrong_data(self):
        from pki_skills.crypto import generate_keypair, sign_data, verify_signature

        kp = generate_keypair()
        sig = sign_data(b"original data", kp.private_key)
        assert not verify_signature(b"tampered data", sig, kp.public_key)

    def test_save_and_load_keypair(self):
        from pki_skills.crypto import generate_keypair, save_keypair, load_private_key, load_public_key, sign_data, verify_signature

        kp = generate_keypair()
        with tempfile.TemporaryDirectory() as tmpdir:
            priv_path, pub_path = save_keypair(kp, tmpdir)
            
            assert priv_path.exists()
            assert pub_path.exists()
            
            loaded_priv = load_private_key(priv_path)
            loaded_pub = load_public_key(pub_path)
            
            # Sign with loaded private key, verify with loaded public key
            sig = sign_data(b"test", loaded_priv)
            assert verify_signature(b"test", sig, loaded_pub)

    def test_compute_sha256(self):
        from pki_skills.crypto import compute_sha256

        h = compute_sha256(b"hello world")
        assert len(h) == 64  # hex digest
        assert h == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"


class TestManifest:
    """Test manifest creation and verification."""

    def test_create_and_verify_manifest(self):
        from pki_skills.crypto import generate_keypair
        from pki_skills.manifest import create_manifest, verify_manifest

        kp = generate_keypair()
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("---\nname: test-skill\ndescription: Test\n---\nBody content here.\n")
            f.flush()
            skill_path = f.name

        manifest = create_manifest(
            skill_path=skill_path,
            skill_name="test-skill",
            private_key=kp.private_key,
            public_key=kp.public_key,
            version="1.0.0",
            description="Test skill",
            checksum_value=0.85,
        )

        assert manifest.skill.name == "test-skill"
        assert manifest.skill.version == "1.0.0"
        assert manifest.skill.sha256 != ""
        assert manifest.skill.checksum["value"] == 0.85
        assert manifest.signature != ""

        # Verify
        assert verify_manifest(manifest, kp.public_key)

        Path(skill_path).unlink()

    def test_manifest_serialization(self):
        from pki_skills.crypto import generate_keypair
        from pki_skills.manifest import create_manifest, Manifest

        kp = generate_keypair()
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("---\nname: test\ndescription: Test\n---\nBody\n")
            f.flush()
            skill_path = f.name

        manifest = create_manifest(
            skill_path=skill_path,
            skill_name="test",
            private_key=kp.private_key,
            public_key=kp.public_key,
        )

        # Serialize and deserialize
        json_str = manifest.to_json()
        restored = Manifest.from_json(json_str)
        
        assert restored.skill.name == manifest.skill.name
        assert restored.skill.sha256 == manifest.skill.sha256
        assert restored.signature == manifest.signature

        Path(skill_path).unlink()


class TestRegistry:
    """Test SQLite trust registry."""

    def test_registry_init(self):
        from pki_skills.registry import TrustRegistry

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        registry = TrustRegistry(db_path)
        registry.init()
        
        stats = registry.stats()
        assert stats["total_authors"] == 0
        assert stats["total_skills"] == 0
        
        registry.close()
        Path(db_path).unlink()

    def test_register_author_and_trust(self):
        from pki_skills.registry import TrustRegistry

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        registry = TrustRegistry(db_path)
        registry.init()

        author_id = registry.register_author("ed25519:testkey123", "Test Author")
        assert author_id != ""

        # Default trust score
        trust = registry.get_author_trust("ed25519:testkey123")
        assert trust == 0.5

        # Update trust
        registry.update_author_trust("ed25519:testkey123", 0.9)
        trust = registry.get_author_trust("ed25519:testkey123")
        assert trust == 0.9

        registry.close()
        Path(db_path).unlink()

    def test_publish_and_get_skill(self):
        from pki_skills.registry import TrustRegistry

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        registry = TrustRegistry(db_path)
        registry.init()

        skill_id = registry.publish_skill(
            name="test-skill",
            author_pubkey="ed25519:testkey",
            version="1.0.0",
            sha256="abc123",
            checksum_value=0.85,
            checksum_model="all-MiniLM-L6-v2",
            manifest_json="{}",
        )

        skill = registry.get_skill("test-skill")
        assert skill is not None
        assert skill["name"] == "test-skill"
        assert skill["version"] == "1.0.0"

        # Transparency log should have entry
        log = registry.get_transparency_log()
        assert len(log) == 1
        assert log[0]["operation"] == "publish"

        registry.close()
        Path(db_path).unlink()

    def test_revoke_skill(self):
        from pki_skills.registry import TrustRegistry

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        registry = TrustRegistry(db_path)
        registry.init()

        registry.publish_skill(
            name="test-skill",
            author_pubkey="ed25519:testkey",
            version="1.0.0",
            sha256="abc123",
            checksum_value=0.85,
            checksum_model="all-MiniLM-L6-v2",
            manifest_json="{}",
        )

        assert not registry.is_revoked("test-skill", "1.0.0")
        
        result = registry.revoke_skill("test-skill", "1.0.0", "Security vulnerability")
        assert result is True
        assert registry.is_revoked("test-skill", "1.0.0")

        registry.close()
        Path(db_path).unlink()
