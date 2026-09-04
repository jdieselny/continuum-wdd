import os
import json
import hashlib
from pathlib import Path

def get_hash_of_file(filepath):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def get_hash_of_dict(d):
    return hashlib.sha256(json.dumps(d, sort_keys=True).encode("utf-8")).hexdigest()

def append_entry(workorder, receipt):
    """
    Append an entry to the ledger.
    workorder: dict representing the workorder
    receipt: dict representing the receipt
    """
    # Use paths relative to project root, assuming cwd is project root
    ledger_dir = Path("ledger")
    ledger_dir.mkdir(parents=True, exist_ok=True)
    
    entries = sorted(ledger_dir.glob("*.json"))
    
    if not entries:
        previous_hash = "0" * 64
    else:
        last_entry_path = entries[-1]
        previous_hash = get_hash_of_file(last_entry_path)
        
    entry_data = {
        "previous_hash": previous_hash,
        "workorder_id": workorder.get("workorder_id", ""),
        "receipt_id": receipt.get("receipt_id", "")
    }
    
    current_hash = get_hash_of_dict(entry_data)
    entry_data["current_hash"] = current_hash
    
    new_entry_filename = f"{len(entries):06d}_{current_hash[:8]}.json"
    new_entry_path = ledger_dir / new_entry_filename
    
    with open(new_entry_path, "w") as f:
        json.dump(entry_data, f, indent=2)
    
    return new_entry_path
