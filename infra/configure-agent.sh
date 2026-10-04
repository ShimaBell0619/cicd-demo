#!/usr/bin/env bash
# Run through Azure VM Run Command as root. No PAT or Azure client secret is created.
set -euo pipefail
test "$(id -u)" = 0
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq curl ca-certificates git python3 unzip jq libicu74
if ! command -v az >/dev/null; then
  curl -fsSL https://aka.ms/InstallAzureCLIDeb -o /tmp/install-azurecli.sh
  bash /tmp/install-azurecli.sh >/var/log/cicd-azurecli-install.log 2>&1
  rm /tmp/install-azurecli.sh
fi
id cicdagent >/dev/null 2>&1 || useradd --create-home --shell /bin/bash cicdagent
install -d -m 700 -o cicdagent -g cicdagent /opt/cicd-agent
cd /opt/cicd-agent
curl -fsSL https://download.agent.dev.azure.com/agent/5.279.0/vsts-agent-linux-x64-5.279.0.tar.gz -o /tmp/cicd-agent.tar.gz
echo '6e3352e1dc44c924cd85840df279f21c200e6365596a7c38f3087015262555dc  /tmp/cicd-agent.tar.gz' | sha256sum -c -
tar -xzf /tmp/cicd-agent.tar.gz
rm /tmp/cicd-agent.tar.gz
chown -R cicdagent:cicdagent /opt/cicd-agent
python3 - <<'PY'
import json,os,subprocess,urllib.request,urllib.parse
# Azure DevOps accepts an Entra access token through the agent's registration transport.
# "PAT" is the CLI transport label; the value is a short-lived IMDS Entra JWT, never a PAT.
u='http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource='+urllib.parse.quote('499b84ac-1321-427f-aa17-267ca6975798',safe='')
with urllib.request.urlopen(urllib.request.Request(u,headers={'Metadata':'true'}),timeout=20) as r:token=json.load(r)['access_token']
env={**os.environ,'VSTS_AGENT_INPUT_TOKEN':token,'VSO_AGENT_IGNORE':'VSTS_AGENT_INPUT_TOKEN'}
subprocess.run(['runuser','-u','cicdagent','--','./config.sh','--unattended','--url','https://dev.azure.com/shimaoka0619','--auth','PAT','--pool','cicd-selfhosted-linux','--agent','vm-cicd-sh-agent','--work','_work','--acceptTeeEula'],env=env,check=True)
del env['VSTS_AGENT_INPUT_TOKEN'];del token
from pathlib import Path
c=json.loads(Path('.credentials').read_text(encoding='utf-8-sig'))
assert c['scheme']=='OAuth', 'Registration credential must not be persisted'
assert 'VSTS_AGENT_INPUT_TOKEN' not in Path('.env').read_text()
print('Registration complete: persisted agent credential scheme OAuth; no registration token saved.')
PY
./svc.sh install cicdagent
./svc.sh start
az version --query '"azure-cli"' -o tsv
python3 --version
echo 'Agent service started as unprivileged cicdagent.'
