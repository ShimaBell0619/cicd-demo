# GitHub → Azure Repos同期

GitHubをソース管理の正本、[Azure Repos](https://dev.azure.com/shimaoka0619/cicd-demo/_git/cicd-demo)をAzure Pipelinesの実行ミラーとする。通常の変更はGitHubへPRで反映し、Azure Reposを直接編集しない。

[mirror-azure-repos.yml](../.github/workflows/mirror-azure-repos.yml)が`main` / `develop` / `release/**` / `hotfix/**`と`v*` Tagのpushを同期する。ブランチはfast-forwardだけ、既存Tagは対象objectが一致する場合だけ許容し、force pushと上書きを行わない。ブランチ・Tagの削除は同期しない。

## 認証と権限

GitHub Actions → GitHub OIDC → Microsoft Entra Identity → Azure DevOps短期access token → Git push。PATを保存しない。Repository variablesは`AZURE_CLIENT_ID` / `AZURE_TENANT_ID` / `AZURE_SUBSCRIPTION_ID`。

ミラー用Identityには対象RepoのRead / Contribute / Create branch / Create tagだけを与え、Force push / Manage permissions / policy bypassを与えない。これは[Azure配布用6接続](setup.md)とは別の信頼・役割である。既存[Issue Bridge](chat-azure-pipelines-bridge.md)は同じGitHub OIDC Identityを使い、指定Pipelineへの読取・起動権限も必要。

## 運用

1. GitHubの変更後、Mirror Workflow成功を確認する。
2. Azure Reposの対象refとSHAがGitHubに一致してから、Releaseを起動・承認する。
3. 同期先が分岐した場合は止め、差分の原因を調べる。force pushやpolicy bypassで解消しない。

Azure Reposの厳格なPR必須Policyはミラーpushを妨げる場合がある。ソース側GitHubのPR保護と実行側Azure DevOpsの権限制御を併せて設計する。検証時のPolicy未設定は[残課題](selfhosted-validation.md)を参照。

ReleaseのTagはPROD確認後に**Azure Reposで作成**する。このWorkflowは逆方向の同期を行わない。GitHubにもTagを表示する場合は、元の注釈付きTag objectを確認した管理操作が必要で、GitHub側で同じ名前のTagを作り直さない。
