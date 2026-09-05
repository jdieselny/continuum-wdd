"""Full canonical binding + adversarial ledger negative tests.

CI-safe: ephemeral keypairs are generated in-process. No dependency on a
developer-local `keys/agent_private.pem` leftover.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from wdd.canonical import canonical_json_bytes, digest_obj, ledger_hash_payload
from wdd.crypto import save_trust_registry
from wdd.gate import sign_payload, sign_workorder, verify_workorder_signature
from wdd.ledger import append_entry, get_hash_of_dict
from wdd.replay import ReplayError, replay_ledger

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _mint_ephemeral_principal(keys_dir: Path) -> ed25519.Ed25519PrivateKey:
    """Create a throwaway Ed25519 principal enrolled as ACTIVE in keys_dir."""
    keys_dir.mkdir(parents=True, exist_ok=True)
    priv = ed25519.Ed25519PrivateKey.generate()
    pub_pem = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    (keys_dir / "agent_private.pem").write_bytes(priv_pem)
    (keys_dir / "agent_public.pem").write_text(pub_pem, encoding="utf-8", newline="\n")
    registry = {
        "version": 1,
        "keys": {
            "agent_key": {
                "status": "ACTIVE",
                "alg": "Ed25519",
                "public_key_pem": pub_pem,
            },
            "principal_agent_smith": {
                "status": "ACTIVE",
                "alg": "Ed25519",
                "public_key_pem": pub_pem,
                "alias_of": "agent_key",
            },
        },
        "revoked": [],
    }
    save_trust_registry(registry, path=str(keys_dir / "trust_registry.v1.json"))
    return priv


class TestFullCanonicalBinding(unittest.TestCase):
    def test_action_tamper_invalidates_signature(self):
        wo = _load(ROOT / "mailbox" / "archive" / "wo-001-cli-init.json")
        verify_workorder_signature(wo)
        wo["action"] = "evil.bypass"
        with self.assertRaises(ValueError):
            verify_workorder_signature(wo)

    def test_id_only_signature_rejected(self):
        """Signing only the workorder_id must not verify under full canonical rules."""
        tmp = Path(tempfile.mkdtemp(prefix="wdd-idonly-"))
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            priv = _mint_ephemeral_principal(tmp / "keys")
            wo = _load(ROOT / "mailbox" / "archive" / "wo-001-cli-init.json")
            wo.pop("issuer_signature", None)
            # Deliberately broken binding: sign the ID alone.
            sig = sign_payload(priv, wo["workorder_id"].encode("utf-8"))
            wo["issuer_signature"] = {
                "key_id": "principal_agent_smith",
                "alg": "Ed25519",
                "signature_hex": base64.b64decode(sig).hex(),
            }
            with self.assertRaises(ValueError):
                verify_workorder_signature(wo)
            # Control: full canonical sign with the same ephemeral key must verify.
            good = sign_workorder(
                {k: v for k, v in wo.items() if k != "issuer_signature"},
                key_path=str(tmp / "keys" / "agent_private.pem"),
                key_id="principal_agent_smith",
            )
            verify_workorder_signature(good)
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp, ignore_errors=True)

    def test_wo032_binds_tree_sha_and_manifest(self):
        wo = _load(ROOT / "mailbox" / "archive" / "wo-032-genesis-seal.json")
        receipt = _load(ROOT / "mailbox" / "receipts" / "receipt_wo-032-genesis-seal.json")
        self.assertIn("tree_sha", wo)
        self.assertIn("result_manifest", wo)
        self.assertIn("seal_evidence_digest", wo)
        self.assertEqual(receipt["evidence_digest_sha256"], wo["seal_evidence_digest"])
        expected = digest_obj(
            {"tree_sha": wo["tree_sha"], "result_manifest": wo["result_manifest"]}
        )
        self.assertEqual(wo["seal_evidence_digest"], expected)
        verify_workorder_signature(wo)
        # Verifier source must be inside the sealed manifest (Phase 2 / F-3).
        lib_keys = [k for k in wo["result_manifest"] if k.startswith("lib/wdd/")]
        self.assertIn("lib/wdd/validator.py", lib_keys)
        self.assertIn("lib/wdd/gate.py", lib_keys)
        self.assertGreaterEqual(len(lib_keys), 5)

    def test_ledger_entries_carry_digests(self):
        entry = _load(sorted((ROOT / "ledger").glob("*.json"))[0])
        self.assertIn("workorder_digest", entry)
        self.assertIn("receipt_digest", entry)
        self.assertEqual(
            entry["current_hash"], get_hash_of_dict(ledger_hash_payload(entry))
        )


class TestAdversarialLedger(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wdd-adv-"))
        self.ledger = self.tmp / "ledger"
        self.mailbox = self.tmp / "mailbox"
        (self.mailbox / "archive").mkdir(parents=True)
        (self.mailbox / "receipts").mkdir(parents=True)
        self.ledger.mkdir()
        self.priv = _mint_ephemeral_principal(self.tmp / "keys")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _seed_valid_pair(self):
        """Re-sign production artifacts under the ephemeral principal."""
        wo = _load(ROOT / "mailbox" / "archive" / "wo-000-genesis-audit.json")
        wo.pop("issuer_signature", None)
        wo = sign_workorder(
            wo,
            key_path=str(self.tmp / "keys" / "agent_private.pem"),
            key_id="principal_agent_smith",
        )
        receipt = _load(ROOT / "mailbox" / "receipts" / "receipt_wo-000-genesis-audit.json")
        receipt = dict(receipt)
        receipt.pop("signature", None)
        receipt["token_burn"] = int(receipt.get("token_burn", 0) or 0)
        sig = sign_payload(self.priv, canonical_json_bytes(receipt))
        receipt["signature"] = {
            "key_id": "agent_key",
            "alg": "Ed25519",
            "sig_b64": sig,
        }
        wo_path = self.mailbox / "archive" / "wo-000-genesis-audit.json"
        rcpt_path = self.mailbox / "receipts" / "receipt_wo-000-genesis-audit.json"
        wo_path.write_text(json.dumps(wo, indent=2) + "\n", encoding="utf-8", newline="\n")
        rcpt_path.write_text(
            json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        return wo, receipt

    def test_ledger_without_receipts_fails(self):
        wo, receipt = self._seed_valid_pair()
        cwd = Path.cwd()
        try:
            os.chdir(self.tmp)
            append_entry(wo, receipt, ledger_dir=self.ledger)
            (self.mailbox / "receipts" / "receipt_wo-000-genesis-audit.json").unlink()
            with self.assertRaises(ReplayError) as ctx:
                replay_ledger(benchmark=False, ledger_dir=self.ledger)
            self.assertIn("receipt artifact missing", str(ctx.exception))
        finally:
            os.chdir(cwd)

    def test_max_token_burn_violation_fails(self):
        wo, receipt = self._seed_valid_pair()
        receipt = dict(receipt)
        receipt.pop("signature", None)
        receipt["token_burn"] = 9_999_999
        sig = sign_payload(self.priv, canonical_json_bytes(receipt))
        receipt["signature"] = {
            "key_id": "agent_key",
            "alg": "Ed25519",
            "sig_b64": sig,
        }

        cwd = Path.cwd()
        try:
            os.chdir(self.tmp)
            tests = self.tmp / "tests"
            tests.mkdir(exist_ok=True)
            (tests / "rubric.json").write_text(
                json.dumps({"max_wall_clock_seconds": 3600, "max_token_burn": 100}),
                encoding="utf-8",
            )
            rcpt_path = self.mailbox / "receipts" / "receipt_wo-000-genesis-audit.json"
            rcpt_path.write_text(
                json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n"
            )
            append_entry(wo, receipt, ledger_dir=self.ledger)
            with self.assertRaises(ReplayError) as ctx:
                replay_ledger(benchmark=True, ledger_dir=self.ledger)
            self.assertIn("Token burn", str(ctx.exception))
        finally:
            os.chdir(cwd)

    def test_digest_mismatch_fails(self):
        wo, receipt = self._seed_valid_pair()
        cwd = Path.cwd()
        try:
            os.chdir(self.tmp)
            append_entry(wo, receipt, ledger_dir=self.ledger)
            entry_path = next(self.ledger.glob("*.json"))
            entry = json.loads(entry_path.read_text(encoding="utf-8"))
            entry["workorder_digest"] = "0" * 64
            entry["current_hash"] = get_hash_of_dict(ledger_hash_payload(entry))
            entry_path.write_text(
                json.dumps(entry, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            with self.assertRaises(ReplayError) as ctx:
                replay_ledger(benchmark=False, ledger_dir=self.ledger)
            self.assertIn("workorder_digest mismatch", str(ctx.exception))
        finally:
            os.chdir(cwd)


class TestSchemaFailClosed(unittest.TestCase):
    def test_missing_schema_is_rejected(self):
        from wdd.validator import _schema_validate_file

        tmp = Path(tempfile.mkdtemp(prefix="wdd-schema-"))
        try:
            path = tmp / "payload-forgery.json"
            path.write_text(
                json.dumps({"workorder_id": "wo-evil", "action": "trust.bypass"}),
                encoding="utf-8",
            )
            errors = _schema_validate_file(str(path), require_schema=True)
            self.assertTrue(any("Missing required $schema" in e for e in errors))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestLiveGenesisReplay(unittest.TestCase):
    def test_replay_completes_all_blocks(self):
        result = replay_ledger(benchmark=True, ledger_dir=ROOT / "ledger")
        self.assertEqual(result["blocks"], 30)

    def test_seal_tree_sha_matches_head_tree(self):
        """Phase-2 invariant: tree_sha equals HEAD^{tree}, or HEAD~1^{tree} when tip is seal-only."""
        import subprocess

        wo = _load(ROOT / "mailbox" / "archive" / "wo-032-genesis-seal.json")
        head_tree = subprocess.check_output(
            ["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True
        ).strip()
        candidates = {head_tree}
        try:
            parent_tree = subprocess.check_output(
                ["git", "rev-parse", "HEAD^^{tree}"], cwd=ROOT, text=True
            ).strip()
            candidates.add(parent_tree)
        except subprocess.CalledProcessError:
            pass
        self.assertIn(
            wo["tree_sha"],
            candidates,
            msg=f"tree_sha {wo['tree_sha']} not in {candidates}",
        )


if __name__ == "__main__":
    unittest.main()
