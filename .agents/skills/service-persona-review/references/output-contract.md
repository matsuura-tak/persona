# 出力仕様 v1.0

標準成果物は `report.md` と `review.json`。証拠の画面等は `evidence/` に保存し、個人情報を取り除く。保存先は依頼または実行環境の規約に合わせる。下記のIDは実行内で一意にする。

## JSON

[example-review.json](../assets/example-review.json) が読み込み可能な最小例。例をコピーしただけの証拠・日時・結果を実レビューに残さない。例は資料レビューのため動的な評価はすべて未確認。

トップレベルの必須項目:

| キー | 型と内容 |
| --- | --- |
| `schema_version` | `"1.0"` |
| `run` | 下記の実行情報 |
| `personas` | 1件以上のペルソナカード |
| `tasks` | 1件以上のタスク |
| `evidence` | 証拠の配列。何も確認できなければ空 |
| `sessions` | 1件以上。割り当てた全組合せを含める。未着手も残す |
| `findings` | 指摘の配列。根拠がなければ空でよい |
| `human_checks` | 実ユーザーで確認する問い。仮説の指摘は必ず1件以上に紐付ける |

### run

`id`, `target`, `target_version`, `recorded_at`, `mode`, `nature`, `environment`, `permissions`, `limits`, `limitations`。

- `mode`: `interactive` / `artifact` / `mixed`。全セッションの実際の方式と一致させる。
- `nature`: `review` / `example`。架空データのデモは必ず `example`。
- `recorded_at`: タイムゾーン付きISO 8601。例 `2026-11-08T15:00:00+09:00`。
- `target_version`: 不明なら `unknown`。環境・対象版を捏造しない。
- `environment`: 使用ツール・モデル（分かる場合）・端末・画面幅・入力方法・認証状態。
- `permissions`: 許可された操作と停止する操作。
- `limits`: 実行前に固定した操作・再試行上限、選定範囲。
- `limitations`: 制約を表す文字列の配列。実ユーザー不在、単一コンテキスト、未確認範囲など。

### personas と tasks

ペルソナの必須項目は [persona-design.md](persona-design.md) のカードと同じ。`source_refs` は文字列の配列、それ以外は文字列。

タスクは `id`, `goal`, `start_state`, `success_criteria`, `allowed_actions`（すべて文字列）を持つ。達成条件は操作前に定義する。

### evidence

各証拠は `id`, `kind`, `ref`, `locator`, `captured_at`, `observation`（文字列）。

- `kind`: `ui`（実操作で確認した表示）、`artifact`（画面・仕様等の資料）、`tool`（認証エラー等、検証環境の記録）。
- `ref`: 画面ファイル、出典資料、保存したツールログへの参照。URLだけでなく再確認できる形にする。
- `locator`: ページ、画面名、該当箇所。`captured_at` は確認日時で、資料の制作日時ではない。
- `observation`: 直接確認した事実だけ。心理・行動の推測は指摘の `interpretation` に置く。

### sessions

`id`, `persona_id`, `task_id`, `mode`, `outcome`, `outcome_reason`, `result_evidence_ids`, `state_reset`, `steps`, `scores`, `review`。

- `mode`: `interactive` / `artifact`。資料確認の結果は必ず `not_run`。
- `outcome`: [session-protocol.md](session-protocol.md) の6種類。
- `outcome_reason`: 達成条件との照合、停止・未実行の理由。`state_reset`: 開始状態の復元方法と状態共有の有無。
- `review`: 目的に照らした短い評価。推定した反応には「AIによる仮説」と明示。
- `result_evidence_ids`: 最終状態の証拠ID配列。操作の結果を判定する4状態では、実行済みステップの結果に含まれるUI証拠が必要。
- `steps`: 下記のステップ配列。試せなかったら空でよい。
- `scores`: 7つの評価軸IDをすべてキーとして持つオブジェクト。

ステップは `observation_evidence_ids`, `action`, `action_status`, `expected`, `actual`, `result_evidence_ids`。ID配列以外は文字列。`action_status` は `executed` / `proposed`。資料では `proposed` のみで、実行結果の証拠は空にする。`expected` は仮説、`actual` は観察または未実行の明記。

各スコアは `score`（整数1〜5またはnull）, `reason`（文字列）, `evidence_ids`（配列）。数値にはUIまたは資料の証拠が必要。`efficiency`・`recovery`・`inclusion` の数値には実操作のUI証拠が必要。スコアの証拠はそのセッションのステップまたは最終状態で参照した証拠に限る。

### findings

`id`, `kind`, `title`, `session_ids`, `evidence_ids`, `fact`, `interpretation`, `impact`, `severity`, `confidence`, `priority`, `recommendation`, `acceptance_check`, `alternative_explanation`。

ID配列以外は文字列。分類・重大度・確かさ・優先度は [evaluation.md](evaluation.md) に従う。`fact` と `interpretation` を分ける。仮説の重大度は想定影響の大きさとして読む。観察した指摘にはUI/資料の証拠を必須とし、ツールの制約のみでは欠陥扱いしない。

`session_ids` は1件以上。証拠は参照先セッション内のものに限る。`alternative_explanation` に反証・別の原因・確認できていない範囲を書く。長所では `recommendation` に維持したい設計、`acceptance_check` に回帰確認を記載する。

### human_checks

`id`, `finding_ids`, `prompt`, `supports`, `refutes`。`finding_ids` は1件以上の指摘ID配列。他は文字列。`prompt` は人へ渡す中立的な課題、`supports` / `refutes` は仮説が支持／反証される観察条件。

## 整合性検査と限界

```bash
python3 <skill>/scripts/validate_review.py <output>/review.json
```

成功時は終了コード0、入力不備は1。最初の不整合を表示する。証拠の存在・真正性・主張との対応、個人情報の混入、仮説の妥当性は人またはレビュー担当AIが別途確認する。任意の追加キーは許容するが、追加項目は機械検査の対象外。
