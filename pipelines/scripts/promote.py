"""Two release actions: check eligibility before swap; tag after PROD smoke."""
import json
import os
import re
import subprocess
import sys

from artifact import VERSION, verify
from smoke import read_health


def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(VERSION, value):
        raise ValueError(f"Invalid release version: {value!r}")
    return tuple(int(part) for part in value.split("."))


def tag_message(metadata):
    return f"pipelineRun={metadata['buildId']}; sha256={metadata['sha256']}"


def guard(metadata, production_url, first_release=False):
    # A production-stage retry might swap twice or destroy the rollback slot.
    if os.environ.get("SYSTEM_STAGEATTEMPT", "1") != "1":
        raise ValueError("Do not rerun the PROD stage. Follow docs/operations.md")
    git("fetch", "origin", "+refs/heads/main:refs/remotes/origin/main", "--tags")
    source = metadata["commitSha"]
    git("merge-base", "--is-ancestor", source, "origin/main")
    if git("rev-parse", source + "^{tree}") != git("rev-parse", "origin/main^{tree}"):
        raise ValueError("main differs from the UAT candidate. Merge main, rebuild and repeat UAT")
    version = version_tuple(metadata["version"])
    released = [version_tuple(tag[1:]) for tag in git("tag", "--list", "v*").splitlines()
                if re.fullmatch("v" + VERSION, tag)]
    if released and version <= max(released):
        raise ValueError("Version must be greater than every previously released vX.Y.Z tag")
    try:
        current = read_health(production_url)
    except (OSError, ValueError):
        if first_release and not released:
            print("Approved first deployment: no existing release tags or readable PROD identity")
            return
        raise ValueError("Cannot read PROD identity; diagnose via the runbook, do not bypass") from None
    if (current.get("status") != "ok" or current.get("environment") != "prod"
            or current.get("service") != "cicd-demo-nextjs"):
        raise ValueError("PROD health identity is invalid")
    if version <= version_tuple(current.get("version")):
        raise ValueError("PROD already runs this or a newer version; use the runbook")
    current_sha = current.get("commitSha", "")
    if not re.fullmatch(r"[0-9a-f]{40}", current_sha):
        raise ValueError("PROD commit identity is invalid")
    git("merge-base", "--is-ancestor", current_sha, source)
    print(f"Promotion eligible: {metadata['version']} / run {metadata['buildId']}")


def create_tag(metadata):
    # AzureCLI@3 supplies the dedicated Entra identity, never Project Build Service.
    url = (os.environ["SYSTEM_COLLECTIONURI"] + os.environ["SYSTEM_TEAMPROJECTID"]
           + "/_apis/git/repositories/" + os.environ["BUILD_REPOSITORY_ID"]
           + "/annotatedtags?api-version=7.1")
    payload = {"name": "v" + metadata["version"],
               "taggedObject": {"objectId": metadata["commitSha"]},
               "message": tag_message(metadata)}
    result = json.loads(subprocess.check_output([
        "az", "rest", "--method", "post", "--url", url,
        "--resource", "499b84ac-1321-427f-aa17-267ca6975798",
        "--headers", "Content-Type=application/json", "--body", json.dumps(payload),
        "--output", "json"], text=True))
    if (result.get("taggedObject", {}).get("objectId") != metadata["commitSha"]
            or result.get("name") != "refs/tags/" + payload["name"]
            or result.get("message") != payload["message"]):
        raise ValueError("Tag response differs from the released artifact; inspect remote tag")
    print(f"Created {payload['name']}: {payload['message']}")


if __name__ == "__main__":
    action = sys.argv[1]
    metadata = verify(sys.argv[2])
    if action == "guard":
        guard(metadata, sys.argv[3], os.environ.get("FIRST_RELEASE", "false").lower() == "true")
    elif action == "tag":
        create_tag(metadata)
    else:
        raise ValueError(f"Unknown promotion action: {action}")
