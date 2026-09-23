# GKE Agent Sandbox 検証見送りメモ

## 概要

GKE Agent Sandbox を利用することで、既存の GKE Job ベースの実行基盤における実装・運用負荷を減らせないか検討した。

調査の結果、GKE Agent Sandbox には以下のような機能があることが分かった。

* gVisor によるカーネル分離
* Sandbox / SandboxTemplate / SandboxClaim による実行環境の抽象化
* SandboxWarmPool による事前起動済み実行環境の払い出し
* NetworkPolicy を含む Sandbox 向けセキュリティ設定
* PVC を利用した workspace の永続化
* Sandbox の終了時刻や TTL に基づく Lifecycle 管理
* Sandbox 用の安全な Pod 設定の標準化
* Snapshot / restore を利用した stateful workload 向け機能

一方で、現在の利用要件では Agent Sandbox に移行するメリットが小さいと判断し、現時点での検証は見送る。

---

## 想定していた用途

現在は GKE Job を利用し、Agent が実行する長時間タスクを処理している。

おおまかな構成は以下。

```text
Request
  ↓
GKE Job 作成
  ↓
PVC を workspace として mount
  ↓
FQDNNetworkPolicy 適用
  ↓
Agent / Task 実行
  ↓
Job 終了
  ↓
workspace は必要に応じて保持
```

主な用途は社内利用であり、利用頻度はそれほど高くない。

また、1タスクあたり30分程度かかるケースも多いため、Pod / Sandbox の起動時間が数秒程度増えることは問題にならない。

Agent Sandbox を検討した主目的は、性能向上ではなく、既存の Kubernetes 周辺実装を Agent Sandbox 側に任せることで作り込みを減らせないか、という点だった。

---

# GKE Agent Sandbox でできること

## 1. gVisor によるカーネル分離

Agent Sandbox は gVisor を利用し、Sandbox 内のプロセスを GKE Node のホストカーネルから隔離する。

通常のコンテナよりも、ホストカーネルへの直接的な syscall 面を縮小できる。

主に以下のような用途に適している。

* LLM が生成した任意コードの実行
* ユーザー提供コードの実行
* Code Interpreter
* Coding Agent
* Plugin / Tool execution
* 信頼できない処理の隔離

今回の用途では、実行コード自体の信頼境界として gVisor を強く必要としていないため、主要なメリットにはならなかった。

---

## 2. Sandbox / SandboxTemplate / SandboxClaim

Agent Sandbox は通常の Job / Pod を直接扱う代わりに、以下の CRD を利用する。

```text
SandboxTemplate
       │
       ▼
SandboxClaim
       │
       ▼
Sandbox
       │
       ▼
Pod
```

これにより、利用側は具体的な Pod を直接管理するのではなく、

> このテンプレートに基づく実行環境を1つ欲しい

という形で実行環境を要求できる。

実行環境の生成や一部 Lifecycle は Agent Sandbox controller が管理する。

大量の一時的な Sandbox を払い出すシステムでは有効な抽象化と考えられる。

一方、現在の実装では Job を1つ作る処理自体はそれほど複雑ではなく、この抽象化によるコード削減効果は限定的。

---

## 3. SandboxWarmPool

事前に起動済みの Sandbox を用意しておき、SandboxClaim が来た際に払い出す仕組み。

```text
SandboxWarmPool

├─ Ready Sandbox
├─ Ready Sandbox
└─ Ready Sandbox

        ↓ Claim

利用可能な Sandbox を即時割当
```

通常の Pod 起動では、

```text
Create
→ Schedule
→ Image pull
→ Container start
→ Ready
```

という処理が必要になる。

WarmPool を使うと、この初期化済み Sandbox を再利用できるため、sub-second provisioning を狙える。

これは Agent Sandbox の大きなメリットの1つ。

ただし今回の環境では、

* 社員が時々利用する程度
* 同時実行数が多くない
* 1タスク30分程度
* 起動に数秒余計にかかっても問題ない

ため、WarmPool の恩恵はほぼない。

---

## 4. Network isolation

