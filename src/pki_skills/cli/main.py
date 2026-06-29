"""
PKI for Agent Skills — command-line interface.

Commands:
    keygen      Generate a new ed25519 keypair
    sign        Sign a skill and create a manifest
    verify      Verify a skill's manifest and trust status
    registry    Manage the local trust registry
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..core.crypto import generate_keypair, load_private_key, load_public_key, save_keypair
from ..core.manifest import (
    Manifest,
    create_manifest,
    verify_manifest,
    verify_manifest_file,
)
from ..registry import TrustRegistry


def cmd_keygen(args: argparse.Namespace) -> int:
    """Generate a new ed25519 keypair."""
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Generating ed25519 keypair...")
    keypair = generate_keypair()
    priv_path, pub_path = save_keypair(keypair, output_dir)

    print(f"   Private key: {priv_path}")
    print(f"   Public key:  {pub_path}")
    print(f"   Public key (base64): {keypair.public_key_b64}")
    print(f"\n   Keep your private key secure. Never commit it to version control.")
    return 0


def cmd_sign(args: argparse.Namespace) -> int:
    """Sign a skill file and create a manifest."""
    skill_path = Path(args.skill)
    if not skill_path.exists():
        print(f"Skill file not found: {skill_path}")
        return 1

    private_key = load_private_key(args.private_key)
    public_key = load_public_key(args.public_key)

    skill_name = args.name or skill_path.parent.name

    manifest = create_manifest(
        skill_path=skill_path,
        skill_name=skill_name,
        private_key=private_key,
        public_key=public_key,
        version=args.version,
        description=args.description,
        checksum_value=args.checksum,
        checksum_model=args.checksum_model,
        dependencies=[],
    )

    manifest_path = skill_path.parent / f"{skill_path.stem}.manifest.json"
    if args.output:
        manifest_path = Path(args.output)
    manifest.save(manifest_path)

    print(f"Signed {skill_name} v{args.version}")
    print(f"   Manifest: {manifest_path}")
    print(f"   SHA-256:  {manifest.skill.sha256[:16]}...")
    if manifest.skill.checksum:
        print(f"   Checksum: {manifest.skill.checksum.get('value', 'N/A')}")
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    """Publish a signed skill manifest to the registry."""
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}")
        return 1

    pubkey_pem = args.public_key
    if Path(pubkey_pem).exists():
        pubkey_pem = Path(pubkey_pem).read_text()

    # 1. Verify signature
    is_valid, manifest = verify_manifest_file(manifest_path, pubkey_pem)
    if not is_valid:
        print("Signature INVALID — manifest cannot be published")
        return 1

    # 2. Publish to registry
    registry = TrustRegistry(args.db)
    registry.init()
    
    skill_id = registry.publish_skill(
        name=manifest.skill.name,
        author_pubkey=manifest.author.get("pubkey", ""),
        version=manifest.skill.version,
        sha256=manifest.skill.sha256,
        checksum_value=manifest.skill.checksum.get("value") if manifest.skill.checksum else None,
        checksum_model=manifest.skill.checksum.get("model", "") if manifest.skill.checksum else "",
        manifest_json=manifest.to_json(),
        dependencies=manifest.skill.dependencies,
    )
    registry.close()

    print(f"Successfully published {manifest.skill.name} v{manifest.skill.version}")
    print(f"   Skill ID: {skill_id}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify a skill manifest."""
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}")
        return 1

    pubkey_pem = args.public_key
    if Path(pubkey_pem).exists():
        pubkey_pem = Path(pubkey_pem).read_text()

    is_valid, manifest = verify_manifest_file(manifest_path, pubkey_pem)

    if is_valid:
        print(f"Signature valid")
        print(f"   Skill:  {manifest.skill.name} v{manifest.skill.version}")
        print(f"   Author: {manifest.author.get('pubkey', 'unknown')[:32]}...")
        print(f"   Signed: {manifest.timestamp}")
        print(f"   SHA-256:{manifest.skill.sha256[:16]}...")
        if manifest.skill.checksum:
            print(f"   Checksum: {manifest.skill.checksum.get('value', 'N/A')}")
    else:
        print(f"Signature INVALID — manifest may be tampered")
        return 1

    if args.db:
        registry = TrustRegistry(args.db)
        registry.init()
        pubkey = manifest.author.get("pubkey", "")
        trust = registry.get_author_trust(pubkey)
        print(f"   Trust:   {trust:.2f}")
        revoked = registry.is_revoked(
            manifest.skill.name, manifest.skill.version
        )
        if revoked:
            print(f"   WARNING: SKILL IS REVOKED")
            return 1
        registry.close()

    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    """Audit a skill manifest against the transparency log."""
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}")
        return 1

    pubkey_pem = args.public_key
    if Path(pubkey_pem).exists():
        pubkey_pem = Path(pubkey_pem).read_text()

    is_valid, manifest = verify_manifest_file(manifest_path, pubkey_pem)
    if not is_valid:
        print("Signature INVALID — cannot audit")
        return 1

    registry = TrustRegistry(args.db)
    registry.init()
    
    skill = registry.get_skill(manifest.skill.name, manifest.skill.version)
    if not skill:
        print(f"Skill {manifest.skill.name} v{manifest.skill.version} not found in registry.")
        registry.close()
        return 1

    rows = registry.conn.execute(
        "SELECT * FROM transparency_log WHERE skill_id = ? AND operation = 'publish' ORDER BY sequence ASC",
        (skill["id"],)
    ).fetchall()

    if not rows:
        print(f"No transparency log entry found for skill ID {skill['id']}")
        registry.close()
        return 1

    first_entry = rows[0]
    print(f"Transparency Verification SUCCESS")
    print(f"   Skill:       {manifest.skill.name} v{manifest.skill.version}")
    print(f"   Skill ID:    {skill['id']}")
    print(f"   Log Seq:     {first_entry['sequence']}")
    print(f"   Merkle Root: {first_entry['merkle_root']}")
    print(f"   Timestamp:   {first_entry['timestamp']}")
    registry.close()
    return 0


