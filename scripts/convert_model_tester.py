"""Freeze local model-tester datasets into EvalScope chat JSONL subsets."""

import argparse
import base64
import hashlib
import io
import json
from pathlib import Path

import pyarrow as pa
import requests
from PIL import Image

from evalscope.benchmarks.local_model_tester.scoring import last_number

TEXT_PATHS = {
    'mmlu': 'mmlu',
    'gsm8k': 'gsm8k-main',
    'humaneval': 'humaneval',
    'geo_mmlu': 'geo-mmlu-high-school',
    'law_mmlu': 'law-mmlu-professiona',
}
SYSTEM = 'You are a precise evaluator assistant. Follow output format strictly.'


def text_sample(task: str, row: dict, index: int) -> dict:
    """Preserve the original runner's prompts and expected answers."""
    metadata = {'task': task, 'source_index': index, 'source_id': row.get('id', row.get('task_id', index))}
    system = SYSTEM
    if task in ('mmlu', 'geo_mmlu', 'law_mmlu'):
        choices = '\n'.join(f'{letter}. {choice}' for letter, choice in zip('ABCD', row['choices']))
        query = f'Question:\n{row["question"]}\n\nChoices:\n{choices}\n\nAnswer with only one letter: A, B, C, or D.'
        gold = 'ABCD'[int(row['answer'])]
    elif task == 'gsm8k':
        query = f'Solve this math problem. End your answer with #### <number>.\n\nQuestion:\n{row["question"]}'
        gold = last_number(row['answer'])
    elif task == 'humaneval':
        query = (
            'Complete the following Python function. Return only Python code, no markdown fences. '
            'You may return either the full function definition or only the function body.\n\n' + row['prompt']
        )
        metadata.update({key: row[key] for key in ('prompt', 'test', 'entry_point')})
        gold = row.get('canonical_solution', '')
    elif task == 'opseval':
        system = '你是精準的選擇題評測助理。請嚴格只輸出答案字母，不要解釋。'
        choices = '\n'.join(f'{chr(65 + i)}. {choice}' for i, choice in enumerate(row['choices']))
        query = (
            '請作答下列選擇題。若為多選題，請只輸出所有正確選項字母並以逗號分隔，例如 A,C；不要輸出解釋。'
            f'\n\n題目：\n{row["question"]}\n\n選項：\n{choices}\n\n答案：'
        )
        gold = row['answer']
        metadata['choice_count'] = len(row['choices'])
    else:
        raise ValueError(task)
    return {
        'id': index,
        'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': query}],
        'target': json.dumps(gold, ensure_ascii=False),
        'metadata': metadata,
    }


def load_arrow(path: Path) -> tuple[list[dict], dict]:
    """Read Hugging Face save_to_disk Arrow files without changing their order."""
    state = json.loads((path / 'state.json').read_text())
    rows = []
    for entry in state['_data_files']:
        with pa.memory_map(str(path / entry['filename']), 'r') as source:
            rows.extend(pa.ipc.open_stream(source).read_all().to_pylist())
    return rows, json.loads((path / 'dataset_info.json').read_text())['features']


def image_bytes(value: dict) -> bytes:
    """Encode embedded dataset images in PNG, matching the reference vision runner."""
    source = io.BytesIO(value['bytes']) if value.get('bytes') else value['path']
    with Image.open(source) as image:
        if image.mode not in ('RGB', 'RGBA', 'L'):
            image = image.convert('RGB')
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        return buffer.getvalue()