Agent Sandbox には NetworkPolicy を含む Sandbox 用ネットワーク制御がある。

また、安全側のデフォルトとして、

* Private network へのアクセス制限
* Metadata 系アクセスの制限
* 不要な Ingress の遮断

などを組み込みやすい。

ただし、Agent Sandbox の `networkPolicy` 自体で扱えるのは基本的に Kubernetes NetworkPolicy 相当であり、FQDN 単位の allowlist を直接記述できるわけではない。

例えば、

```text
github.com              ALLOW
www.tohoho-web.com      DENY
```

のような制御を行いたい場合は、GKE の `FQDNNetworkPolicy` を別途利用する。

現在の環境ではすでに FQDNNetworkPolicy を利用しており、動作も確認済み。

したがって、この部分は Agent Sandbox に移行しても簡略化されない。

---

## 5. Storage / workspace

Agent Sandbox では PVC を Sandbox に mount し、workspace として利用できる。

例えば、

```text
Sandbox
   │
   └─ /workspace
          │
          ▼
         PVC
```

という構成にできる。

Sandbox を削除しても PVC を残しておけば、後から別の Sandbox に同じ workspace を mount することも可能。

ただし、この仕組みの本体は Kubernetes の PVC であり、Agent Sandbox 独自の永続ストレージ機構ではない。

現在の GKE Job ベースでも既に同様の構成を実装済み。

そのため、

> Agent Sandbox にすることで workspace 永続化の仕組みを大幅に簡略化できる

というほどの差はなかった。

---

## 6. Lifecycle

Agent Sandbox には Lifecycle 管理がある。

例えば、

* `shutdownTime`
* `shutdownPolicy`
* `ttlSecondsAfterFinished`

などを使い、Sandbox を一定時刻で終了させたり、終了後に GC することができる。

概念としては、

```text
Sandbox 作成
   │
   │ running
   │
shutdownTime
   │
   ▼
Delete / Retain
```

というもの。

これは、

> 最大1時間だけ実行可能

のような hard deadline を設定する用途には有効。

また、利用側が削除処理を忘れた場合の resource leak 防止にもなる。

---

# 期待していたが、現状はできないこと

## 1. Idle timeout

期待していたのは例えば以下のような Lifecycle。

```text
最後のアクセス
     │
     │ 30分操作なし
     ▼
Sandbox 自動停止
     │
     │ 24時間再利用なし
     ▼
Sandbox / state 削除
```

しかし現在の Agent Sandbox の Lifecycle は、基本的に絶対時刻または作成時点からの TTL ベース。

例えば、

```text
15:00 Sandbox 作成
16:00 shutdown
```

と設定した場合、15:50 に利用されたとしても 16:00 に終了する。

以下のような機能は現時点では組み込みではない。

* 最終アクセス時刻の追跡
* activity があったら TTL を延長
* 一定期間 idle なら suspend
* suspend 後さらに一定期間で delete
* resume 時に idle timer をリセット

そのため、

```text
last_activity_at
```

のような情報はアプリケーション側で管理する必要がある。

Idle lifecycle 自体は upstream でも feature request として議論されている。

---

## 2. Chat / Conversation Session 管理

Agent Sandbox という名前だが、Agent の会話セッション自体を管理するものではない。

Agent Sandbox の責務は実行環境であり、以下は別レイヤーで管理する必要がある。

```text
Conversation
Session
Chat history
Memory
User identity
Agent state
```

例えば実際には、

```text
Chat history
    ↓
DB / external storage
    ↓
conversation_id / session_id
    ↓
Sandbox 起動時に必要情報を渡す
```

という設計になる。

会話が終了したら Sandbox 自体は終了させることもできる。

つまり、

```text
Application Session ≠ Sandbox
```

である。

Agent Sandbox を導入しても、Agent application 側の Session Manager は別途必要。

---

## 3. Session 単位の自動 workspace lifecycle

PVC を Session ID と紐付けて workspace を保持すること自体は可能。

例えば、

```text
session-123
   │
   ├─ Sandbox
   └─ PVC workspace-session-123
```

という構成にできる。

ただし、

> Session が idle になったら Sandbox を停止し、workspace だけ残す

