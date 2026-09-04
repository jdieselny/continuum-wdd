import argparse
import sys

def init_command(args):
    print("WDD Init: Initializing new project...")
    import os
    import json
    from wdd.compiler import BlueprintEngine

    # Generate the mailbox/ structure with .gitkeep locks
    dirs = [
        "mailbox/inbox",
        "mailbox/outbox",
        "mailbox/receipts",
        "mailbox/archive",
        "mailbox/failed",
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        gitkeep_path = os.path.join(d, ".gitkeep")
        if not os.path.exists(gitkeep_path):
            with open(gitkeep_path, "w") as f:
                f.write("")

    # Invoke the 3-pass BlueprintEngine
    engine = BlueprintEngine()
    try:
        engine.pass_1(args.prompt)
    except FileExistsError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
        
    engine.pass_2()
    envelopes = engine.pass_3()

    from wdd.gate import load_private_key, sign_payload
    import base64
    priv_key = load_private_key()

    # Spit out generated JSON envelopes into the inbox
    for env in envelopes:
        import os
        from datetime import datetime, timezone, timedelta
        wo_id = env["workorder_id"]
        
        env["nonce"] = os.urandom(8).hex()
        env["expires_at"] = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat().replace("+00:00", "Z")
        
        canonical = wo_id.encode("utf-8")
        sig = sign_payload(priv_key, canonical)
        env["issuer_signature"] = {
            "key_id": "principal_agent_smith",
            "alg": "Ed25519",
            "signature_hex": base64.b64decode(sig).hex()
        }
        
        out_path = f"mailbox/inbox/{wo_id}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(env, f, indent=2)
        print(f"Emitted: {out_path}")

def compile_command(args):
    print("WDD Compile: Parsing vomit prompt into OB...")

def replay_command(args):
    from wdd.replay import replay_ledger
    replay_ledger(benchmark=args.benchmark)

def sweep_command(args):
    print("WDD Sweep: Checking outbox for receipts...")
    from wdd.mailbox import MailboxHandler
    handler = MailboxHandler()
    handler.sweep_outbox()

def validate_command(args):
    print("WDD Validate: Verifying envelopes against schemas...")
    from wdd.validator import validate_all
    if not validate_all():
        sys.exit(1)

def keygen_command(args):
    print("WDD Keygen: Generating agent keypairs...")
    from wdd.crypto import generate_keys
    generate_keys()

def main():
    parser = argparse.ArgumentParser(description="Workorder Driven Development (WDD) CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Init
    p_init = subparsers.add_parser("init", help="Initialize a new WDD project")
    p_init.add_argument("prompt", help="The raw vomit prompt string")
    p_init.set_defaults(func=init_command)
    
    # Compile
    p_compile = subparsers.add_parser("compile", help="Compile vomit prompt into OB")
    p_compile.set_defaults(func=compile_command)
    
    # Replay
    p_replay = subparsers.add_parser("replay", help="Replay ledger workorders")
    p_replay.add_argument("--benchmark", action="store_true", help="Score the run against the benchmark rubric")
    p_replay.set_defaults(func=replay_command)
    
    # Sweep
    p_sweep = subparsers.add_parser("sweep", help="Sweep outbox and generate BOLs")
    p_sweep.set_defaults(func=sweep_command)
    
    # Validate
    p_validate = subparsers.add_parser("validate", help="Validate all JSON envelopes")
    p_validate.set_defaults(func=validate_command)
    
    # Keygen
    p_keygen = subparsers.add_parser("keygen", help="Generate Ed25519 agent keys")
    p_keygen.set_defaults(func=keygen_command)
    
    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
