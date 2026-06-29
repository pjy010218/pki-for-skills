"""
Plugin wrapper for Hermes Agent framework integration.
"""
from typing import Any
from ..core.verifier import SkillVerifier

class HermesSkillMiddleware:
    """
    Middleware that plugs into Hermes' tool dispatch pipeline.
    Ensures that dynamically loaded skills pass PKI verification.
    """
    def __init__(self, registry_db: str = "pki-registry.db"):
        self.verifier = SkillVerifier(registry_db=registry_db)
        
    def pre_execute(self, tool_context: dict[str, Any]) -> bool:
        manifest_path = tool_context.get("manifest_path")
        pubkey = tool_context.get("author_pubkey")
        
        if not manifest_path or not pubkey:
            # Enforce strict mode
            return False
            
        result = self.verifier.verify_and_load(
            skill_path="",
            manifest_path=manifest_path,
            public_key_pem=pubkey
        )
        return result.trusted
