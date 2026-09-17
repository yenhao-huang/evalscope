# Filetree rules

## Allowed structure and directory roles

Preserve upstream `.github/`, `custom_eval/`, `docs/`, `evalscope/`, `examples/`, `requirements/`, `scripts/`, `skills/`, `tests/` and root build files.
- `evalscope/`: upstream framework code; personal evaluations must not add adapters or modify internals.
- `scripts/custom_datasets/`: source-to-native-format `convert_<name>.py` scripts, public-interface evaluation configuration, and clearly labeled independent report analysis.
- `tests/`: offline fixture and integration tests.
- `docs/rules/`: governance; `docs/feature-list.md`: feature status.
- `exp/<exp-name>/`: every experiment, including configs, manifest, report and aggregate results. Use a new dated directory for an independent run.
- `.venv/`: repository-local Python environment.

## Creation rules

Read this document before directory changes. Extend existing roles before creating another top-level directory.

## Generated files

Ignore `.venv/`, caches, `exp/*/data/`, `exp/*/runs/`, `exp/*/logs/`, `exp/*/runtime/`. Store weights and source datasets externally; record paths in local configuration and provenance in manifests. Commit only small reproducibility artifacts, never dataset content or credentials.

## Change procedure

Update this file in the same change when adding top-level directories. Preserve upstream generated benchmark documentation; use its generation commands.
