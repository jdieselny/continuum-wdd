"""Ed25519 keygen and versioned public trust registry."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

KEYS_DIR = "keys"
TRUST_REGISTRY_PATH = os.path.join(KEYS_DIR, "trust_registry.v1.json")
# Compat shim read by older call sites; always regenerated from the registry.
TRUST_STORE = os.path.join(KEYS_DIR, "trusted.json")
REGISTRY_VERSION = 1


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def default_registry() -> dict[str, Any]:
    return {
        "version": REGISTRY_VERSION,
        "updated_at": _utcnow(),
        "keys": {},
        "revoked": [],
    }


def load_trust_registry(path: str = TRUST_REGISTRY_PATH) -> dict[str, Any]:
    if not os.path.exists(path):
        return default_registry()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "version" not in data:
        # Legacy trusted.json shape: {key_id: pem}
        migrated = default_registry()
        for key_id, pem in data.items():
            if isinstance(pem, str) and "BEGIN PUBLIC KEY" in pem:
                migrated["keys"][key_id] = {
                    "status": "ACTIVE",
                    "alg": "Ed25519",
                    "public_key_pem": pem,
                }
        return migrated
    data.setdefault("keys", {})
    data.setdefault("revoked", [])
    return data


def save_trust_registry(registry: dict[str, Any], path: str = TRUST_REGISTRY_PATH) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    registry = dict(registry)
    registry["version"] = REGISTRY_VERSION
    registry["updated_at"] = _utcnow()
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(registry, f, indent=2, sort_keys=True)
        f.write("\n")
    # Compat shim lives beside the registry (never a hardcoded cwd-relative path).
    compat = os.path.join(os.path.dirname(path) or ".", "trusted.json")
    _write_compat_trusted(registry, compat_path=compat)


def _write_compat_trusted(
    registry: dict[str, Any], compat_path: str = TRUST_STORE
) -> None:
    """Write trusted.json ACTIVE-only map for legacy readers."""
    active = {
        key_id: meta["public_key_pem"]
        for key_id, meta in registry.get("keys", {}).items()
        if meta.get("status") == "ACTIVE"
    }
    with open(compat_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(active, f, indent=2, sort_keys=True)
        f.write("\n")


def revoke_key(
    *,
    key_id: str,
    public_key_pem: str,
    reason: str,
    historical_commit: str | None = None,
    path: str = TRUST_REGISTRY_PATH,
) -> dict[str, Any]:
    registry = load_trust_registry(path)
    # Remove from active set if present
    registry.get("keys", {}).pop(key_id, None)
    revoked_entry = {
        "key_id": key_id,
        "status": "REVOKED",
        "alg": "Ed25519",
        "public_key_pem": public_key_pem,
        "revoked_at": _utcnow(),
        "reason": reason,
    }
    if historical_commit:
        revoked_entry["historical_commit"] = historical_commit
    # Deduplicate by public key PEM
    existing = [
        r
        for r in registry.get("revoked", [])
        if r.get("public_key_pem") != public_key_pem
    ]
    existing.append(revoked_entry)
    registry["revoked"] = existing
    save_trust_registry(registry, path)
    return registry


def get_active_public_pem(key_id: str, path: str = TRUST_REGISTRY_PATH) -> str | None:
    registry = load_trust_registry(path)
    meta = registry.get("keys", {}).get(key_id)
    if not meta or meta.get("status") != "ACTIVE":
        return None
    # Refuse if the same PEM appears on the revocation list
    pem = meta.get("public_key_pem")
    for revoked in registry.get("revoked", []):
        if revoked.get("public_key_pem") == pem:
            return None
    return pem


def is_revoked_pem(public_key_pem: str, path: str = TRUST_REGISTRY_PATH) -> bool:
    registry = load_trust_registry(path)
    return any(
        r.get("public_key_pem") == public_key_pem for r in registry.get("revoked", [])
    )


def generate_keys(key_id: str = "agent_key") -> None:
    print("Generating Ed25519 keypair...")
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    os.makedirs(KEYS_DIR, exist_ok=True)

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    priv_path = os.path.join(KEYS_DIR, "agent_private.pem")
    pub_path = os.path.join(KEYS_DIR, "agent_public.pem")

    with open(priv_path, "wb") as f:
        f.write(private_pem)
    try:
        os.chmod(priv_path, 0o600)
    except OSError:
        pass

    with open(pub_path, "wb") as f:
        f.write(public_pem)

    print(f"Saved private key to {priv_path}")
    print(f"Saved public key to {pub_path}")

    registry = load_trust_registry()
    registry.setdefault("keys", {})[key_id] = {
        "status": "ACTIVE",
        "alg": "Ed25519",
        "public_key_pem": public_pem.decode("utf-8"),
        "enrolled_at": _utcnow(),
    }
    # Alias used by workorder issuer_signature.key_id in this fleet
    registry["keys"]["principal_agent_smith"] = dict(registry["keys"][key_id])
    save_trust_registry(registry)
    print(f"Updated trust registry at {TRUST_REGISTRY_PATH}")


if __name__ == "__main__":
    generate_keys()
