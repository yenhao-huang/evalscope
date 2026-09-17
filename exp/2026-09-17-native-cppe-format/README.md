# CPPE-5 原生參考答案格式修正

原生 `general_vqa` 的 `answer` 應符合題目要求的輸出形式。CPPE 提示詞要求逗號分隔類別，但首輪轉換誤用了 JSON 陣列字串，例如 `["Coverall", "Mask"]`。原生英文 ROUGE 依空白分詞，與正確回答 `Coverall, Mask` 的 token 不匹配，因此首輪 ROUGE 為 0；它不是 PPE 類別正確率。

已修正 `scripts/custom_datasets/convert_vision.py` 的格式轉換，參考答案改為 `Coverall, Mask`。模型輸入、圖片、樣本順序與獨立類別集合指標不變。已加入回歸測試，驗證相同正確回答可得到原生 ROUGE-L Recall = 1。

- 原資料 500 筆全部重新格式化，sidecar 雜湊與父實驗完全一致；參照 [manifest.json](manifest.json)。
- 本目錄使用新 run name `local-native-cppe-100` 對同一批前 100 筆做全新推論，沒有重用首輪回答。
- 最終總表只採本次 CPPE 結果；父實驗的 100 筆首輪 CPPE 紀錄仍保留。因此本機實際推論共 1,200 筆，最終評估樣本仍為九項共 1,100 筆。
- 全程未改 EvalScope 內部函式。

## 重現

使用最新版 converter 建立新實驗，即會直接輸出正確格式：

```bash
.venv/bin/python scripts/custom_datasets/convert_all.py --exp exp/new-native-export
.venv/bin/python scripts/custom_datasets/run_native.py --exp exp/new-native-export \
  --run-name cppe-native --subsets cppe5 --limit 100
.venv/bin/python scripts/custom_datasets/analyze_results.py --exp exp/new-native-export \
  --run-name cppe-native
```

## 完成結果

100/100 成功，0 執行或指標錯誤。原生 ROUGE-L Recall 78.93%；獨立 PPE 類別集合正確率 48/100。參考答案修正前後的 100 筆 API response IDs 不重疊，確認為全新推論；sidecar 來源身分與圖片雜湊保持相同。詳見 [原生報告](local-native-cppe-100.json) 與 [逐筆稽核／任務分析](local-native-cppe-100-task-analysis.json)。