といった判断は Agent Sandbox が行ってくれるわけではない。

利用側で、

```text
session_id
last_activity_at
sandbox_id
pvc_name
```

のような情報を管理し、Lifecycle を制御する必要がある。

この部分は既存実装を大きく削減できない。

---

## 4. FQDN allowlist の統合

Agent Sandbox 自体には、

```yaml
allow:
  - github.com
  - api.github.com
```

のような FQDN ベースの egress allowlist API はない。

FQDN 単位で制御したい場合は、GKE の既存機能である `FQDNNetworkPolicy` を利用する。

現在すでに FQDNNetworkPolicy を使っているため、Agent Sandbox 導入によるメリットはない。

---

# 既存 GKE Job 構成との比較

| 機能                 | 現在の GKE Job            | Agent Sandbox | 今回の評価   |
| ------------------ | ---------------------- | ------------- | ------- |
| Job / Task 実行      | 対応済み                   | 対応可能          | 差が小さい   |
| workspace 永続化      | PVC で対応済み              | PVC           | 差が小さい   |
| FQDN egress 制御     | FQDNNetworkPolicy 対応済み | 同じ仕組みが必要      | メリットなし  |
| Chat history       | 外部 DB                  | 外部 DB が必要     | メリットなし  |
| Session 管理         | 自前                     | 自前            | メリットなし  |
| Idle timeout       | 自前                     | 自前            | メリットなし  |
| Lifecycle hard TTL | Job/Controller等        | 組み込みあり        | 若干メリット  |
| gVisor             | 必要なら構成                 | 標準化されている      | 今回は重要度低 |
| WarmPool           | 自作が必要                  | 組み込み          | 今回は不要   |
| Sandbox Claim      | なし                     | あり            | 現状では不要  |
| Secure defaults    | 自前                     | あり            | 一部メリット  |
| 起動高速化              | 通常 Pod 起動              | WarmPool      | 今回は不要   |

---

# 今回 Agent Sandbox が刺さらなかった理由

今回の環境では、Agent Sandbox が特に強い以下の機能を必要としていない。

```text
gVisor isolation
        ↓
重視していない

WarmPool
        ↓
低トラフィック・長時間処理なので不要

sub-second provisioning
        ↓
数秒の差は問題にならない
```

一方、期待していた以下の領域は Agent Sandbox では解決されない。

```text
Conversation lifecycle
Session lifecycle
Idle timeout
FQDN allowlist
Session と workspace の自動管理
```

これらは既存のアプリケーション側や GKE 標準機能を引き続き利用する必要がある。

---

# 判断

現時点では、既存の GKE Job ベースの実行基盤を Agent Sandbox に移行するメリットは小さい。

特に今回の目的は、

> Agent Sandbox を使うことで、既存の Kubernetes 周辺実装を減らせるか

という点だった。

しかし実際には、

```text
会話履歴
Session 管理
Idle timeout
FQDNNetworkPolicy
PVC と Session の紐付け
```

は引き続き自前管理が必要。

現在すでに、

```text
GKE Job
+
PVC
+
FQDNNetworkPolicy
```

を中心とした基盤が動作しているため、Agent Sandbox に移行しても十分な簡略化効果は見込めない。

そのため、現時点での Agent Sandbox の追加検証は見送る。

---

# 将来、再評価する条件

以下のいずれかが必要になった場合は再評価する。

* ユーザー提供コードや LLM 生成コードをより強く隔離したくなった
* gVisor による kernel isolation が重要になった
* 同時実行数が大幅に増えた
* Sandbox 起動時間が UX 上の問題になった
* WarmPool が必要になった
* SandboxClaim を使った大量の一時実行環境払い出しが必要になった
* Agent Sandbox に idle timeout / suspend / resume が追加された
* Session lifecycle と Sandbox lifecycle の統合機能が追加された
* FQDN allowlist が SandboxTemplate / SandboxClaim に統合された
* Agent Sandbox / Agent Substrate 周辺の Lifecycle 機能が成熟した

それまでは、既存の GKE Job ベースの構成を維持する。
