# インフラとAgent

保持する専用検証環境を定義する。RGは`rg-cicd-selfhosted-jpw`、Japan West。S1をDEV / UAT / PROD / DRとPROD stagingで共有する。Public endpointを使用し、Private Endpointは作成しない。

## 定義の役割

| ファイル | 役割 |
|---|---|
| [main.bicep](main.bicep) / [selfhosted.bicepparam](selfhosted.bicepparam) | subscription scopeで専用RGを作成し、App Serviceを構築する初期用定義 |
| [app-service.bicep](app-service.bicep) | RG内のS1 Plan、4 Web Apps、PROD staging、固定APP_ENV、Node 22設定 |
| [agent.bicep](agent.bicep) | Ubuntu Agent VM、VNet / NSG / NIC / 送信用Public IP、Bastion Developer |
| [configure-agent.sh](configure-agent.sh) | 初回登録専用。Agent digest照合、短期Entra tokenで登録、非rootサービス化 |
| [infra.yml](../pipelines/infra.yml) | RG scopeのInfra WIFでApp Serviceだけをvalidate / what-if / apply |

RGとApp Serviceには`lifecycle=retained`、`workload=selfhosted-validation`を設定する。Infra PipelineはこのRGタグを照合してから操作する。旧使い捨てPoCの期限・削除用プロファイルは削除した。

## 初期構築の順序

1. 管理者がBicepをvalidate / what-ifし、`main.bicep`と`selfhosted.bicepparam`で専用RG / App Serviceを構築する。Infra接続の権限はRG内だけなので、RG自体の作成には使用しない。
2. `agent.bicep`を専用RGへ適用する。`adminPassword`は安全な実行時入力で与え、パラメータファイル・Repo・ログへ保存しない。
3. 専用PoolとVMのSystem-assigned Identityの登録用権限を用意し、VM Run Commandで`configure-agent.sh`を初回だけ実行する。登録済みVMの通常Infra更新では実行しない。
4. 登録用のPool管理権限とAzure DevOpsへの登録用アクセスを除去し、Agentがオンラインであることを確認する。標準OAuth資格情報はAgentディレクトリで保護する。
5. 環境別WIF、Pipelineごとの認可、Environment / PROD接続Checksを[設定](../docs/setup.md)に従って用意する。

Agent VMには配布用Managed Identityを割り当てず、Azure RBACを付けない。Internetからの受信は拒否し、管理はBastion Developerを使用する。VMのPublic IPはPublic App Service / SCMとAzure DevOpsへの送信に使用する。

Web Apps、VM、Bastionはユーザーの判断で残す。Bicepの更新やドキュメント整理だけではAzureへ自動適用せず、削除もしない。実際の変更時はwhat-ifを確認し、手動Infra Runで適用する。
