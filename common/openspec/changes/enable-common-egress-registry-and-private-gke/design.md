## Context

動機は [proposal.md](proposal.md) を参照する。`common` は `nnyn-dev/us-central1` の `common-egress`、専用 VPC `common-agent-gateway-vpc`、PSC Network Attachment を独立した Terraform state で管理している。Gateway は `AGENT_TO_ANYWHERE`、`MCP`、regional Agent Registry path を設定済みであり、consumer は完全修飾 Gateway ID を入力として参照する。

consumer 側では private DNS `gke.mcp-20260823.internal`、Internal HTTPS Load Balancer `10.240.0.5`、healthy NEG、ClusterIP `10.242.0.20:80`、Pod までを GKE 内の caller から検証済みである。ただしこれは Agent Runtime E2E ではなく、endpoint は現時点で internal network/TLS 以外の authorization を実証していない。Runtime query は Registry discovery で `SSLError` となり、同時刻の Gateway log は `CONNECT 240.0.0.2:443` を `default_denied` で拒否した。Runtime image 内の Gateway inspection CA は live fingerprint と一致しているが、この結果だけでは Gateway-to-origin TLS trust を証明しない。

この変更は shared-owner と consumer-owner の二つの境界をまたぐ。common は Gateway/network/policy のみを変更でき、Registry Service、Runtime、GKE、Internal Load Balancer、endpoint authorization、および MCP application は consumer-owned のままとする。仕様上の判定層は [shared-agent-gateway-consumer-access spec](specs/shared-agent-gateway-consumer-access/spec.md) に従う。

## Goals / Non-Goals

**Goals:**

- `240.0.0.2:443` と Registry discovery の対応、および `default_denied` の正確な enforcement layer を再現可能な live evidence で確定する。
- common-owned の変更が必要な場合、現在の Gateway を置換せず、許可 tuple と既存 consumer への影響を plan で示してから最小変更する。
- Runtime-to-Gateway、Gateway-to-control-plane、Gateway-to-private-origin の各 TLS/authorization/network boundary を別々に検証する。
- 同じ correlation ID と狭い時刻範囲から、Runtime invocation から Pod execution までを追跡する。
- cloud capability または owner 境界で完了できない場合、推測した workaround を実装せず、再試行可能な blocker packet を作る。

**Non-Goals:**

- consumer-owned Registry、Runtime、GKE、Load Balancer、certificate、または endpoint authorization を common Terraform state へ移すこと。
- Gateway を汎用 Internet proxy にすること、全 Google API を許可すること、またはすべての consumer を自動 onboarding すること。
- 既存 Autopilot GKE、public frontend、plain HTTP、TLS verification 無効化、匿名 endpoint を使って成功扱いすること。
- この変更の cleanup として Terraform destroy を実行すること。

## Decisions

### 1. read-only diagnosis を write path の前提ゲートにする

最初に一つの bounded probe packet を作る。packet は probe ID、UTC time window、Runtime resource/effective identity、target Registry Service、Gateway ID/etag、Gateway request log、関連する control-plane/audit log、および結果を含む。`240.0.0.2` は、公式ドキュメント、live API response、同一 request の structured log field、または provider/API metadata の少なくとも一つで意味を裏付ける。IP の見た目、reverse lookup、別時刻の類似 log だけでは分類しない。

診断は次の仮説を独立に判定する。

| 仮説 | 必須 evidence | 次の action |
| --- | --- | --- |
| Registry scope/registration mismatch | Gateway `registries` read-back と requested Registry project/location | registration/scope 修正案 |
| host/port/protocol policy deny | request destination、matched rule、Gateway protocol | exact tuple の allow 案 |
| Runtime identity deny | effective principal と policy subject/action | principal-scoped allow 案 |
| 別 authorization extension/policy deny | Gateway/policy/extension relation と各 layer の log | common-owned policy 修正案 |
| Gateway 内部または未公開 managed endpoint | 公式/live surface による IP の分類 | supported allow surface がなければ blocker |
| CA/TLS failure | deny を通過した後の TLS leg と検証 error | trust chain owner ごとの修正案 |

先に allow rule を推測して追加する案は、default-deny の範囲を不必要に広げ、`240.0.0.2` が user-configurable host でない場合に誤った変更となるため採用しない。

### 2. 現在の `common-egress` を in-place で維持し、allow surface は live schema で確定する

