# CI/CD Self-hosted Linux Agent 検証台帳

2026-10-04 JST。前回のS1 PoCの続き。状態は「未実施」「実施中」「合格」「不合格」「未検証」で区別し、成功Runだけでなく拒否・失敗Runも記録する。

## 前回から引き継ぐ結果

- Run 43: 1.0.0の同一ZIPをDEV/UAT/PROD stagingへ配布し、確認後にswap。PROD正常、Tagで停止。
- Run 49: Tag作成済み。Run 51: 元Run 43のZIPとTagを照合し、PRODへの再配布・再swapなしでDR復旧に成功。
- 最新main/develop 3e3d8c3: 15テスト成功。mainからのRelease拒否は実測済み。
- 古いRG、6 Identity、6接続と仮設権限は削除済み。旧Artifactとv1.0.0の履歴は保持。
- Rollback、競合Run、Hotfix、承認却下、一般開発者の拒否は未実施。別リージョンDRとPrivate Endpointは今回の範囲外。

出典: [前回のS1検証](poc-s1.md)、[Run 43](https://dev.azure.com/shimaoka0619/cicd-demo/_build/results?buildId=43)、[復旧51](https://dev.azure.com/shimaoka0619/cicd-demo/_build/results?buildId=51)。

## 今回の構成と前提

- study-02 / Japan West / 新規専用RG `rg-cicd-selfhosted-jpw`。前回・SwitchBotのRGとは分離。
- S1 Linux 1 worker、DEV/UAT/PROD/DRとPROD staging。Public endpoint、APP_ENV sticky、ZIPの再Buildなし。
- Ubuntu 24.04 / Standard_B2sを1台、専用Pool `cicd-selfhosted-linux`。Infraと配布・復旧だけに使用。アプリのBuildは既存Microsoft-hostedで継続し、配布AgentではアプリコードをBuildしない。
- VM、Web App、Bastion Developerはユーザーの指示により残す。自動削除・当日期限は設けない。
- 6つのWIF接続 `sc-cicd-sh-{infra,dev,uat,prod,dr,tags}`。Infra=専用RG Contributor、各配布=対象App Website Contributor。Tag=当該Repo Read/Create tagとProject情報参照だけ。
- 各WIF IdentityはVMに割り当てない。VMの登録用IdentityはAzure RBACなし、専用Poolの登録時だけ権限を持ち、登録後に除去。
- Poolと接続の全Pipeline許可=false。新規Infra/Release/復旧に必要な接続だけを認可。旧Pipeline/CIには認可しない。
- VMのインターネットからのSSHを閉じ、Bastion Developer経由で管理する。初期管理パスワードはファイル・Repo・ログに保存せず、利用者はAzureのパスワードリセットで設定する。
- UAT受入とPROD Approvalは維持。使い捨てではないが専用検証環境での本人承認・予定した承認/却下操作の扱いは、実行前に人間の判断を記録する。

## 優先順位、検証方法、完了条件

| ID / 優先 | 検証項目 | 方法 | 完了条件 | 状態 / 証跡 |
|---|---|---|---|---|
| A01 / P0 | 実Agentへの切替 | 専用Pool/VMでInfraと4環境の配布・swap・Tag/DRを実行。各JobのAgent名、OS、バージョン、WIF Taskログを確認 | 配布/Infra Jobが指定Linux Agentで実行。PAT/接続secretなし。Microsoft-hostedはBuildだけ | 未実施 |
| A02 / P0 | 接続・Poolの閉鎖と環境分離 | 全許可=false/個別認可一覧を保存。未認可PipelineでPool/接続を参照。DEV WIFでUAT/PROD/VMの読取を試す | 未認可参照がJob開始前に拒否。DEVが他App/VMにアクセスできない。Infra/各App/Tagの権限が指定scopeと一致 | 未実施 |
| A03 / P0 | Agent残留認証と作業領域 | 登録用Identityの権限除去、VMに配布Identityがないこと、clean:all、AzureCLI Task後のキャッシュとgit資格情報を確認 | 登録用権限が残らず、次Jobで前JobのWIF接続が使えない。成果物は毎回選択Runから取得 | 未実施 |
| B01 / P0 | 復旧/戻し先の基準作成 | 保持済み旧Run 43 ZIPを専用環境へ初期化。Tagを読取照合し、次の新Releaseを1回通す | 旧1.0.0と新1.1.0の両Artifactが保持され、元Run/branch/SHA/digest、現在PROD/DRを照合できる | 未実施 |
| C01 / P1 | UATの競合・排他 | 通常Release AがUAT受入待ちの間にBを起動し、Bのチェック状態とUAT healthを観測。Aを却下/中止してBの進行を観測 | BがExclusive lock待ち。Aの受入中にUATを書換えない。終了後のみBが進む。単なるAgent順番待ちとは区別 | 未実施 |
| C02 / P1 | PRODからDRまでの排他 | テスト用チェックポイントでAをPROD確認後/DR前に保持し、BをPromoteへ進めてチェックを観測 | Bが同じPROD接続のExclusive lock待ちでstaging/swapを開始しない。AのDR終了後に限り解除 | 未実施 |
| D01 / P1 | UAT却下 | 実際のManualValidationを却下 | UAT失敗、Promote/Tag/DRはSkip、PRODの識別値とswap履歴が不変 | 未実施 |
| D02 / P1 | PROD却下 | UAT受入後、PROD接続Approvalを却下 | PromoteのAzure Jobが動かず、staging/PROD/DR/Tagに変更なし | 未実施 |
| E01 / P1 | Hotfix | 保留通常Releaseを止め、現在mainからhotfix/1.1.1を作る。同じRelease/承認/slot手順を通し、main/develop/継続候補へ同期 | 通常候補が停止。Hotfixだけが承認後に配布/Tag/DR完了。旧Runを再開せず、新候補で再検証する | 未実施 |
| F01 / P1 | 旧ZIPによるRollback | 2版の配布後、指定旧RunのZIPを再Buildせずstaging→smoke→swap→PROD smoke→DR同期。新Tagは作らない | PROD/DRが旧version/SHA/buildId、ZIP digestは元Runと一致。新旧Tag不変。swapは1回 | 未実施 |
| G01 / P1 | DR失敗後の安全な復旧 | 専用検証RunでDR直前に意図的停止/失敗を入れ、PROD/Tag成功・DR旧版の証跡を保存。復旧でその元ZIPだけDRへ配布 | PROD再配布/再swap=0、Tag変更=0。DR一致。全Promote再実行は使用しない | 未実施 |
| G02 / P1 | 誤った復旧Artifact/再実行を拒否 | DR-onlyに現在PRODと異なる旧Runを指定。Rollbackで誤った現PROD Runを指定。StageAttempt>1で既存guard確認 | 事前照合で停止しAzure書込なし。必要な操作だけ再開できる | 未実施 |
| H01 / P2 | Artifact破損・欠損時の停止 | 元ZIPの複製だけを改変/欠損させ、既存verifyを実行 | digest/identity検証で配布前に停止。元ZIPは保持 | 未実施 |
| H02 / P2 | Agent停止・再開 | 配布前のAgentを停止してJob待機/キャンセル、起動して次Jobを実行 | 待機中にAzure変更なし。再起動後のAgent識別と認証が正常。処理中swap障害は別ケースとして残す | 未実施 |
| H03 / P2 | 本番の運用権限/ブランチ保護 | 現行ACL/Policyを読取監査。人間の一般開発者アカウントがある場合だけ拒否を実測 | 実測と設定監査を区別。Release/Checks/Pool編集、PR保護と複数人承認の未検証を明記 | 未実施 |

## 実施順と証跡の扱い

1. A01〜A03とB01。接続/Poolの否定試験が通るまでPROD昇格へ進めない。
2. C01 + D01 + E01を同じ保留候補で組み合わせ、重複配布を減らす。D02は独立して実際に却下する。
3. C02 + G01の1候補でPROD/DR境界を観測し、DRだけ復旧。最後にF01を実施して戻し先を実証。
4. G02/H01/H02を短い否定試験で補完。H03は人間アカウント不足などの制約を記録する。

成功/拒否/失敗のRun ID、前後の全health、Timeline/チェック状態、Artifact digest、Tag、swap Activity Logと権限設定を保存する。意図的失敗は成功と書かず、復旧Runと組にして完了条件で判定する。変更はAgent/接続の切替と限定検証・復旧に必要な範囲に留める。

## 現時点の確認結果と残課題

- Azureに前回RG/接続なし。既存のCI・Release・復旧Runは完了済みで実行中なし。
- 既存Linux Agentは別PCのWSL。今回は流用せず専用VM/Poolを作る。
- ADOのBranch Policyは0件。一般開発者の実ユーザー拒否と複数人承認は今回のアカウント構成で実証できない可能性がある。
- Bastion DeveloperはJapan West対応。EntraによるBastion SSHはBasic以上が必要なため、Developerでは利用者が設定したローカル認証を使用する。
- 未検証項目は上表に維持する。実行結果をここへ追記し、完了時に未実施を合格扱いしない。

参考: [Linux Agent](https://learn.microsoft.com/en-us/azure/devops/pipelines/agents/linux-agent?view=azure-devops)、[Agent認証](https://learn.microsoft.com/en-us/azure/devops/pipelines/agents/agent-authentication-options?view=azure-devops)、[Bastion SKU](https://learn.microsoft.com/en-us/azure/bastion/bastion-sku-comparison)、[Bastion Entra](https://learn.microsoft.com/en-us/azure/bastion/bastion-entra-id-authentication)。
