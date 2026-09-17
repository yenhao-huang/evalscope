# Native custom dataset workflow

These scripts use EvalScope's existing `general_mcq`, `general_qa`, and `general_vqa` formats through public `TaskConfig` / `run_task` configuration. They do not register adapters, patch functions, or modify files under `evalscope/`.

## Mapping

| Source | Built-in dataset | Output schema | Native metric | Independent task metric |
| --- | --- | --- | --- | --- |
| MMLU / Geo-MMLU / Law-MMLU | general_mcq | question, A..J, answer | accuracy | none |
| OpsEval | general_mcq (multiple_correct) | question, A..J, answer as letter list | accuracy | none |
| GSM8K | general_qa | messages, answer | BLEU / ROUGE | numeric answer equality |
| HumanEval | general_qa | messages, answer | BLEU / ROUGE | isolated test pass rate |
| PokemonCards | general_vqa | messages, answer | BLEU / ROUGE | JSON name/hp field match |
| CIFAR-10 | general_vqa | messages, answer | BLEU / ROUGE | normalized exact label |
| CPPE-5 | general_vqa | messages, answer | BLEU / ROUGE | PPE class-set equality |

The general QA/VQA adapters do not expose arbitrary deterministic scoring via `metric_list`: unsupported names are not evaluated. We leave them unchanged and keep task-specific analysis in a separate output file. Native BLEU/ROUGE scores are never labeled task accuracy. HumanEval code is never executed by the general QA adapter; the independent analyzer uses macOS `sandbox-exec` with network, home-file access and file writes denied and resource/time limits. Other hosts must supply an explicitly configured isolated analysis environment before computing that metric.

## Convert

From the repository root, use the root `.venv`:

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e '.[dev,perf,docs]'
.venv/bin/python -c "import nltk; nltk.download('punkt_tab', download_dir='.venv/nltk_data', raise_on_error=True)"
.venv/bin/python scripts/custom_datasets/convert_all.py \
  --dataset-root "$HOME/Desktop/datasets" --exp exp/my-native-run
```

Optional `--image-cache exp/2026-09-15/data/images` reuses downloaded Pokemon images. `convert_text.py` and `convert_vision.py` can also be run separately with `--output exp/<name>/data`; `convert_all.py` combines their output into the manifest required by the runner. Conversion rejects overwrites. Data and sidecars are ignored by Git; the tracked manifest stores source/output hashes and counts.

## Evaluate and analyze

```bash
.venv/bin/python scripts/custom_datasets/run_native.py \
  --exp exp/my-native-run --run-name local-native \
  --api-url http://127.0.0.1:8092/v1 --model gemma4-26b-a4b
.venv/bin/python scripts/custom_datasets/analyze_results.py \
  --exp exp/my-native-run --run-name local-native
```

The default cohort is PokemonCards 300 and each other source's first 100 records in original order. Set `--limit` and `--pokemon-limit` explicitly for different cohorts; conversion itself always includes all rows. The runner refuses framework changes relative to `origin/main`, validates frozen input hashes, uses built-in metrics, and rejects incomplete execution or metric errors. Fresh run names perform new inference; `--resume` is allowed only for the same recorded configuration and runner hash.

For a remote endpoint, use the same runner and frozen files:

```bash
.venv/bin/python scripts/custom_datasets/run_native.py \
  --exp exp/my-native-run --run-name remote-pokemon \
  --subsets pokemon --pokemon-limit 300 \
  --api-url http://100.109.182.22:3335/v1 --model /workspace/llm_model
.venv/bin/python scripts/custom_datasets/analyze_results.py \
  --exp exp/my-native-run --run-name remote-pokemon
```

`<run-name>.json` retains public task configuration, native aggregate reports and execution status. `<run-name>-task-analysis.json` is an independent audited analysis, including per-index correctness but no model responses. Raw native predictions/reviews remain in ignored `runs/` directories. Native MCQ uses its built-in prompt/parser, so its scores are not interchangeable with the earlier adapter's prompts/scoring. QA/VQA message text and images preserve the original source preparation.

References: [LLM custom datasets](https://evalscope.readthedocs.io/zh-cn/latest/advanced_guides/custom_dataset/llm.html), [multimodal custom datasets](https://evalscope.readthedocs.io/zh-cn/latest/advanced_guides/custom_dataset/vlm.html).
