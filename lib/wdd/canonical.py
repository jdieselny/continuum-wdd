"""Canonical JSON + digest helpers for WDD cryptographic binding."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


CANONICAL_SEPARATORS = (",", ":")


def canonical_json_bytes(obj: Any) -> bytes:
    """Deterministic UTF-8 JSON bytes (sorted keys, compact separators)."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=CANONICAL_SEPARATORS,
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_obj(obj: Any) -> str:
    return sha256_hex(canonical_json_bytes(obj))


def workorder_signing_payload(workorder: Mapping[str, Any]) -> dict:
    """Full canonical workorder body excluding the detached issuer_signature."""
    payload = {k: v for k, v in workorder.items() if k != "issuer_signature"}
    return payload


def receipt_signing_payload(receipt: Mapping[str, Any]) -> dict:
    """Receipt body excluding the detached signature block."""
    return {k: v for k, v in receipt.items() if k != "signature"}


def ledger_hash_payload(entry: Mapping[str, Any]) -> dict:
    """Ledger entry body used to compute current_hash (excludes current_hash)."""
    return {k: v for k, v in entry.items() if k != "current_hash"}
