## Goal
Support reproducible custom benchmark evaluation in this EvalScope fork, referencing https://github.com/yenhao-huang/model-tester.

## Acceptance criteria
- [x] Preserve upstream instructions and add docs/rules plus root AGENTS.md requirements: experiments in exp/<exp-name>, git workflow from docs, environment in root .venv.
- [x] Convert all rows from the nine available local benchmarks into registered EvalScope-compatible samples with stable IDs and content hashes.
- [x] Support MMLU, GSM8K, HumanEval, Geo-MMLU, Law-MMLU, OpsEval, PokemonCards_train_300, CIFAR-10 and CPPE-5.
- [x] Test converters and deterministic scoring offline, including malformed output and infrastructure failure cases; isolate HumanEval execution.
- [x] Start local gemma4-26b-a4b with multimodal support; complete all nine smoke tests and the declared cohort evaluation (PokemonCards 300, eight others 100 each); record configuration, scores, errors and provenance in exp/2026-09-15/.
- [x] Keep aggregate results separate from ignored datasets, images and raw predictions.

## Scope discrepancy
The request table contains 12 benchmarks. Nine local sources were found. ARCH, Docker and Linux still need datasets and scoring/task specifications; they must not be represented by fabricated substitutes.

## Scoring
Preserve model-tester prompt/sample order. Record strict Pokemon name/hp field match separately from its historical substring metric. CPPE-5 is class-set accuracy, not bounding-box mAP.

## Completed local experiment
All nine datasets converted: 21,307 rows total. Evaluated 1,100 samples: PokemonCards 300, all other subsets first 100 in original order. These are declared cohorts, not full-dataset scores. All API requests succeeded. Native v1.1 cache-only rescoring preserved all original prediction hashes. 26 custom tests, upstream test_ci_lite, and make lint passed.

| Benchmark | Correct / evaluated |
| --- | ---: |
| MMLU abstract_algebra cohort | 89 / 100 |
| GSM8K | 97 / 100 |
| HumanEval | 94 / 100 |
| Geo-MMLU | 91 / 100 |
| Law-MMLU | 69 / 100 |
| OpsEval | 56 / 100 |
| PokemonCards | 278 / 300 |
| CIFAR-10 | 92 / 100 |
| CPPE-5 | 48 / 100 |

MMLU is entirely abstract_algebra, not 57-subject MMLU. Current text cohorts differ from the historical random-100 samples. GSM8K v1.0 lexical matching scored 92/100; Decimal numerical equivalence fixes five formatting false negatives, preserving legacy_numeric_string=0.92. CPPE-5 is class-set equality, not bounding-box mAP.
