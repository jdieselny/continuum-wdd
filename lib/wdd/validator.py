"""Schema + cryptographic verifier execution (never schema-only PASS)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema

from wdd.canonical import ledger_hash_payload
from wdd.gate import (
    verify_receipt_signature,
    verify_workorder_signature,
)
from wdd.ledger import get_hash_of_dict
from wdd.replay import ReplayError, replay_ledger


def _load_schema(schema_ref: str, file_path: str) -> dict[str, Any] | None:
    if schema_ref.startswith("https://wdd.jdieselny.com/schemas/"):
        schema_filename = schema_ref.split("/")[-1]
        schema_path = os.path.join("schemas", schema_filename)
    else:
        schema_path = os.path.normpath(
            os.path.join(os.path.dirname(file_path), schema_ref)
        )
    if not os.path.exists(schema_path):
        return None
    with open(schema_path, "r", encoding="utf-8") as sf:
        return json.load(sf)


def _schema_validate_file(file_path: str, *, require_schema: bool = True) -> list[str]:
    errors: list[str] = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return [f"Malformed JSON in {file_path}: {e}"]

    if "$schema" not in data:
        if require_schema:
            return [f"Missing required $schema in {file_path}"]
        return []

    schema_data = _load_schema(data["$schema"], file_path)
    if schema_data is None:
        return [f"Schema missing for {file_path}"]

    try:
        jsonschema.validate(instance=data, schema=schema_data)
    except jsonschema.exceptions.ValidationError as e:
        errors.append(f"Validation failed for {file_path}: {e.message}")

    if "expires_at" in data:
        try:
            expires_at_dt = datetime.fromisoformat(
                data["expires_at"].replace("Z", "+00:00")
            )
            if expires_at_dt < datetime.now(timezone.utc):
                errors.append(f"Workorder expired {file_path}: {data['expires_at']}")
        except ValueError as e:
            errors.append(f"Invalid expiry format in {file_path}: {e}")

    return errors


def _verify_workorder_file(file_path: str) -> list[str]:
    errors = _schema_validate_file(file_path, require_schema=True)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        return errors

    if "issuer_signature" in data:
        try:
            verify_workorder_signature(data)
        except ValueError as e:
            errors.append(f"Workorder signature failed for {file_path}: {e}")
    elif data.get("workorder_id"):
        errors.append(f"Workorder missing issuer_signature: {file_path}")
    return errors


def _verify_receipt_file(file_path: str) -> list[str]:
    errors = _schema_validate_file(file_path, require_schema=True)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        return errors

    if "signature" in data or data.get("receipt_id"):
        try:
            verify_receipt_signature(data)
        except ValueError as e:
            errors.append(f"Receipt signature failed for {file_path}: {e}")

        wo_id = data.get("workorder_id")
        evidence = data.get("evidence_digest_sha256")
        if wo_id and evidence:
            for folder in ("mailbox/archive", "mailbox/outbox", "mailbox/inbox"):
                wo_path = Path(folder) / f"{wo_id}.json"
                if not wo_path.is_file():
                    continue
                with open(wo_path, "r", encoding="utf-8") as wf:
                    wo = json.load(wf)
                expected = wo.get("seal_evidence_digest")
                if expected is None:
                    from wdd.gate import generate_evidence_digest

                    expected = generate_evidence_digest(str(wo_path))
                if evidence != expected:
                    errors.append(
                        f"Receipt evidence digest mismatch for {wo_id}: "
                        f"receipt={evidence} expected={expected}"
                    )
                break
    return errors


def _classify_envelope(file_path: str, data: dict[str, Any]) -> str:
    """Content-based dispatch (not filename-based)."""
    name = os.path.basename(file_path)
    if name.endswith(".result.json"):
        return "result"
    if data.get("receipt_id") or "signature" in data and "evidence_digest_sha256" in data:
        return "receipt"
    if data.get("workorder_id") and (
        "issuer_signature" in data or "action" in data or "assigned_to" in data
    ):
        return "workorder"
    if data.get("receipt_id"):
        return "receipt"
    return "other"


def _verify_ledger_dir(ledger_dir: str = "ledger") -> list[str]:
    """Strict ledger verification — never schema-only."""
    errors: list[str] = []
    path = Path(ledger_dir)
    if not path.exists():
        return errors

    for entry_path in sorted(path.glob("*.json")):
        try:
            with open(entry_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"Malformed ledger entry {entry_path}: {e}")
            continue

        schema_path = Path("schemas/ledger.schema.json")
        if schema_path.is_file():
            with open(schema_path, "r", encoding="utf-8") as sf:
                schema = json.load(sf)
            try:
                jsonschema.validate(instance=data, schema=schema)
            except jsonschema.exceptions.ValidationError as e:
                errors.append(f"Ledger schema failed for {entry_path}: {e.message}")

        recalc = get_hash_of_dict(ledger_hash_payload(data))
        if data.get("current_hash") != recalc:
            errors.append(f"Ledger current_hash mismatch in {entry_path.name}")

        for field in ("workorder_digest", "receipt_digest"):
            if field not in data:
                errors.append(f"Ledger entry {entry_path.name} missing {field}")

    try:
        replay_ledger(benchmark=True, ledger_dir=ledger_dir)
    except ReplayError as e:
        errors.append(f"Ledger replay/verifier failed: {e}")
    except ValueError as e:
        # Signature failures must be clean FAIL lines, not tracebacks (Claude F-6).
        errors.append(f"Ledger verifier failed: {e}")

    return errors


def validate_all(include_ledger: bool = True) -> bool:
    all_valid = True
    directories = ["mailbox", "workorders"]

    for directory in directories:
        if not os.path.exists(directory):
            continue
        for root, _, files in os.walk(directory):
            for file in files:
                if not file.endswith(".json"):
                    continue
                file_path = os.path.join(root, file)
                if file in ("trusted.json",):
                    continue

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except json.JSONDecodeError as e:
                    print(f"FAIL: Malformed JSON in {file_path}: {e}")
                    all_valid = False
                    continue

                kind = _classify_envelope(file_path, data)
                if kind == "receipt":
                    errors = _verify_receipt_file(file_path)
                elif kind == "workorder":
                    errors = _verify_workorder_file(file_path)
                else:
                    # result / other — still fail closed without $schema
                    errors = _schema_validate_file(file_path, require_schema=True)

                if errors:
                    all_valid = False
                    for err in errors:
                        print(f"FAIL: {err}")
                else:
                    print(f"PASS: {file_path}")

    if include_ledger:
        ledger_errors = _verify_ledger_dir("ledger")
        if ledger_errors:
            all_valid = False
            for err in ledger_errors:
                print(f"FAIL: {err}")
        elif Path("ledger").exists() and any(Path("ledger").glob("*.json")):
            print("PASS: ledger/ (chain + digests + receipts + rubric)")

    return all_valid
