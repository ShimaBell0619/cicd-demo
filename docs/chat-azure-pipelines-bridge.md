# Issue経由のPipeline操作補助

既存[azure-pipelines-bridge.yml](../.github/workflows/azure-pipelines-bridge.yml)は、Repository ownerによる[Issue #1](https://github.com/ShimaBell0619/cicd-demo/issues/1)のコメントだけを受け付ける。PRコメントや他ユーザーからの操作は受け付けない。通常運用はAzure DevOps画面からも行える。

GitHub ActionsのOIDC IdentityでAzure DevOps REST APIを呼び、結果を同じIssueへ返す。PATやAzure DevOps Service ConnectionをBridge用に保存しない。GitHub変数とIdentityは[ミラー](github-azure-repos-mirror.md)と共通。

## 対応コマンド

```text
/ado-list <org> <project>
/ado-run <org> <project> <pipelineId> <refs/heads/...>
/ado-run <org> <project> <pipelineId> <refs/heads/...> firstProductionRelease=true
/ado-status <org> <project> <pipelineId> <runId>
```

現行のInfra / Release / Recovery定義IDは16 / 17 / 18。通常Releaseは`firstProductionRelease=false`（既定値）で起動する。BridgeにはUAT / PROD承認・却下操作やRecoveryのmode / 元Run / 現PROD指定を渡す機能はない。**RecoveryはAzure DevOps画面から明示入力して起動する**。

Azure DevOpsでは対象PipelineのView build pipeline / View builds / Queue buildsが必要。Pipeline編集・削除・管理、Checks変更、Pool管理の権限は付けない。ミラーで必要なRepo権限とは別に扱う。

Bridgeから起動しても、PipelineのWIF認可・Agent Pool認可・Environment・承認・排他は省略されない。配布接続は`sc-cicd-sh-{infra,dev,uat,prod,dr,tags}`で、詳細は[設定](setup.md)を参照。
