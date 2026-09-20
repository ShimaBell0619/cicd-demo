# 開発・Release・復旧

通常フローは `pipelines/release.yml`、例外時はこの Runbook を読みます。Release の操作責任者を1人決め、同時に進める候補は原則1つとします。

## 通常開発

1. develop から feature/* を作り、実装します。
2. feature → develop の PR を作成します。Branch Policy の CI とレビューを通してマージします。
3. develop の CI が成功したことを確認します。DEV への配布はこの時点では行いません。

## 通常 Release

1. Release Manager がレビュー済み develop から `release/X.Y.Z` を作ります。版は既存のすべての vX.Y.Z より大きくします。
2. main の変更があれば release へ PR で取り込みます。候補への修正も PR で行い、CI を通します。
3. Azure Pipelines の Release を開き、対象の release ブランチを選び、手動起動します。初回だけ、PROD に既存アプリがなく vX.Y.Z Tag もないことを確認して `firstProductionRelease=true` を指定します。
4. Build → DEV → UAT が自動実行されます。Run ID・候補 SHA・UAT の `/api/health` を確認して UAT を行います。候補を変更したら新しい Run でやり直します。
5. UAT 担当者が受入結果と戻し先の Run ID を記録し、この Run を **Retain indefinitely** にします。release → main の PR を merge commit で完了し、ManualValidation を再開します。
6. PROD 承認者が UAT 証跡、main、戻し先、実施時間を確認して Service Connection の Approval を承認します。
7. 投入前確認 → staging 配布 → staging 確認 → 再確認 → swap → production 確認 → Tag → DR 配布・確認が進みます。ここまで main へ別 Release をマージしません。
8. `vX.Y.Z` の候補 SHA / Run ID / ZIP digest、PROD と DR の health を確認します。結果を記録し、main → develop を PR で反映します。成功した本番 Run は保持したままにします。

main マージ時に競合解決や追加修正が必要なら、その内容を先に候補へ反映し、**再 Build・DEV・UAT** を行います。UAT 後の main だけを修正して既存 Artifact を配布することはできません。

## Hotfix

現在の PROD と main が対応していることを確認し、Release Manager が main から `hotfix/X.Y.Z` を作ります。修正 PR / CI を通し、**通常 Release と同じ Pipeline・UAT・PROD 承認・Slot 手順**を使います。

進行中の通常 Release がある場合はキャンセル/却下してから Hotfix を開始します。UAT のロックを承認で無理に抜けません。完了後、main を develop と継続する release へ PR で取り込み、通常 Release は新しい Run で再検証します。古い Run の再開は禁止です。

main に未配布の通常 Release が既にマージされている場合、main から Hotfix を作るとその変更も含まれます。先に担当者が取り扱いを決め、未配布変更を PR で戻して PROD と整合させるか、その変更を含む配布を承認します。履歴の自動修復や force push は行いません。

## 再実行の判断

| 対象 | 再実行方法 |
| --- | --- |
| CI / Build の失敗 | 原因修正後に新しい Run。Release Artifact 発行済みの Build は再実行しない |
| DEV | コード・候補が同じなら同じ Run の DEV Stage を再実行。次に UAT を実施 |
| UAT | 配布/設定の一時障害なら同じ Run の UAT Stage を再実行し、受入も再実施 |
| PROD Approval の期限切れ | PROD ジョブが一度も動いていないことを確認。新 Run を開始する方針を基本とする |
| Promote の開始後 | Stage 全体を再実行しない。下記の復旧手順で、必要な操作だけを行う |
| DR のみ失敗 | 現在の PROD に対応する保持済み ZIP を確認し、DR 同期だけを行う |

新 Run は別 Build です。再 Build したものを「UAT 済みの同じ Artifact」と扱いません。並行する候補の確認を妨げないよう、DEV/UAT の再実行も Release 担当者が調整します。

## 復旧前の共通確認

1. インシデント責任者が復旧方針と操作を承認します。該当 Run と、待機中を含む他 Release を止め、Azure 側の deploy/swap が終了したことを確認します。
2. 現在の PROD・staging・DR の health、Azure Activity Log、Pipeline の最終成功タスクを確認します。タイムアウトやキャンセルは「何も変更されていない」という意味ではありません。
3. 対象の **元 Release Run** から `release` Artifact をダウンロードします。失敗 Run に PROD 成功が含まれる場合もあります。選択した Run の branch / SHA / Run ID と、Tag の記録を照合します。`latest` で選びません。
4. DB/schema・外部連携・非同期処理との後方互換性を確認します。戻せないデータ変更がある場合は、アプリの逆 swap だけで復旧しません。
5. PE に届く承認済み管理端末から、期限付き・対象 App に限定した運用者権限で実行します。**手動 CLI は Pipeline の Approval / Exclusive lock の対象外**なので、作業票・別担当の承認とリリース停止を必須とします。常用の管理者 PAT は使いません。

ARM 操作前は `az login --tenant <tenant-id>` と `az account set --subscription <subscription-id>` で対象を明示し、`az account show` で確認します。環境ごとに Subscription が異なる場合は切り替えます。接続できないことを理由に Public access や証明書検証を無効化しません。

以下は新方式の Artifact 用です。`ARTIFACT_DIR` に展開した ZIP と release.json を置きます。各値はダウンロードした JSON を盲信せず、Azure DevOps の元 Run 画面から転記します。

```bash
export ARTIFACT_DIR=/absolute/path/to/downloaded/release
export RELEASE_BUILD=true
export BUILD_SOURCEBRANCH=refs/heads/release/1.2.3  # 元 Run の branch（hotfix の場合もある）
export BUILD_SOURCEVERSION=REPLACE_WITH_ORIGINAL_40_CHARACTER_SHA
export BUILD_BUILDID=REPLACE_WITH_ORIGINAL_RUN_ID
export PROD_APP=REPLACE_WITH_PROD_APP
export PROD_GROUP=REPLACE_WITH_PROD_RESOURCE_GROUP
export PROD_URL=https://REPLACE_WITH_PROD_HOST
export STAGING_URL=https://REPLACE_WITH_STAGING_HOST
export DR_APP=REPLACE_WITH_DR_APP
export DR_GROUP=REPLACE_WITH_DR_RESOURCE_GROUP
export DR_URL=https://REPLACE_WITH_DR_HOST

# このリポジトリの保護された main のツールを使用する。
python3 pipelines/scripts/artifact.py verify "$ARTIFACT_DIR"
```

## PROD が正常、Tag だけ失敗

**再配布・swap は行いません。** 元 Run の本番確認成功ログを保存し、現在の PROD も同じ Artifact であることを確認します。

```bash
python3 pipelines/scripts/smoke.py "$PROD_URL" "$ARTIFACT_DIR/release.json" prod
git fetch origin --tags
git tag --list "v${BUILD_SOURCEBRANCH##*/}"
```

既に Tag があれば `git show vX.Y.Z` で候補 SHA・注釈の Run ID と digest を照合します。一致すれば作成済みとして扱い、**変更・削除しません**。不一致なら調査します。Tag がない場合のみ、承認された Create tag 権限を持つ運用者が以下を実行します。

```bash
export SYSTEM_COLLECTIONURI=https://dev.azure.com/REPLACE_WITH_ORGANIZATION/
export SYSTEM_TEAMPROJECTID=REPLACE_WITH_PROJECT_ID
export BUILD_REPOSITORY_ID=REPLACE_WITH_REPOSITORY_ID
az login --tenant REPLACE_WITH_TENANT_ID --allow-no-subscriptions
python3 pipelines/scripts/promote.py tag "$ARTIFACT_DIR"
```

API の応答が不明な場合も先に遠隔 Tag の存在を確認します。Tag ができたら必要に応じて次の DR 同期を行います。

## PROD が正常、DR だけ同期したい

現在の PROD と同じ保持済み Run を選びます。古い失敗 Run をそのまま使いません。本番操作が停止中であることを再確認します。

```bash
python3 pipelines/scripts/artifact.py verify "$ARTIFACT_DIR"
python3 pipelines/scripts/smoke.py "$PROD_URL" "$ARTIFACT_DIR/release.json" prod
az webapp deploy --resource-group "$DR_GROUP" --name "$DR_APP" \
  --src-path "$ARTIFACT_DIR/webapp.zip" --type zip
