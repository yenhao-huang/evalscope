# Feature list

| Feature | Status | Entry points / notes |
| --- | --- | --- |
| Existing-interface-only policy | enforced | [AGENTS](../AGENTS.md), [rules](rules/git.md); no framework edits or new adapters for personal evaluation |
| Nine local dataset conversions | available | [Native converters](../scripts/custom_datasets/README.md); 21,307 rows, source and output hashes |
| Native evaluation | available | [2026-09-17 experiment](../exp/2026-09-17-native-interfaces/README.md); 1,100 local samples, separate native and task metrics |
| DGX native comparison | in dependent PR | [PR #5](https://github.com/yenhao-huang/evalscope/pull/5) |
| Historical adapter experiment | archived | [2026-09-15](../exp/2026-09-15/README.md), executable code at commit 667e878b (same tree as original 60c1e98f) |
| Contract CI | configured | [.github/workflows/custom-datasets.yml](../.github/workflows/custom-datasets.yml) |
| ARCH / Docker / Linux | missing inputs | Source datasets and task definitions still required |
