# S1 / Public / Microsoft-hosted の当日PoC

## 2026-10-04 の条件

- Subscription: study-02 / `82615ba2-5bd4-401d-b054-50df1e0e0333`。
- Region / Group: Japan West / `rg-cicd-demo-poc-jpw`。
- S1 PlanをDEV/UAT/PROD/DRとPROD stagingで共有する。
- Build once、同一RunのZIP、UAT受入、mainの内容一致、PROD承認、staging smoke、swap、production smoke、注釈Tag、DRを検証する。
- 起動者本人によるUAT/PROD承認を今回だけ許可する。自動承認・承認省略は行わない。本番の自己承認禁止の設計は `setup.md` を参照する。
- Azureリソースを当日削除する。Azure DevOpsのRun/Artifact/タグ・検証記録は保持する。

## 接続の境界

| 接続 | Identityの権限 | 許可Pipeline |
| --- | --- | --- |
| sc-cicd-infra | PoCグループのみContributor | Infraのみ |
| sc-cicd-dev/uat/prod/dr | 対象Web AppのみWebsite Contributor | Releaseのみ |
| sc-cicd-tags | 対象Azure RepoのみRead/Create tag、Azure管理権限なし | Releaseのみ |

IdentityはPoCグループ内のUser-assigned Managed Identityとし、WIFで接続する。全PipelineへのOpen accessは許可しない。prod接続は人間のApprovalとExclusive lock、dev/uat/dr環境はExclusive lockを使用する。Branch controlの許可候補はrelease/hotfix、Infraはmain。承認・接続の権限境界を本番対応済みとするには `setup.md` の追加検証が必要。

今回のBranch controlは許可ブランチ名を検証し、branch protectionの必須化は行わない。GitHubからのミラーを使う個人PoCの条件であり、必須レビュー・保護必須・一般開発者の権限拒否の本番検証は未実証として記録する。配布処理にはResource Groupを明示し、Subscription全体のリソース探索を行わない。

## 実行順

1. Bicepのvalidate/what-ifを実行し、専用Groupをbootstrapする。
2. InfraをMicrosoft-hostedで実行し、構成と生成された名前/URLを保存する。
3. レビューした変更をdevelopへ反映し、release/1.0.0を作る。
4. 初回配布オプションを指定してReleaseを手動実行する。
5. DEV/UATのhealthからversion/SHA/Run IDを確認する。
6. 本人がUATを受け入れ、Runを保持し、候補をmainへmerge commitで反映してManualValidationを再開する。
7. 本人がprod接続を承認する。
8. stagingとPRODのidentity、swap後のAPP_ENV、TagのSHA/注釈、DRの同一identityを確認する。
9. 検証記録を保存してPoCグループを削除する。`az group exists`がfalseになることを確認し、仮設接続とIdentityのAzure DevOps登録を片付ける。

未実行の失敗系・Hotfix・Rollback演習を成功扱いにしない。初回の通常ルートを実測した後、当日の残り時間に合わせて実施記録を追加する。
