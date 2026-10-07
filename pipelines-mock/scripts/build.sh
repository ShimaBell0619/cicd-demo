#!/usr/bin/env bash
set -euo pipefail

# Mock uses Microsoft-hosted Agent; no Azure deployment is performed.
[[ "$(node -p 'process.versions.node.split(".")[0]')" == 22 ]] || {
  echo 'Build requires Node.js 22.' >&2
  exit 1
}
test -f package-lock.json
npm ci --no-audit --no-fund
# Application tests are disabled. Git-flow tests run separately before publication.
# python3 -m unittest discover -s tests -v
python3 pipelines-mock/scripts/artifact.py embed
npm run build

# The ZIP contains ready-to-run output. App Service must not build it again.
artifact_dir="${BUILD_ARTIFACTSTAGINGDIRECTORY:?}/release"
package_dir="$(mktemp -d)"
trap 'rm -rf "$package_dir"' EXIT
mkdir -p "$artifact_dir"
cp -a .next/standalone/. "$package_dir/"
mkdir -p "$package_dir/.next"
cp -a .next/static "$package_dir/.next/static"
if [[ -d public ]]; then cp -a public "$package_dir/public"; fi
rm -f "$artifact_dir/webapp.zip"
(cd "$package_dir" && zip -qr "$artifact_dir/webapp.zip" .)
python3 pipelines-mock/scripts/artifact.py create "$artifact_dir"
