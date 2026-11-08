# 設計根拠と採用範囲

確認日: 2026-11-08。以下の手法を組み合わせた独自の検証手順であり、参考研究と同じ性能が得られるという主張ではない。

| 出典 | 採用する考え方 | 採用しない解釈 |
| --- | --- | --- |
| [UXAgent: A System for Simulating Usability Testing of Web Design with LLM Agents](https://arxiv.org/abs/2504.09407)（2025） | ペルソナ生成・実際の操作・結果の分析を分離し、行動ログを残す。人を対象にした調査の前段で検証設計を改善する | 大量のAIを動かせば人間と同等の調査になる |
| [NN/g: Cognitive Walkthroughs](https://www.nngroup.com/articles/cognitive-walkthroughs/)（2022） | タスクの各段階で、目標・操作の発見・表示と結果の対応・進捗の理解を確認する | 専門家の予測を実ユーザーの観察と呼ぶ |
| [NN/g: 10 Usability Heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/)（1994、2024更新） | 状態の可視化、利用者の言葉、制御、誤りの予防・復帰などを原因整理に使う | チェックを通ればサービスの価値や需要まで証明できる |
| [W3C WAI: Easy Checks](https://www.w3.org/WAI/test-evaluate/preliminary/) | キーボード・フォーカス・表示拡大・フォーム等を、条件を明示して確認する | 初期確認だけでアクセシビリティ全体の適合を保証する |
| [NN/g: Synthetic Users — If, When, and How to Use AI-Generated Research](https://www.nngroup.com/articles/synthetic-users/)（2024） | 合成ユーザーの出力を仮説の材料として使い、実ユーザーの調査につなぐ | AIが述べた欲求や経験を人間の回答として扱う |

このスキルの6つの種、7つの評価軸、1〜5の採点基準、停止上限は運用上の設計判断。心理尺度や統計的に検証された標本設計ではない。UXAgentの論文にあるペルソナ数や研究者による評価も、本スキルの有効性の実証には流用しない。

実調査を使える場合は、最初に少数の実タスク観察と照合し、外れた予測を含めて残す。サービスの需要、継続意向、購入意思、母集団の割合など、人間に関する意思決定はこの検証の出力だけで結論付けない。
