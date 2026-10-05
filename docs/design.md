# CI/CD方式設計

## 1. 構成と責務

GitHubをソース管理の正本、Azure Reposを実行ミラーとする。CIとReleaseのBuildをMicrosoft-hostedで行い、Infra・配布・swap・Tag・復旧を専用Self-hosted Linux Agentで実行する。配布AgentでアプリのBuildやnpm installを行わない。

```mermaid
flowchart LR
    G[GitHub] -->|OIDC・一方向同期| R[Azure Repos]
    R --> B["Microsoft-hosted<br/>Build / 回帰テスト"]
    B --> A[("Pipeline Artifact<br/>webapp.zip / release.json")]
    A --> S[Self-hosted Linux Agent]
    S -->|環境別WIF| D[DEV / UAT / PROD staging / DR]
    D -->|staging確認後swap| P[PROD]
```

S1 Linux Planを4 Web AppsとPROD stagingで共有し、Public endpointを使用する。`APP_ENV`はslot固定の設定としてswapで移動させない。リソースは専用RG内に保持する。接続・Pool・Environmentの権限とChecksはYAML外の設定も必要であり、[設定](setup.md)にまとめる。

| 要素 | 方針 |
|---|---|
| Artifact | Release Runごとに1回生成。version・候補SHA・Run ID・ZIP SHA-256を記録し、各配布前に照合 |
| 承認 | UATは配布したRunの受入。PRODはService Connection Approval。却下・タイムアウトでは後続を書き換えない |
| 排他 | UAT受入中の上書きを防止。PROD接続のExclusive lockをstaging → swap → Tag → DRまで保持。`lockBehavior: sequential` |
| Tag | PROD応答確認後、Azure Reposに`vX.Y.Z`を作成。対象は候補SHA、注釈は`pipelineRun=<元Run>; sha256=<ZIP digest>` |
| 復旧 | 保持済み元RunのZIP・Tag・現在PRODを照合し、必要な配布だけ実行。Tagを変更しない |

## 2. Gitフロー

`develop`から`release/X.Y.Z`、現在の`main`から`hotfix/X.Y.Z`を作る。Release / Hotfixは同じPipelineを使用する。バージョンは安定版SemVerで、既存Tagと現在PRODより大きくする。

```mermaid
gitGraph
    commit id: "既存版"
    branch develop
    commit id: "開発"
    branch release/1.1.0
    commit id: "候補R・UAT対象" tag: "v1.1.0"
    checkout main
    merge release/1.1.0 id: "UAT受入後PR merge"
    checkout develop
    merge release/1.1.0 id: "開発へ反映"
    checkout main
    branch hotfix/1.1.1
    commit id: "修正候補H" tag: "v1.1.1"
    checkout main
    merge hotfix/1.1.1 id: "Hotfix PR merge"
    checkout develop
    merge hotfix/1.1.1 id: "Hotfixを開発へ反映"
```

図のTagは**PROD確認後に候補コミットへ付与する参照**を表す。図中の左右位置はTag作成の時刻を表さない。mainのmerge commitをTag対象にはしない。

UAT受入後、PROD承認前に候補をmainへ**merge commit方式**で反映する。Squash / Rebase mergeでは候補SHAの祖先関係を保てない。PROD配布直前とswap直前に、候補SHAがmainの祖先であり、候補と最新mainのファイルツリーが一致することを再確認する。

Hotfixが割り込む場合は旧候補Runを中止する。修正をmain / develop / 継続候補へ反映し、新しいRunでUATをやり直す。同じversionの別Buildを承認済みArtifactとして扱わない。

## 3. 配布と復旧の制御

フロー図では角丸を開始・終了、長方形を処理、ひし形を判断、円筒を保持Artifactとして使用する。

```mermaid
flowchart TD
    S([手動Release / Hotfix]) --> B[Hosted Build・テスト]
    B --> A[(同一Artifactを保持)]
    A --> D[Self-hostedでDEV → UAT配布・応答確認]
    D --> U{UAT受入?}
    U -->|却下 / タイムアウト| X([停止・PROD変更なし])
    U -->|受入| M[元Runを保持・候補をmainへPR merge]
    M --> P{PROD承認?}
    P -->|却下| X
    P -->|承認・排他取得| G{main・version・現PRODの照合OK?}
    G -->|いいえ| X
    G -->|はい| ST[stagingへ配布・応答確認]
    ST --> H{確認・swap直前照合OK?}
    H -->|いいえ| X
    H -->|はい| SW[slot swap・PROD応答確認]
    SW --> Q{PROD確認OK?}
    Q -->|いいえ| I([実状態確認・復旧判断])
    Q -->|はい| T[候補SHAへ注釈付きTag]
    T --> K{Tag照合OK?}
    K -->|いいえ| I
    K -->|はい| DR[同一ArtifactをDRへ配布・確認]
    DR --> E{DR確認OK?}
    E -->|いいえ| I
    E -->|はい| F([完了・排他解除])
```

PROD以降の処理は一つのPromote Stageにまとめる。Stage再実行による二重swapをガードで拒否する。Agentが1台でも、手動承認待ち中はAgentを占有しないため、Agentの順番待ちだけを排他手段にはしない。

```mermaid
flowchart TD
    S([復旧開始]) --> R[元Pipeline / 元Run / 期待する現PROD Runを指定]
    R --> V{元ZIP・Tag・現PRODの照合OK?}
    V -->|いいえ| N([配布前に停止])
    V -->|はい| M{復旧モード?}
    M -->|rollback| P[旧ZIPをstagingへ配布・確認]
    P --> G{現PROD再照合OK?}
    G -->|いいえ| N
    G -->|はい| W[swap・旧版PROD確認]
    M -->|dr-only| D[現PRODと元Runの一致確認]
    W --> D
    D --> H{現PRODと元Artifact一致?}
    H -->|いいえ| N
    H -->|はい| DR[同じ元ZIPをDRへ配布・確認]
    DR --> F([復旧完了・Tag変更なし])
```

Rollbackの実機成功は未確認。DR-onlyは実機成功済み。処理中のAgent停止、複数人承認、一般開発者の権限拒否など、本番利用前の課題は[検証結果](selfhosted-validation.md)へ分離する。
