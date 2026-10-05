# CI/CD demo — Azure App Service

GitHubをソース管理の正本とし、Azure Reposへの一方向ミラーを通してAzure Pipelinesを実行する。Next.jsの同一ArtifactをDEV → UAT → PROD → DRへ配布する検証環境。

## 現行構成

- **Build / CI**: Microsoft-hosted Ubuntu、Node.js 22。ReleaseのBuildは1回だけ。
- **Infra / 配布 / swap / Tag / 復旧**: 専用Self-hosted Linux Agent `cicd-selfhosted-linux` / `vm-cicd-sh-agent`。
- **Azure**: 専用RG `rg-cicd-selfhosted-jpw`、Japan West、S1、DEV/UAT/PROD/DRの4 Web AppsとPROD `staging` slot。Public endpointを使用。
- **認証**: Infra・各環境・Tagの6つのWIF接続を分離し、対象Pipelineだけに認可。接続に秘密鍵・client secret・PATを保存しない。
- **PROD**: UAT受入 → mainへのPR merge → PROD承認 → staging配布・確認 → swap → PROD確認 → 注釈付きTag → 同じZIPをDRへ配布。
- **保持**: Web Apps、Agent VM、Bastion Developerを残す。旧使い捨てPoCの当日削除ルールは適用しない。

DRは同じリージョン・同じPlan内の配布先であり、リージョン障害時の切替は検証していない。Private Endpointは今回の対象外。

## ドキュメント

| 資料 | 内容 |
|---|---|
| [方式設計](docs/design.md) | 基本構成、Gitフロー、配布・復旧フロー |
| [設定](docs/setup.md) | Pipeline、WIF、Pool、承認・排他の設定 |
| [運用手順](docs/operations.md) | 通常Release、Hotfix、Rollback、後段失敗の対応 |
| [検証結果・残課題](docs/selfhosted-validation.md) | 完了条件、実施結果、実機未検証の区別 |
| [インフラ](infra/README.md) | Bicepの役割、Agentの初期設定 |
| [GitHub → Azure Repos](docs/github-azure-repos-mirror.md) | 同期・認証・分岐時の扱い |
| [Issue経由の操作補助](docs/chat-azure-pipelines-bridge.md) | 既存のowner専用Bridge |

## 維持するPipeline

| YAML | 役割 |
|---|---|
| [ci.yml](pipelines/ci.yml) | ブランチ更新時のBuildと回帰テスト。Azure配布権限なし |
| [infra.yml](pipelines/infra.yml) | 専用RG内のApp Serviceを手動でvalidate / what-if / apply |
| [release.yml](pipelines/release.yml) | 手動Release / Hotfix。同一Artifactの昇格、承認、排他、Tag |
| [recovery-selfhosted.yml](pipelines/recovery-selfhosted.yml) | 保持済み元Runを明示指定するRollback / DR-only。再Build・Tag作成なし |

通常Release、Hotfix、承認却下、排他待ち、DR-only復旧は実機で確認済み。**旧ZIPへのRollbackは事前拒否ガードのみ確認し、実際のswapによる復元は未実施**。詳細と2026-10-04の状態は[検証結果](docs/selfhosted-validation.md)を参照。

## ローカル確認

Node.js 22とPython 3.11以上を使用する。

```sh
npm ci
python3 -m unittest discover -s tests -v
npm run build
```

`/api/health`は環境・version・commit SHA・元Build Run IDを返す。Release用ZIPと`release.json`の生成は[build.sh](pipelines/scripts/build.sh)で行い、配布先では再Buildしない。
