# cicd-demo

現在の検証は専用RG `rg-cicd-selfhosted-jpw` とSelf-hosted Linux Agentを使用します。Web App/VM/Bastion Developerは保持します。[検証台帳・完了条件](docs/selfhosted-validation.md)、[復旧Pipeline](pipelines/recovery-selfhosted.yml)を参照してください。旧S1 PoCの成果物とTagは保持されています。

**Azure Repos Git + Azure Pipelines で、1回作った ZIP を DEV → UAT → PROD → DR へ配布する PoC です。**
GitHub は設計・実装用のミラーです。今回の使い捨てPoCはStandard S1とPublic経由で検証します。

## 最初に覚えること

| Pipeline | 起動条件 | 行うこと |
| --- | --- | --- |
| [CI](pipelines/ci.yml) | PR の Branch Policy と develop/main/release/hotfix の更新 | テスト・Build・パッケージ化の検証。配布権限なし |
| [Infra](pipelines/infra.yml) | 担当者が当日の日付を指定して手動起動 | 使い捨てS1環境の検証・差分確認・構築 |
| [Release](pipelines/release.yml) | 担当者が release/X.Y.Z または hotfix/X.Y.Z を選んで手動起動 | Build once → DEV → UAT → main 反映確認 → PROD 承認 → staging/swap → Tag → DR |

今回のPoCではBuild/DeployともMicrosoft-hosted Ubuntuを使用し、各ジョブで使い捨てのホストを使用します。最終構成で使用するSelf-hosted Agentのpool設定は、`release.yml`の配布ジョブにコメントアウトで残しています。

**develop の更新は CI だけを実行します。DEV は Release 候補の確認環境です。** 日々の develop 自動配布は採用せず、候補を上書きする経路をなくしました。

## Release の流れ

```mermaid
flowchart TD
  A["担当者が Release / Hotfix を開始"] --> B["Build：ZIP を1回生成"]
  B --> C["DEV：配布・確認"]
  C --> D["UAT：配布・確認"]
  D --> E["UAT 担当者：受入・Run 保持・main へ PR マージ"]
  E --> F["PROD 承認者：実施を承認"]
  F --> G["staging 配布・確認 → swap → production 確認"]
  G --> H["vX.Y.Z 作成 → 同じ ZIP を DR へ配布・確認"]
```

Stage は **Build / DEV / UAT / Promote の4つ**です。Promote の中に PROD・Tag・DR を並べ、完了まで本番の排他ロックを維持します。UAT のロックも人間の確認が終わるまで維持します。

人間の判断は2か所です。

1. **UAT 担当者**：この Run の受入結果を確認し、Run を `Retain indefinitely` に設定します。候補を main へ PR マージしてから ManualValidation を再開します。
2. **PROD 承認者**：UAT・main・戻し先・実施時間を確認し、`sc-cicd-prod` の Approval を承認します。

本番投入直前に、main の内容と UAT 候補の一致、既存 Tag より新しい版であること、現在の PROD の履歴を含むことを確認します。古い候補を進めるための強制オプションはありません。

## ファイルの読み方

| パス | 内容 |
| --- | --- |
| `app/` | 確認用 Next.js アプリ。`/api/health` が環境・版・SHA・Run ID を返す |
| `pipelines/ci.yml` | CI の全体 |
| `pipelines/release.yml` | Release の全体と環境ごとの設定値 |
| `pipelines/templates/build.yml` | CI/Release 共通の Node Build 手順 |
| `pipelines/templates/deploy.yml` | Web App への配布と Smoke Test |
| `pipelines/scripts/` | Build、Artifact 検証、Smoke、投入前確認・Tag の小さな処理 |
| `tests/test_release.py` | 誤配布・古い候補・二重投入を防ぐ回帰テスト |
| [infra/](infra/README.md) | 当日削除するPoC用Bicep。S1共有Plan + DEV/UAT/PROD/DR + PROD staging |
| [docs/setup.md](docs/setup.md) | Azure DevOps / Azure の必須設定と PoC チェックリスト |
| [docs/operations.md](docs/operations.md) | 開発・Release・Hotfix・再実行・Rollback の手順 |
| [docs/design.md](docs/design.md) | 採用理由、削除した仕組み、.NET Functions への展開 |

`release.yml` から読む YAML テンプレートは1階層です。Stage 用テンプレート、共通ルートはありません。通常運用の復旧はRunbookを使います。2026-10-04のPoCでは、Tagの権限不足からRun 43の保持済みZIPを再利用する[Tag/DR専用復旧](https://github.com/ShimaBell0619/cicd-demo/blob/release/1.0.0-recovery/pipelines/recovery-tag-dr.yml)を別途実測しました。この設定はRun 43に固定されており、将来のReleaseにはそのまま使いません。

## Artifact と失敗時の基本

Artifact 名は `release`、中身は `webapp.zip` と `release.json` だけです。後者には版・SHA・Run ID・ZIP の SHA-256 を記録します。全環境で **同じ Run の同じ ZIP** を使い、配布先では再 Build しません。Tag は元の候補 SHA を指し、注釈に Run ID と ZIP の SHA-256 を残します。

| 停止箇所 | 基本対応 |
| --- | --- |
| Build / DEV / UAT | 原因を修正。同じ Artifact なら配布 Stage を再実行、コードを変えたら新しい Run |
| PROD の swap 前 | 本番は通常未変更。状態を確認し、[Runbook](docs/operations.md) で判断 |
| swap 実行中・実行後 | **Promote を再実行しない。** 本番の実状態を確認して復旧 |
| Tag / DR | 本番の成功と Pipeline 全体の成功を区別。再配布せず必要な処理だけ復旧 |

PROD と DR の切替は原子的ではありません。障害時の操作は承認された担当者が行い、Tag や main を自動で巻き戻しません。

## ローカル確認

Node.js 22、Python 3.11 以上を使用します。

```bash
npm ci
python3 -m unittest discover -s tests -v
npm run build
npm run dev
```

Azure PoC を始める前に [setup.md](docs/setup.md) の全項目を確認してください。YAML の条件式だけでは権限境界を構成できません。


## 当日削除する Azure PoC

[infra/README.md](infra/README.md) のBicepで、Japan Westに **Standard S1を1つ、DEV/UAT/PROD/DRとPROD staging** を構築します。Public経由＋Microsoft-hosted AgentでCI/CDを確認し、Azureリソースは検証当日に削除します。今回のDRは同一Plan/リージョンへの配布検証です。

この個人PoCに限りUAT/PRODは本人承認を許可します。人による承認ステップは残します。Private Endpoint / Private DNS / Self-hosted Agentの実環境設定は今回の検証対象に含めません。詳しくは [当日の検証手順](docs/poc-s1.md) を参照してください。
