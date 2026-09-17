## Goal
Support a remote OpenAI-compatible model endpoint and compare DGX Spark with local Gemma using PokemonCards_train_300.

## Acceptance criteria
- [x] Reach DGX Spark at 100.109.182.22 via SSH and locate gemma-4-26B-A4B-it.yaml.
- [x] Inspect config, GPU capacity and existing workloads; start the requested model and verify model identity and multimodal API health.
- [x] Evaluate the same 300 PokemonCards samples with identical content hashes, prompt, decoding and scorers.
- [x] Record local/remote accuracy, per-sample agreement, errors and latency; document backend/precision differences and paired uncertainty.
- [x] Add reusable remote configuration and comparison commands; save evidence under exp/2026-09-15/.

## Completed experiment
DGX Spark vLLM evaluated all 300 PokemonCards with zero evaluation errors: 280/300 (93.33%), versus local 278/300 (92.67%). Remote minus local is +0.67 percentage points; the paired bootstrap 95% interval is [0.00, 1.67] pp, within the predefined ±5 pp tolerance. Correctness agreement is 298/300 (99.33%); remote-only correct 2, local-only correct 0.

Mean request latency: remote 2.213 seconds, local 4.071 seconds; all 300 requests have metrics. This compares deployment stacks (vLLM FP8 versus llama.cpp GGUF Q4_K_XL), not hardware alone.

All 300 source indices, image hashes, input roles/text, targets and metadata were independently verified. Source scorer hashes, frozen data and decoding settings passed paired-comparison checks. Evidence: exp/2026-09-15/phase2-results.md, remote-pokemon-validation.json, remote-pokemon-300.json and comparison-local-pokemon-300-v1_1-remote-pokemon-300.json.

## Deployment and repair
SSH: wingene@100.109.182.22. Original YAML: /workspace/deprecated/gemma-4-26B-A4B-it.yaml. Installed NVIDIA Container Toolkit/CDI in the sandbox and verified actual GPU computation. Downloaded and verified pinned official Transformers weights to the original mount path. The separate resource override changes only GPU memory utilization 0.4 -> 0.25 after the original preflight required 48.68 GiB while only 32.95 GiB was available. Actual FP8 model loading completed in about 425 seconds using 25.67 GiB. Model remains available at http://100.109.182.22:3335/v1 with ID /workspace/llm_model.

Image digest, model revision, command, precision and override hashes are in remote-model-provenance.json. The existing remote GGUF was not substituted. Code and results are committed locally; no code push yet. This issue remains open for review.