python3 pipelines/scripts/smoke.py "$DR_URL" "$ARTIFACT_DIR/release.json" dr
```

元の成功 Tag と Artifact が対応していることも確認します。Rollback 後は復元した旧版の Run/Tag を使います。DR 完了まで非同期にずれた状態であることを記録します。

## Rollback：保持済み旧 ZIP の再配布を標準にする

標準の戻し方は **承認済み旧 Artifact を staging へ配布 → 確認 → swap → production 確認**です。staging に残っている内容を推測せず、戻し先を明示できます。復旧する旧 Run に共通設定の branch / SHA / Run ID / ARTIFACT_DIR を切り替えます。Git から再 Build しません。

```bash
python3 pipelines/scripts/artifact.py verify "$ARTIFACT_DIR"
az webapp deploy --resource-group "$PROD_GROUP" --name "$PROD_APP" --slot staging \
  --src-path "$ARTIFACT_DIR/webapp.zip" --type zip
python3 pipelines/scripts/smoke.py "$STAGING_URL" "$ARTIFACT_DIR/release.json" prod-staging
az webapp deployment slot swap --resource-group "$PROD_GROUP" --name "$PROD_APP" \
  --slot staging --target-slot production
python3 pipelines/scripts/smoke.py "$PROD_URL" "$ARTIFACT_DIR/release.json" prod
```

緊急時、staging の health が戻し先 Artifact と完全一致し、DB 互換性も確認できる場合に限り、旧 ZIP の配布を省略して上記の swap を実行できます。これが逆 swap です。staging を誰かが上書きしていたり、確認できなければ省略しません。

swap 前の障害では production が変わっていなければ戻す操作は不要です。swap の成否不明時は両 Slot を確認してから決めます。自動で逆 swap する処理はありません。

復旧後に DR を同期し、戻した Run ID と時刻を記録します。過去の Tag は成功実績であり「今動いている版」のポインタではありません。Tag の付け替えは行いません。main が新しい版のままであれば、revert / Hotfix の PR で整合を戻し、次は過去の全 Tag より大きいバージョンを使用します。
