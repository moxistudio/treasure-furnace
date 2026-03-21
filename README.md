# treasure-furnace

`treasure-furnace` is the standalone developer toolchain for HoluBot Treasures.

In P0, this repository focuses on the smallest useful public surface:

- preview imported skills or packs
- validate a Treasure package directory
- install an imported source into a local `runtime_assets/` folder
- keep the import-manager flow portable outside the HoluBot monorepo

This repository is for Treasure developers and migration work. It is not the HoluBot runtime itself.

## What It Contains

- `treasure_forge.py`
  The core import / preview / install / validate logic.
- `core/import_manager.py`
  The `/import` style conversational state machine for preview-adjust-confirm flows.
- `adapters/agent_runtime.py`
  The minimal compiler that converts pack specs into runtime plans.
- `adapters/agent_registry.py`
  A pack loader for local `runtime_assets/`.
- `adapters/agent_executor.py`
  A compatibility executor shim used by tests and runtime-plan smoke checks.

## Quick Start

Create a virtualenv, then install the repo in editable mode:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

Preview a local source:

```bash
python -m treasure_forge preview ./templates/basic-treasure/pack.yaml
```

Validate a Treasure directory:

```bash
python -m treasure_forge validate ./runtime_assets/deep-search
```

Install an imported source into local `runtime_assets/`:

```bash
python -m treasure_forge install ./templates/basic-treasure/pack.yaml
```

## CLI Surface

Current P0 commands:

- `python -m treasure_forge preview <source>`
- `python -m treasure_forge install <source> [--runtime-assets-dir PATH]`
- `python -m treasure_forge validate <treasure_dir>`

`<source>` can be:

- a local `SKILL.md`
- a local `pack.yaml`
- a local `.zip`
- pasted raw text
- a GitHub or raw HTTP URL

## Repository Layout

```text
treasure-furnace/
├── adapters/
├── core/
├── templates/
├── tests/
├── pocket_manifest_builder.py
└── treasure_forge.py
```

## Scope Notes

- AI Sentinel knowledge-base content is intentionally out of scope for this repo snapshot.
- Helper treasure discovery degrades safely when the HoluBot `pocket` module is not present.
- `agent_executor` is kept as a compatibility layer, not as the full production runtime.
