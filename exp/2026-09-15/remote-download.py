"""Download the pinned Transformers checkpoint and verify Hugging Face object hashes."""

import argparse
import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def download_file(entry: dict, repo: str, revision: str, output: Path) -> str:
    """Resume partial transfers and publish only files whose size and hash match."""
    name = entry['rfilename']
    target = output / name
    partial = target.with_name(target.name + '.part')
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        subprocess.run(
            [
                'curl',
                '--fail',
                '--location',
                '--silent',
                '--show-error',
                '--retry',
                '5',
                '--continue-at',
                '-',
                '--output',
                str(partial),
                f'https://huggingface.co/{repo}/resolve/{revision}/{name}',
            ],
            check=True,
        )
    candidate = target if target.exists() else partial
    size = candidate.stat().st_size
    if size != entry['size']:
        raise ValueError(f'Size mismatch: {name}')
    lfs = entry.get('lfs')
    digest = hashlib.sha256() if lfs else hashlib.sha1()
    if not lfs:
        digest.update(f'blob {size}\0'.encode())
    with candidate.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    expected = lfs['sha256'] if lfs else entry['blobId']
    if digest.hexdigest() != expected:
        raise ValueError(f'Content hash mismatch: {name}')
    if candidate != target:
        candidate.rename(target)
    print(f'Verified {name}: {size} bytes', flush=True)
    return name


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    status = args.manifest.with_name('download-status.json')
    state = {'status': 'running', 'revision': manifest['revision']}
    status.write_text(json.dumps(state, indent=2) + '\n')
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(download_file, entry, manifest['repo'], manifest['revision'], args.output)
                for entry in manifest['files']
            ]
            state['verified_files'] = [future.result() for future in futures]
        state['status'] = 'completed'
    except Exception as error:
        state['status'] = 'failed'
        state['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        status.write_text(json.dumps(state, indent=2) + '\n')


if __name__ == '__main__':
    main()