Gateway ID、direction、protocol、Registry、Network Attachment を変えないことを基本とする。実装時点の `google-nightly` schema、Network Services/Network Security discovery document、`gcloud` surface、および live resource relation を記録し、Gateway egress rule、security policy、authz policy/extension、Registry binding、IAM のどれが実際の enforcement owner かを確定する。

supported surface が Terraform で表現できる場合、common root module に typed allow tuple を追加する。tuple は少なくとも logical name、principal/resource、host、port、protocol、purpose を持ち、catch-all、空 host、`allUsers`、Owner/Editor を validation/static test で拒否する。既存 default-deny は明示的に残し、positive tuple と隣接する negative tuple を同じ validation run で確認する。

公式 API にだけ surface があり provider にない場合、いきなり CLI/REST write を行わない。冪等性、etag/precondition、Terraform drift、rollback を示す別の変更案として提示し、再承認を得る。supported write surface がない場合は blocker とする。

Gateway の再作成、新しい同方向 Gateway、consumer state への import は、Runtime association の競合、既存 consumer の停止、所有権混在を招くため採用しない。

### 3. allow は destination と identity の二軸で最小化する

allow inventory は observed request から構築し、候補を最初から一括許可しない。Registry discovery に必要な control-plane destination を先に一つずつ通し、次の deny へ進むたびに同じ probe packet を更新する。Vertex AI regional/global endpoint または IAM Credentials endpoint は実際の request/log と runtime behavior が必要性を示した場合だけ追加する。private MCP destination は `gke.mcp-20260823.internal:443` の exact host/port と MCP/HTTPS に限定する。

IAM の `roles/iap.egressor` binding は consumer-owned Registry resource 上の endpoint authorization input として read-back するが、それだけで Gateway allow とみなさない。Gateway policy subject が Runtime resource principal、service agent、または別の managed identity を使う場合は、live log/API で effective subject を確定してから binding を選ぶ。

host-only allow や project-wide Google API allow は設定が簡単でも、identity isolation と negative test を満たさないため採用しない。identity を policy surface が表現できない場合は、その制約と代替 enforcement layer を明示し、仕様を満たせなければ blocker とする。

### 4. private route を control-plane path と data-plane path に分ける

Registry discovery は control-plane path、MCP call は data-plane path として別々に観測する。data-plane は次の順で検証する。

```text
Agent Runtime identity
  -> common-egress allow decision
  -> PSC Network Attachment / common-agent-gateway-vpc
  -> private DNS: gke.mcp-20260823.internal -> 10.240.0.5
  -> INTERNAL_MANAGED HTTPS frontend
  -> endpoint authorization
  -> healthy NEG / ClusterIP 10.242.0.20:80
  -> GKE MCP Pod
```

Network Attachment の accepted connection、VPC/subnet relation、DNS peering suffix、private DNS record、forwarding scheme/IP、target proxy/certificate metadata、backend health、Service/NEG/Pod を read-back する。Gateway VPC connectivity は private RFC1918/private DNS path に使われるもので、通常の Internet egress 全体を VPC へ強制する Cloud Run VPC Connector `ALL_TRAFFIC` として扱わない。private ILB 到達だけを理由に Cloud NAT を追加しない。

ClusterIP への直接 route を試す案は、Kubernetes Service CIDR が Gateway VPC から到達可能であることを証明しておらず、既に internal HTTPS frontend があるため採用しない。public Load Balancer fallback も採用しない。

### 5. TLS を Runtime-to-Gateway と Gateway-to-origin の二つの trust leg で扱う

Runtime image の Gateway Root CA presence、`openssl verify` 結果、live CA fingerprint 一致は Runtime-to-Gateway inspection leg の evidence とする。証明書本文、秘密鍵、token は保存しない。

Gateway-to-origin leg では、SNI/hostname が `gke.mcp-20260823.internal` であること、origin certificate の SAN、有効期間、issuer/fingerprint、および Agent Gateway がその chain を trust する公式方式を別に確認する。現在の self-managed test certificate が GKE Pod から trust された事実だけで Gateway からの trust を PASS にしない。Gateway が private/self-managed issuer を trust する supported configuration がない場合は consumer endpoint certificate の blocker とし、`-k`、hostname bypass、plain HTTP は使わない。

### 6. endpoint authorization は consumer-owned prerequisite として fail-closed にする

