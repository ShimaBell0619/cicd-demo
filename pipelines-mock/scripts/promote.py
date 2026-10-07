"""Azure Repos Git-flow validation. No Azure resource or HTTP health operations."""
import json
import os
import re
import subprocess
import sys
from urllib.error import HTTPError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

from artifact import VERSION, verify

SHA = re.compile(r"[0-9a-f]{40}")
MOCK_REPOSITORY = "cicd-demo-mock"


def require_mock_repository():
    if (os.environ.get("BUILD_REPOSITORY_PROVIDER") != "TfsGit"
            or os.environ.get("BUILD_REPOSITORY_NAME") != MOCK_REPOSITORY):
        raise ValueError(f"This mock may run only in Azure Repos repository {MOCK_REPOSITORY}")


def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()


class AzureRepos:
    def __init__(self):
        collection = os.environ["SYSTEM_COLLECTIONURI"]
        origin = urlparse(collection)
        if (origin.scheme != "https" or origin.username or origin.password
                or not (origin.hostname == "dev.azure.com"
                        or (origin.hostname or "").endswith(".visualstudio.com"))):
            raise ValueError("Expected an Azure DevOps collection URL")
        self.base = (collection.rstrip("/") + "/"
                     + quote(os.environ["SYSTEM_TEAMPROJECTID"], safe="")
                     + "/_apis/git/repositories/"
                     + quote(os.environ["BUILD_REPOSITORY_ID"], safe=""))
        self.token = os.environ["SYSTEM_ACCESSTOKEN"]
        if not self.token:
            raise ValueError("System.AccessToken is required")

    def request(self, method, path, query=None, payload=None):
        params = {"api-version": "7.1", **(query or {})}
        url = self.base + path + "?" + urlencode(params)
        data = None if payload is None else json.dumps(payload).encode()
        request = Request(url, data=data, method=method, headers={
            "Authorization": "Bearer " + self.token,
            "Content-Type": "application/json",
        })
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    def completed_pull_requests(self, branch):
        return self.request("GET", "/pullrequests", {
            "searchCriteria.status": "completed",
            "searchCriteria.sourceRefName": branch,
            "searchCriteria.targetRefName": "refs/heads/main",
            "$top": "100",
        }).get("value", [])

    def pull_request(self, number):
        return self.request("GET", "/pullrequests/" + str(number))

    def commit(self, sha):
        return self.request("GET", "/commits/" + sha)

    def find_tag(self, name):
        refs = self.request("GET", "/refs", {"filter": "tags/" + name}).get("value", [])
        matches = [ref for ref in refs if ref.get("name") == "refs/tags/" + name]
        if not matches:
            return None
        if len(matches) != 1 or not SHA.fullmatch(matches[0].get("objectId", "")):
            raise ValueError("Ambiguous or invalid existing tag")
        return self.request("GET", "/annotatedtags/" + matches[0]["objectId"])

    def create_tag(self, payload):
        return self.request("POST", "/annotatedtags", payload=payload)


def validate_pull_request(pr, metadata, branch):
    if (pr.get("status") != "completed"
            or pr.get("sourceRefName") != branch
            or pr.get("targetRefName") != "refs/heads/main"
            or pr.get("lastMergeSourceCommit", {}).get("commitId") != metadata["commitSha"]):
        raise ValueError("The completed main PR does not match this UAT candidate")
    sha = pr.get("lastMergeCommit", {}).get("commitId", "")
    if not SHA.fullmatch(sha):
        raise ValueError("The completed PR has no valid Merge Commit SHA")
    number = pr.get("pullRequestId")
    if not isinstance(number, int) or isinstance(number, bool) or number <= 0:
        raise ValueError("Invalid main PR number")
    return sha, number


def select_pull_request(prs, metadata, branch):
    matches = [pr for pr in prs
               if pr.get("status") == "completed"
               and pr.get("sourceRefName") == branch
               and pr.get("targetRefName") == "refs/heads/main"
               and pr.get("lastMergeSourceCommit", {}).get("commitId") == metadata["commitSha"]]
    if len(matches) != 1:
        raise ValueError("Expected exactly one completed main PR for this candidate; merge then resume")
    return matches[0]


