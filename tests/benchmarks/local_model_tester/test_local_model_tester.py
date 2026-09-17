import importlib.util
import json
import sys
from pathlib import Path

import pytest

from evalscope.api.evaluator import TaskState
from evalscope.api.registry import get_benchmark
from evalscope.benchmarks.local_model_tester.local_model_tester_adapter import LocalModelTesterAdapter
from evalscope.benchmarks.local_model_tester.scoring import code_program, execute_code, score_response

spec = importlib.util.spec_from_file_location('converter', Path(__file__).parents[3] / 'scripts/convert_model_tester.py')
converter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(converter)


@pytest.mark.parametrize('task,pred,gold,expected', [
    ('mmlu', 'Answer: B', 'B', 1), ('mmlu', '', 'A', 0),
    ('geo_mmlu', 'A\nFinal answer: D', 'D', 1), ('law_mmlu', 'C', 'B', 0),
    ('gsm8k', 'calculation 10 then #### 1,200', '1200', 1),
    ('gsm8k', '', '0', 0), ('cifar10', 'Cat.', 'cat', 1),
    ('cifar10', 'cat or dog', 'cat', 0),
    ('cppe5', 'Mask, Gloves', ['Mask', 'Gloves'], 1),
    ('cppe5', 'Mask, Gloves', ['Mask'], 0), ('cppe5', '', [], 0),
    ('pokemon', '{"name":"Pikachu", "hp":60}', {'name':'Pikachu','hp':'60'}, 1),
    ('pokemon', '{"name":"Pikachu", "hp":160}', {'name':'Pikachu','hp':'60'}, 0),
    ('pokemon', 'Pikachu 60', {'name':'Pikachu','hp':'60'}, 0),
])
def test_scoring(task: str, pred: str, gold: object, expected: int) -> None:
    assert score_response(pred, json.dumps(gold), {'task': task})['acc'] == expected


def test_opseval_multi_answer() -> None:
    metadata = {'task': 'opseval', 'choice_count': 4}
    assert score_response('A,C', '["C", "A"]', metadata)['acc'] == 1
    assert score_response('A', '["A", "C"]', metadata)['acc'] == 0
    assert score_response('A,C,D', '["A", "C"]', metadata)['acc'] == 0


def test_adapter_preserves_prompt() -> None:
    row = {'question': '2+2?', 'choices': ['1','2','3','4'], 'answer': 3}
    sample = get_benchmark('local_model_tester').record_to_sample(converter.text_sample('mmlu', row, 7))
    assert sample.id == 7
    assert sample.metadata['source_index'] == 7
    assert 'D. 4' in sample.input[-1].content
    result = get_benchmark('local_model_tester').match_score('D', 'D', sample.target, TaskState('mock', sample))
    assert result.value['acc'] == 1


@pytest.mark.skipif(sys.platform != 'darwin', reason='macOS isolated HumanEval runner')
def test_humaneval_isolation(tmp_path: Path) -> None:
    metadata = {'prompt': 'def add(a, b):\n', 'test': 'def check(fn):\n    assert fn(2, 3) == 5', 'entry_point': 'add'}
    assert execute_code(code_program('return a + b', metadata))
    assert execute_code(code_program('def add(a, b):\n    return a + b', metadata))
    assert not execute_code(code_program('return 0', metadata))
    assert not execute_code('while True: pass')
    path = tmp_path / 'forbidden'
    assert not execute_code(f'open({str(path)!r}, "w").write("bad")')
    assert not path.exists()
    assert not execute_code('import socket; socket.socket().bind(("127.0.0.1",0))')


def test_loader_limit_and_ids(tmp_path: Path) -> None:
    from evalscope import TaskConfig
    rows = [converter.text_sample('mmlu', {'question': str(i), 'choices': ['a','b','c','d'], 'answer': i % 4}, i)
            for i in range(5)]
    (tmp_path / 'mmlu.jsonl').write_text('\n'.join(json.dumps(row) for row in rows) + '\n')
    config = TaskConfig(model='mock', eval_type='mock_llm', datasets=['local_model_tester'], limit=2,
                        dataset_args={'local_model_tester': {'local_path': str(tmp_path), 'subset_list': ['mmlu']}})
    adapter = get_benchmark('local_model_tester', config)
    loaded = adapter.load_dataset()['mmlu']
    assert len(loaded) == 2
    assert [sample.metadata['source_index'] for sample in loaded] == [0, 1]


def test_vision_conversion(tmp_path: Path) -> None:
    import io

    from PIL import Image
    image = Image.new('RGB', (8, 8), (128, 0, 0))
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    sample = converter.vision_sample('cifar10', {'img': {'bytes': buffer.getvalue()}, 'label': 0},
                                     {'label': {'names': ['cat']}}, 0, tmp_path)
    assert json.loads(sample['target']) == 'cat'
    assert sample['messages'][0]['content'][1]['image_url']['url'].startswith('data:image/png;base64,')
    assert len(sample['metadata']['image_sha256']) == 64
    converted = get_benchmark('local_model_tester').record_to_sample(sample)
    assert converted.input[0].content[1].type == 'image'
    assert converted.input[0].content[1].image.startswith('data:image/png;base64,')


