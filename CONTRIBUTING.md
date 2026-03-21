# Contributing

## P0 Contribution Rules

This repository is a toolchain repo, not the HoluBot runtime repo.

Good contributions in P0:

- improve Treasure import / preview / install behavior
- expand validator coverage
- harden source parsing and safety checks
- improve Treasure developer templates and docs
- add focused tests for migration and compatibility cases

Avoid in P0:

- embedding runtime-only business logic
- bundling unrelated HoluBot app features
- pulling in large monorepo dependencies unless they are required to keep the toolchain standalone

## Local Checks

```bash
pip install -e '.[dev]'
pytest
python -m treasure_forge validate templates/basic-treasure
```

## Pull Requests

Keep pull requests narrow. Each PR should ideally focus on one of:

- parsing / import
- validation / governance
- CLI / packaging
- developer templates / docs

If behavior changes, update or add tests in `tests/`.

