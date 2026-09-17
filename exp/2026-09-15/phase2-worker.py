"""Finish the authorized DGX experiment after its pinned checkpoint download completes."""

import hashlib
import json
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

EXP = Path(__file__).resolve().parent
ROOT = EXP.parent.parent
HOST = 'wingene@100.109.182.22'
REMOTE_EXP = '/workspace/exp/2026-09-15-evalscope'
CONFIG = '/workspace/deprecated/gemma-4-26B-A4B-it.yaml'
PROJECT = 'evalscope-phase2-20260915'
COMPOSE = ['docker', 'compose', '-f', CONFIG, '-p', PROJECT]
OVERRIDE = EXP / 'remote-resource-override.yaml'
if OVERRIDE.exists():
    COMPOSE += ['-f', f'{REMOTE_EXP}/remote-resource-override.yaml']
API = 'http://100.109.182.22:3335/v1'
MODEL = '/workspace/llm_model'
STATE = EXP / 'phase2-progress.json'


def remote(args: list[str]) -> str:
    return subprocess.check_output(
        ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', HOST, shlex.join(args)],
        text=True,
        timeout=120,
    )


def main() -> None:
    record = {'started_at': datetime.now(timezone.utc).isoformat(), 'status': 'running', 'stage': 'download'}

    def stage(name: str) -> None:
        record['stage'] = name
        record['updated_at'] = datetime.now(timezone.utc).isoformat()
        STATE.write_text(json.dumps(record, indent=2) + '\n')
        print(name, flush=True)

    try:
        stage('waiting_for_verified_weights')
        deadline = time.monotonic() + 7200
        while time.monotonic() < deadline:
            download = json.loads(remote(['cat', f'{REMOTE_EXP}/download-status.json']))
            if download['status'] == 'completed':
                (EXP / 'remote-download-validation.json').write_text(json.dumps(download, indent=2) + '\n')
                break
            if download['status'] == 'failed':
                raise RuntimeError(f'Checkpoint download failed: {download.get("error")}')
            command = remote(['cat', '/proc/2979/cmdline'])
            if 'remote-download.py' not in command:
                raise RuntimeError('Expected download process is no longer running')
            time.sleep(20)
        else:
            raise TimeoutError('Checkpoint download deadline exceeded')
        stage('starting_original_yaml')
        expected = hashlib.sha256((EXP / 'remote-original-gemma.yaml').read_bytes()).hexdigest()
        if remote(['sha256sum', CONFIG]).split()[0] != expected:
            raise RuntimeError('Original remote YAML changed after inspection')
        if OVERRIDE.exists():
            expected_override = hashlib.sha256(OVERRIDE.read_bytes()).hexdigest()
            if remote(['sha256sum', f'{REMOTE_EXP}/remote-resource-override.yaml']).split()[0] != expected_override:
                raise RuntimeError('Resource override differs from the recorded local copy')
            record['resource_override_sha256'] = expected_override
        remote(
            [
                'python3',
                '-c',
                'import os,pathlib; '
                'paths=pathlib.Path("/home/wingene/transformers_models/gemma-4-26B-A4B-it").glob("*"); '
                '[(lambda f: (os.posix_fadvise(f.fileno(),0,0,os.POSIX_FADV_DONTNEED),f.close()))'
                '(p.open("rb")) for p in paths if p.is_file()]',
            ]
        )
        print(remote([*COMPOSE, 'up', '-d', '--pull', 'never']), flush=True)
        stage('waiting_for_model_api')
        deadline = time.monotonic() + 1800
        while time.monotonic() < deadline:
            try:
                response = requests.get(API + '/models', timeout=10)
                if response.ok and MODEL in {m['id'] for m in response.json()['data']}:
                    record['model_info'] = response.json()
                    break
            except (requests.RequestException, ValueError, KeyError):
                pass
            container = remote([*COMPOSE, 'ps', '-aq']).strip()
            if container:
                info = json.loads(remote(['docker', 'inspect', container]))[0]
                if info['RestartCount'] or info['State']['Status'] in ('exited', 'dead'):
                    logs = remote([*COMPOSE, 'logs', '--no-color', '--tail', '100'])
                    (EXP / 'logs/remote-startup-failure.log').write_text(logs)
                    remote([*COMPOSE, 'stop'])
                    raise RuntimeError('Model failed to start; see logs/remote-startup-failure.log')
            time.sleep(10)
        else:
            remote([*COMPOSE, 'stop'])
            raise TimeoutError('Model API did not become ready within 30 minutes')
        stage('evaluating_300_cards')
        subprocess.run(
            [
                sys.executable,
                'scripts/run_model_tester.py',
                '--run-name',
                'remote-pokemon-300',
                '--subsets',
                'pokemon',
                '--limit',
                '300',
                '--api-url',
                API,
                '--model',
                MODEL,
            ],
            cwd=ROOT,
            check=True,
        )
        stage('paired_comparison')
        subprocess.run(
            [
                sys.executable,
                'scripts/compare_model_tester.py',
                '--local',
                'local-pokemon-300-v1_1',
                '--remote',
                'remote-pokemon-300',
                '--subset',
                'pokemon',
            ],
            cwd=ROOT,
            check=True,
        )
        record['status'] = 'completed'
        stage('completed')
    except BaseException as error:
        record['status'] = 'failed'
        record['error'] = f'{type(error).__name__}: {error}'
        stage('failed')
        raise


if __name__ == '__main__':
    main()
