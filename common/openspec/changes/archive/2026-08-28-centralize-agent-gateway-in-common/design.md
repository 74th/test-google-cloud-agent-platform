## Context

動機は [proposal.md](proposal.md) を参照する。現在の実 Gateway `agw-20260822-egress` は `20260822-agent-gateway/terraform` の local state で作成され、Agent Runtime、Artifact Registry、IAM、IAP authorization extension/policy と同じ state に含まれる。`20260823-mcp-server` は Gateway 作成コードをコメントアウトし、完全修飾 ID を変数で受けて同じ Gateway を利用している。

Google Cloud プロジェクトは `nnyn-dev`、region は `us-central1` で固定する。同じ project/direction に複数 Gateway を作れないため、新旧 Gateway は並行作成できない可能性がある。また、OpenSpec の検証は計画の整合性のみを示し、provider/API 対応やクラウドでの VPC 接続を実証しない。

## Goals / Non-Goals

**Goals:**

- `common/terraform` を共有ネットワークと共有 Agent Gateway の唯一の Terraform 所有者にする。
- Gateway と専用 VPC/subnet の接続を構成および live API 応答で検証可能にする。
- 既存2 state の破壊的移行を、読み取り専用 preflight と人間承認付き実行に分離する。
- 利用側が state を共有せず、明示入力された完全修飾 Gateway ID だけに依存する契約を作る。

**Non-Goals:**

- `common` で Agent Runtime、Agent Registry service、MCP server、GKE、Cloud Run、Artifact Registry、または検証固有 IAM を管理すること。
- この変更中に `20260822-agent-gateway` または `20260823-mcp-server` を再 apply すること。
- 無停止移行、本番向け高可用性、Shared VPC host project 化、または任意の project/region を支える汎用 module 化。
- OpenSpec 提案作成中に apply または destroy を実行すること。

## Decisions

### 1. `common/terraform` に専用 root module と独立 state を置く

Terraform root は project/region、リソース名、subnet CIDR、labels を明示変数にし、既定値を `nnyn-dev/us-central1` に固定する。VPC は auto subnet を無効化し、Gateway 専用 subnet を1つだけ作る。Gateway、VPC、subnet の ID を output し、利用側は remote state を直接読むのではなく、承認済み output 値を変数または tfvars で受け取る。

remote-state coupling は state backend への権限を全利用者へ広げるため採用しない。既存検証 state への resource move/import も、不要な検証リソースと所有境界を結合したままにするため採用しない。

### 2. VPC 接続方式は実装時の公式 schema で確定し、静的検査と live API の両方で証明する

実装前に現在の `google`/`google-beta`/必要に応じた明示的な preview provider の schema と Network Services API discovery を確認し、Gateway が要求する network、subnet、network attachment、または同等の公式フィールドを採用する。provider と API のバージョン、および採用した接続フィールドを runbook に記録する。Terraform test/validate/plan に加え、作成後に Gateway describe と VPC/subnet describe を保存する。

推測した Terraform 属性や、VPC を作るだけで Gateway へ接続しない構成は採用しない。provider が未対応でも公式 API が対応する場合に限り、冪等で監査可能な CLI/REST 経路を Terraform と明確に分離して提案し、apply 前に再承認する。公式に接続手段がなければ blocker とし、非接続 Gateway へ要件を弱めない。

### 3. common の責務をネットワークと Gateway に限定する

主な実体リソースは VPC、subnet、Agent Gateway の3つとする。API 有効化を Terraform で扱う場合は `disable_on_destroy = false` とし、共有 project の既存 API 利用を破壊しない。Gateway 作成に公式 API が必須とする補助的接続リソースだけは、schema 確認の証跡とともに追加できるが、Agent Registry service、Runtime、endpoint IAM、egress policy の検証固有設定は利用側に残す。

既存の IAP authorization extension/policy をそのまま common へ移す案は、endpoint authorization と Gateway の共有ライフサイクルを再結合するため採用しない。公式 API が Gateway 自体の必須構成として要求する場合は、実装前に設計・spec を更新する。

### 4. 既存環境は「preflight → 明示承認 → state 単位 destroy → コード除去」の順で移行する

