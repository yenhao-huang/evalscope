# 原生介面重評 — 2026-09-17

## 設計與範圍

本輪依使用者要求移除自訂 `local_model_tester` adapter。EvalScope 的 `evalscope/` 目錄與上游基準 `09b1be41` 相同；僅使用既有 `TaskConfig`、`run_task` 與 general_mcq／general_qa／general_vqa 介面。

- 原始九個資料集全部轉換：21,307 筆；來源與輸出 SHA-256 見 [manifest](manifest.json)。
- 正式本機重評：PokemonCards 300 張，其餘八项原始順序前 100 題，共 1,100 筆。不是其餘八項全量測試。
- 正式 DGX 重評：同一批 PokemonCards 300 張、同一份圖片與提示詞。
- 全新推論與 run name，不使用 2026-09-15 的回答快取。
- 四個選擇題來源使用原生提示詞／答案抽取；原生 MCQ accuracy 與舊 adapter 的成績不可直接混用。
- 文字／影像問答保留原始 messages，EvalScope 原生 BLEU／ROUGE 與獨立任務正確率分開記錄。HumanEval 的測試只在獨立分析的 macOS sandbox 執行。
- MMLU 前 100 筆仍僅為 abstract_algebra；CPPE-5 為類別集合，並非 bbox mAP。

## 重現

詳見 [轉換、執行與分析說明](../../scripts/custom_datasets/README.md)。從 repo 根目錄執行：

```bash
.venv/bin/python -c "import nltk; nltk.download('punkt_tab', download_dir='.venv/nltk_data', raise_on_error=True)"
.venv/bin/python scripts/custom_datasets/convert_all.py \
  --exp exp/your-new-experiment --image-cache exp/2026-09-15/data/images
.venv/bin/python scripts/custom_datasets/run_native.py \
  --exp exp/your-new-experiment --run-name local-native-1100
.venv/bin/python scripts/custom_datasets/analyze_results.py \
  --exp exp/your-new-experiment --run-name local-native-1100
```

遠端使用同一 runner，增加 `--subsets pokemon --api-url http://100.109.182.22:3335/v1 --model /workspace/llm_model` 並使用不同 run name。

## 驗證

原生資料載入、來源順序、選項／目標、圖片 bytes、不覆寫凍結資料、公開介面依賴與独立指標／隔離執行皆有離線測試。正式執行前，本機九項各一筆與遠端 Pokemon 一筆通過推論及完整稽核。

第一輪 smoke 發現原生 BLEU 缺少 `punkt_tab`，失敗記錄 `native-smoke.json` 保留；在根 `.venv/nltk_data` 補齊後另用 `native-smoke-validated` 完整重跑成功，不將錯誤分數算成成功。

舊實驗完整保留於 `exp/2026-09-15/`，其可執行程式版本為 Git commit `60c1e98f` (published identical tree: `667e878b`)。本輪不更動舊數值與原始回答。

## DGX 新推論已完成

原生 general_vqa 新推論 300/300 成功、0 錯誤；逐筆圖片、提示詞與目標稽核通過。獨立 JSON name/hp 正確率 280/300（93.33%）；原生 ROUGE-L Recall 26.35%、BLEU-4 35.27%。不同指標分開記錄，不能互換。完整本機九項與配對比較已完成，見 [最終結果](results.md)、[本機結果](local-results.md) 與 [完整性驗證](final-validation.json)。

## 最終採用結果

本機最終樣本共 1,100 筆，全部完成原生評估與逐筆稽核；DGX 300 筆也完成。CPPE 的參考答案格式修正後另做 100 筆全新推論，因此本機實際生成共 1,200 筆。最終表格的 CPPE 欄位採用 [格式修正實驗](../2026-09-17-native-cppe-format/README.md)，原本 JSON 陣列參考答案下的原生 ROUGE 0 保留為歷史紀錄。

22 項自訂資料／輸出分析測試與 1 項上游 CI smoke 共 23 項通過；`make lint` 與框架零差異檢查通過。
