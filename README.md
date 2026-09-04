# Continuum WDD (Workorder Driven Development)

**WDD is built by WDD, to build WDD, delivered as a WDD replay engine.**

## Quickstart

### Option 1: Watch it build itself (Training / Benchmark Mode)
```bash
python wdd replay
```
This replays the Genesis Block (WO-000 through WO-032). You will watch the synthetic workforce construct the telemetry dashboard, the schemas, the mailbox runner, and the OB writer in real-time.

### Option 2: Instantiate a new project
```bash
python wdd init "I want to build a trinket shop..."
```
The OB Writer (Intent Processor) will take your vomit prompt, execute the 3-pass fan-out, and generate a populated `docs/HOLEMAP.md` and a stack of `workorder.json` envelopes in `mailbox/inbox/`.
