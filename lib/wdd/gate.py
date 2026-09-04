import os
import json
import hashlib
import base64
from datetime import datetime, timezone
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

def load_private_key(key_path="keys/agent_private.pem"):
    with open(key_path, "rb") as f:
        key_bytes = f.read()
    return serialization.load_pem_private_key(key_bytes, password=None)

def generate_evidence_digest(workorder_path):
    with open(workorder_path, "rb") as f:
        data = f.read()
    return hashlib.sha256(data).hexdigest()

def sign_payload(private_key, payload_bytes):
    signature = private_key.sign(payload_bytes)
    return base64.b64encode(signature).decode('utf-8')

def issue_receipt(workorder_path, key_path="keys/agent_private.pem", out_dir="mailbox/receipts"):
    with open(workorder_path, "r", encoding="utf-8") as f:
        wo = json.load(f)

    wo_id = wo.get("workorder_id", "unknown")
    evaluator = wo.get("assigned_to", "unknown_agent")
    action = wo.get("action", "unknown_action")

    digest = generate_evidence_digest(workorder_path)

    receipt = {
        "$schema": "https://wdd.jdieselny.com/schemas/receipt.schema.json",
        "receipt_id": f"rcpt-{wo_id}",
        "version": "EP-RECEIPT-v1.0",
        "issued_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "workorder_id": wo_id,
        "evaluator": evaluator,
        "policy_outcome": "ACCEPTED",
        "admitted_action": action,
        "evidence_digest_sha256": digest
    }

    # Sign the canonical json representation without the signature field
    canonical_payload = json.dumps(receipt, sort_keys=True, separators=(',', ':')).encode('utf-8')
    
    priv_key = load_private_key(key_path)
    sig_b64 = sign_payload(priv_key, canonical_payload)

    receipt["signature"] = {
        "key_id": "agent_key",
        "alg": "Ed25519",
        "sig_b64": sig_b64
    }

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"receipt_{wo_id}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2)
        
    return out_path
