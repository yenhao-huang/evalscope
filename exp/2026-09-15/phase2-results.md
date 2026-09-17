# Phase 2：DGX Spark 與本機 PokemonCards 比較

## 結論

本輪 300 張可視為「差不多」：DGX 多對 2 張，正確率高 0.67 個百分點。配對 bootstrap 95% 區間為 [0.00, 1.67] 個百分點，完全位於事先設定的 ±5 個百分點範圍內。這不表示所有資料集或模型能力等價。

| 指標 | 本機 llama.cpp / GGUF Q4_K_XL | DGX Spark vLLM / FP8 |
| --- | ---: | ---: |
| 正確 / 題數 | 278 / 300 | 280 / 300 |
| name / hp 精確比對 | 92.67% | 93.33% |
| 評估錯誤 | 0 | 0 |
| 平均請求延遲 | 4.071 秒 | 2.213 秒 |
| 中位數延遲 | 4.138 秒 | 1.942 秒 |
| P90 延遲 | 4.469 秒 | 2.996 秒 |

- 正確／錯誤判定一致率：99.33%（298/300）。本機獨對 0 張，遠端獨對 2 張。
- 遠端平均請求延遲少 45.6%；兩邊效能紀錄均涵蓋 300/300 筆。延遲包含影像處理、網路與生成，排除伺服器啟動；不能把差異全部歸因於硬體。
- 遠端 legacy_substring 亦為 280/300，沒有因此改變本輪主分數。

## 控制條件與驗證

使用同一份凍結的 PokemonCards_train_300、相同順序、提示文字、temperature=0、request seed=42、max_tokens=4096、reasoning=off，以及 v1.1 評分程式。已核對全部 300 個唯一索引、上傳圖片內容雜湊、輸入角色與文字、標準答案和 metadata；沒有缺題或評估錯誤。配對比較使用 seed=42、10,000 次 bootstrap。

[完整比較 JSON](comparison-local-pokemon-300-v1_1-remote-pokemon-300.json) · [逐題完整性驗證](remote-pokemon-validation.json) · [遠端原生彙總](remote-pokemon-300.json)

## 遠端部署

- SSH：wingene@100.109.182.22；API：http://100.109.182.22:3335/v1；model ID：/workspace/llm_model。模型保持運行。
- 指定的 /workspace/deprecated/gemma-4-26B-A4B-it.yaml 作為基礎，vLLM image 的 ARM64 digest 與官方 Transformers revision 均已固定。
- NVIDIA Container Toolkit 1.20.0、driver 580.142、CUDA 13.0、PyTorch 2.10.0、vLLM 0.19.1.dev6+g6d4a8e6d2。
- 原 0.4 記憶體設定要求 48.68 GiB，當時只有 32.95 GiB 可用；[獨立 override](remote-resource-override.yaml) 僅改為 0.25。實際模型載入使用 25.67 GiB，約 425 秒。
- 原 YAML 重複列出 quantization，實際採最後的 fp8；BF16 safetensors 在載入時量化為 FP8，compute dtype 為 BF16、KV cache 為 FP8。

本機是既有 GGUF 量化與 llama.cpp，遠端是固定 revision 的官方 Transformers 權重與 vLLM。這是部署組合的配對評估，並未隔離 backend、量化、模板／影像前處理及版本差異。未使用遠端既有且雜湊不同的 GGUF。

[遠端模型版本與命令](remote-model-provenance.json) · [官方檔案 manifest](remote-hf-manifest.json) · [下載驗證](remote-download-validation.json) · [原始 YAML](remote-original-gemma.yaml) · [執行流程](phase2-worker.py)
