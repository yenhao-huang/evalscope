"""Verify remote review inputs against frozen samples before publishing comparison evidence."""

import base64
import hashlib
import json
from pathlib import Path


def image_hashes(value: object) -> list[str]:
    if isinstance(value, str) and value.startswith('data:image/'):
        return [hashlib.sha256(base64.b64decode(value.split(',', 1)[1], validate=True)).hexdigest()]
    if isinstance(value, dict):
        return [digest for child in value.values() for digest in image_hashes(child)]
    if isinstance(value, list):
        return [digest for child in value for digest in image_hashes(child)]
    return []


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def prompt_text(messages: list[dict]) -> list[tuple[str, list[str]]]:
    result = []
    for message in messages:
        content = message['content']
        texts = [content] if isinstance(content, str) else [part['text'] for part in content if part['type'] == 'text']
        result.append((message['role'], texts))
    return result


def main() -> None:
    exp = Path(__file__).resolve().parent
    manifest = json.loads((exp / 'manifest.json').read_text())
    run = json.loads((exp / 'remote-pokemon-300.json').read_text())
    assert run['status'] == 'completed'
    assert run['identity']['manifest_sha256'] == file_hash(exp / 'manifest.json')
    source_file = exp / 'data/pokemon.jsonl'
    assert file_hash(source_file) == manifest['subsets']['pokemon']['sha256']
    source = {}
    for line in source_file.open():
        row = json.loads(line)
        source[row['metadata']['source_index']] = {
            'target': row['target'],
            'metadata': row['metadata'],
            'images': image_hashes(row['messages']),
            'message_count': len(row['messages']),
            'prompt_text': prompt_text(row['messages']),
        }
    reviews = list((exp / 'runs/remote-pokemon-300/pokemon/reviews').rglob('*.jsonl'))
    assert len(reviews) == 1
    correct = 0
    legacy_correct = 0
    indices = set()
    for line in reviews[0].open():
        row = json.loads(line)
        index = row['sample_score']['sample_metadata']['source_index']
        assert index not in indices and row['index'] == index
        indices.add(index)
        sample = source[index]
        assert row['target'] == sample['target']
        assert row['sample_score']['sample_metadata'] == sample['metadata']
        assert image_hashes(row['messages'][: sample['message_count']]) == sample['images']
        assert prompt_text(row['messages'][: sample['message_count']]) == sample['prompt_text']
        assert len(sample['images']) == 1
        score = row['sample_score']['score']
        assert score['status'] == 'success' and score['value']['acc'] in (0, 1)
        correct += int(score['value']['acc'])
        legacy_correct += int(score['value']['legacy_substring'])
    assert indices == set(range(300))
    result_file = exp / 'comparison-local-pokemon-300-v1_1-remote-pokemon-300.json'
    comparison = json.loads(result_file.read_text())
    assert comparison['n'] == 300 and comparison['remote_accuracy'] == correct / 300
    execution = run['completed_subsets'][0]['reports'][0]['execution_summary']
    assert execution['succeeded'] == 300 and execution['errored'] == 0 and not execution['incomplete']
    evidence = {
        'run': 'remote-pokemon-300',
        'n': 300,
        'correct': correct,
        'legacy_correct': legacy_correct,
        'execution_summary': execution,
        'review_sha256': file_hash(reviews[0]),
        'run_sha256': file_hash(exp / 'remote-pokemon-300.json'),
        'comparison_sha256': file_hash(result_file),
        'manifest_sha256': file_hash(exp / 'manifest.json'),
        'unique_source_indices_verified': True,
        'targets_metadata_verified': True,
        'all_300_uploaded_image_hashes_verified': True,
        'all_input_roles_and_text_verified': True,
    }
    (exp / 'remote-pokemon-validation.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
