# 単純化の設計判断

## 出発点と結論

評価対象は main `7f8a1e4a9d6fa45ad77dde0cc19dec65b8969557` の全26ファイルです。AGENTS.md はありませんでした。

複雑化への懸念は妥当でした。4つの入口が共通 root に集まり、mode で再分岐して Stage / Step テンプレートを追う必要がありました。Recovery は5操作を持ち、その Stage テンプレートだけで452行ありました。例外への備えが通常 Release より目立ち、構成の責務を一読で把握しにくくなっていました。さらに lockfile 未登録のため、既存の npm ci 前提をそのまま実行できませんでした。

採用方針は **CI と Release を分け、通常の配布順を1つの YAML に書き、低頻度の復旧は Runbook にする**ことです。必要なリスク低減が説明できる仕組みは残します。

## 何を変えたか

| 項目 | 採用した方式と理由 |
| --- | --- |
| Pipeline | CI / Release の2本。PR は無権限の検証だけ、Release は明示起動 |
| DEV | Release 候補のみ配布。develop 自動配布との競合を根本からなくす |
| Agent | 使い捨て Build と private Deploy の2種類。制御専用 Pool を廃止し、信頼済み制御処理は Deploy に集約 |
| YAML | 4 Stage を release.yml に直接記載。Build と Web App 配布だけ1階層の Step template |
| extends / Required Template | 廃止。候補ブランチの作成制限、必須インフラレビュー、リソースの認可/Checks に責務を移す |
| Git Guard | 候補が main に含まれ、内容が一致することを確認。main HEAD の親数・第2親 SHA の厳密な固定は廃止 |
| 古い候補 | main との内容一致、SemVer の数値比較、現在の PROD の版と履歴を確認。投入直前にも再確認 |
| Artifact | ZIP + release.json（version / commitSha / buildId / sha256）。SBOM と独立 checksum 一覧・重複 digest を廃止 |
| Smoke | HTTP 200、status、service、環境、version、SHA、Run ID を照合して待機。単なる疎通では旧版が通るため identity は維持 |
| Recovery | Pipeline を廃止。Tag 補完、DR 同期、旧 ZIP 再配布・逆 swap を Runbook にする |
| Rollback | 保持した旧 ZIP の staging 再配布が標準。既存 staging の identity が確認できた場合だけ逆 swap を許容 |
| Retention | 独自 lease API と専用 Stage を廃止。UAT 受入時に Run を Retain indefinitely |
| Tag | PROD 確認直後に専用 WIF 身元で自動作成。注釈に Run ID と digest を記録 |
| 排他 | UAT の人間の確認と、PROD/Tag/DR の昇格を各 Stage 内で標準 Exclusive lock により保護 |

テンプレート行数を減らすために、ダウンロードや verify の数行を無理に共通化していません。各環境の入口に同じ処理を見える形で置いています。

## 残した複雑性

| 仕組み | 削除すると起きる現実的な事故 |
| --- | --- |
| Build と Deploy のホスト分離 | PR/npm スクリプトが残したプロセス等から後続ジョブの本番資格情報へ到達する |
| PROD Service Connection の Approval | Environment を使わないタスクが承認を迂回できる |
| 専用 Tag 身元 | Project Build Service への Create tag 付与が PR ジョブにも及び、偽の Release 実績を作れる |
| UAT Stage 内の ManualValidation | 別候補が UAT を上書きし、検証した Run を特定できなくなる |
| PROD/Tag/DR を同一 Stage に配置 | 新しい Release の後に古い Tag/DR 処理が割り込みやすくなる |
| Artifact の identity / ZIP digest / Smoke | 間違った Run、破損、配布先 URL 間違い、旧プロセスの成功を見逃す |
| 現在の PROD との比較 | swap 成功・Tag 失敗後の別 Run が同じ版を配布し、戻し用 Slot を上書きする |
| 本番 Stage の再実行禁止 | 途中成功した swap を繰り返し、期待しない Slot 内容を配布する |