def vision_sample(task: str, row: dict, features: dict, index: int, cache: Path) -> dict:
    """Freeze actual image bytes into data URLs for paired local/remote evaluation."""
    metadata = {'task': task, 'source_index': index, 'source_id': index}
    if task == 'pokemon':
        query = 'OCR task: read this Pokemon card and answer strictly JSON with keys "name" and "hp" (hp as integer).'
        gold = {'name': row['name'], 'hp': row['hp']}
        url = row['image_url']
        cached = cache / (hashlib.sha256(url.encode()).hexdigest() + '.image')
        if not cached.exists():
            response = requests.get(url, timeout=45)
            response.raise_for_status()
            Image.open(io.BytesIO(response.content)).verify()
            cached.write_bytes(response.content)
        content = cached.read_bytes()
        with Image.open(io.BytesIO(content)) as image:
            mime = Image.MIME[image.format]
        metadata['source_image_url'] = url
    elif task == 'cifar10':
        query = (
            'Image classification task: choose one label from '
            '[airplane, automobile, bird, cat, deer, dog, frog, horse, ship, truck]. Output one label only.'
        )
        gold = features['label']['names'][row['label']]
        content, mime = image_bytes(row['img']), 'image/png'
    else:
        query = (
            'Object detection task: list which PPE classes are present in the image from '
            '[Coverall, Face_Shield, Gloves, Goggles, Mask]. Return comma-separated class names only.'
        )
        categories = features['objects']['category']['feature']['names']
        gold = sorted({categories[c] for c in row['objects']['category']})
        content, mime = image_bytes(row['image']), 'image/png'
    metadata['image_sha256'] = hashlib.sha256(content).hexdigest()
    data_url = f'data:{mime};base64,' + base64.b64encode(content).decode()
    return {
        'id': index,
        'messages': [
            {
                'role': 'user',
                'content': [{'type': 'text', 'text': query}, {'type': 'image_url', 'image_url': {'url': data_url}}],
            }
        ],
        'target': json.dumps(gold, ensure_ascii=False),
        'metadata': metadata,
    }


def write_subset(path: Path, samples: list[dict], source: Path) -> dict:
    """Write the exact model inputs and publish a content fingerprint."""
    with path.open('w') as handle:
        for sample in samples:
            handle.write(json.dumps(sample, ensure_ascii=False, sort_keys=True) + '\n')
    return {
        'source': str(source),
        'count': len(samples),
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'sample_ids': [sample['metadata']['source_id'] for sample in samples],
        'image_sha256': [
            sample['metadata']['image_sha256'] for sample in samples if 'image_sha256' in sample['metadata']
        ],
    }


def main() -> None:
    """Convert all nine local sources and save a small tracked manifest."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset-root', type=Path, default=Path.home() / 'Desktop/datasets')
    parser.add_argument('--exp', type=Path, default=Path('exp/2026-09-15'))
    args = parser.parse_args()
    output = args.exp / 'data'
    output.mkdir(parents=True, exist_ok=True)
    cache = output / 'images'
    cache.mkdir(exist_ok=True)
    manifest = {'schema_version': 1, 'scoring_version': 'v1.0', 'sampling': 'original order, no shuffle', 'subsets': {}}
    for task, folder in {**TEXT_PATHS, 'opseval': 'opseval'}.items():
        root = args.dataset_root / ('chinese-question-eval/converted' if task == 'opseval' else 'full-textgen-evalset')
        source = root / folder / 'test.jsonl'
        rows = [json.loads(line) for line in source.read_text().split('\n') if line.strip()]
        manifest['subsets'][task] = write_subset(
            output / f'{task}.jsonl', [text_sample(task, row, i) for i, row in enumerate(rows)], source
        )
        print(task, len(rows), flush=True)
    for task, folder in [
        ('pokemon', 'PokemonCards_train_300'),
        ('cifar10', 'cifar10_classification'),
        ('cppe5', 'object_detection'),
    ]:
        source = args.dataset_root / 'vision-dataset' / folder
        rows, features = load_arrow(source)
        samples = []
        for i, row in enumerate(rows):
            samples.append(vision_sample(task, row, features, i, cache))
            if (i + 1) % 25 == 0:
                print(task, i + 1, '/', len(rows), flush=True)
        manifest['subsets'][task] = write_subset(output / f'{task}.jsonl', samples, source)
    (args.exp / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print('Saved', args.exp / 'manifest.json', flush=True)


if __name__ == '__main__':
    main()
