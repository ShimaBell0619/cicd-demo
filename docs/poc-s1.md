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
| sc-cicd-dev/uat/prod/dr | 対象Web AppのみWebsite Contributor | Releaseのみ（drだけ当日限定復旧にも認可） |
| sc-cicd-tags | 対象Azure RepoのRead/Create tag、同ProjectのView project-level informationのみ。Azure管理権限なし | Release / 当日限定Tag・DR復旧のみ |

IdentityはPoCグループ内のUser-assigned Managed Identityとし、WIFで接続する。全PipelineへのOpen accessは許可しない。prod接続は人間のApprovalとExclusive lock、dev/uat/dr環境はExclusive lockを使用する。Branch controlの許可候補はrelease/hotfix、Infraはmain。承認・接続の権限境界を本番対応済みとするには `setup.md` の追加検証が必要。

今回のBranch controlは許可ブランチ名を検証し、branch protectionの必須化は行わない。GitHubからのミラーを使う個人PoCの条件であり、必須レビュー・保護必須・一般開発者の権限拒否の本番検証は未実証として記録する。配布処理にはResource Groupを明示し、Subscription全体のリソース探索を行わない。

## 実行順

1. Bicepのvalidate/what-ifを実行し、専用Groupをbootstrapする。
2. InfraをMicrosoft-hostedで実行し、構成と生成された名前/URLを保存する。
3. レビューした変更をdevelopへ反映し、release/1.0.0を作る。
4. 初回配布オプションを指定してReleaseを手動実行する。
5. DEV/UATのhealthからversion/SHA/Run IDを確認する。
6. 本人がUATを受け入れ、Runを保持し、mainと候補の内容一致を確認してManualValidationを再開する。本番はPRのmerge commitを使う。今回の使い捨てPoCでは、本人が許可した既存GitHub/Azure Reposへのmain/develop/releaseの直接同期を例外として用いる。
7. 本人がprod接続を承認する。
8. stagingとPRODのidentity、swap後のAPP_ENV、TagのSHA/注釈、DRの同一identityを確認する。
9. 検証記録を保存してPoCグループを削除する。`az group exists`がfalseになることを確認し、仮設接続とIdentityのAzure DevOps登録を片付ける。

未実行の失敗系・Hotfix・Rollback演習を成功扱いにしない。初回の通常ルートを実測した後、当日の残り時間に合わせて実施記録を追加する。

## 実測結果

- Infra Run 38: S1 / Public / stagingのvalidate・what-if・作成が成功。
- Release Run 43: Buildと13テスト、DEV/UAT配布、本人によるUAT受入・PROD承認、staging確認、swap、PROD確認が成功。Tagで停止したためRun全体の結果はFailed。
- Repo ACLだけではTag IdentityのProjectアクセス確認がVS800075で失敗。同ProjectのView project-level information 1項目について本人が追加許可し、Readers継承を外したまま付与した。
- Recovery Run 47: 元Runの識別値をTask envで渡す方法が効かず、事前検証で停止。スクリプト内exportへ修正。
- Recovery Run 49: Tag IdentityのWIFでv1.0.0を作成。API応答の短いTag名を検証側がref形式だけに限定していたため、作成後の検証がエラー。遠隔Tagは正しく存在し、変更・削除していない。
- promote.pyはTag名の短い形式/ref形式の双方を受け入れ、SHA/Run/digestの厳密な照合を維持。既存Tagを読み取り専用で検証するverify-tagを追加し、CI Run 50で15テストが成功。
- Recovery Run 51: 元Run43の保持済みZIPを再利用し、WIFで既存Tagを検証してDRだけ配布・確認。成功。PROD再配布・再swapは行っていない。
- 最終healthはDEV/UAT/PROD/DRのすべてHTTP 200、version=1.0.0、commitSha=5fb8464833440843e87d9705960b231e6772e202、buildId=43。
- swap後APP_ENVはproduction=prod / staging=prod-staging。slotSetting=trueを維持。
- v1.0.0の注釈はpipelineRun=43、sha256=4f6c330658b15c84d5e01944889630e798fee8e12cbef898f2f8c20ea2a7cb6e。専用Tag Identityが作成。
- Run 43のArtifactとRun 51の復旧ログは長期保持。ZIPを保存してSHA-256を再検証。
- Run 41: mainからの誤ったReleaseはBuildで拒否され、配布ステージはSkip。

[Run 43](https://dev.azure.com/shimaoka0619/cicd-demo/_build/results?buildId=43) / [復旧 Run 51](https://dev.azure.com/shimaoka0619/cicd-demo/_build/results?buildId=51)。Tag/DR限定の設定はrelease/1.0.0-recoveryブランチのpipelines/recovery-tag-dr.ymlにあり、Run 43専用。将来のReleaseでそのまま再利用しない。

DRは同一Plan・同一Regionへの配布一致検証。リージョン障害、Hotfix、Rollback、承認却下、一般開発者の権限拒否、競合Runの排他演習は未実施。本番構成の追加検証はsetup.mdを参照する。

## 当日削除

2026-10-04 18:09 JSTに専用グループの不存在を確認。S1 / 4 Apps / PROD staging / 6 Managed Identitiesを削除。該当IdentityのAzure RBAC残存は0、仮設Service Connectionは6件すべて削除。Tag用のRepo ACL / ProjectメタデータACL / Azure DevOps登録も削除した。Run / Artifact / Git履歴 / v1.0.0は保持する。再実行時はAzure構成と接続を再作成する。
