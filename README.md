# Continuum WDD (Workorder Driven Development)

**The Mathematical Assembly Line for Autonomous Fleets.**

Continuum WDD is not a conversational AI tool. It is a strictly-typed, cryptographically-secured topological execution framework. It treats LLM agents not as conversational partners, but as robotic arms on an assembly line. 

## The Genesis Block

This entire repository was constructed autonomously by a swarm of A:iB agents (Agent Smith, Grok, Codex, Opus, Agy) via the WDD Mailbox Protocol. 

**Execution Sequence:**
1. **Phase 0 (Bootstrap):** Zero-dependency envelope routing.
2. **Phase 1 (Contracts):** Strict JSON Schema validation for all envelopes.
3. **Phase 2 (Trust):** Ed25519 signature enforcement, receipt gates, replay-attack prevention (nonce/expiry), and dead-letter queues.
4. **Phase 3 (Ledger):** SHA-256 hash-chained execution logs.
5. **Phase 4 (Compiler):** The 3-pass Intent Engine and Topological Scheduler.
6. **Phase 5 (Glass):** React Telemetry Dashboard and OB Writer GUI.
7. **Phase 6 (Seal):** The Genesis Seal.

## Cryptographic Replay & Benchmarking

Because every state transition in the system requires a cryptographic receipt and is appended to the ledger, you can mathematically prove the sequence and speed of the Genesis build.

Install (clean clone):
```bash
python -m pip install -e ".[dev]"
```

To verify the chain and score the benchmark, run:
```bash
python -m wdd validate
python -m wdd replay --benchmark
python -m pytest tests/ -v
```

Public trust lives in `keys/trust_registry.v1.json`. Private keys are gitignored; the historically leaked key is permanently revoked in that registry.

The Sweep Engine actively enforces the trust boundary. Any agent attempting to drop a receipt without a valid Ed25519 signature matching an enrolled identity will be violently rejected and sent to the `failed/` queue.

## WDD Init

To use the compiler to scaffold a new project:
```bash
python -m wdd init "I want to build a trinket shop"
```
The intent is logged immutably, the topological scheduler calculates dependencies, and the `mailbox/inbox` is populated for the fleet.

---
*Built via WDD. Sealed by Agent Smith.*
