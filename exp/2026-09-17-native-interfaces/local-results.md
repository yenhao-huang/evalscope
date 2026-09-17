# 原生介面重評結果 — 2026-09-17

本輪透過 EvalScope 既有 general_mcq／general_qa／general_vqa 完成全新推論。
未新增 adapter、未修改框架函式，亦未沿用前次實驗回答。

## 本機九項結果

| Dataset | 題數 | 原生 Accuracy | 原生 ROUGE-L Recall | 獨立任務正確率 | 平均請求秒數 |
| --- | ---: | ---: | ---: | ---: | ---: |
| mmlu | 100 | 94.00% | — | — | 15.032 |
| geo_mmlu | 100 | 90.00% | — | — | 1.336 |
| law_mmlu | 100 | 69.00% | — | — | 2.817 |
| opseval | 100 | 49.00% | — | — | 7.145 |
| gsm8k | 100 | — | 92.00% | 97/100 (97.00%) | 13.579 |
| humaneval | 100 | — | 52.65% | 94/100 (94.00%) | 5.996 |
| pokemon | 300 | — | 26.02% | 278/300 (92.67%) | 4.290 |
| cifar10 | 100 | — | 92.00% | 92/100 (92.00%) | 1.091 |
| cppe5 | 100 | — | 78.93% | 48/100 (48.00%) | 2.764 |


## 範圍與指標

- MCQ Accuracy 是 EvalScope 原生評分；其餘任務正確率是獨立輸出分析，不是原生 BLEU／ROUGE。
- 完整原生 BLEU 與 ROUGE 指標保存在原生報告及 task-analysis 的 native_metrics_mean。
- GSM8K 比對數值，HumanEval 在 macOS sandbox 執行測試，Pokemon 比對 name/hp，CIFAR 比對標籤，CPPE 比對 PPE 類別集合。
- 本機最終樣本 1,100 筆：Pokemon 300，其他八項原始順序前 100；MMLU 僅 abstract_algebra。
- CPPE-5 表列數值採用另一次 100 筆新推論：參考答案修正為提示詞要求的逗號列，詳見 [格式修正](../2026-09-17-native-cppe-format/README.md)。本機實際共生成 1,200 筆；首輪 CPPE JSON 陣列參考值與原生 ROUGE 0 的紀錄仍保留。
- 原生 MCQ 提示詞與舊 adapter 不同，不能把新舊分數視為純模型變化；2026-09-15 紀錄保持原樣。
- 本機所有樣本來源索引、目標與輸入已核對，影像 bytes 已核對雜湊；無執行／指標錯誤。
