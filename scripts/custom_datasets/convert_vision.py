"""Convert local images to the existing General-VQA messages/answer format."""

import argparse
import json
import shutil
from pathlib import Path

from source_data import load_arrow, vision_sample


def format_answer(task: str, gold: object) -> str:
    """Match the requested output format so native lexical metrics stay meaningful."""
    if task == 'cppe5':
        return ', '.join(gold)
    return gold if isinstance(gold, str) else json.dumps(gold, ensure_ascii=False, sort_keys=True)


def convert(dataset_root: Path, output: Path, image_cache: Path | None = None) -> dict:
    """Freeze original images and retain task targets in independent sidecars."""
    from convert_all import write_dataset

    cache = output / 'images'
    cache.mkdir(parents=True, exist_ok=True)
    if image_cache and image_cache.exists():
        for source in image_cache.glob('*.image'):
            shutil.copy2(source, cache / source.name)
    result = {}
    for task, folder in [
        ('pokemon', 'PokemonCards_train_300'),
        ('cifar10', 'cifar10_classification'),
        ('cppe5', 'object_detection'),
    ]:
        source = dataset_root / 'vision-dataset' / folder
        rows, features = load_arrow(source)
        pairs = []
        for index, row in enumerate(rows):
            original = vision_sample(task, row, features, index, cache)
            gold = json.loads(original['target'])
            answer = format_answer(task, gold)
            pairs.append(
                (
                    {'messages': original['messages'], 'answer': answer},
                    {'index': index, 'target': original['target'], 'metadata': original['metadata']},
                )
            )
        sources = [source / 'state.json', source / 'dataset_info.json', *sorted(source.glob('*.arrow'))]
        result[task] = write_dataset(output, task, 'general_vqa', pairs, sources)
        print(task, len(rows), 'general_vqa', flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset-root', type=Path, default=Path.home() / 'Desktop/datasets')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--image-cache', type=Path)
    args = parser.parse_args()
    print(json.dumps(convert(args.dataset_root, args.output, args.image_cache), indent=2))
