# 導入設定と PoC

この設定は実装の一部です。接続名を置き換えるだけで本番運用を開始しないでください。対象は Azure DevOps **Services** です。

## 1. Pipeline と実行者

| 名前 | YAML | Queue 権限 |
| --- | --- | --- |
| CI | `pipelines/ci.yml` | 開発者、Branch Policy |
| Release | `pipelines/release.yml` | Release Managers のみ |

通常の開発者と Project Build Service に、Release の Queue/Edit、Checks/Service Connection/Agent Pool の管理権限を与えません。Pipeline 定義の YAML パス変更もインフラ管理者だけにします。Classic Pipeline は無効化します。

`release.yml` 冒頭の `REPLACE_WITH_*` を変更します。Service Connection 名は下表に合わせて作成します。Queue 時の変数上書きは許可しません。

## 2. ブランチと必須レビュー

| 対象 | 必須設定 |
| --- | --- |
| develop / main / release/* / hotfix/* | PR 必須、CI Build validation、作成者以外の承認、変更時の票リセット、未解決コメント禁止 |
| 同じ全対象 | `/pipelines/*;/tests/*` の変更にインフラ担当者の必須レビュー。必須レビューを単なる自動追加にしない |
| main | Release 候補の履歴を残す merge commit。squash/rebase は使わない |
| release/* / hotfix/* | **Release Managers だけが作成可能**。それぞれレビュー済み develop / main から作成。その後の変更は PR |
| 通常の開発者 | feature/* にブランチを作成。保護対象への直 push、Force push、Policy bypass、Policy/権限変更は禁止 |

Branch Policy は prefix スコープで `release/` と `hotfix/` にあらかじめ設定します。「Branch control が protected と判定した」だけではレビュー済みの証拠になりません。新規ブランチの最初の commit は PR を経ずに作成できるため、**作成権限と作成元のルールが必要**です。

フォルダ単位の CreateBranch 権限は Microsoft の [設定手順](https://learn.microsoft.com/en-us/azure/devops/repos/git/require-branch-folders?view=azure-devops) に従います。一般開発者は feature/、Release Managers は release/ と hotfix/ を許可します。作成者に自動付与される Force push / Manage permissions も確認し、候補では外します。Release Managers に常用の Policy bypass を付けません。

main へのマージから DR 完了までは別 Release/Hotfix の main マージを行いません。急ぐ Hotfix が入る場合は進行中の通常 Release をキャンセルし、作業中の Azure Task が終了したことを確認して引き継ぎます。この短い凍結期間は運用ルールです。

## 3. Agent と資格情報

| 種類 | 利用 Pipeline | 設定 |
| --- | --- | --- |
| Microsoft-hosted `ubuntu-24.04` | CI / Release の Build | ジョブごとに破棄。Azure 配布権限・本番 Managed Identity・PE 経路なし |
| `deploy-private-linux` | Release のみ | 別ホスト。Python 3.11+、Git、Azure CLI、タスクの前提ソフトを導入。npm / アプリのテスト・Build は実行しない |

Deploy Pool は Open access を無効化し、Release だけを許可します。Branch control は `refs/heads/release/*,refs/heads/hotfix/*`、Require branch protection を有効、保護状態が不明なら拒否にします。CI を許可しません。Pool の User 権限も管理者に限定し、他 Pipeline を勝手に認可できないようにします。

Project Settings で job authorization scope を現在の Project に制限し、Protect access to repositories in YAML pipelines を有効化します。Project Build Service は対象 Repo の **Read のみ**とし、Contribute / Create tag / Force push / Policy bypass / Release の Queue/Edit を与えません。`System.AccessToken` を環境変数としてアプリ Build に渡しません。

Deploy ホストに常設の広い Managed Identity / PAT / Azure CLI ログインを残しません。Azure タスクの Service Connection で必要時に認証します。App 自体の Managed Identity に CI/CD 管理権限を付与しません。

## 4. Service Connection と Environment

| Service Connection | 権限・Checks |
| --- | --- |
| `sc-cicd-dev` / `sc-cicd-uat` / `sc-cicd-dr` | 環境ごとの ARM WIF。各 Web App に必要な範囲だけ。Release のみ認可、Branch control |
| `sc-cicd-prod` | PROD Web App と Slot に必要な ARM WIF。Release のみ認可、Branch control、**人間の Approval（自己承認不可）と Exclusive lock** |
| `sc-cicd-tags` | 専用 Entra 身元の Azure DevOps WIF 接続。対象 Repo の Read / Create tag のみ。Release のみ認可、Branch control |

全接続で Grant access to all pipelines を無効にします。Branch control は Deploy Pool と同じ許可ブランチ・保護必須・不明時拒否です。Azure RBAC は Web App 単位の Website Contributor を出発点に PoC で検証し、必要なら操作を絞った Custom Role とします。Subscription Contributor / Owner は不要です。

**PROD の Approval は Environment だけでなく Service Connection 自体に置きます。** これにより `environment: prod` を YAML から外したジョブも、接続の承認なしで本番へ配布できません。承認者は UAT、SHA/Run ID、main、戻し先 Run、初回配布オプション、メンテナンス時間を確認します。

`sc-cicd-tags` の身元を Azure DevOps に登録し、タグ作成以外の branch 書込み、Force push、タグ変更/削除、Policy bypass を許可しません。Project Build Service にタグ権限を追加して代用しません。`AzureCLI@3` と Azure DevOps WIF 接続の利用可否を初回 PoC で確認します。

Environment は `dev / uat / prod / dr` をあらかじめ作成し、Release だけに許可します。dev・uat・dr に Exclusive lock を設定します。prod の排他の基点は **sc-cicd-prod** です。YAML の `lockBehavior: sequential` とセットで使用します。

UAT Stage は ManualValidation まで同じロックを持ち、Promote Stage は PROD 配布・Tag・DR まで同じ本番ロックを持ちます。Checks は Stage 開始時にその Stage の全リソースについて評価されるため、DR 接続の認可不備も PROD 開始前に解消する必要があります。Pipeline のロックは Portal/CLI の手動操作を止めません。復旧操作時の調整は Runbook に従います。

Required Template / extends は使用しません。保護された候補、必須インフラレビュー、ブランチ作成権限、リソース側 Checks を信頼境界とします。多くのチームへ共通ポリシーを強制する段階になった場合だけ再検討します。

## 5. App Service と Private Endpoint

Linux / Node.js 22 を使用します。通常配布は ZIP Deploy、Build-on-deploy は無効です。`SCM_DO_BUILD_DURING_DEPLOYMENT=false`、既存の Oryx 自動 Build も無効にします。環境固有値は App Settings に入れ、環境ごとの `NEXT_PUBLIC_*` を Build に埋め込みません。native module がある場合は Build/App Service の OS・CPU・libc 互換性を検証します。

| 配布先 | APP_ENV |
| --- | --- |
| DEV | dev |
| UAT | uat |
| PROD production | prod |
| PROD staging | prod-staging |
| DR | dr |

PROD の `APP_ENV` は **deployment slot setting** にします。DB 接続・秘密情報・外部接続先の slot 固定方針も確認します。自動 swap は無効化します。App Service の warm-up path と application health の役割を区別し、`/api/health` が匿名の内部監視で読み取れることを確認します。Easy Auth を使用する場合は監視経路の認証/除外を設計し、ログイン画面への redirect を成功扱いにしません。

Deploy Agent から各 App / SCM(Kudu) の名前解決と TCP/443 を確認します。**PROD staging は production と別の Private Endpoint と DNS 設定が必要**です。通常の `azurewebsites.net` のホスト名を使い、Private DNS により PE へ解決します。ARM・Entra・Azure DevOps・Pipeline Artifact への外向き通信も許可します。

## 6. 保持・移行・本番 PoC の完了条件

UAT を受け入れた担当者が **同じ Release Run** を `Retain indefinitely` にします。担当者にはその操作権限を付与し、保持解除には運用管理者の判断を必要とする運用ルールを設けます。少なくとも現在の PROD/DR と承認済み戻し先 Run を保持し、復旧演習と保存期間の合意までは成功した本番 Run を解除しません。通常 CI の保存は Project の標準 Retention に任せます。Pipeline/Run 削除の権限は運用管理者に限定します。長期監査や別障害ドメインのバックアップが必要なら外部保存を別途設計します。

旧4本の定義・Required Template Checks・旧 Pool 認可を、稼働中 Run の終了後に廃止します。旧 Release Artifact は保持し、旧 manifest と新 `release.json` を混在させません。既存 Run は旧版 Runbook で復旧し、新 Pipeline へ暗黙に読み替えません。新コードを PR で develop へ反映してから新 release/* を作ります。

- [ ] `REPLACE_WITH_*`、5接続、2 Pipeline、Deploy Pool、4 Environment の設定を完了
- [ ] 新 YAML を Azure DevOps でコンパイルし、パラメータ・タスク入力・Approval の順序を確認
- [ ] PR/feature から Deploy Pool / 各接続を使おうとして拒否されることを確認
- [ ] 一般開発者の release/hotfix 作成、必須インフラレビューの迂回を拒否
- [ ] Environment を省略したタスクでも sc-cicd-prod の Approval が効くことを確認
- [ ] Build Service のタグ作成を拒否し、タグ専用身元は作成だけできることを確認
- [ ] UAT の人間の確認中に別候補を配布できないことを確認
- [ ] PROD → Tag → DR の間、別 Run が sc-cicd-prod のロックを取得できないことを確認
- [ ] 全 App/SCM/Slot の PE/DNS/認証、slot 固定設定、swap 前後の健康確認を実測
- [ ] 初回配布、通常 Release、Hotfix、古い UAT 候補の拒否を確認
- [ ] Run 保持後の Artifact ダウンロード、Tag と Run/ZIP の対応を確認
- [ ] swap 失敗/応答不明、Tag 失敗、DR 失敗、旧 ZIP 再配布の復旧演習
- [ ] RTO/RPO、DB 互換性、承認担当/代行者、保存期間、Azure RBAC を合意

## 公式仕様

- [Approvals / Branch control / Exclusive lock](https://learn.microsoft.com/en-us/azure/devops/pipelines/process/approvals?view=azure-devops)
- [Branch Policies](https://learn.microsoft.com/en-us/azure/devops/repos/git/branch-policies?view=azure-devops)
- [Branch security と作成者の権限](https://learn.microsoft.com/en-us/azure/devops/repos/git/branch-permissions?view=azure-devops)
- [Job token / Repo access](https://learn.microsoft.com/en-us/azure/devops/pipelines/security/secure-access-to-repos?view=azure-devops)
- [ManualValidation](https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/manual-validation-v1?view=azure-pipelines)
- [AzureCLI@3](https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/azure-cli-v3?view=azure-pipelines)
- [Retention](https://learn.microsoft.com/en-us/azure/devops/pipelines/policies/retention?view=azure-devops)
- [App Service Private Endpoint](https://learn.microsoft.com/en-us/azure/app-service/overview-private-endpoint)
- [Deployment slots](https://learn.microsoft.com/en-us/azure/app-service/deploy-staging-slots)
