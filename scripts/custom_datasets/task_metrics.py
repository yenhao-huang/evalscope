"""Independent task metrics on saved EvalScope outputs; never registered with EvalScope."""

import json
import os
import re
import signal
import subprocess
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

SCORING_VERSION = 'v1.1'

PPE = ['Coverall', 'Face_Shield', 'Gloves', 'Goggles', 'Mask']


def last_number(text: str) -> str:
    """Extract the last numeric token, matching the reference runner."""
    numbers = re.findall(r'-?\d+(?:\.\d+)?', text.replace(',', ''))
    return numbers[-1] if numbers else ''


def code_program(response: str, metadata: dict) -> str:
    """Build a HumanEval program from a full function or a body completion."""
    code = re.sub(r'^```[\w+-]*\n|\n```\s*$', '', response.strip()).strip()
    entry = metadata['entry_point']
    if not re.search(rf'\bdef\s+{re.escape(entry)}\s*\(', code):
        if any(line.strip() and not line.startswith((' ', '\t')) for line in code.splitlines()):
            code = '\n'.join('    ' + line if line.strip() else line for line in code.splitlines())
        code = metadata['prompt'] + code + '\n'
    return code + '\n' + metadata['test'] + f'\ncheck({entry})\n'


def sandbox_command(program: str) -> list[str]:
    """Use the macOS sandbox with no network, home-data access or writable files."""
    if sys.platform != 'darwin' or not Path('/usr/bin/sandbox-exec').exists():
        raise RuntimeError('HumanEval requires macOS sandbox-exec; configure an isolated runner on other hosts')
    python_root = Path(sys.base_prefix).resolve()
    # Python is explicitly allowed; arbitrary home files and network remain denied.
    profile = '\n'.join(
        [
            '(version 1)',
            '(allow default)',
            '(deny network*)',
            '(deny file-write*)',
            '(deny file-read-data (require-all (subpath "/Users")',
            f'  (require-not (subpath {json.dumps(str(python_root))}))))',
            '(deny file-read-data (subpath "/Volumes"))',
            '(allow file-write* (literal "/dev/null"))',
        ]
    )
    limits = (
        'import resource\n'
        'resource.setrlimit(resource.RLIMIT_CPU, (3, 3))\n'
        'resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))\n'
        'resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))\n'
    )
    return [
        '/usr/bin/sandbox-exec',
        '-p',
        profile,
        str(Path(sys.executable).resolve()),
        '-I',
        '-B',
        '-c',
        limits + program,
    ]


def execute_code(program: str) -> bool:
    """Run code with a bounded lifetime; discard untrusted stdout/stderr."""
    process = subprocess.Popen(
        sandbox_command(program),
        cwd='/private/tmp',
        env={'PATH': '/usr/bin:/bin'},
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        return process.wait(timeout=5) == 0
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        return False


def score_response(prediction: str, target: str, metadata: dict) -> dict[str, float]:
    """Score content only; transport failures must be rejected by the evaluator."""
    task = metadata['task']
    gold = json.loads(target)
    if task == 'gsm8k':
        number = last_number(prediction)
        try:
            equivalent = bool(number) and Decimal(number) == Decimal(str(gold))
        except InvalidOperation:
            equivalent = False
        return {'acc': float(equivalent), 'legacy_numeric_string': float(bool(number) and number == gold)}
    if task == 'pokemon':
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', prediction.strip())
        try:
            answer = json.loads(text)
            exact = (
                isinstance(answer, dict)
                and str(answer.get('name', '')).strip().casefold() == str(gold['name']).strip().casefold()
                and str(answer.get('hp', '')).strip() == str(gold['hp']).strip()
            )
        except (ValueError, TypeError):
            exact = False
        legacy = bool(
            str(gold['name']).strip()
            and str(gold['hp']).strip()
            and str(gold['name']).strip().lower() in prediction.lower()
            and str(gold['hp']).strip() in prediction
        )
        return {'acc': float(exact), 'legacy_substring': float(legacy)}
    if task == 'cifar10':

        def normalize(value: str) -> str:
            return re.sub(r'[^a-z]', '', value.lower())

        return {'acc': float(normalize(prediction) == normalize(gold))}
    if task == 'cppe5':
        found = {label for label in PPE if label.lower() in prediction.lower()}
        return {'acc': float(bool(prediction.strip()) and found == set(gold))}
    if task == 'humaneval':
        return {'acc': float(bool(prediction.strip()) and execute_code(code_program(prediction, metadata)))}
    raise ValueError(f'Unknown scoring task: {task}')