初回配布オプションは「Tag がなく、まだ PROD の identity を読めない」ときだけを救済します。既存のリリースがある状態で health 障害を無視する用途には使いません。初回であることは PROD 承認者も確認します。

## 標準設定・人間との責務分担

Pipeline は配布する対象と順序、内容の一致を検証します。誰が候補を作れるか、誰が変更を承認できるか、どの Pipeline が資格情報を使えるかは Azure DevOps 設定で制限します。UI 管理者や Azure 管理者まで悪意がある想定を、複雑な YAML だけで解決しようとはしません。

main マージから DR 完了までの別マージ禁止、Hotfix 優先時の旧候補キャンセル、Run 保持、DB 後方互換性、復旧の承認は人間の責務です。Git の ancestry は「修正が意味的に維持されている」ことまでは証明できません。意図的な revert や内容の消し戻しは PR レビューと UAT で判断します。

SHA-256 は保護された Pipeline Artifact 経路での取り違え/破損検出です。悪意ある Build が ZIP と metadata を両方作り替えることに対する署名・完全な supply chain attestation ではありません。追加の SBOM/署名が組織要件になった場合は、その目的に限定して追加します。

この PoC の health は起動と配布物の同一性を確認します。DB・業務処理・全インスタンスの正常性までは証明しません。本番アプリでは副作用のない業務 Smoke と監視を追加します。自動 Rollback は DB や外部副作用を戻せないため採用しません。

## .NET Functions API / Batch へ展開する場合

| そのまま利用する考え方・処理 | ワークロードに合わせて変更する箇所 |
| --- | --- |
| CI/手動 Release の分離、PR と承認、候補ブランチ管理 | Node の Build を dotnet restore/test/publish に変更。SDK/依存関係を固定 |
| Build once / 同じ Run の Artifact / release.json / digest | 配布 ZIP の作成手順・エントリポイント・ファイル名 |
| main/版/履歴の Guard、Tag 注釈、Run 保持 | Functions の適切な Deploy Task とプランに応じた Slot 操作 |
| UAT と PROD の人間の判断、排他、復旧判断 | API は readiness/identity endpoint、Batch は起動状態と実行履歴を検証 |
| App/SCM Private DNS と Agent 分離 | Functions の host storage、VNet、各 Slot の設定と認証 |

**Batch の staging を通常起動するだけで Timer/Queue が動く可能性があります。** 非 production Slot では対象 Function の trigger を無効にする slot 固定設定等を設計し、swap 前後の重複実行・リトライ・冪等性を検証します。API の HTTP Smoke をそのまま流用したり、本番 Batch を Smoke のためだけに実行したりしません。

将来のための汎用 engine、言語切替 mode、複数ワークロードの巨大 template は今は作りません。共通なのはリリースの契約であり、具体的な Build/Deploy/Smoke まで同じである必要はありません。

## 自己レビューと限界

README で本数・契機・Artifact・人間の判断を確認し、release.yml を上から読むと通常ルートを追える構成です。**新任のインフラ SE が30分で全体像を説明することは可能**と評価します。目安は README 5分、Release YAML 10分、setup の権限表5分、operations の失敗判断10分です。Azure DevOps の初期構築や本番復旧を30分で習得できる、という意味ではありません。

実装検証では13件の回帰テスト、4 YAML の構文・Stage 依存順・文書リンク確認、Node.js 22 の `npm ci` / 本番 Build / ZIP 生成が成功しました。生成 ZIP を展開して実際に起動し、health の版・SHA・Run ID・環境一致、誤った環境の拒否、トップページの HTTP 200 も確認しました。ここで使った Run ID はローカル検証用です。

ローカル検証と Azure 実環境での実証は分けます。Azure Pipelines サーバーでの YAML 展開、Approval / Branch control / Pool permissions / WIF / PE / Slot / Retention の有効性は [setup.md](setup.md) の PoC を終えるまで未実証です。
