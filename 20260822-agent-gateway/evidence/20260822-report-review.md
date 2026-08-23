並行して走らせていた実装コードのレビューが返ってきました。先ほどの指摘はすべて裏付けが取れ、追加で報告すべき点がいくつか出たので補足します。

追加の指摘

🟡 README の手順が、そのままでは実行不可能

README の手順5（allow-github）は Runtime の identity principal を必要としますが（README.md:68-72）、その Runtime を作るのは手順6の deploy.sh です。順序が逆で、書かれた通りには通りません。
また手順3の docker build（README.md:52-53）はタグも push も無い捨てビルドで、実ビルドは deploy.sh → build_push.sh:12-22 が証明書を独自に再取得してやり直しています。

🟡 ESSENTIAL_GOOGLE_ENDPOINTS は完全な dead code

先ほど「未文書」と書きましたが、実際はもっと弱く、scripts/gateway.py:16-20 の dict は register_essential_google からも読まれていません（76行、service/url を必須 CLI 引数で受け取る）。つまり aiplatform エンドポイントの登録は完全にアドホックな手作業で、コードにもドキュメントにも痕跡がありません。再現性はさらに低いです。

🟡 拒否の証跡は IAP ログの1本足

同時刻（15:19:27.829845Z）の Gateway 判定ログは hostname: "240.0.0.2:443"、matchedRules なしです。つまり「www8.cao.go.jp が拒否された」というホスト帰属は IAP 監査ログからしか取れていません。レポート32行目は正しくそう書いていますが、Gateway 側の判定ログでは拒否対象ホストが見えない、という制約は明記しておく価値があります。

🟢 恒真アサーションはもう1件ある

tests/test_terraform.py:13 の assert "deny:" not in policy.lower() も絶対に失敗しません。ポリシー内の deny は default_action: DENY のみで、小文字化すると default_action: deny — deny: という部分文字列は存在しないためです。「個別 deny ルールが無いこと」を検証しているつもりで何も検証していません。

🟢 その他

- validate.py:96 の case.name == "github" or ... により、github ケースは応答チェックが実質無効（空でなければ何でも通る）。
- _fetch_url / web_fetch_server（唯一の外向き通信コード）にテストが1件もありません。
- test_terraform.py:4 が Path("terraform") の相対パスで、pytest の cwd に暗黙依存。
- test_adapter.py:47-54 の fake_tool/fake_server は現行実装から未参照の残骸。
- deploy_agent.py:28 の AGENT_GATEWAY_RESOURCE env var は agent_service/ のどこからも読まれていません（情報用）。
- Dockerfile:11 の AGENT_GATEWAY_ROOT_CERT_302034098528 の数字は、この環境のどのプロジェクト番号とも一致しません（Runtime = 776113568960、テナント = 122306729336）。他所からコピーされたリテラルと思われます。実害は無い（システムバンドルを指しているだけ）ですが、意図した効果は出ていない可能性が高いです。

---

全体の評価

検証としては成立しています。「Agent Gateway で許可ホストのみ通し、未登録ホストはデフォルト拒否で落ちる」という計画書の主眼は、Runtime のバインド設定・Gateway 許可ログ・IAP 拒否ログの3点で実証できており、クライアント側の細工でもありません。

一方でレポートは実態より強く書かれています。修正すべきは優先度順に:

1. ログ収集を呼び出しの後に変える（gateway.py logs --since が既にある）— これで判定が初めて反証可能になる
2. aiplatform 等の追加登録エンドポイントをレポートと policy-source.yaml に開示する
3. README の手順5/6 の順序を入れ替える
4. 恒真アサーション2件（test_validation_runner.py:43、test_terraform.py:13）を直す
