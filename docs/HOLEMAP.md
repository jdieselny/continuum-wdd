# HOLE MAP: WDD Genesis Block

**Domain:** `[Continuum | WDD]`
**Objective:** The self-hosting Workorder Driven Development engine.

This is the Genesis Block. These workorders construct the WDD engine itself. Once complete, this repository becomes the canonical CLI/GUI for instantiating new WDD projects.

## Grid Squares (The Scaffold)
- **A-01 [Core Schemas]:** The strict JSON definitions.
- **B-01 [CLI Engine]:** The `wdd` python CLI (init, compile, replay, sweep).
- **C-01 [OB Writer Backend]:** The 3-pass intent processor.
- **D-01 [Glass / GUI]:** The React/HTML MMC snap-ins (Dashboard, OB Writer).

## The Queue

| ID | Square | Description | Status |
|---|---|---|---|
| **WO-000** | A-01 | Peer Review: Architect audit of the Genesis Block | OPEN |
| **WO-001** | B-01 | CLI: `wdd init` (repo scaffolding generator) | HOLE |
| **WO-002** | C-01 | Engine: 3-pass OB Intent Processor (`compiler.py`) | HOLE |
| **WO-003** | D-01 | GUI: Original Blueprint React UI (`wdd_blueprint.html`) | HOLE |
| **WO-004** | D-01 | GUI: Telemetry Dashboard (`wdd_telemetry.html`) | HOLE |
| **WO-005** | B-01 | Mailbox Runner: Sweep outbox, verify crypto BOL, mark SEALED | HOLE |
| **WO-006** | A-01 | Schemas: Refine `workorder.schema.json` with token projections | HOLE |
