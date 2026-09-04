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
