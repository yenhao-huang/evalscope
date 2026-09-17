# Gemma / EvalScope 評估 — 2026-09-15

> Historical adapter-based experiment. Its runnable code is preserved at Git commit `60c1e98f`; the scripts below describe that version. Current native-interface conversions and reruns are documented in [2026-09-17](../2026-09-17-native-interfaces/README.md).

## 狀態

- Repo: https://github.com/yenhao-huang/evalscope
- [Phase 1 issue](https://github.com/yenhao-huang/evalscope/issues/1)：九個本地 benchmark 轉換與本機 Gemma 評估。
- Phase 2 deployment and comparison artifacts are delivered in the dependent PR (issue #2).
- 參照：https://github.com/yenhao-huang/model-tester
- 已完成每個 benchmark 3 題的 smoke test，僅證明流程能完成，不代表模型完整能力。
- PokemonCards 全部 300 題已完成：278/300（92.67%），API 錯誤 0。見 [完整結果](pokemon-results.md)。
- 九項本機批次已全部完成：PokemonCards 300 張，其餘八項各取原始順序前 100 題，共 1,100 筆、API 錯誤 0。見 [完整成績與範圍](local-results.md) 與 [完整性驗證](local-final-validation.json)。

## 資料與評分

[manifest.json](manifest.json) 記錄九個轉換檔的 SHA-256、筆數、原始 sample IDs 與圖片雜湊。完整輸出保存在忽略的 `data/`，共約 1.4 GB。來源不會被修改。

Text 來源是 `~/Desktop/datasets/full-textgen-evalset`，五項合計 17,257 題。OpsEval 共 2,250 題；PokemonCards 300、CIFAR-10 1,000、CPPE-5 500。轉換不隨機洗牌。

**歷史比較限制**：舊 model-tester 的文字 100 題小樣本現位於 `~/Desktop/datasets/deorecated/fast-textgen-evalset`，採 seed 42 抽樣。本輪 full-textgen 的前 100 題不是同一組，不能直接拿舊報告百分比判斷模型進退。

- MMLU / Geo / Law：沿用選項字母抽取與比對；GSM8K：v1.1 以 Decimal 比對最後數字的數值等價（26.00 = 26），並保留 legacy_numeric_string 字串分數。
- OpsEval：選項集合精確比對，少選、多選均錯。
- Pokemon：主指標要求 JSON name/hp 欄位一致，另記錄 `legacy_substring`，對應舊版寬鬆字串命中。
- CIFAR-10：正規化後標籤完全一致；CPPE-5：PPE 類別集合一致，不是框位置或 mAP。
- HumanEval：全函式或 body completion 轉為測試程式，在 macOS sandbox-exec 中執行，禁止網路與檔案寫入、阻擋家目錄資料讀取，限制 CPU、子程序數與牆鐘時間；不在主評估程序直接 exec。不同於舊 runner，本版不進行第二次縮排修復。
- ARCH、Docker、Linux 共三項尚無可用本地資料或 task success 定義，未以其他資料集代替。

## Smoke test 結果

每項 3 題，temperature=0、seed=42、max_tokens=4096、reasoning=off；原始報告與逐題檔在 `runs/local-smoke/`。彙總見 [local-smoke.json](local-smoke.json)。

| Benchmark | 題數 | Accuracy |
| --- | ---: | ---: |
| mmlu | 3 | 100.00% |
| gsm8k | 3 | 100.00% |
| humaneval | 3 | 66.67% |
| geo_mmlu | 3 | 100.00% |
| law_mmlu | 3 | 33.33% |
| opseval | 3 | 33.33% |
| pokemon | 3 | 66.67% |
| cifar10 | 3 | 100.00% |
| cppe5 | 3 | 66.67% |

本輪 OCR 的 legacy_substring 同為 2/3。API 失敗或缺少結果不會被包裝成成功完成；完成的各子集 execution_summary 均為零錯誤。

## 重現

從 repo 根目錄執行：

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e '.[dev,perf,docs]'
.venv/bin/python scripts/convert_model_tester.py
.venv/bin/pytest tests/benchmarks/local_model_tester -q
.venv/bin/python scripts/run_model_tester.py --run-name new-smoke --limit 3
.venv/bin/python scripts/model_tester_queue.py
```

模型啟動命令完整記在 [local-server.json](local-server.json)，權重與執行檔證據見 [model-provenance.json](model-provenance.json)。先確認 `/health`，再確認 `/v1/models` 內的模型別名。依賴快照：[environment-freeze.txt](environment-freeze.txt)。環境固定於 repo 根目錄 `.venv/`。

`run_model_tester.py` 可用 `--api-url`、`--model`、`--subsets`、`--limit`。API key 從 `EVAL_API_KEY` 讀取。重新開始必須使用新的 run-name；`--resume` 僅能使用相同資料、配置與程式版本，避免混用快取分數。程式會驗證來源 hash 與模型 ID，逐個子集寫入成績，保存失敗狀態。實際執行參數見 `<run-name>.json`；queue 狀態見 `queue-status.json`。

## 維護與驗證

- 根目錄 [AGENTS.md](../../AGENTS.md) 與 [docs/rules](../../docs/rules/git.md) 定義目錄、環境與 git 工作流程。
- GitHub Actions `Local benchmark contract` 執行離線轉換/評分/隔離測試；Dependabot 準備每週檢查 Python 依賴、每月檢查 Actions。這些設定須推送後才會在 GitHub 生效。
- 本地自訂測試 26 passed；上游 `test_ci_lite` 1 passed；`make lint` passed。評分修正後的 make lint 亦已通過。
- 上游 `make docs-pipeline BENCHMARK=local_model_tester FORCE=1` 已執行；中文翻譯因沒有 DASHSCOPE_API_KEY 失敗，local-only dataset 統計亦無遠端來源。`make docs-generate` 成功；實際資料統計以 manifest 為準。
- Smoke 期間修正 JSONL 特殊換行與影像訊息轉換問題後完成；中間失敗 logs 保存在忽略的 `logs/`，不是模型成績。

## 評分修正與快取重新評分

GSM8K v1.0 字串比對誤判 5 筆等值小數，v1.1 修正為數值等價：97/100，保留的 legacy_numeric_string 為 92/100。逐筆差異與雜湊見 [gsm8k-results.json](gsm8k-results.json)。原始生成紀錄保持原樣；新版另存至 local-gsm8k-100-v1_1-verified，PokemonCards 也另存 local-pokemon-300-v1_1（仍為 278/300）。

```bash
.venv/bin/python scripts/run_model_tester.py --rescore-from local-suite-100 --run-name new-gsm8k-rescore --subsets gsm8k --limit 100
```

重新評分會複製已完成子集的快取至新目錄，禁止推論，並要求回答檔雜湊完全不變。保留原始生成延遲與錯誤數，不能將重新評分耗時當作模型速度。資料 manifest 中 v1.0 是轉換當時版本；每次評估實際評分版本以 run identity.scoring_version 與 source_sha256 為準。原始八項批次使用 v1.0，已完成並保留；另以 local-suite-100-v1_1 保存一致版本的重評結果。所有回答快取均與原始檔案完全相同。
