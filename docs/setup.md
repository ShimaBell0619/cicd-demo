# 設定

## 対象とPipeline

Azure DevOps: [shimaoka0619 / cicd-demo](https://dev.azure.com/shimaoka0619/cicd-demo)。実行Repoは`cicd-demo`、ソースの正本は[GitHub](https://github.com/ShimaBell0619/cicd-demo)。専用RGは`rg-cicd-selfhosted-jpw`、Japan West。保持環境のため削除期限や自動削除は設定しない。

| Pipeline | 定義 | 実行場所 / 起動 |
|---|---|---|
| CI（既存） | `pipelines/ci.yml` | Hosted。develop / main / release / hotfixのpush |
| Infra（ID 16） | `pipelines/infra.yml` | Self-hosted。mainから手動 |
| Release（ID 17） | `pipelines/release.yml` | BuildはHosted、配布はSelf-hosted。release / hotfixから手動 |
| Recovery（ID 18） | `pipelines/recovery-selfhosted.yml` | Self-hosted。手動、元Runを明示指定 |

Pipelineを新規に作る場合もYAMLパスを指定し、必要な接続・Pool・Environmentだけに認可する。旧PipelineのIDや旧PoCの接続名を流用しない。

## WIFと最小権限

環境別にManaged IdentityとWIF Service Connectionを分離する。信頼先は当該Azure DevOps接続に限定し、client secret・秘密鍵・PATを作成・保存しない。

| Service Connection | 権限の範囲 | 通常運用で必要なPipeline |
|---|---|---|
| `sc-cicd-sh-infra` | 専用RGだけのContributor | Infra 16 |
| `sc-cicd-sh-dev` | DEV AppだけのWebsite Contributor | Release 17 |
| `sc-cicd-sh-uat` | UAT AppだけのWebsite Contributor | Release 17 |
| `sc-cicd-sh-prod` | PROD Appと配下slotのWebsite Contributor | Release 17 / Recovery 18 |
| `sc-cicd-sh-dr` | DR AppだけのWebsite Contributor | Release 17 / Recovery 18 |
| `sc-cicd-sh-tags` | Azure Reposの対象RepoだけRead / Create tag、ProjectのView project-level information。Azure RBACなし | Release 17 |

`Grant access permission to all pipelines`は無効にする。Tag IdentityへContribute、Build管理、Project管理、Readersグループ所属を追加しない。Project Build ServiceにはRepo読取と保持Artifact取得に必要な範囲を与え、Tag書込は専用WIFで行う。

RecoveryはTagを読み取って照合する。Repo読取と元RunのBuild / Artifact参照が必要。失敗したRunも、PRODとTagが完了した元Artifactであれば候補とするため`allowFailedBuilds: true`を使用し、成功扱いへの書換えは行わない。

## Agent PoolとVM

- Pool: `cicd-selfhosted-linux`（ID 12）。全Pipeline許可を無効化し、通常運用では16 / 17 / 18だけを認可する。
- Agent: `vm-cicd-sh-agent`、Linux、検証時5.279.0。YAMLのdemandsでOSとAgent名を固定する。
- VM: Ubuntu 24.04、Standard_B2s。非root `cicdagent`サービス。Azure CLI、Python 3.11以上、Gitなど配布に必要なツールだけを用意する。
- VMに配布用Managed Identityを割り当てない。VMのSystem-assigned Identityは登録用で、Azure RBACなし。Pool登録権限を登録後に除去する。
- 登録時は短期Entra tokenをメモリ内で渡す。Agent設定CLIの`--auth PAT`は入力方式の名称であり、この手順ではPATを発行しない。継続通信に使う標準OAuth資格情報・署名鍵はVM内で保護する。
- Internetからの受信を拒否し、管理はBastion Developerを使用する。配布先はPublic App Service / SCM。Private EndpointとPrivate DNSは作成しない。
- 各配布Jobは`workspace.clean: all`とclean checkoutで始め、指定Artifactをダウンロードする。Agent更新や管理者のVM操作は運用責任者に限定する。

VMとBastionの初期構築は[infra](../infra/README.md)を参照。Infra PipelineはApp Serviceだけを管理し、Agentを再登録しない。

## Environment・承認・Checks

| 対象 | 設定する制御 |
|---|---|
| `sh-dev` | Releaseだけに認可。Exclusive lock |
| `sh-uat` | Releaseだけに認可。Exclusive lock。UAT配布とManualValidationを同一Stage内に置く |
| `sh-prod` | Release / Recoveryだけに認可 |
| `sh-dr` | Release / Recoveryだけに認可。Exclusive lock |
| `sc-cicd-sh-prod` | ApprovalとExclusive lock。Promote / Recover Stage終了まで保持 |

配布用Checksでは許可ブランチを`refs/heads/release/*` / `refs/heads/hotfix/*`に限定する。Recoveryの実行ブランチもこの範囲とし、`main`から起動する場合はChecksの変更が別途必要。YAMLの`lockBehavior: sequential`だけではExclusive lockは有効にならないため、Azure DevOps側のChecksと併せて設定する。

UAT承認者は`release.yml`の`uatApprovers`、PROD承認者は接続のChecksで設定する。**今回の専用検証環境だけ本人承認を許可済み**。本番化では自己承認を禁止し、別承認者と代行者を設定する。

GitHubのmainをPR経由で保護し、必要なレビュー・Build確認を設定する。ミラー先で直接編集しない。2026-10-04のAzure Repos Branch Policyは0件で、一般開発者の編集拒否や複数人承認は実証していない。

## この整理で変更していない外部設定

GitHub上の権限試験用YAMLを削除しても、Azure DevOpsの試験定義19 / 20や試験用の個別認可は自動削除されない。検証時にはPoolに20、DEV接続に20の追加認可があった。通常運用表との差分は[残課題](selfhosted-validation.md)に記載し、Azure DevOps側の整理対象とする。
