import argparse
import sys

def init_command(args):
    print("WDD Init: Initializing new project...")

def compile_command(args):
    print("WDD Compile: Parsing vomit prompt into OB...")

def replay_command(args):
    print("WDD Replay: Replaying ledger entries...")

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
    p_init.set_defaults(func=init_command)
    
    # Compile
    p_compile = subparsers.add_parser("compile", help="Compile vomit prompt into OB")
    p_compile.set_defaults(func=compile_command)
    
    # Replay
    p_replay = subparsers.add_parser("replay", help="Replay ledger workorders")
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
