"""Exercise conversion against built-in loaders without adding a benchmark adapter."""

import ast
import base64
import io
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/custom_datasets'))

from convert_all import write_dataset
from convert_text import convert_record
from run_native import build_config
from source_data import vision_sample
from task_metrics import code_program, execute_code, score_response

from evalscope import TaskConfig
from evalscope.api.registry import get_benchmark as registered_benchmark


def get_benchmark(name: str, settings: dict) -> object:
    return registered_benchmark(name, TaskConfig(model="fixture", datasets=[name], dataset_args={name: settings}))


@pytest.mark.parametrize('task', ['mmlu', 'geo_mmlu', 'law_mmlu', 'opseval'])
def test_mcq_native_loader(tmp_path: Path, task: str) -> None:
    row = {'question': '第一行\u2028第二行：2+2?', 'choices': ['1', '2', '3', '4'],
           'answer': ['B', 'D'] if task == 'opseval' else 3}
    pairs = [convert_record(task, row, i) for i in range(2)]
    entry = write_dataset(tmp_path, task, 'general_mcq', pairs, [])
    config = {'local_path': str(tmp_path / 'general_mcq'), 'subset_list': [task], 'shuffle': False,
              'few_shot_num': 0, 'extra_params': {'multiple_correct': task == 'opseval'}}
    samples = get_benchmark('general_mcq', config).load_dataset()[task]
    assert len(samples) == 2
    assert samples[0].target == (['B', 'D'] if task == 'opseval' else 'D')
    assert samples[0].choices == row['choices']
    assert [s.metadata['id'] for s in samples] == ['0', '1']
    assert entry['count'] == 2


def test_qa_native_loader_preserves_messages(tmp_path: Path) -> None:
    pair = convert_record('gsm8k', {'question': '2+2?', 'answer': 'Reasoning. #### 4'}, 0)
    write_dataset(tmp_path, 'gsm8k', 'general_qa', [pair], [])
    sample = get_benchmark('general_qa', {'local_path': str(tmp_path / 'general_qa'),
                          'subset_list': ['gsm8k'], 'shuffle': False}).load_dataset()['gsm8k'][0]
    assert sample.target == '4'
    assert [m.content for m in sample.input] == [m['content'] for m in pair[0]['messages']]


def test_vqa_native_loader_preserves_image(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    Image.new('RGB', (8, 8), (128, 0, 0)).save(buffer, format='PNG')
    original = vision_sample('cifar10', {'img': {'bytes': buffer.getvalue()}, 'label': 0},
                             {'label': {'names': ['cat']}}, 0, tmp_path)
    record = {'messages': original['messages'], 'answer': 'cat'}
    write_dataset(tmp_path, 'cifar10', 'general_vqa', [(record, {'index': 0})], [])
    sample = get_benchmark('general_vqa', {'local_path': str(tmp_path / 'general_vqa'),
                          'subset_list': ['cifar10']}).load_dataset()['cifar10'][0]
    assert sample.target == 'cat'
    assert base64.b64decode(sample.input[0].content[1].image.split(',', 1)[1]) == buffer.getvalue()


def test_invalid_mcq_and_overwrite_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        convert_record('opseval', {'question': 'q', 'choices': ['a', 'b'], 'answer': ['Z']}, 0)
    write_dataset(tmp_path, 'q', 'general_qa', [({'query': 'q', 'answer': 'a'}, {})], [])
    with pytest.raises(FileExistsError):
        write_dataset(tmp_path, 'q', 'general_qa', [], [])


def test_runner_uses_only_builtin_configuration(tmp_path: Path) -> None:
    config = build_config(tmp_path, 'opseval', {'benchmark': 'general_mcq', 'multiple_correct': True},
                          'fresh', 'http://localhost:9999/v1', 'test', 3)
    assert config.datasets == ['general_mcq']
    assert config.dataset_args['general_mcq']['extra_params']['multiple_correct'] is True
    assert config.use_cache is None
    assert config.limit == 3


def test_no_framework_extension_or_internal_imports() -> None:
    for path in (ROOT / 'scripts/custom_datasets').glob('*.py'):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or '').startswith('evalscope'):
                assert node.module == 'evalscope'
                assert {item.name for item in node.names} <= {'TaskConfig', 'run_task'}
            if isinstance(node, ast.Import):
                assert all(not item.name.startswith('evalscope.') for item in node.names)
        assert 'register_benchmark' not in path.read_text()
        assert 'monkeypatch' not in path.read_text()


@pytest.mark.parametrize('task,pred,gold,expected', [
    ('gsm8k', '#### 26.00', '26', 1), ('gsm8k', '', '0', 0),
    ('pokemon', '{"name":"Pikachu", "hp":60}', {'name': 'Pikachu', 'hp': '60'}, 1),
    ('pokemon', '{"name":"Pikachu", "hp":160}', {'name': 'Pikachu', 'hp': '60'}, 0),
    ('pokemon', 'Pikachu 60', {'name': 'Pikachu', 'hp': '60'}, 0),
    ('cifar10', 'Cat.', 'cat', 1), ('cifar10', 'cat or dog', 'cat', 0),
    ('cppe5', 'Mask, Gloves', ['Mask', 'Gloves'], 1), ('cppe5', '', [], 0),
])
def test_independent_task_metrics(task: str, pred: str, gold: object, expected: int) -> None:
    assert score_response(pred, json.dumps(gold), {'task': task})['acc'] == expected


@pytest.mark.skipif(sys.platform != 'darwin', reason='macOS sandbox required')
def test_code_report_isolation(tmp_path: Path) -> None:
    metadata = {'prompt': 'def add(a, b):\n', 'test': 'def check(fn):\n    assert fn(2, 3) == 5', 'entry_point': 'add'}
    assert execute_code(code_program('return a + b', metadata))
    assert not execute_code(code_program('return 0', metadata))
    assert not execute_code(f'open({str(tmp_path / "forbidden")!r}, "w").write("bad")')
    assert not execute_code(f'open({str(ROOT / "AGENTS.md")!r}).read()')
    assert not execute_code('import socket; socket.socket().connect(("127.0.0.1", 80))')


def test_cppe_reference_matches_native_metric_format() -> None:
    from convert_vision import format_answer
    target = format_answer('cppe5', ['Coverall', 'Mask'])
    adapter = get_benchmark('general_vqa', {'metric_list': ['Rouge']})
    score = adapter.match_score('Coverall, Mask', 'Coverall, Mask', target, None)
    assert score.value['Rouge-L-R'] == 1.0
    assert not score.metadata.get('metric_errors')