common の apply は Gateway allow までに限定する。GKE endpoint authorization は consumer owner が管理し、approved Runtime identity/audience の positive case と credential-less/wrong-audience/wrong-identity の negative caseを提供する。internal network 上にあること、Gateway を通過したこと、または TLS が成功したことだけでは authorization PASS としない。

consumer endpoint が現在のように network-only で認証なし request を受け入れる場合、private routing までは個別 PASS にできるが governed Agent Runtime E2E は FAIL/SKIP とし、consumer-owned authorization が整うまで停止する。common 側から consumer state を変更して埋め合わせる案は所有境界に反するため採用しない。

### 7. evidence は層別 verdict と一つの correlation record にまとめる

validation runner/runbook は secret でない UUID を一回の probe に割り当て、MCP input または許可された correlation header に伝播する。Runtime API が correlation ID を error response に返さない段階では、UTC time window、Runtime resource、target Service、method、Gateway log tuple を provisional join key とし、相関の強度を明記する。E2E PASS には同じ correlation ID が endpoint と Pod log まで到達することを必須とする。

最終 evidence は各層を `PASS`、`FAIL`、`SKIP`、`BLOCKED` で記録し、caller、identity、source、destination、route、authorization layer、resource ID、timestamp、log query、result を含める。operator-side/in-cluster check は補助的な backend baseline とラベル付けし、Agent Runtime E2E へ昇格させない。

## Risks / Trade-offs

- [Gateway の `default_denied` が user-managed policy ではなく managed internal enforcement である] → live schema/API/log relation を先に確定し、supported allow surface がなければ owner と再試行条件を含む blocker にする。
- [段階的 allow により複数回の plan/apply が必要になる] → 観測されていない endpoint を一括許可せず、各追加 tuple の理由と negative regression を evidence に残す。
- [in-place policy update が既存 consumer を後退させる] → pre-change consumer inventory、saved plan、etag、既存 allow regression test、post-change read-back を必須にする。
- [Gateway/API の preview schema が Terraform state と drift する] → provider/API version を固定し、unknown field や out-of-band mutation を検出したら apply を停止する。
- [Runtime request と Gateway log を一意に相関できない] → bounded single probe と専用 correlation ID を使い、相関できない段階は E2E PASS にしない。
- [origin certificate を Gateway が trust できない] → two-leg TLS evidence を分離し、supported trust configuration または consumer-owned certificate remediation がない限り verification を無効化しない。
- [endpoint authorization が未実装のまま private route が成功する] → routing PASS と authorization FAIL/SKIP を分離し、governed E2E を未達とする。
- [evidence に secret が混入する] → token/CA/key/Secret field を取得・出力しない query と redaction check を validation workflow に含める。

## Migration Plan

1. common state、live Gateway、policy/extension、Network Attachment/DNS peering、Registry scope、Runtime relation、既存 consumer、直近の `default_denied` log を read-only で inventory する。
2. 一つの bounded Registry probe を実行し、`240.0.0.2:443`、effective identity、matched rule、enforcement resource の対応を診断 packet にまとめる。確定できなければ blocker を返して write を行わない。
3. current provider/API schema から supported allow surface を確定し、必要な exact tuple、resource、principal、差分、rollback を設計する。common Terraform/static tests/runbook を実装して format、validate、test、refresh-only plan、通常 plan を確認する。
4. plan に replacement、delete、範囲外 resource、既存 allow の後退がないことを確認する。write に必要な承認境界を満たした後だけ apply し、etag を含む post-apply read-back と positive/negative Gateway log を取得する。
5. Registry discovery を再試行し、必要性を新たに実測した endpoint だけ同じ手順で追加する。Registry 成功時点では E2E PASS としない。
6. Network Attachment/private DNS/origin TLS/frontend/backend を read-back し、consumer owner が endpoint authorization の positive/negative prerequisite を満たしたことを確認する。満たさなければ owner-specific blocker で停止する。
7. correlation ID 付き Runtime query で registered GKE Tool を一度実行し、Runtime、Registry、Gateway、endpoint authorization、ILB/backend、Pod execution の evidence を層別に確定する。

ロールバックは新規に追加した exact allow tuple/policy change だけを同じ common state から除去し、plan、承認境界、apply、post-read-back、deny regression の順で行う。Gateway、VPC、subnet、Network Attachment の destroy や consumer resource の変更はロールバックに含めない。provider/API が安全な in-place rollback を表現できない場合は apply 前に blocker とする。
