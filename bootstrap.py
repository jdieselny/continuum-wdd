import os
import sys
import json
import shutil
import glob

def main():
    print("[STAGE 0] Bootstrapping WDD Genesis Run...")
    inbox_dir = os.path.join("mailbox", "inbox")
    outbox_dir = os.path.join("mailbox", "outbox")
    
    # Ensure dirs exist
    os.makedirs(inbox_dir, exist_ok=True)
    os.makedirs(outbox_dir, exist_ok=True)
    
    envelopes = glob.glob(os.path.join(inbox_dir, "*.json"))
    
    if not envelopes:
        print("[STAGE 0] Inbox is empty. Nothing to bootstrap.")
        sys.exit(0)
        
    # Sort to get deterministic behavior (e.g. WO-007 before WO-008)
    envelopes.sort()
    
    target_envelope = envelopes[0]
    filename = os.path.basename(target_envelope)
    
    print(f"[STAGE 0] DISPATCHING WORKORDER: {filename}")
    
    with open(target_envelope, 'r') as f:
        try:
            data = json.load(f)
            print(f"  Title: {data.get('title', 'Unknown')}")
            print(f"  Assigned To: {data.get('assigned_to', 'Unknown')}")
        except Exception as e:
            print(f"  Failed to parse JSON: {e}")
            
    # Move to outbox
    dest_path = os.path.join(outbox_dir, filename)
    shutil.move(target_envelope, dest_path)
    
    print(f"[STAGE 0] Execution simulated. Envelope moved to {dest_path}")
    print("[STAGE 0] Bootstrap cycle complete.")

if __name__ == "__main__":
    main()
