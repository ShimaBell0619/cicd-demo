# Gitフロー検証用Pipeline

既存のCI／Release／Recoveryと共通処理をコピーし、アプリケーションCI/CD方式設計のGitフローを検証するために変更した。既存の`pipelines/`、アプリケーション、IaCは変更しない。

## 検証範囲

- Azure ReposのPR・Branch Policy、UAT受入、mainへの手動Merge、PROD承認、Merge Commitへの自動Tag付与を検証する。
- アプリケーションBuildとPipeline Artifactの登録・取得は実行する。各環境で同じArtifactを使用し、mainへのMerge後にRelease用の再Buildは行わない。
- DEV／UAT／PROD staging／DRへの配布、Slot Swap、Rollbackはログによる模擬処理とする。Azureの実デプロイ、Slot操作、HTTP確認、アプリケーションの自動テストは行わない。
- Self-hosted AgentのPool指定とAzureタスクは無効化し、AgentジョブはMicrosoft-hosted Ubuntuで実行する。承認・main Merge完了待ちはAgentを使わないジョブで待機する。
- mockのUAT承認はGitフロー確認用であり、実アプリケーションの業務受入やSlot動作を実証するものではない。

## 検証用Azure Repos

同じAzure DevOpsプロジェクトに、同期対象外の`cicd-demo-mock`を作成し、本リポジトリのコードを初期コピーする。検証中のPR・Commit・TagはこのRepoだけで作成する。全mock PipelineはRepo名とAzure Reposであることを確認し、元の`cicd-demo`では実行を拒否する。

既存の同期先Repoに直接mainへのPR Mergeを行うと、元Repoと履歴が分岐して同期が停止するため、この検証では使用しない。検証Repoへの継続ミラーは設定しない。

## Pipeline登録

| 検証Pipeline | YAML | 起動・役割 |
|---|---|---|
| mock CI | `pipelines-mock/ci.yml` | develop／main向けPRのBuild検証、develop Merge後のBuild・mock DEV反映、任意ブランチからの手動Build・mock DEV反映 |
| mock Release | `pipelines-mock/release.yml` | release／hotfixから手動。UAT → main Merge → PROD承認 → mock Swap →実Tag → mock DR |
| mock Recovery | `pipelines-mock/recovery.yml` | mainから手動。Rollback承認 → mock Slot再Swap。Build・Artifact再配布・Tag作成は行わない |

1. 検証Repoのmain／developに、mock CIのBuild validationとPRレビューのBranch Policyを設定する。Merge方式はMerge commitのみとする。1名での検証ではPRレビューを本人が行える設定とし、顧客環境の承認者分担の検証とは区別する。
2. Release実行時に`uatApprovers`と`prodApprovers`を指定する。Recoveryでは`rollbackApprovers`を指定する。既定値は既存PoCの検証者であり、全承認で本人による検証を許可する。通知メールは送信しない。
3. 検証Repoに対する対象Build Service IdentityのRead／Create tag権限を確認する。Pipelineは`System.AccessToken`を使う。専用Tag ID、Azure Service Connection、PATは使用しない。

インフラPipelineはコピー・登録しない。既存の本番用Service Connection・Environment・Agent Poolも使用しない。このmockでは、それらのWIF・接続・排他Checksを検証しない。

## Release／Hotfixの検証手順

1. `develop`から`release/vX.Y.Z`、または`main`から`hotfix/vX.Y.Z`を作成する。候補Commitを確定し、mock Releaseをそのブランチから手動起動する。
2. Build → Artifact登録 → mock DEV → mock UATを確認し、UAT受入を承認する。
3. Pipelineがmain Merge完了待ちに入った後、対象ブランチからmainへのPRをReposでレビュー・承認し、Merge commitで手動Mergeする。その後、Pipelineの完了待ちを再開する。この再開操作はPRのマージ承認ではない。
4. Pipelineは、ブランチと候補SHAが一致する完了PRを1件に特定する。PRの実Merge Commit、Merge方式と候補のソース内容一致を確認し、Merge Commit SHAとPR番号を当該Runの出力変数に保持する。
5. PROD承認後、同一Artifactのmock staging配布とmock Slot Swapを実行する。成功後、保持したmain Merge Commitへ`vX.Y.Z`の注釈付きTagを作成する。Tagメッセージにもmockであること、Run、候補SHA、Merge SHA、PR番号を記録する。
6. 同じArtifactのmock DR取得を確認する。必要な修正がdevelopに未反映の場合は、main → developのPRで同期する。

Git操作は実際に行うが、Tag作成の契機は模擬Swapの成功である。本番デプロイ完了の実証として扱わない。

## 確認するケース

| ケース | 期待結果 |
|---|---|
| 通常Release／Hotfix | 候補を一度Buildし、対象PRのmain Merge CommitへTagが付く |
| PR未完了・候補変更・取込結果の内容不一致 | PROD承認へ進まず失敗。変更が必要なら新しいRunでUATをやり直す |
| Squash／Rebase | Merge Commitの親情報が条件に合わず拒否 |
| UAT／PRODの否決・期限超過 | 後続処理を実行しない。検証用待機期間は120分 |
| SHA保持後にmainへ別Commitを追加 | Tagは最新HEADではなく、保持したMerge Commitに付く |
| `mockSwapResult=failed` | Tagもmock DRも実行されない |
| 同じRunでTag処理を再実行 | 既存Tagの付与先とRunが同じなら完了扱い。異なるTagは付け替えず拒否 |
| mainへのMerge | CIによる自動DEV反映を起動しない |
| Recovery | 承認後にmock再Swapのみ。実Azure操作・Artifact再配布・Tag変更なし |

## ローカル検証

Python 3.11以上とGitで`python3 -m unittest discover -s pipelines-mock/tests -v`を実行する。テストは一時Gitリポジトリで実Merge・注釈付きTagを作成し、Azure Repos API応答だけを模擬する。検証Repoへ接続・書き込みは行わない。

アプリケーションBuildにはNode.js 22を使用する。Azure PipelinesのYAML展開、認証、Branch Policy、承認画面は実機で別途確認する。ローカルテストの成功をAzure Pipelines上の検証成功とみなさない。

## 実施記録・再開位置（2026-10-07）

- ローカルGitフロー検証18件：成功。mainの後続更新、Tag再実行、誤ったMerge方式・候補・既存Tagの拒否を含む。
- Node.js 22による実アプリBuild、ZIP生成、Artifact識別・整合確認：成功。
- YAMLの構文と参照、ReleaseのBuild回数、PROD → DRの依存関係、Azureタスク・Self-hosted Poolの無効化：静的確認済み。
- Azure Pipelines実機検証：未実施。Azure DevOpsへのサインインが必要。

再開時は「検証用Azure Repos」「Pipeline登録」に従って専用Repoと3つのmock Pipelineを準備し、通常Releaseから確認する。実機のRun結果を確認した後、本節を更新する。既存Repo・既存Pipelineの変更は不要。
