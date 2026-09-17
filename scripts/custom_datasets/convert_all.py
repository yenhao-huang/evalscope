"""Export all nine local datasets in built-in EvalScope formats."""

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    """Hash files without loading image datasets into memory."""
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def write_dataset(output: Path, task: str, benchmark: str, pairs: list, sources: list[Path]) -> dict:
    """Write native input plus independent provenance and task-metric sidecars."""
    folder = output / benchmark
    folder.mkdir(parents=True, exist_ok=True)
    suffix = '_val' if benchmark == 'general_mcq' else ''
    data = folder / f'{task}{suffix}.jsonl'
    sidecar = output / f'{task}.sidecar.jsonl'
    if data.exists() or sidecar.exists():
        raise FileExistsError(f'Refusing to overwrite frozen data: {task}')
    with data.open('w') as dst, sidecar.open('w') as audit:
        for native, metadata in pairs:
            dst.write(json.dumps(native, ensure_ascii=False, sort_keys=True) + '\n')
            audit.write(json.dumps(metadata, ensure_ascii=False, sort_keys=True) + '\n')
    return {
        'benchmark': benchmark,
        'count': len(pairs),
        'file': str(data.relative_to(output)),
        'sha256': sha256(data),
        'sidecar': sidecar.name,
        'sidecar_sha256': sha256(sidecar),
        'source_files': [{'path': str(p), 'sha256': sha256(p)} for p in sources],
        'multiple_correct': task == 'opseval',
    }


def main() -> None:
    """Create a fresh export and publish a small manifest."""
    from convert_text import convert as convert_text
    from convert_vision import convert as convert_vision

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset-root', type=Path, default=Path.home() / 'Desktop/datasets')
    parser.add_argument('--exp', type=Path, required=True)
    parser.add_argument('--image-cache', type=Path)
    args = parser.parse_args()
    manifest_path = args.exp / 'manifest.json'
    if manifest_path.exists():
        raise FileExistsError('Use a new experiment; manifest already exists')
    output = args.exp / 'data'
    output.mkdir(parents=True, exist_ok=True)
    subsets = convert_text(args.dataset_root, output)
    subsets.update(convert_vision(args.dataset_root, output, args.image_cache))
    manifest = {
        'schema_version': 2,
        'interface': 'built-in general_mcq/general_qa/general_vqa',
        'sampling': 'original source order; all source rows converted',
        'subsets': subsets,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