まず各ディレクトリで backend/state、workspace、refresh-only plan、通常 plan、destroy plan、Gateway/Runtime などの live inventory、他の利用者を収集する。この段階では書き込みを行わない。人間が state ごとの destroy plan を確認して明示承認した後だけ、`20260822-agent-gateway`、次に `20260823-mcp-server` を個別に destroy し、state と live inventory の残存を確認する。実行順は live dependency の結果により変更できるが、一括 command や曖昧な working directory は使わない。

destroy 後、旧 Gateway resource、Gateway 専用 authorization resource、不要な変数/output/テスト、および旧 `agw-20260822-egress` 固定値を除去する。利用側は共有 ID を明示入力する形へ更新するが再 apply しない。その後、project に競合 Gateway がないことを確認して common を plan し、別の人間承認後に apply する。

destroy を resource-target だけに限定する案は、依存する Runtime や policy と state の不整合を残しやすく、ユーザーが既存 Terraform を一度 destroy する意図にも反するため採用しない。コードを先に消す案も state 上のリソースを orphan 化するため採用しない。

### 5. 共有 ID は安定した output 契約にし、利用側 state とは共有しない

`agent_gateway_id`、`network_id`、`subnetwork_id` を機械可読 output とし、ID の project/location を検証する。利用側は tfvars など明示的な入力で `agent_gateway_id` を受け取り、自身の構成に `google_network_services_agent_gateway` resource を持たない。Gateway の変更・削除前には利用者 inventory を確認する。

Gateway 名を既存値のまま再利用する案は、削除の伝播待ちや古い証跡との混同を招くため採用しない。`common` を示す新しい衝突しにくい名前を使い、最終名は live inventory と命名制約を plan 前に検証する。

## Risks / Trade-offs

- [Gateway の VPC 接続 surface が preview provider/API で変更されている] → 実装前に公式 schema と API discovery を保存し、version を固定する。未確認属性では apply しない。
- [同方向 Gateway の削除反映が遅く common apply が競合する] → delete operation 完了と live list からの消失を確認し、再試行可能な待機条件を runbook に記載する。
- [既存 state の full destroy が Runtime、Artifact Registry、GKE/Cloud Run なども削除する] → state ごとの destroy plan に全対象を列挙し、人間の明示承認を別々に得る。自動実行しない。
- [旧 Gateway を参照する未確認 consumer が停止する] → state、コード、Agent Runtime API、ログを使って consumer inventory を取得し、未解決 consumer があれば destroy を停止する。
- [subnet CIDR が既存 VPC と重複する] → live network inventory を確認してから CIDR を確定し、変数 validation と plan review を行う。
- [local state が失われ共有基盤を管理できなくなる] → backend と state の保護方法を実装時に明記し、機密値を output/state に保存しない。backend 変更が必要なら別途レビューする。
- [OpenSpec の common scope と隣接検証ディレクトリの変更境界が曖昧になる] → common 実装と、明示承認後の隣接ディレクトリ cleanup を別コミット・別検証結果として記録する。

## Migration Plan

1. 現行 provider/API の VPC 接続 surface、project の Gateway 上限、命名制約、および `nnyn-dev/us-central1` の VPC/CIDR inventory を読み取り専用で確認する。
2. `common/terraform` とテスト/runbook を実装し、format、validate、静的テストを通す。まだ apply しない。
3. `20260822-agent-gateway` と `20260823-mcp-server` ごとに state、依存 consumer、live resource、destroy plan を収集し、人間へ提示する。
4. 人間が各 destroy を明示承認した場合のみ、対象を明記して state 単位で destroy し、完了と残存リソースを確認する。承認がなければここで停止する。
5. 旧 Gateway 管理コードと固定参照を除去し、利用側を共有 Gateway ID の入力契約へ更新する。利用側 Terraform は再 apply しない。
6. 競合 Gateway が存在しないことを確認し、common の plan を作成する。project、region、CIDR、名前、全 action を人間が承認した場合のみ apply する。
7. Terraform output と live describe を保存し、VPC/subnet 接続および state 所有範囲を検証する。

ロールバックでは、まず common の構成を修正して同じ state から再 apply する。common を削除する必要がある場合も利用者 inventory と destroy plan に対する新たな明示承認を必須とする。旧検証 stack の再 apply はこの変更の自動ロールバックに含めず、必要なら別途承認された復旧作業として扱う。
