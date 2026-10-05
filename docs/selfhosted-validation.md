# 検証結果・残課題

基準日: **2026-10-04 JST**。通常Releaseを繰り返す追加検証は行わず、今回追加した価値のある観点をまとめる。実機成功、否定試験成功、部分確認、未実施を区別する。

## 前回S1 PoCから引き継ぐ結果

[Run 43](https://dev.azure.com/shimaoka0619/cicd-demo/_build/results?buildId=43)の1.0.0を同じZIPでDEV / UAT / PROD stagingに配布し、swap後のPRODを確認した。Tagで停止した後、Run 49でTag作成、[Run 51](https://dev.azure.com/shimaoka0619/cicd-demo/_build/results?buildId=51)で元43のZIPをDRへ配布した。PRODへの再配布・再swapは行っていない。旧RG・Identity・接続は削除済みで、Artifactと履歴は保持している。

今回は別RGにSelf-hosted Linux Agentを構築した。BuildはMicrosoft-hostedで継続。VM / Web Apps / Bastion Developerは保持する。

## 検証項目・完了条件・結果

| ID / 優先 | 項目・方法 | 完了条件 | 実施結果 |
|---|---|---|---|
| A01 / P0 | Infraと全配布JobのAgent / WIFログ確認 | 配布等が指定Linux Agent、BuildだけHosted。接続secret / PATなし | 実機確認。Infra 57、Release 69 |
| A02 / P0 | 未認可Pipeline参照とDEV権限の越境読取 | 未認可参照はJob前停止、他App / VMは拒否、全Pipeline許可=false | 否定試験確認。58で他App / VM=403、59 / 60で認可待ち停止し中止 |
| A03 / P0 | 登録権限・VM Identity・認証キャッシュ監査 | 登録権限除去、配布IdentityをVMに持たせず、次Jobへ認証を引継がない | 部分確認。権限除去、キャッシュ残留0。前Job tokenの再利用拒否・プロセス隔離は未実証 |
| B01 / P0 | 旧43の初期化後、1.1.0を配布 | 戻し先と新版の元Run / SHA / digest / Tagを保持 | 実機確認。初期化61、通常69。初期化専用コードは役目を終えて削除 |
| C01 / P1 | UAT受入待ち中に別Runを起動 | UATを上書きせずlock待ち、先行Run終了後に進行 | 実機確認。71保持中に72待機、Agent idle、71却下後72進行 |
| C02 / P1 | PROD完了 / DR前で先行Runを保持し競合起動 | 競合がstaging / swapを開始せずPROD接続lock待ち | 範囲限定で確認。80保持中に承認済み81待機、配布前に中止。80失敗終了後82が取得。81自身の待機解除後配布は未実測 |
| D01 / P1 | UAT受入を却下 | Promote / Tag / DRがSkip、PROD不変 | 実機確認。71 |
| D02 / P1 | PROD接続承認を却下 | Production / DR Job未開始、staging / PROD / DR / Tag不変 | 実機確認。72 |
| E01 / P1 | 通常候補を止め、Hotfixを同じ経路で配布 | 修正だけを配布・Tag・DR完了、main / develop / 次候補へ反映 | 実機確認。73=1.1.1、PR #2 merge後85ca1e7を同期 |
| F01 / P1 | 保持旧ZIPをstagingへ戻してswap、DR同期 | PROD / DRが旧Run、元digest一致、Tag不変、swap1回 | **未実施**。84は誤指定を拒否した試験で、Rollback成功ではない |
| G01 / P1 | DR前の意図的失敗からDR-only復旧 | 元ZIPでDR一致、PROD / staging / Tag不変、追加swap0 | 実機確認。80 → 82。通常Release再実行なし |
| G02 / P1 | 誤った元Run / 現PROD指定で復旧起動 | ガードで停止し、staging / swap / DR書込なし | 否定試験確認。83=Tagの元Run / digest不一致、84=現PROD期待Run不一致。StageAttempt>1はローカル回帰確認 |
| H01 / P2 | 元ZIPの複製を破損 / 欠損させ照合 | 配布前に拒否し元ZIP不変 | ローカル確認。Azure上のArtifact置換試験はしていない |
| H02 / P2 | idle Agent停止・Job待機・再起動 | 未開始時Azure変更なし、再起動後WIF正常 | 範囲限定で実機確認。74未開始で中止、同じAgent再起動後79成功。配布 / swap中断は未実測 |
| H03 / P2 | 開発者権限・承認・ブランチ保護監査 | 実ユーザーで編集拒否、複数人承認、PR保護を実証 | 未完。Azure Repos Policy=0、本人承認は専用検証のみ許可。一般開発者 / 複数人は未実証 |

主要Run: [69 通常](https://dev.azure.com/shimaoka0619/cicd-demo/_build/results?buildId=69)、[71 UAT却下](https://dev.azure.com/shimaoka0619/cicd-demo/_build/results?buildId=71)、[72 PROD却下](https://dev.azure.com/shimaoka0619/cicd-demo/_build/results?buildId=72)、[73 Hotfix](https://dev.azure.com/shimaoka0619/cicd-demo/_build/results?buildId=73)、[80 DR前失敗](https://dev.azure.com/shimaoka0619/cicd-demo/_build/results?buildId=80)、[81 排他待ち・中止](https://dev.azure.com/shimaoka0619/cicd-demo/_build/results?buildId=81)、[82 DR-only復旧](https://dev.azure.com/shimaoka0619/cicd-demo/_build/results?buildId=82)、[83 誤Artifact拒否](https://dev.azure.com/shimaoka0619/cicd-demo/_build/results?buildId=83)、[84 現PROD不一致拒否](https://dev.azure.com/shimaoka0619/cicd-demo/_build/results?buildId=84)。

## 最終記録の環境状態

これは2026-10-04の実測記録であり、常に現在値を示すものではない。全endpointのhealthはHTTP 200だった。復旧Run 82であっても応答の`buildId`は元Artifactの80。

| 環境 | version | 元Build Run | 候補SHA（短縮） |
|---|---|---|---|
| DEV / UAT | 1.2.1 | 81 | 85ca1e7 |
| PROD / DR | 1.2.0 | 80 | 85ca1e7 |
| PROD staging | 1.1.1 | 73 | 133c0a8 |

元80のZIP SHA-256: `bd8351d4dde1ef577f6c74fac2068676de94e42fc114135c9c3702306c3a1aba`。保持Tagは`v1.0.0`（元43）、`v1.1.0`（69）、`v1.1.1`（73）、`v1.2.0`（80）。失敗・中止Runを正常配布完了と扱わない。

## 本番利用前の残課題

| 優先 | 残課題 | 完了条件 |
|---|---|---|
| P0 | 旧ZIPの実機Rollback | 現PRODを明示して旧ZIPへ1回swap、PROD / DR一致、元digest・Tag不変を確認 |
| P0 | 自己承認禁止・一般開発者の権限・PR保護 | 別承認者で受入 / 承認 / 却下し、一般開発者のPipeline / Checks / Pool編集拒否とPR保護を実測 |
| P1 | 配布 / swap中のAgent停止 | Azure実状態を照合し、二重swapなしで安全に再開できることを確認 |
| P1 | Agentの資格情報・プロセス隔離 | 前Job tokenの利用拒否、別Jobからの読取・操作境界を確認 |
| P1 | 競合Releaseの完全な順次進行 | 先行終了後に待機していた同じ後続Runが正しいArtifactで進むことを確認 |
| P1 | Tagだけ失敗した際の運用標準化 | 元Run / PROD / digest照合と既存Tag確認を含む限定補償手順を整備。全Promote再実行を使わない |

同一PlanのDRは別リージョンDR / フェイルオーバーの証明にならない。Private Endpointや別リージョン切替は今回の方式の対象外で、必要なら別案件として検討する。

## 運用・資材整理の別課題

- S1共有でCPUが99〜100%となり、初期化・cold startup・swapが長引いた。初期化約48分、初回swap約11.5分、通常Run 69約41分（承認等の待ちを含む）。本番の性能設計とは分けて扱う。
- Repositoryの権限試験YAML、DR保留 / 故意失敗フック、元43専用bootstrap、旧使い捨てプロファイル、初回ADO定義作成Workflowを削除した。通常Pipelineと運用で使う復旧ガードは維持する。
- Azure DevOpsの試験定義19 / 20と試験用個別認可の削除はこのGitHub整理に含めていない。通常運用はPool=16 / 17 / 18、DEV接続=17で、試験時に追加した20の認可が整理対象。
- 履歴のRelease / Hotfixブランチ、Tag、保持Artifact、Azureリソースはこの整理では削除しない。古い候補YAMLには検証フックが残るため、次の候補は更新済みmain / developを取り込んで作成する。