def cmd_abc(args: argparse.Namespace) -> int:
    """Evaluate skill behavioral integrity (ABC)."""
    from ..abc.sandbox import SandboxSimulator
    from ..abc.embedding import SentenceTransformerProvider
    from ..abc.checksum import compute_distributional_checksum, verify_abc_distance
    import json
    import numpy as np
    
    if args.abc_action == "compute":
        print(f"Loading embedding model 'all-MiniLM-L6-v2' (this may take a moment)...")
        embedder = SentenceTransformerProvider()
        
        print("Running Sandbox Simulator...")
        simulator = SandboxSimulator()
        skill_name = Path(args.skill).stem if args.skill else "unknown_skill"
        traces = simulator.execute_skill(skill_name)
        
        print(f"Generated {len(traces)} execution traces.")
        print("Computing embeddings...")
        embeddings = [embedder.embed_trace(t) for t in traces]
        
        print("Computing ABC (Mean, Covariance)...")
        mu, sigma = compute_distributional_checksum(embeddings)
        
        abc_data = {
            "skill": skill_name,
            "mu": mu.tolist(),
            "sigma": sigma.tolist(),
        }
        out_path = Path(args.skill).parent / f"{skill_name}.abc.json" if args.skill else Path(f"{skill_name}.abc.json")
        with open(out_path, "w") as f:
            json.dump(abc_data, f)
            
        print(f"ABC Checksum computed and saved to {out_path}")
        return 0

    elif args.abc_action == "verify":
        abc_path = Path(args.abc_file)
        if not abc_path.exists():
            print(f"ABC file not found: {abc_path}")
            return 1
            
        with open(abc_path, "r") as f:
            abc_data = json.load(f)
            
        mu = np.array(abc_data["mu"])
        sigma = np.array(abc_data["sigma"])
        
        trace_text = Path(args.trace_file).read_text(encoding="utf-8")
        print(f"Loading embedding model...")
        embedder = SentenceTransformerProvider()
        
        trace_emb = embedder.embed_trace(trace_text)
        
        is_valid, dist = verify_abc_distance(trace_emb, mu, sigma, threshold=args.threshold)
        print(f"Mahalanobis Distance: {dist:.4f} (Threshold: {args.threshold})")
        
        if is_valid:
            print("BEHAVIORAL INTEGRITY VERIFIED (PASS)")
            return 0
        else:
            print("BEHAVIORAL INTEGRITY VIOLATION DETECTED (FAIL)")
            return 1
    else:
        print(f"Unknown abc action: {args.abc_action}")
        return 1


def cmd_registry(args: argparse.Namespace) -> int:
    """Manage the trust registry."""
    registry = TrustRegistry(args.db)
    registry.init()

    if args.action == "init":
        print(f"Registry initialized at {args.db}")
        return 0

    elif args.action == "stats":
        stats = registry.stats()
        print("Registry Statistics")
        for k, v in stats.items():
            print(f"   {k}: {v}")
        return 0

    elif args.action == "log":
        entries = registry.get_transparency_log(limit=args.limit)
        print(f"Transparency Log (last {len(entries)} entries):")
        for e in entries:
            print(f"   [{e['sequence']}] {e['operation']:8s} {e['skill_id']} @ {e['timestamp']}")
        return 0

    elif args.action == "trust":
        if not args.pubkey or args.score is None:
            print("--pubkey and --score required for trust action")
            return 1
        registry.update_author_trust(args.pubkey, args.score)
        print(f"Trust score for {args.pubkey[:32]}... set to {args.score}")
        return 0

    elif args.action == "list":
        skills = registry.list_skills()
        if not skills:
            print("(no skills published)")
        for s in skills:
            print(f"   {s['name']} v{s['version']} [{s['status']}]")
        return 0

    else:
        print(f"Unknown registry action: {args.action}")
        return 1


