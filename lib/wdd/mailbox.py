import json
import os
import shutil

class MailboxHandler:
    def __init__(self, base_dir="mailbox"):
        self.base_dir = base_dir
        self.failed_dir = os.path.join(self.base_dir, "failed")
        os.makedirs(self.failed_dir, exist_ok=True)

    def handle_failed_envelope(self, filepath):
        try:
            with open(filepath, 'r') as f:
                envelope = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return

        attempts = envelope.get("attempt_counter", 0) + 1
        envelope["attempt_counter"] = attempts

        if attempts > 3:
            # Move to failed directory
            filename = os.path.basename(filepath)
            failed_path = os.path.join(self.failed_dir, filename)
            
            with open(failed_path, 'w') as f:
                json.dump(envelope, f, indent=2)
                
            os.remove(filepath)
        else:
            # Update the attempt counter in place
            with open(filepath, 'w') as f:
                json.dump(envelope, f, indent=2)

    def sweep_outbox(self):
        outbox_dir = os.path.join(self.base_dir, "outbox")
        archive_dir = os.path.join(self.base_dir, "archive")
        receipts_dir = os.path.join(self.base_dir, "receipts")
        os.makedirs(archive_dir, exist_ok=True)
        os.makedirs(receipts_dir, exist_ok=True)

        if not os.path.exists(outbox_dir):
            return

        for filename in os.listdir(outbox_dir):
            if filename.startswith("wo-") and filename.endswith(".json") and not filename.endswith(".result.json") and not filename.endswith(".receipt.json"):
                wo_id = filename[:-5]
                envelope_path = os.path.join(outbox_dir, filename)
                
                # Find associated receipt
                receipt_candidates = [
                    f"{wo_id}.receipt.json",
                    f"receipt_{wo_id}.json",
                    "receipt.json"
                ]
                
                receipt_path = None
                for cand in receipt_candidates:
                    cand_path = os.path.join(outbox_dir, cand)
                    if os.path.exists(cand_path):
                        receipt_path = cand_path
                        break
                        
                if not receipt_path:
                    # Fallback: check if it's already in receipts dir
                    cand_path = os.path.join(receipts_dir, f"receipt_{wo_id}.json")
                    if os.path.exists(cand_path):
                        receipt_path = cand_path
                
                if not receipt_path or not os.path.exists(receipt_path):
                    continue

                try:
                    with open(envelope_path, 'r') as f:
                        envelope = json.load(f)
                    with open(receipt_path, 'r') as f:
                        receipt = json.load(f)
                except Exception as e:
                    print(f"Error reading {filename} or receipt: {e}")
                    continue

                # Verify signature
                if self._verify_receipt(receipt):
                    # Mark SEALED
                    envelope["status"] = "SEALED"
                    
                    # Move envelope to archive
                    archive_path = os.path.join(archive_dir, filename)
                    with open(archive_path, 'w') as f:
                        json.dump(envelope, f, indent=2)
                    os.remove(envelope_path)
                    
                    # Drop receipt in receipts if it's in outbox
                    if os.path.dirname(receipt_path) == outbox_dir:
                        final_receipt_path = os.path.join(receipts_dir, os.path.basename(receipt_path))
                        if receipt_path != final_receipt_path:
                            shutil.move(receipt_path, final_receipt_path)
                            
                    # Append to ledger
                    from wdd.ledger import append_entry
                    append_entry(envelope, receipt)
                            
                    print(f"Swept and sealed {filename}")
                else:
                    print(f"Invalid signature for {filename}")

    def _verify_receipt(self, receipt):
        if "signature" not in receipt:
            return False
            
        import base64
        from cryptography.hazmat.primitives import serialization
        from cryptography.exceptions import InvalidSignature
        
        sig_info = receipt["signature"]
        key_id = sig_info.get("key_id")
        sig_b64 = sig_info.get("sig_b64")
        
        if not key_id or not sig_b64:
            return False
            
        trust_store_path = "keys/trusted.json"
        try:
            with open(trust_store_path, "r") as f:
                trust_store = json.load(f)
        except Exception:
            return False
            
        pub_key_pem = trust_store.get(key_id)
        if not pub_key_pem:
            return False
            
        try:
            public_key = serialization.load_pem_public_key(pub_key_pem.encode('utf-8'))
            sig_bytes = base64.b64decode(sig_b64)
            
            receipt_copy = dict(receipt)
            del receipt_copy["signature"]
            canonical_payload = json.dumps(receipt_copy, sort_keys=True, separators=(',', ':')).encode('utf-8')
            
            public_key.verify(sig_bytes, canonical_payload)
            return True
        except Exception:
            return False

