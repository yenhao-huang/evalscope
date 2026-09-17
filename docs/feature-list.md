# Feature list

| Feature | Status | Entry points | Notes |
| --- | --- | --- | --- |
| Repository governance | available | [Rules](rules/git.md), [AGENTS](../AGENTS.md) | Root .venv; experiments under exp/ |
| Nine local benchmark migration | available | [Converter](../scripts/convert_model_tester.py) | 5 text + 3 vision + OpsEval; stable hashes |
| Local Gemma evaluation | available | [Experiment](../exp/2026-09-15/README.md) | All 9 complete: Pokemon 300, eight other subsets 100 each; v1.1 audited results |
| Remote endpoint and paired comparison | available | [Runner](../scripts/run_model_tester.py), [Compare](../scripts/compare_model_tester.py) | Shared frozen data and scoring |
| Contract CI and dependency maintenance | available | [Workflow](../.github/workflows/local-model-tester.yml), [Dependabot](../.github/dependabot.yml) | Activates after push |
| ARCH / Docker / Linux | planned | [Issue 1](https://github.com/yenhao-huang/evalscope/issues/1) | Dataset and task specifications missing |
| Cached review-only rescoring | available | [Runner](../scripts/run_model_tester.py) | v1.1 numeric equivalence; immutable prediction hashes; original generation performance |

DGX deployment and results are delivered in the dependent Phase 2 PR.
