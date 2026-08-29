## ADDED Requirements

### Requirement: 共有 Agent Gateway を利用する検証用 Runtime のデプロイ
検証手段は、外部所有の共有 Agent Gateway を完全修飾リソース名で入力し、BYOC Agent Runtime の Agent-to-Anywhere 構成へ関連付けなければならない（SHALL）。デプロイ前に共有 Terraform output、共有 Terraform state、および live API の Gateway が同じ project、location、リソース名を示すことを確認しなければならない（MUST）。作成後の BYOC Runtime GET では、Gateway ID、identity type、および `spec.containerSpec.imageUri` の immutable digest を要求値と照合しなければならない（MUST）。BYOC の Reasoning Engine GET が提供しない `revision`、`traffic`、`deployedModels` は関連付け確認の必須項目としてはならない。 この検証の構成は共有 Gateway、VPC、subnet、Network Attachment を作成、変更、削除してはならない（MUST NOT）。

#### Scenario: common-egress を関連付けてデプロイする
- **WHEN** `common` の output、state、live API が `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress` を示す
- **THEN** 検証用 Runtime はその完全修飾 ID を Agent-to-Anywhere Gateway として明示した構成で作成される
- **AND** デプロイ結果には Runtime リソース名、`imageUri` から確認したイメージ digest、Gateway ID、identity、および作成時刻が機密情報を含まず保存される

#### Scenario: 共有 Gateway の同一性を確認できない
- **WHEN** output、state、live API の project、location、リソース名が一致しない、またはいずれかを確認できない
- **THEN** 検証手段は Runtime を作成せず、不一致または不足した確認項目を報告する

#### Scenario: Gateway 関連付けが拒否される
- **WHEN** Runtime の作成または更新が Gateway の競合、参照エラー、権限不足によって失敗する
- **THEN** 検証手段は失敗した API 操作、対象 Runtime、Gateway ID、安全なエラー分類を記録し、既存 Runtime または共有 Gateway を変更して回避しない

### Requirement: BYOC 所有の egress Service と Endpoint policy
query-job proxy の GCS egress を検証する場合、検証手段は現行 `common-egress` が参照する Registry に BYOC 専用の GCS endpoint Service を登録し、投影された Endpoint に対象 Runtime の effective identity だけを `roles/iap.egressor` として付与しなければならない（SHALL）。Service と policy は既存の `mcp-20260823-*` consumer resource と異なる一意な名前で管理し、既存 resource の policy を置換してはならない（MUST NOT）。

#### Scenario: GCS egress Service と policy を作成する
- **WHEN** `common-egress` の Registry、GCS endpoint URL、対象 Runtime の effective identity が検証済みである
- **THEN** 検証手段は `storage.googleapis.com` および managed proxy が使用する `storage.mtls.googleapis.com` を表す BYOC 専用 Service を作成または管理する
- **AND** 投影 Endpoint の `roles/iap.egressor` は対象 Runtime principal に限定され、他 consumer の policy を変更しない

#### Scenario: 旧 Gateway resource を整理する
- **WHEN** live inventory に旧 experiment の `agw-20260822-*` Gateway、Service、または Endpoint policy が残っている
- **THEN** 検証手段は inventory で確認した完全な resource ID だけを削除し、現行 `common-egress`、その Registry、VPC、Network Attachment、`mcp-20260823-*` consumer を削除または変更しない
- **AND** 旧 resource が live inventory に存在しない場合は削除を実行せず、不在を証跡に記録する

#### Scenario: Service または policy の確認に失敗する
- **WHEN** Service の endpoint URL、投影 Endpoint、IAM member、または common Registry の一致を確認できない
- **THEN** 検証手段は query-job を再実行せず、作成・変更した範囲と不足した read-back を記録する

### Requirement: 共有 Gateway 関連付け後の BYOC 回帰検証
検証手段は、Runtime の live 構成が入力された共有 Gateway を参照することを確認してから、デプロイ済みエージェントの4操作、短時間長時間ジョブ経路、15分を超えるジョブ、および SDK と REST の長時間ジョブ経路比較を実行しなければならない（SHALL）。各試行は、Gateway 関連付け、Runtime 到達、アプリケーション処理、ジョブ終端、GCS 入出力を個別の証跡として判定しなければならない（MUST）。Runtime への ingress 操作が成功したことだけを、外向き通信が Gateway を通過した証拠として扱ってはならない（MUST NOT）。

#### Scenario: 通常4操作が共有 Gateway 関連付け後も成功する
- **WHEN** live Runtime が `common-egress` を参照し、検証者が `query`、`async_query`、`stream_query`、`async_stream_query` を実行する
- **THEN** 各操作は既存契約の応答内容と順序を返し、検証 ID で対応する Runtime ログと照合できる
- **AND** 結果は Runtime が共有 Gateway に関連付けられた状態での互換性確認として報告される

#### Scenario: 短時間ジョブを長時間試験のゲートにする
- **WHEN** Runtime の Gateway 関連付け確認後に約10秒の長時間ジョブ経路を実行する
- **THEN** GCS 入力取得、`POST /`、処理完了、成功終端、GCS 出力が同じ試行として確認された場合だけ960秒ジョブへ進む

#### Scenario: 960秒ジョブと SDK REST 比較が成功する
- **WHEN** 短時間ゲートが成功し、960秒ジョブならびに同等入力の SDK 経路と REST 経路を実行する
- **THEN** 検証結果は各経路の入力 URI、`POST /`、処理完了、成功終端、出力 URI と非機密の出力属性を対応付ける
- **AND** 以前の検証結果との差異と使用した Runtime、image digest、Gateway ID を記録する

#### Scenario: Gateway 通過を証明できない
- **WHEN** Runtime の Gateway 関連付けと BYOC 操作成功は確認できるが、その試行に対応する Gateway decision log が存在しない
- **THEN** 検証結果は共有 Gateway 関連付けと BYOC 互換性を成功として報告できる
- **AND** 実トラフィックが Gateway を通過したとは報告しない

#### Scenario: 検証リソースを保持して人間の確認を待つ
- **WHEN** ライブ検証と証跡収集が完了する
- **THEN** 検証手段は作成した Runtime と Terraform 管理対象を一覧化し、削除対象の plan を作成できる
- **AND** 人間の明示承認なしに Runtime 削除または `terraform destroy` を実行しない
