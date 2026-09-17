"""EvalScope adapter for versioned local model-tester exports."""

from typing import Any

from evalscope.api.benchmark import BenchmarkMeta, DefaultDataAdapter
from evalscope.api.dataset import Sample
from evalscope.api.evaluator import TaskState
from evalscope.api.metric import Score
from evalscope.api.model import Model
from evalscope.api.registry import register_benchmark
from evalscope.constants import Tags
from evalscope.models.utils.openai import chat_messages_from_openai

from .scoring import SCORING_VERSION, score_response

SUBSETS = ['mmlu', 'gsm8k', 'humaneval', 'geo_mmlu', 'law_mmlu', 'opseval', 'pokemon', 'cifar10', 'cppe5']


@register_benchmark(
    BenchmarkMeta(
        name='local_model_tester',
        pretty_name='Local Model Tester',
        description="""
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
""",
        tags=[Tags.CUSTOM],
        dataset_id='local_model_tester',
        subset_list=SUBSETS,
        metric_list=['acc'],
        extra_params={'review_only': False},
        few_shot_num=0,
        train_split=None,
        eval_split='test',
        prompt_template='{question}',
        evaluation_version=SCORING_VERSION,
    )
)
class LocalModelTesterAdapter(DefaultDataAdapter):
    """Load pre-converted chat samples and apply task-specific deterministic scores."""

    def load_from_remote(self) -> Any:
        """Require a verified local export instead of downloading an unrelated dataset."""
        raise FileNotFoundError('Convert the local sources and set dataset_args.local_model_tester.local_path')

    def load_from_disk(self, **kwargs: Any) -> Any:
        return super().load_from_disk(use_local_loader=True)

    def record_to_sample(self, record: dict[str, Any]) -> Sample:
        """Keep converter messages, IDs and provenance intact."""
        return Sample(
            id=record['id'],
            input=chat_messages_from_openai(model='', messages=record['messages']),
            target=record['target'],
            metadata=record['metadata'],
        )

    def run_inference(self, model: Model, sample: Sample, output_dir: str, **kwargs: Any) -> TaskState:
        """Fail closed when a review-only run encounters an uncached sample."""
        if (self.extra_params or {}).get('review_only'):
            raise RuntimeError('Review-only run has missing or invalid prediction cache; inference is disabled')
        return super().run_inference(model, sample, output_dir, **kwargs)

    def match_score(
        self, original_prediction: str, filtered_prediction: str, reference: str, task_state: TaskState
    ) -> Score:
        """Apply the scorer selected by the sample metadata."""
        values = score_response(filtered_prediction, reference, task_state.metadata)
        return Score(
            value=values,
            main_score_name='acc',
            prediction=original_prediction,
            extracted_prediction=filtered_prediction,
        )
