"""Convert local text sources to documented General-MCQ and General-QA JSONL."""

import argparse
import json
from pathlib import Path

from source_data import text_sample

SOURCES = {
    'mmlu': 'full-textgen-evalset/mmlu/test.jsonl',
    'geo_mmlu': 'full-textgen-evalset/geo-mmlu-high-school/test.jsonl',
    'law_mmlu': 'full-textgen-evalset/law-mmlu-professiona/test.jsonl',
    'opseval': 'chinese-question-eval/converted/opseval/test.jsonl',
    'gsm8k': 'full-textgen-evalset/gsm8k-main/test.jsonl',
    'humaneval': 'full-textgen-evalset/humaneval/test.jsonl',
}


def convert_record(task: str, row: dict, index: int) -> tuple[dict, dict]:
    """Map source columns to existing public schemas and retain an audit sidecar."""
    original = text_sample(task, row, index)
    sidecar = {'index': index, 'target': original['target'], 'metadata': original['metadata']}
    if task in ('mmlu', 'geo_mmlu', 'law_mmlu', 'opseval'):
        choices = row['choices']
        if not 2 <= len(choices) <= 10:
            raise ValueError('General-MCQ supports 2 to 10 contiguous choices')
        answer = row['answer'] if task == 'opseval' else 'ABCD'[int(row['answer'])]
        if task == 'opseval':
            answer = sorted(set(answer))
        letters = 'ABCDEFGHIJ'[: len(choices)]
        if not answer or any(letter not in letters for letter in answer):
            raise ValueError('Answer references an absent choice')
        result = {'id': str(index), 'question': row['question'], 'answer': answer}
        result.update(dict(zip(letters, choices)))
    else:
        gold = json.loads(original['target'])
        result = {'messages': original['messages'], 'answer': str(gold)}
    return result, sidecar


def convert(dataset_root: Path, output: Path) -> dict:
    """Convert all six text datasets without shuffling or truncation."""
    from convert_all import write_dataset

    result = {}
    for task, relative in SOURCES.items():
        source = dataset_root / relative
        rows = [json.loads(line) for line in source.read_text().split('\n') if line.strip()]
        benchmark = 'general_qa' if task in ('gsm8k', 'humaneval') else 'general_mcq'
        pairs = [convert_record(task, row, index) for index, row in enumerate(rows)]
        result[task] = write_dataset(output, task, benchmark, pairs, [source])
        print(task, len(rows), benchmark, flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset-root', type=Path, default=Path.home() / 'Desktop/datasets')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(convert(args.dataset_root, args.output), indent=2))
