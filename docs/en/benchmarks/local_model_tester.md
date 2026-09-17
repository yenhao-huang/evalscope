# Local Model Tester


## Overview
A reproducible migration of nine local model-tester benchmarks into EvalScope.

## Task Description
- **Task Type**: Multiple choice, mathematics, code generation, OCR and visual classification.
- **Input**: Versioned local JSONL chat samples with frozen image content.
- **Output**: Choice letters, numeric answers, Python code, JSON fields or class labels.
- **Domain**: Knowledge, operations, mathematics, code and vision.

## Key Features
- Nine subsets: MMLU, GSM8K, HumanEval, Geo-MMLU, Law-MMLU, OpsEval, PokemonCards, CIFAR-10 and CPPE-5.
- Stable sample IDs, original ordering and source-content hashes from the conversion manifest.
- No remote dataset fallback; converted local data is required.

## Evaluation Notes
- Zero-shot deterministic accuracy, version v1.1. GSM8K compares numerical values (26.00 equals 26) and retains legacy string accuracy separately. Pokemon primary accuracy requires name/hp field equality.
- Historical Pokemon substring accuracy is reported separately; CPPE-5 measures class sets, not boxes.
- HumanEval uses macOS sandbox-exec with denied network/file writes and resource/time limits.
- Samples and image bytes are local generated artifacts and are not committed.


## Properties

| Property | Value |
|----------|-------|
| **Benchmark Name** | `local_model_tester` |
| **Dataset ID** | `local_model_tester` |
| **Paper** | N/A |
| **Tags** | `Custom` |
| **Metrics** | `accuracy` |
| **Default Shots** | 0-shot |
| **Evaluation Split** | `test` |


## Data Statistics

*Statistics not available.*

## Sample Example

*Sample example not available.*

## Prompt Template

**Prompt Template:**
```text
{question}
```

## Extra Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `review_only` | - | `False` | - |

## Usage

### Using CLI

```bash
evalscope eval \
    --model YOUR_MODEL \
    --api-url OPENAI_API_COMPAT_URL \
    --api-key EMPTY_TOKEN \
    --datasets local_model_tester \
    --limit 10  # Remove this line for formal evaluation
```

### Using Python

```python
from evalscope import run_task
from evalscope.config import TaskConfig

task_cfg = TaskConfig(
    model='YOUR_MODEL',
    api_url='OPENAI_API_COMPAT_URL',
    api_key='EMPTY_TOKEN',
    datasets=['local_model_tester'],
    dataset_args={
        'local_model_tester': {
            # extra_params: {}  # uses default extra parameters
        }
    },
    limit=10,  # Remove this line for formal evaluation
)

run_task(task_cfg=task_cfg)
```
