# 運用手順

## 通常Release

1. developから`release/X.Y.Z`を作り、GitHub → Azure Reposの同期成功と候補SHAを確認する。既存Tagと現在PRODより大きいversionを使う。
2. Release Pipeline 17を候補ブランチから手動起動する。`firstProductionRelease`は通常false。BuildがZIPと`release.json`を一度生成し、同じArtifactをDEV / UATへ配布する。
3. UATのhealthと利用者確認でversion / 候補SHA / 元Run IDを照合する。受入するRunを`Retain indefinitely`にし、戻し先の元Run IDも記録する。
4. 受入後、候補をmainへPR mergeする。**merge commit方式**を使い、mainの内容を候補と一致させる。ミラー成功後、PROD接続の承認を行う。
5. Pipelineがstaging配布・確認、swap、PROD確認、Tag、DR配布・確認まで完了したことを確認する。Tag対象SHAと注釈の元Run / digestを確認する。mainのmerge SHAと候補SHAを取り違えない。
6. developへ反映し、承認・Artifact・Tag・配布記録を残す。途中でmainが変わった場合は旧Runを再開せず、新候補でBuild / UATをやり直す。

`firstProductionRelease=true`は既存Tagも読取可能なPROD識別値もない初回に限る。現在の保持環境では使用しない。UAT却下・PROD却下時は後続が停止し、PROD / Tag / DRを変更しない。

## Hotfixと競合Run

現在のmainから`hotfix/X.Y.Z`を作り、通常Releaseと同じPipeline・承認・slot手順を使う。保留中の通常候補を中止し、修正をmain / develop / 継続候補へ反映する。旧候補Runの受入を使い回さない。

UAT待機中はUATのlock、PRODからDR完了まではPROD接続のlockを保持する。競合RunはChecksで待つ。Hotfix用にlockを解除したり、既存Runの承認だけを追い越させたりしない。Agentの空き状況とExclusive lock待ちを区別する。

## Rollback / DR-only

Recovery Pipeline 18を、Checksが許可し、更新済みの復旧YAMLを含むrelease / hotfixブランチから起動する。現在のYAMLは次の入力を必須とし、旧Run 43などへの自動初期化を行わない。

| 入力 | 意味 |
|---|---|
| `mode` | `rollback` または `dr-only` |
| `sourcePipeline` | 元ArtifactのRelease定義ID。現行は17 |
| `sourceRun` | 保持した**元Release Run ID**。空欄のまま配布しない |
| `expectedCurrentRun` | 開始前にPROD healthで確認した元Build Run ID。復旧RunのIDではない |

元Runが完了済みで指定Pipelineに属すること、ZIPのdigestと識別情報、注釈付きTagのSHA / 元Run / digest、現在PRODを照合してから配布する。Tagがない・別Runを指す・PRODが読めない・期待Runが違う場合は停止する。

- **rollback**: 保持した旧ZIPをstagingへ配布・確認 → 現PRODを再照合 → swap → 旧版PROD確認 → 同じ旧ZIPをDRへ配布。新Tagは作らない。既にそのRunがPRODの場合は二重swapを拒否する。DEV / UATは変更しない。
- **dr-only**: 元Artifactが現在PRODと一致する場合だけDRへ配布。PROD接続の承認・lockを取得し、PRODは読み取るだけ。staging配布・swap・Tag作成を含まない。

2026-10-04の実測例は、`mode=dr-only / sourcePipeline=17 / sourceRun=80 / expectedCurrentRun=80` → 復旧Run 82成功。これは履歴の例であり、次回の指定値は毎回現在PRODから決める。Rollbackの実機復元は未確認。

## 後段失敗の判断

| 停止位置 | 対応 |
|---|---|
| staging / swap前 | PRODは据え置き。原因を修正し、新候補を確認する |
| swap中・直後に応答が不明 | PRODとstagingのhealth、Azure Activity Logのswap結果、元Artifactを確認する。成功・失敗を推測して再swapしない |
| PROD正常、Tag作成・応答照合で停止 | リモートのTagを先に読む。正しいTagが既にあれば作り直さない。存在しない場合だけ、元Run・PROD・digestを照合した限定Tag補償を行う |
| PROD / Tag完了、DRだけ失敗 | 元Runを保持し、`dr-only`で同じ元ZIPをDRへ配布する |
| 復旧の事前ガードで停止 | 指定値・Tag・現PRODを再確認する。ガードを無効化して進めない |

**Promote Stageやswapを含むRecover Stageを再実行しない**。StageAttemptのガードが二重swapを拒否する。新しい復旧Runでも、期待する現PRODを必ず指定する。

Tagだけの補償はRecovery Pipelineに実装していない。既存の`promote.py verify-tag`は読取照合、`promote.py tag`は専用WIFでの作成用である。単独実行には元Run由来の識別情報、Azure DevOps環境変数とTag用WIFを正しく設定する必要があり、全Promote再実行で代用しない。前回の手動補償は確認済みだが、現構成での標準化は[残課題](selfhosted-validation.md)に記載する。

Agentがidle中に停止した場合、Jobは開始待ちになる。再起動後にAgent識別とWIFを確認する。処理中の停止はAzure側の実状態を先に照合し、未完了のJobを無条件に再実行しない。
