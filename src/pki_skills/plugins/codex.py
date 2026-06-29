"""
Plugin wrapper for Codex Agent tool integration.
"""
from ..core.verifier import SkillVerifier

def verify_codex_skill(manifest_path: str, pubkey: str) -> bool:
    """
    Utility function meant to be called within Codex tool definitions 
    prior to executing sandbox code.
    """
    verifier = SkillVerifier(registry_db="pki-registry.db")
    result = verifier.verify_and_load(
        skill_path="",
        manifest_path=manifest_path,
        public_key_pem=pubkey
    )
    if not result.trusted:
        print(f"[Codex Security] Tool blocked. Validation failures: {result.warnings}")
        return False
    return True