@pytest.mark.skipif(sys.platform != 'darwin', reason='macOS sandbox')
def test_home_read_denied() -> None:
    path = Path(__file__).resolve()
    assert not execute_code(f'open({str(path)!r}).read()')


def test_comparison_requires_paired_samples() -> None:
    spec = importlib.util.spec_from_file_location('comparison', Path(__file__).parents[3] / 'scripts/compare_model_tester.py')
    comparison = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(comparison)
    with pytest.raises(ValueError):
        comparison.paired_summary({0:1}, {1:1})
    result = comparison.paired_summary({0:1, 1:0}, {0:1, 1:0})
    assert result['remote_minus_local'] == 0
    assert result['correctness_agreement'] == 1
    assert result['within_tolerance']


def test_comparison_manifest_and_scorer_identity() -> None:
    import copy
    import hashlib
    spec = importlib.util.spec_from_file_location('comparison', Path(__file__).parents[3] / 'scripts/compare_model_tester.py')
    comparison = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(comparison)
    manifest = b'{"subsets":{"pokemon":{"count":300}}}'
    record = {'status': 'completed', 'identity': {
        'subsets': ['pokemon'], 'manifest_sha256': hashlib.sha256(manifest).hexdigest(),
        'limit': 300, 'temperature': 0, 'seed': 42, 'max_tokens': 4096, 'reasoning': 'off', 'scoring_version': 'v1.0'},
        'source_sha256': {'evalscope/benchmarks/local_model_tester/scoring.py': 'scorer-hash',
                          'evalscope/benchmarks/local_model_tester/local_model_tester_adapter.py': 'adapter-hash'}}
    assert comparison.validate_pair(record, record, manifest, 'pokemon') == set(range(300))
    with pytest.raises(ValueError, match='manifest'):
        comparison.validate_pair(record, record, manifest + b' ', 'pokemon')
    other = copy.deepcopy(record)
    other['source_sha256']['evalscope/benchmarks/local_model_tester/scoring.py'] = 'different'
    with pytest.raises(ValueError, match='Scoring implementation differs'):
        comparison.validate_pair(record, other, manifest, 'pokemon')
    del other['source_sha256']['evalscope/benchmarks/local_model_tester/scoring.py']
    with pytest.raises(ValueError, match='Missing or ambiguous'):
        comparison.validate_pair(record, other, manifest, 'pokemon')


def test_comparison_performance_missing_values() -> None:
    spec = importlib.util.spec_from_file_location('comparison', Path(__file__).parents[3] / 'scripts/compare_model_tester.py')
    comparison = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(comparison)
    record = {'completed_subsets': [{'subset': 'pokemon', 'reports': [{}]}]}
    missing = comparison.performance_summary(record, 'pokemon')
    assert missing['latency_seconds']['mean'] is None
    assert missing['measurement_coverage'] is None
    record['completed_subsets'][0]['reports'][0] = {
        'perf_metrics': {'summary': {'latency': {'mean':4.0, '50%':3.5, '90%':float('nan')}},
                         'coverage': {'requests_with_metrics':300, 'total_requests':300}},
        'execution_summary': {'errored':0}}
    measured = comparison.performance_summary(record, 'pokemon')
    assert measured['latency_seconds']['mean'] == 4.0
    assert measured['latency_seconds']['median'] == 3.5
    assert measured['latency_seconds']['p90'] is None
    assert measured['execution']['errored'] == 0



def test_numeric_equivalence_retains_legacy_score() -> None:
    assert score_response('26.00', '"26"', {'task': 'gsm8k'}) == {'acc': 1.0, 'legacy_numeric_string': 0.0}
    assert score_response('26.01', '"26"', {'task': 'gsm8k'})['acc'] == 0.0


def test_review_only_refuses_uncached_inference() -> None:
    from evalscope import TaskConfig
    config = TaskConfig(model='mock', eval_type='mock_llm', datasets=['local_model_tester'],
                        dataset_args={'local_model_tester': {'extra_params': {'review_only': True}}})
    adapter = get_benchmark('local_model_tester', config)
    with pytest.raises(RuntimeError, match='inference is disabled'):
        adapter.run_inference(None, None, '/tmp/unused')


def test_rescore_preserves_generation_performance() -> None:
    spec = importlib.util.spec_from_file_location('comparison', Path(__file__).parents[3] / 'scripts/compare_model_tester.py')
    comparison = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(comparison)
    record = {'completed_subsets': [{
        'subset': 'pokemon', 'reports': [{'perf_metrics': {}}],
        'generation_perf_metrics': {'summary': {'latency': {'mean': 4.0}}},
        'generation_execution_summary': {'errored': 0},
    }]}
    result = comparison.performance_summary(record, 'pokemon')
    assert result['latency_seconds']['mean'] == 4.0
    assert result['execution']['errored'] == 0