def validate_merge(commit, metadata, run_git=git):
    sha = commit.get("commitId", "")
    if not SHA.fullmatch(sha):
        raise ValueError("Invalid Merge Commit")
    parents = commit.get("parents", [])
    if len(parents) != 2 or parents[1] != metadata["commitSha"]:
        raise ValueError("Use Merge commit; squash/rebase or a changed candidate is not accepted")
    if run_git("rev-parse", sha + "^{tree}") != run_git("rev-parse", metadata["commitSha"] + "^{tree}"):
        raise ValueError("Merged source differs from UAT; create a new candidate/Run and repeat UAT")


def capture(metadata, client, run_git=git):
    branch = os.environ["BUILD_SOURCEBRANCH"]
    selected = select_pull_request(client.completed_pull_requests(branch), metadata, branch)
    # Re-read the specific PR after completion, not a PR validation/test-merge commit.
    pr = client.pull_request(selected["pullRequestId"])
    sha, number = validate_pull_request(pr, metadata, branch)
    commit = client.commit(sha)
    if commit.get("commitId") != sha:
        raise ValueError("Commit response mismatch")
    run_git("fetch", "origin", "+refs/heads/main:refs/remotes/origin/main", "--no-tags")
    run_git("merge-base", "--is-ancestor", sha, "origin/main")
    validate_merge(commit, metadata, run_git)
    print(f"Captured main PR {number}: candidate={metadata['commitSha']}, merge={sha}")
    print(f"##vso[task.setvariable variable=mergeCommitSha;isOutput=true]{sha}")
    print(f"##vso[task.setvariable variable=mainPrId;isOutput=true]{number}")
    return sha, number


def tag_message(metadata, merge_sha, number):
    return (f"mock=true; pipelineRun={metadata['buildId']}; "
            f"candidate={metadata['commitSha']}; mergeCommit={merge_sha}; pr={number}")


def verify_tag(result, metadata, merge_sha, number):
    name = "v" + metadata["version"]
    if (result.get("name") not in (name, "refs/tags/" + name)
            or result.get("taggedObject", {}).get("objectId") != merge_sha
            or result.get("message") != tag_message(metadata, merge_sha, number)):
        raise ValueError("Existing tag differs from this Run/Merge Commit; tags are never moved")


def create_tag(metadata, merge_sha, number, swap_succeeded, client):
    if swap_succeeded != "true":
        raise ValueError("No tag may be created before successful mock Slot Swap")
    if (not SHA.fullmatch(merge_sha)
            or not re.fullmatch(r"[1-9][0-9]*", str(number))
            or not re.fullmatch(VERSION, metadata["version"])):
        raise ValueError("Missing retained Merge Commit SHA, PR number or release version")
    # Check the frozen PR association again. Never choose the latest main HEAD.
    pr = client.pull_request(int(number))
    expected, actual_number = validate_pull_request(pr, metadata, os.environ["BUILD_SOURCEBRANCH"])
    if expected != merge_sha or actual_number != int(number):
        raise ValueError("Retained Merge Commit does not match the selected completed PR")
    name = "v" + metadata["version"]
    existing = client.find_tag(name)
    if existing is not None:
        verify_tag(existing, metadata, merge_sha, number)
        print(f"Already tagged by this Run: {name} -> {merge_sha}")
        return existing
    payload = {"name": name, "taggedObject": {"objectId": merge_sha},
               "message": tag_message(metadata, merge_sha, number)}
    try:
        result = client.create_tag(payload)
    except HTTPError as error:
        # Reconcile a concurrent/retried creation, without moving an existing tag.
        if error.code not in (400, 409):
            raise
        existing = client.find_tag(name)
        if existing is None:
            raise
        verify_tag(existing, metadata, merge_sha, number)
        return existing
    verify_tag(result, metadata, merge_sha, number)
    print(f"Created {name} -> retained main Merge Commit {merge_sha}")
    return result


def main():
    require_mock_repository()
    action = sys.argv[1]
    if action == "preflight":
        print(f"Git-flow mock repository: {MOCK_REPOSITORY}")
        return
    metadata = verify(sys.argv[2])
    client = AzureRepos()
    if action == "capture":
        capture(metadata, client)
    elif action == "tag":
        create_tag(metadata, os.environ["MERGE_COMMIT_SHA"], os.environ["MAIN_PR_ID"],
                   os.environ.get("MOCK_SWAP_SUCCEEDED", ""), client)
    else:
        raise ValueError(f"Unknown mock action: {action}")


if __name__ == "__main__":
    main()
