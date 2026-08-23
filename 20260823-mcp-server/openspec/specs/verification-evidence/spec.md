# verification-evidence Specification

## Purpose

検証の主張を再実行可能なコマンドと観測証跡に結び付け、Cloud Run と GKE Standard の採用判断を推測ではなく実測結果から行えるようにする。

## Requirements

### Requirement: Reproducible validation procedure
検証手順は prerequisite、変数、主要な Terraform・Google Cloud・Kubernetes・MCP command、および期待結果を秘密情報なしで記録しなければならない（SHALL）。

#### Scenario: 別の operator による再実行
- **WHEN** 必要な Google Cloud 権限を持つ operator が記録された順序で手順を実行する
- **THEN** operator は秘密値をリポジトリへ保存せずに環境構築、登録、discovery、および Tool 実行を再現できる

### Requirement: Evidence-based status
各検証項目は PASS、FAIL、または SKIP として記録され、PASS は command output、API response、resource 状態、または log の証跡を伴わなければならない（SHALL）。未実行または証跡のない項目を PASS としてはならない（MUST NOT）。

#### Scenario: 未実行項目の記録
- **WHEN** 権限、API availability、時間、または外部 prerequisite により項目を実行できない
- **THEN** 結果は SKIP または FAIL とされ、理由と次の確認方法が記録される

### Requirement: Minimum validation matrix
検証結果は少なくとも Cloud Run の認証済み MCP 実行、未認証拒否、Agent Registry 登録・検索、GKE の MCP 実行、GKE entry の登録・検索、Tool specification の整合性、および scale-to-zero 後の Cloud Run 実行を個別に扱わなければならない（SHALL）。

#### Scenario: 必須結果の確認
- **WHEN** 最終 report を検査する
- **THEN** 必須項目ごとに status、実施内容、期待結果、実際の結果、および利用可能な証跡が存在する

### Requirement: Hosting recommendation
最終 report は実測した deploy 容易性、認証、到達性、scale-to-zero、cold-start latency、運用負荷、および継続コストを比較し、Cloud Run と GKE Standard の使い分けを結論付けなければならない（SHALL）。

#### Scenario: 比較結果の作成
- **WHEN** 両ホスティング方式の検証が完了する
- **THEN** report は stateless MCP Server の推奨先、GKE が必要になる条件、制約、未解決事項、および本番導入前の追加検証を示す