def main() -> int:
    """Main entry point for the pki-skills CLI."""
    parser = argparse.ArgumentParser(
        prog="pki-skills",
        description="PKI for Agent Skills — cryptographic trust for AI agent skill supply chains",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # keygen
    p_keygen = subparsers.add_parser("keygen", help="Generate a new ed25519 keypair")
    p_keygen.add_argument("-o", "--output-dir", default=".", help="Output directory for keys")

    # sign
    p_sign = subparsers.add_parser("sign", help="Sign a skill and create a manifest")
    p_sign.add_argument("skill", help="Path to SKILL.md file")
    p_sign.add_argument("-k", "--private-key", default="pki-skills-private.key",
                        help="Path to private key file")
    p_sign.add_argument("-p", "--public-key", default="pki-skills-public.key",
                        help="Path to public key file")
    p_sign.add_argument("-n", "--name", help="Skill name (default: directory name)")
    p_sign.add_argument("-v", "--version", default="0.1.0", help="Skill version")
    p_sign.add_argument("-d", "--description", default="", help="Skill description")
    p_sign.add_argument("-c", "--checksum", type=float, help="Pre-computed SKILLS Checksum value")
    p_sign.add_argument("-m", "--checksum-model", default="all-MiniLM-L6-v2",
                        help="Model used for checksum")
    p_sign.add_argument("-o", "--output", help="Output path for manifest")

    # publish
    p_publish = subparsers.add_parser("publish", help="Publish a signed manifest to the registry")
    p_publish.add_argument("manifest", help="Path to .manifest.json file")
    p_publish.add_argument("-p", "--public-key", required=True,
                           help="Author's public key (PEM file or string)")
    p_publish.add_argument("-d", "--db", default="pki-registry.db",
                           help="Registry database path")

    # verify
    p_verify = subparsers.add_parser("verify", help="Verify a skill manifest")
    p_verify.add_argument("manifest", help="Path to .manifest.json file")
    p_verify.add_argument("-p", "--public-key", required=True,
                          help="Author's public key (PEM file or string)")
    p_verify.add_argument("-d", "--db", default="pki-registry.db",
                          help="Registry database path (for trust lookup)")

    # audit
    p_audit = subparsers.add_parser("audit", help="Audit a skill against the transparency log")
    p_audit.add_argument("manifest", help="Path to .manifest.json file")
    p_audit.add_argument("-p", "--public-key", required=True,
                         help="Author's public key (PEM file or string)")
    p_audit.add_argument("-d", "--db", default="pki-registry.db",
                         help="Registry database path")

    # abc
    p_abc = subparsers.add_parser("abc", help="Evaluate skill behavioral integrity (ABC)")
    p_abc.add_argument("abc_action", choices=["compute", "verify"], help="Action to perform")
    p_abc.add_argument("--skill", help="Path to SKILL.md (for compute)")
    p_abc.add_argument("--abc-file", help="Path to .abc.json file (for verify)")
    p_abc.add_argument("--trace-file", help="Path to execution trace file (for verify)")
    p_abc.add_argument("-t", "--threshold", type=float, default=3.0, help="Mahalanobis distance threshold")

    # registry
    p_reg = subparsers.add_parser("registry", help="Manage the trust registry")
    p_reg.add_argument("action", choices=["init", "stats", "log", "trust", "list"],
                       help="Registry action")
    p_reg.add_argument("-d", "--db", default="pki-registry.db",
                       help="Registry database path")
    p_reg.add_argument("--pubkey", help="Author public key (for trust action)")
    p_reg.add_argument("--score", type=float, help="Trust score 0.0-1.0 (for trust action)")
    p_reg.add_argument("--limit", type=int, default=20,
                       help="Max log entries (for log action)")

    args = parser.parse_args()

    if args.command == "keygen":
        return cmd_keygen(args)
    elif args.command == "sign":
        return cmd_sign(args)
    elif args.command == "publish":
        return cmd_publish(args)
    elif args.command == "verify":
        return cmd_verify(args)
    elif args.command == "audit":
        return cmd_audit(args)
    elif args.command == "abc":
        return cmd_abc(args)
    elif args.command == "registry":
        return cmd_registry(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
