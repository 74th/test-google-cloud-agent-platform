## Purpose

ホストされた Claude エージェントに、金沢さくら台三丁目、金沢みらい駅、金沢テスト市役所の間を走る架空の地域バス路線について、信頼できる日本語のテスト用時刻表知識を与える。

## ADDED Requirements

### Requirement: Bus timetable knowledge is packaged with the agent
エージェントのデプロイには、`workspace/.claude/skills/bus-schedule/SKILL.md` を正とする `金沢テストバス時刻表` スキルを含める SHALL。このファイルは金沢さくら台三丁目、金沢みらい駅、金沢テスト市役所について、架空の路線および出発時刻から到着時刻までの時刻を定義する。デプロイが手動設定されたローカル知識や重複した時刻表定義に依存しないよう、コンテナへ取り込むスキル内容はこのファイルと一致する SHALL。

#### Scenario: Skill is available after deployment
- **WHEN** プロジェクトのコンテナアセットを用いてエージェントサービスをデプロイした場合
- **THEN** デプロイ済みエージェントは `workspace/.claude/skills/bus-schedule/SKILL.md` に由来する `金沢テストバス時刻表` スキルおよびそこで定義された架空の時刻表データにアクセスできる

### Requirement: Agent answers the next-bus question using the home-to-station timetable
`次のバスは何時？` を含め、明示的な路線を指定せずに次のバス時刻を尋ねるリクエストに対して、エージェントは金沢さくら台三丁目から金沢みらい駅への架空路線として扱い、その路線の時刻表に基づいて回答する SHALL。回答には該当する出発時刻と到着時刻を示すか、現在時刻が最終掲載便の出発時刻より後の場合は以降に掲載便がないことを説明する SHALL。

#### Scenario: Next direct-route bus is available
- **WHEN** 利用者が掲載された金沢さくら台三丁目発・金沢みらい駅行き便の出発時刻より前に `次のバスは何時？` と尋ねた場合
- **THEN** エージェントは次に該当する便の出発時刻と対応する到着時刻を答える

#### Scenario: No listed bus remains
- **WHEN** 利用者が最終掲載の金沢さくら台三丁目発・金沢みらい駅行き便の出発後に次のバスを尋ねた場合
- **THEN** エージェントは時刻を作り出さず、パッケージ化された時刻表には以降の便がないことを説明する

### Requirement: Agent warns about the longer hospital-route buses
選択された金沢さくら台三丁目発・金沢みらい駅行き便が、所要時間がおよそ25分と示された兼六・ひがし茶屋コースの場合、エージェントは約25分かかることを伝え、駅への直行便ではなく金沢テスト病院を経由することを注意として示す SHALL。

#### Scenario: Next service is a longer hospital-route bus
- **WHEN** 次に該当する便が、掲載された所要約25分の兼六・ひがし茶屋コースである場合
- **THEN** 回答にはその出発時刻と到着時刻、および金沢テスト病院経由で約25分かかることへの注意を含める

### Requirement: Agent supports explicitly requested covered routes
利用者が時刻表で対象としている方向を明示して尋ねた場合、エージェントは既定の出発停留所から駅への路線に加え、金沢みらい駅から金沢さくら台三丁目、または金沢さくら台三丁目から金沢テスト市役所の、該当路線に掲載された架空の時刻を使用する SHALL。

#### Scenario: User asks for the station-to-home route
- **WHEN** 利用者が金沢みらい駅から金沢さくら台三丁目へのバスを尋ねた場合
- **THEN** エージェントは金沢みらい駅発・金沢さくら台三丁目行きの時刻表を使用して回答する
