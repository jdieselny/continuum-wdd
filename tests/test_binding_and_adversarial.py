"""Full canonical binding + adversarial ledger negative tests."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from wdd.canonical import digest_obj, ledger_hash_payload
from wdd.gate import verify_workorder_signature
from wdd.ledger import append_entry, get_hash_of_dict
from wdd.replay import ReplayError, replay_ledger

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestFullCanonicalBinding(unittest.TestCase):
    def test_action_tamper_invalidates_signature(self):
        wo = _load(ROOT / "mailbox" / "archive" / "wo-001-cli-init.json")
        verify_workorder_signature(wo)
        wo["action"] = "evil.bypass"
        with self.assertRaises(ValueError):
            verify_workorder_signature(wo)

    def test_id_only_signature_rejected(self):
        """Signing only the workorder_id must not verify under full canonical rules."""
        from wdd.gate import load_private_key, sign_payload
        import base64

        wo = _load(ROOT / "mailbox" / "archive" / "wo-001-cli-init.json")
        wo.pop("issuer_signature", None)
        priv = load_private_key(str(ROOT / "keys" / "agent_private.pem"))
        sig = sign_payload(priv, wo["workorder_id"].encode("utf-8"))
        wo["issuer_signature"] = {
            "key_id": "principal_agent_smith",
            "alg": "Ed25519",
            "signature_hex": base64.b64decode(sig).hex(),
        }
        with self.assertRaises(ValueError):
            verify_workorder_signature(wo)

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

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _seed_valid_pair(self):
        wo = _load(ROOT / "mailbox" / "archive" / "wo-000-genesis-audit.json")
        receipt = _load(ROOT / "mailbox" / "receipts" / "receipt_wo-000-genesis-audit.json")
        wo_path = self.mailbox / "archive" / "wo-000-genesis-audit.json"
        rcpt_path = self.mailbox / "receipts" / "receipt_wo-000-genesis-audit.json"
        wo_path.write_text(json.dumps(wo, indent=2) + "\n", encoding="utf-8", newline="\n")
        rcpt_path.write_text(
            json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        return wo, receipt

    def test_ledger_without_receipts_fails(self):
        wo, receipt = self._seed_valid_pair()
        # Build a ledger entry then delete the receipt artifact
        cwd_ledger = Path.cwd()
        try:
            import os

            os.chdir(self.tmp)
            # Copy trust registry + public key so verify can run
            keys = self.tmp / "keys"
            keys.mkdir()
            shutil.copy(ROOT / "keys" / "trust_registry.v1.json", keys / "trust_registry.v1.json")
            shutil.copy(ROOT / "keys" / "agent_public.pem", keys / "agent_public.pem")
            append_entry(wo, receipt, ledger_dir=self.ledger)
            (self.mailbox / "receipts" / "receipt_wo-000-genesis-audit.json").unlink()
            with self.assertRaises(ReplayError) as ctx:
                replay_ledger(benchmark=False, ledger_dir=self.ledger)
            self.assertIn("receipt artifact missing", str(ctx.exception))
        finally:
            os.chdir(cwd_ledger)

    def test_max_token_burn_violation_fails(self):
        wo, receipt = self._seed_valid_pair()
        receipt = dict(receipt)
        receipt.pop("signature", None)
        receipt["token_burn"] = 9_999_999
        # Re-sign receipt with project key from ROOT
        from wdd.gate import load_private_key, sign_payload
        from wdd.canonical import canonical_json_bytes

        priv = load_private_key(str(ROOT / "keys" / "agent_private.pem"))
        sig = sign_payload(priv, canonical_json_bytes(receipt))
        receipt["signature"] = {
            "key_id": "agent_key",
            "alg": "Ed25519",
            "sig_b64": sig,
        }

        import os

        cwd = Path.cwd()
        try:
            os.chdir(self.tmp)
            keys = self.tmp / "keys"
            keys.mkdir(exist_ok=True)
            shutil.copy(ROOT / "keys" / "trust_registry.v1.json", keys / "trust_registry.v1.json")
            shutil.copy(ROOT / "keys" / "agent_public.pem", keys / "agent_public.pem")
            tests = self.tmp / "tests"
            tests.mkdir()
            (tests / "rubric.json").write_text(
                json.dumps({"max_wall_clock_seconds": 3600, "max_token_burn": 100}),
                encoding="utf-8",
            )
            wo_path = self.mailbox / "archive" / "wo-000-genesis-audit.json"
            rcpt_path = self.mailbox / "receipts" / "receipt_wo-000-genesis-audit.json"
            wo_path.write_text(json.dumps(wo, indent=2) + "\n", encoding="utf-8", newline="\n")
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
        import os

        cwd = Path.cwd()
        try:
            os.chdir(self.tmp)
            keys = self.tmp / "keys"
            keys.mkdir(exist_ok=True)
            shutil.copy(ROOT / "keys" / "trust_registry.v1.json", keys / "trust_registry.v1.json")
            shutil.copy(ROOT / "keys" / "agent_public.pem", keys / "agent_public.pem")
            append_entry(wo, receipt, ledger_dir=self.ledger)
            entry_path = next(self.ledger.glob("*.json"))
            entry = json.loads(entry_path.read_text(encoding="utf-8"))
            entry["workorder_digest"] = "0" * 64
            # Fix current_hash so chain self-hash passes but digest compare fails
            entry["current_hash"] = get_hash_of_dict(ledger_hash_payload(entry))
            entry_path.write_text(json.dumps(entry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaises(ReplayError) as ctx:
                replay_ledger(benchmark=False, ledger_dir=self.ledger)
            self.assertIn("workorder_digest mismatch", str(ctx.exception))
        finally:
            os.chdir(cwd)


class TestLiveGenesisReplay(unittest.TestCase):
    def test_replay_completes_all_blocks(self):
        result = replay_ledger(benchmark=True, ledger_dir=ROOT / "ledger")
        self.assertEqual(result["blocks"], 30)


if __name__ == "__main__":
    unittest.main()
