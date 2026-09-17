# PokemonCards：本機 300 題完整結果

- Run：`local-pokemon-300`，已完成。
- 模型：`gemma4-26b-a4b`，本機 llama.cpp，GGUF UD-Q4_K_XL + BF16 mmproj。
- 主指標（JSON name/hp 欄位一致）：**278/300，92.67%**。
- 舊版字串命中：**278/300，92.67%**。
- API 成功 300、錯誤 0、無未完成題目。
- 平均端到端請求延遲：**4.071 秒**；這包含圖片處理與 API 往返，不能當作純 token decode 速度。

## 驗證

已逐筆確認 300 個 source_index 恰為 0–299，沒有重複或缺漏；每題圖片 SHA-256 與凍結 manifest 一致。核對逐題分數合計為 278，並確認所有 score.status 為 success。

- [完整彙總與設定](local-pokemon-300.json)
- [驗證紀錄](pokemon-validation.json)
- [資料 manifest](manifest.json)
- [模型來源與權重雜湊](model-provenance.json)
- 逐題 prediction/review 在忽略的 `runs/local-pokemon-300/`；未上傳圖片或逐題回答。

## 比較限制與後續

DGX Spark `100.109.182.22` 仍離線，尚無遠端成績；本結果不能證明遠端與本機相近。等遠端指定 YAML 的模型啟動後，使用相同 300 題、相同凍結圖片與 prompt/decoding/scorer，才執行配對比較。

其他八項各 100 題的 `local-suite-100` 已自動接續執行，尚未完成。
