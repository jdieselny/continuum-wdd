"""Receipt issuance and workorder/receipt signature verification."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization

from wdd.canonical import (
    canonical_json_bytes,
    digest_obj,
    receipt_signing_payload,
    workorder_signing_payload,
)
from wdd.crypto import get_active_public_pem, is_revoked_pem, load_trust_registry


def load_private_key(key_path: str = "keys/agent_private.pem"):
    with open(key_path, "rb") as f:
        key_bytes = f.read()
    return serialization.load_pem_private_key(key_bytes, password=None)


def generate_evidence_digest(workorder_path: str) -> str:
    with open(workorder_path, "rb") as f:
        data = f.read()
    # Normalize newlines so Windows/Unix checkouts agree.
    normalized = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def sign_payload(private_key, payload_bytes: bytes) -> str:
    signature = private_key.sign(payload_bytes)
    return base64.b64encode(signature).decode("utf-8")


def sign_workorder(
    workorder: dict[str, Any],
    *,
    key_path: str = "keys/agent_private.pem",
    key_id: str = "principal_agent_smith",
) -> dict[str, Any]:
    """Sign the *full* canonical workorder (all fields except issuer_signature)."""
    payload = workorder_signing_payload(workorder)
    priv_key = load_private_key(key_path)
    sig_b64 = sign_payload(priv_key, canonical_json_bytes(payload))
    workorder = dict(workorder)
    workorder["issuer_signature"] = {
        "key_id": key_id,
        "alg": "Ed25519",
        "signature_hex": base64.b64decode(sig_b64).hex(),
    }
    return workorder


def verify_workorder_signature(workorder: Mapping[str, Any]) -> None:
    """Raise ValueError if the workorder signature is missing, revoked, or invalid."""
    sig_info = workorder.get("issuer_signature")
    if not isinstance(sig_info, dict):
        raise ValueError("missing issuer_signature")
    key_id = sig_info.get("key_id")
    sig_hex = sig_info.get("signature_hex")
    if not key_id or not sig_hex:
        raise ValueError("incomplete issuer_signature")

    pub_pem = get_active_public_pem(key_id)
    if pub_pem is None:
        raise ValueError(f"key_id {key_id!r} is not ACTIVE in trust registry")
    if is_revoked_pem(pub_pem):
        raise ValueError(f"key_id {key_id!r} public key is REVOKED")

    public_key = serialization.load_pem_public_key(pub_pem.encode("utf-8"))
    payload = canonical_json_bytes(workorder_signing_payload(workorder))
    try:
        public_key.verify(bytes.fromhex(sig_hex), payload)
    except InvalidSignature as exc:
        raise ValueError("workorder signature verification failed") from exc


def verify_receipt_signature(receipt: Mapping[str, Any]) -> None:
    sig_info = receipt.get("signature")
    if not isinstance(sig_info, dict):
        raise ValueError("missing receipt signature")
    key_id = sig_info.get("key_id")
    sig_b64 = sig_info.get("sig_b64")
    if not key_id or not sig_b64:
        raise ValueError("incomplete receipt signature")

    pub_pem = get_active_public_pem(key_id)
    if pub_pem is None:
        # Fall back: some receipts use agent_key while workorders use principal alias
        registry = load_trust_registry()
        meta = registry.get("keys", {}).get(key_id)
        if not meta or meta.get("status") != "ACTIVE":
            raise ValueError(f"key_id {key_id!r} is not ACTIVE in trust registry")
        pub_pem = meta["public_key_pem"]
        if is_revoked_pem(pub_pem):
            raise ValueError(f"key_id {key_id!r} public key is REVOKED")

    public_key = serialization.load_pem_public_key(pub_pem.encode("utf-8"))
    payload = canonical_json_bytes(receipt_signing_payload(receipt))
    try:
        public_key.verify(base64.b64decode(sig_b64), payload)
    except InvalidSignature as exc:
        raise ValueError("receipt signature verification failed") from exc


def issue_receipt(
    workorder_path: str,
    key_path: str = "keys/agent_private.pem",
    out_dir: str = "mailbox/receipts",
    evidence_digest: str | None = None,
    extra_fields: dict[str, Any] | None = None,
) -> str:
    with open(workorder_path, "r", encoding="utf-8") as f:
        wo = json.load(f)

    wo_id = wo.get("workorder_id", "unknown")
    evaluator = wo.get("assigned_to", "unknown_agent")
    action = wo.get("action", "unknown_action")

    digest = evidence_digest if evidence_digest is not None else generate_evidence_digest(workorder_path)

    receipt: dict[str, Any] = {
        "$schema": "https://wdd.jdieselny.com/schemas/receipt.schema.json",
        "receipt_id": f"rcpt-{wo_id}",
        "version": "EP-RECEIPT-v1.0",
        "issued_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "workorder_id": wo_id,
        "evaluator": evaluator,
        "policy_outcome": "ACCEPTED",
        "admitted_action": action,
        "evidence_digest_sha256": digest,
    }
    if extra_fields:
        receipt.update(extra_fields)

    canonical_payload = canonical_json_bytes(receipt)
    priv_key = load_private_key(key_path)
    sig_b64 = sign_payload(priv_key, canonical_payload)

    receipt["signature"] = {
        "key_id": "agent_key",
        "alg": "Ed25519",
        "sig_b64": sig_b64,
    }

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"receipt_{wo_id}.json")
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(receipt, f, indent=2)
        f.write("\n")

    return out_path


def workorder_digest(workorder: Mapping[str, Any]) -> str:
    return digest_obj(workorder_signing_payload(workorder))


def receipt_digest(receipt: Mapping[str, Any]) -> str:
    return digest_obj(receipt_signing_payload(receipt))
