import sys
import json
from pathlib import Path
from datetime import datetime
from wdd.ledger import get_hash_of_file, get_hash_of_dict

def parse_iso(iso_str):
    if iso_str.endswith("Z"):
        iso_str = iso_str[:-1] + "+00:00"
    return datetime.fromisoformat(iso_str)

def replay_ledger(benchmark=False):
    ledger_dir = Path("ledger")
    if not ledger_dir.exists():
        print("No ledger directory found.")
        return

    entries = sorted(ledger_dir.glob("*.json"))
    
    if not entries:
        print("Ledger is empty.")
        return
        
    expected_prev = "0" * 64
    first_time = None
    last_time = None
    
    print("WDD Replay: Verifying Hash Chain...")
    for i, entry_path in enumerate(entries):
        with open(entry_path, "r") as f:
            data = json.load(f)
        
        prev_hash = data.get("previous_hash")
        
        if i == 0:
            if prev_hash != "0" * 64:
                print(f"FAIL: Block 0 previous_hash is not zeroed.")
                sys.exit(1)
        else:
            if prev_hash != expected_prev:
                print(f"FAIL: Hash chain broken at block {i}. Expected {expected_prev}, got {prev_hash}.")
                sys.exit(1)

        stored_current_hash = data.get("current_hash")
        temp_data = data.copy()
        if "current_hash" in temp_data:
            del temp_data["current_hash"]
        
        recalculated_hash = get_hash_of_dict(temp_data)
        
        if recalculated_hash != stored_current_hash:
            print(f"FAIL: Block {i} current_hash does not match payload digest.")
            sys.exit(1)

        expected_prev = get_hash_of_file(entry_path)
        
        workorder_id = data.get("workorder_id", "UNKNOWN")
        receipt_id = data.get("receipt_id", "UNKNOWN")
        
        receipt_path = Path("mailbox/receipts") / f"receipt_{workorder_id}.json"
        if receipt_path.exists():
            with open(receipt_path, "r") as rf:
                r_data = json.load(rf)
                t = parse_iso(r_data.get("issued_at"))
                if first_time is None: first_time = t
                last_time = t

        print(f"Verified: {workorder_id} -> {receipt_id} (Hash: {stored_current_hash[:8]}...)")

    if benchmark:
        rubric_path = Path("tests/rubric.json")
        if not rubric_path.exists():
            print("FAIL: rubric.json not found.")
            sys.exit(1)
            
        with open(rubric_path, "r") as f:
            rubric = json.load(f)
            
        max_time = rubric.get("max_wall_clock_seconds", 3600)
        
        if first_time and last_time:
            delta = (last_time - first_time).total_seconds()
        else:
            delta = 0
            
        if delta > max_time:
            print(f"FAIL: Execution time {delta}s exceeds rubric limit {max_time}s.")
            sys.exit(1)
            
        print(f"PASS: Multi-record anchored replay successful.")
        print(f"PASS: Execution time: {delta:.2f}s (Limit: {max_time}s)")
        print(f"PASS: Benchmark score within rubric limits.")
