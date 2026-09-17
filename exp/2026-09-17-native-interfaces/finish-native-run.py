"""Audit this experiment and render its report after both native runs finish."""

import json
import subprocess
import sys
import time
from pathlib import Path

EXP = Path(__file__).resolve().parent
ROOT = EXP.parent.parent
NAMES = ['local-native-1100', 'remote-native-pokemon-300']


def command(script: str, *arguments: str) -> None:
    """Run a repository script and fail if its audit fails."""
    subprocess.run(
        [sys.executable, str(ROOT / 'scripts/custom_datasets' / script), '--exp', str(EXP), *arguments],
        cwd=ROOT,
        check=True,
    )


def latency(item: dict) -> float:
    """Read recorded mean request latency, never total post-processing time."""
    return item['perf_metrics']['summary']['latency']['mean']


def main() -> None:
    """Wait for completion, audit saved files, and render separate native/task metrics."""
    deadline = time.monotonic() + 6 * 3600
    while time.monotonic() < deadline:
        states = [json.loads((EXP / f'{name}.json').read_text())['status'] for name in NAMES]
        if 'failed' in states:
            raise RuntimeError(f'Native inference failed: {dict(zip(NAMES, states))}')
        if states == ['completed', 'completed']:
            break
        time.sleep(15)
    else:
        raise TimeoutError('Inference did not complete within the observation window')
    for name in NAMES:
        command('analyze_results.py', '--run-name', name)
    command('compare_results.py', '--local', NAMES[0], '--remote', NAMES[1])
    local = json.loads((EXP / f'{NAMES[0]}-task-analysis.json').read_text())
    remote = json.loads((EXP / f'{NAMES[1]}-task-analysis.json').read_text())
    comparison = json.loads((EXP / f'comparison-{NAMES[0]}-{NAMES[1]}.json').read_text())
    lines = [
        '# 原生介面重評結果 — 2026-09-17',
        '',
        '本輪透過 EvalScope 既有 general_mcq／general_qa／general_vqa 完成全新推論。',
        '未新增 adapter、未修改框架函式，亦未沿用前次實驗回答。',
        '',
        '## 本機九項結果',
        '',
        '| Dataset | 題數 | 原生 Accuracy | 原生 ROUGE-L Recall | 獨立任務正確率 | 平均請求秒數 |',
        '| --- | ---: | ---: | ---: | ---: | ---: |',
    ]
    for task, item in local['subsets'].items():
        native = item['native_metrics_mean']
        accuracy = f'{100 * native["accuracy"]:.2f}%' if 'accuracy' in native else '—'
        rouge = f'{100 * native["Rouge-L-R"]:.2f}%' if 'Rouge-L-R' in native else '—'
        extra = (
            f'{item["correct"]}/{item["n"]} ({100 * item["task_accuracy"]:.2f}%)'
            if item['task_metric_origin'] == 'independent_postprocessing'
            else '—'
        )
        lines.append(f'| {task} | {item["n"]} | {accuracy} | {rouge} | {extra} | {latency(item):.3f} |')
    lo = local['subsets']['pokemon']
    re = remote['subsets']['pokemon']
    interval = comparison['paired_bootstrap_95_interval']
    conclusion = (
        '落在預設 ±5 個百分點門檻內，本輪樣本可視為相近。'
        if comparison['within_tolerance']
        else '未完全落在預設 ±5 個百分點門檻內，不能據此認定相近。'
    )
    lines += [
        '',
        '## PokemonCards 本機／DGX',
        '',
        f'- 本機：{lo["correct"]}/{lo["n"]}（{100 * lo["task_accuracy"]:.2f}%），平均 {latency(lo):.3f} 秒。',
        f'- DGX：{re["correct"]}/{re["n"]}（{100 * re["task_accuracy"]:.2f}%），平均 {latency(re):.3f} 秒。',
        f'- 獨立 JSON name/hp 欄位正確率差：{100 * comparison["remote_minus_local"]:+.2f} 個百分點。',
        f'- 配對 bootstrap 95% 區間：[{100 * interval[0]:.2f}, {100 * interval[1]:.2f}] 個百分點；{conclusion}',
        '',
        '## 指標與範圍',
        '',
        '- MCQ Accuracy 是 EvalScope 原生評分；其餘任務正確率是獨立輸出分析，不是原生 BLEU／ROUGE。',
        '- 完整原生 BLEU 與 ROUGE 指標保存在原生報告及 task-analysis 的 native_metrics_mean。',
        '- GSM8K 比對數值，HumanEval 在 macOS sandbox 執行測試，Pokemon 比對 name/hp，CIFAR 比對標籤，CPPE 比對 PPE 類別集合。',
        '- 本機 1,100 筆：Pokemon 300，其他八項原始順序前 100；MMLU 僅 abstract_algebra。',
        '- 原生 MCQ 提示詞與舊 adapter 不同，不能把新舊分數視為純模型變化；2026-09-15 紀錄保持原樣。',
        '- 本機 llama.cpp GGUF Q4、遠端 vLLM FP8；比較的是部署組合，不是硬體單一變因。',
        '- 兩端所有樣本來源索引、目標與輸入已核對，影像 bytes 已核對雜湊；無執行／指標錯誤。',
        '',
        '## 證據與重現',
        '',
        '[重現步驟](README.md) · [本機原生報告](local-native-1100.json) · [本機任務分析](local-native-1100-task-analysis.json) · [遠端原生報告](remote-native-pokemon-300.json) · [遠端任務分析](remote-native-pokemon-300-task-analysis.json)',
        '',
    ]
    (EXP / 'results.md').write_text('\n'.join(lines))
    print('Completed report:', EXP / 'results.md', flush=True)


if __name__ == '__main__':
    main()
