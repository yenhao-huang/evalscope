# 本機評估結果 — 2026-09-15

九項本機評估已完成：PokemonCards 全部 300 張，其餘各取原始順序前 100 題，共 1,100 筆。這是本輪指定樣本範圍，並非其餘資料集的全量評估。全部採 v1.1 評分；API 錯誤 0。

| Benchmark | 正確 / 題數 | Accuracy | 平均請求延遲（秒） |
| --- | ---: | ---: | ---: |
| MMLU（抽象代數） | 89 / 100 | 89.00% | 12.307 |
| GSM8K | 97 / 100 | 97.00% | 13.435 |
| HumanEval | 94 / 100 | 94.00% | 5.846 |
| Geo-MMLU | 91 / 100 | 91.00% | 0.598 |
| Law-MMLU | 69 / 100 | 69.00% | 4.866 |
| OpsEval | 56 / 100 | 56.00% | 0.711 |
| PokemonCards | 278 / 300 | 92.67% | 4.071 |
| CIFAR-10 | 92 / 100 | 92.00% | 1.088 |
| CPPE-5 | 48 / 100 | 48.00% | 2.625 |

## 驗證與證據

- [完整性驗證](local-final-validation.json)：九份資料 SHA-256、1,100 個唯一索引、target/metadata、評分狀態、原始生成錯誤數、評分程式雜湊與快取回答雜湊均核對通過。
- [八項 v1.1 原生報告](local-suite-100-v1_1.json) 與 [PokemonCards v1.1 報告](local-pokemon-300-v1_1.json) 保存完整彙總。
- 原始 v1.0 生成報告保留於 local-suite-100.json 與 local-pokemon-300.json；v1.1 在新目錄重新評分，沒有重新生成回答。
- GSM8K 舊字串分數 92%，數值等價修正後 97%；五筆差異均為 26.00 與 26 這類等值格式，見 [差異紀錄](gsm8k-results.json)。
- 延遲來自原始生成請求，包含前處理、影像與網路時間，不是重新評分時間或純解碼速度。

## 解讀限制

MMLU 的前 100 題全部是 abstract_algebra，不能當作完整 57 科 MMLU 分數。本輪前 100 題也不是 model-tester 舊版 seed 42 隨機抽樣 100 題，不能直接與歷史百分比比較。

CPPE-5 評估 PPE 類別集合完全一致，並非 bounding-box mAP。HumanEval 以隔離程式測試判分，未做舊 runner 的第二次縮排修復。

ARCH、Docker、Linux 尚缺本地資料與評分定義，未納入九項。DGX Spark 遠端已完成 280/300（93.33%），與本機 278/300 相近，見 [Phase 2 完整比較](phase2-results.md)。
