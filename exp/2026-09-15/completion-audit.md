# Completion audit — 2026-09-15

The requested local framework and both experiment phases are complete for the declared sample cohorts. GitHub publication/CI activation and full-dataset runs beyond those cohorts are not claimed.

| Requirement | Verified evidence | Status |
| --- | --- | --- |
| Local EvalScope fork | origin yenhao-huang/evalscope, upstream modelscope/evalscope; feature branch feat/local-custom-benchmarks | Complete |
| repo-create governance | Upstream AGENTS.md preserved; docs/rules/git.md, filetree.md, environment.md and docs/feature-list.md | Complete |
| Experiment / environment conventions | AGENTS.md requires exp/<exp-name> and root .venv; Python 3.11.14 and dependency freeze recorded | Complete |
| Phase 1 / Phase 2 issues | GitHub issues #1 and #2 created and updated | Complete |
| Start local Gemma | /health returns ok, /v1/models returns gemma4-26b-a4b; local-server.json and model-provenance.json | Complete |
| Nine local benchmark conversion | 21,307 source rows; all nine exported JSONL hashes rechecked against manifest | Complete |
| Run and record local experiment | 1,100 verified reviews: PokemonCards 300, each other subset first 100; all APIs successful; local-final-validation.json | Complete for declared cohorts |
| Full datasets beyond declared cohorts | Remaining rows converted but not evaluated; no full-dataset capability claim | Not run |
| Automated maintenance setup | Contract CI and Dependabot configuration present; make lint and 26 local tests pass | Prepared locally; not activated until push |
| DGX Spark model startup | remote-status.json: SSH, GPU and official weights verified; model API serves /workspace/llm_model under original YAML plus memory override | Complete |
| Remote PokemonCards and paired comparison | remote-pokemon-validation.json verifies all inputs and 300 reviews; phase2-results.md and paired comparison report confirm 280/300 versus 278/300, within the predefined tolerance | Complete |
| ARCH / Docker / Linux from 12-row table | No corresponding local source or task specification found; explicitly excluded from nine-source conversion | Missing inputs |

## Reproducibility limits

The primary scores use v1.1. GSM8K numeric equivalence repairs five v1.0 formatting false negatives and preserves the legacy score. All cached model answers are unchanged. MMLU first 100 is abstract_algebra only; current text prefixes differ from historical random-100 samples. CPPE-5 is class-set equality. Latency is original end-to-end request time.

Raw predictions, data, model weights, logs and .venv stay local and ignored. Aggregate results and reproducibility metadata are committed. No code push has been requested; GitHub CI has not run on this branch. The remote deployment was verified and remains running. The paired result supports similarity on these 300 cards, not universal equivalence.
