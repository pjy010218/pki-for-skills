"""
Plugin wrapper for Claude Code Model Context Protocol (MCP) tool integration.
"""
from typing import Any, Callable
from ..core.verifier import SkillVerifier

def claude_mcp_verifier(
    skill_manifest_path: str,
    author_pubkey: str,
    registry_db: str = "pki-registry.db"
) -> Callable:
    """
    Decorator for intercepting Claude Code MCP tool execution.
    Fails execution if the skill fails cryptographic or behavioral integrity checks.
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            verifier = SkillVerifier(registry_db=registry_db)
            result = verifier.verify_and_load(
                skill_path="",
                manifest_path=skill_manifest_path,
                public_key_pem=author_pubkey
            )
            if not result.trusted:
                raise PermissionError(
                    f"Claude Code blocked tool execution: SKILL UNTRUSTED. Reasons: {result.warnings}"
                )
            return func(*args, **kwargs)
        return wrapper
    return decorator
