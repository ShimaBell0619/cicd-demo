"""Local Git integration tests; Azure Repos API responses are simulated."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import artifact
import promote


class GitFlow(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.g("init", "-b", "main")
        self.g("remote", "add", "origin", str(self.repo))
        self.g("config", "user.email", "mock@example.invalid")
        self.g("config", "user.name", "Mock test")
        self.write("app.txt", "base")
        self.g("checkout", "-b", "develop")
        self.write("app.txt", "feature")
        self.g("checkout", "-b", "release/v1.2.0")
        self.write("fix.txt", "release adjustment")
        self.candidate = self.g("rev-parse", "HEAD")
        self.g("checkout", "main")
        self.g("merge", "--no-ff", "release/v1.2.0", "-m", "main merge")
        self.merge = self.g("rev-parse", "HEAD")
        self.metadata = {"version": "1.2.0", "commitSha": self.candidate, "buildId": "101"}
        self.pr = {"pullRequestId": 12, "status": "completed",
                   "sourceRefName": "refs/heads/release/v1.2.0",
                   "targetRefName": "refs/heads/main",
                   "lastMergeSourceCommit": {"commitId": self.candidate},
                   "lastMergeCommit": {"commitId": self.merge}}
        self.environ = patch.dict(os.environ, {
            "BUILD_SOURCEBRANCH": self.pr["sourceRefName"],
            "BUILD_SOURCEVERSION": self.candidate,
            "BUILD_BUILDID": "101", "RELEASE_BUILD": "true",
            "BUILD_REPOSITORY_PROVIDER": "TfsGit",
            "BUILD_REPOSITORY_NAME": "cicd-demo-mock"})
        self.environ.start()
        self.client = FakeAzureRepos(self)

    def tearDown(self):
        self.environ.stop()
        self.temp.cleanup()

    def g(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args],
                                       text=True, stderr=subprocess.DEVNULL).strip()

    def write(self, name, text):
        (self.repo / name).write_text(text)
        self.g("add", name)
        self.g("commit", "-m", text)

    def commit(self, sha):
        return {"commitId": sha, "parents": self.g("show", "-s", "--format=%P", sha).split()}

    def capture(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return promote.capture(self.metadata, self.client, self.g)

    def tag(self, sha=None, swapped="true"):
        with contextlib.redirect_stdout(io.StringIO()):
            return promote.create_tag(self.metadata, sha or self.merge, 12, swapped, self.client)

    def test_capture_main_merge_with_same_tree(self):
        sha, number = self.capture()
        self.assertEqual((sha, number), (self.merge, 12))
        self.assertNotEqual(sha, self.candidate)

    def test_main_advances_after_capture_tag_stays_on_retained_merge(self):
        retained, _ = self.capture()
        self.write("later.txt", "later main change")
        self.assertNotEqual(self.g("rev-parse", "main"), retained)
        self.tag(retained)
        self.assertEqual(self.g("rev-parse", "v1.2.0^{}"), retained)
        self.assertNotEqual(self.g("rev-parse", "v1.2.0^{}"), self.candidate)

    def test_successful_tag_retry_is_idempotent(self):
        self.tag()
        first = self.g("rev-parse", "v1.2.0")
        self.tag()
        self.assertEqual(self.g("rev-parse", "v1.2.0"), first)
        self.assertEqual(self.client.creations, 1)

    def test_different_existing_tag_is_not_moved(self):
        self.g("tag", "-a", "v1.2.0", self.candidate, "-m", "another release")
        first = self.g("rev-parse", "v1.2.0")
        with self.assertRaisesRegex(ValueError, "never moved"):
            self.tag()
        self.assertEqual(self.g("rev-parse", "v1.2.0"), first)

    def test_existing_tag_from_another_run_is_rejected(self):
        self.tag()
        self.metadata["buildId"] = "102"
        with self.assertRaises(ValueError):
            self.tag()
        self.assertEqual(self.client.creations, 1)

    def test_failed_swap_creates_no_tag(self):
        with self.assertRaisesRegex(ValueError, "successful mock Slot Swap"):
            self.tag(swapped="false")
        self.assertEqual(self.client.creations, 0)

    def test_incomplete_pr_cannot_progress(self):
        self.pr["status"] = "active"
        with self.assertRaisesRegex(ValueError, "exactly one"):
            self.capture()

    def test_pr_candidate_changed_cannot_progress(self):
        self.pr["lastMergeSourceCommit"]["commitId"] = "a" * 40
        with self.assertRaises(ValueError):
            self.capture()

    def test_ambiguous_completed_pr_is_rejected(self):
        self.client.duplicate = True
        with self.assertRaisesRegex(ValueError, "exactly one"):
            self.capture()

    def test_squash_merge_is_rejected(self):
        self.pr["lastMergeCommit"]["commitId"] = self.candidate
        with self.assertRaisesRegex(ValueError, "Merge commit"):
            self.capture()

    def test_rebase_merge_with_different_second_parent_is_rejected(self):
        commit = {"commitId": self.merge, "parents": ["b" * 40, "a" * 40]}
        with self.assertRaisesRegex(ValueError, "Merge commit"):
            promote.validate_merge(commit, self.metadata, self.g)

    def test_different_merged_tree_requires_new_uat(self):
        self.g("checkout", "main")
        (self.repo / "extra.txt").write_text("unaccepted change")
        self.g("add", "extra.txt")
        self.g("commit", "--amend", "--no-edit")
        self.pr["lastMergeCommit"]["commitId"] = self.g("rev-parse", "HEAD")
        with self.assertRaisesRegex(ValueError, "differs from UAT"):
            self.capture()

    def test_tag_rejects_wrong_retained_sha(self):
        with self.assertRaisesRegex(ValueError, "Retained Merge Commit"):
            self.tag(self.candidate)
        self.assertEqual(self.client.creations, 0)

    def test_hotfix_uses_its_own_main_merge(self):
        self.g("checkout", "-b", "hotfix/v1.2.1", "main")
        self.write("urgent.txt", "hotfix")
        self.candidate = self.g("rev-parse", "HEAD")
        self.g("checkout", "main")
        self.g("merge", "--no-ff", "hotfix/v1.2.1", "-m", "hotfix merge")
        self.merge = self.g("rev-parse", "HEAD")
        self.metadata.update(version="1.2.1", commitSha=self.candidate)
        self.pr.update(sourceRefName="refs/heads/hotfix/v1.2.1",
                       lastMergeSourceCommit={"commitId": self.candidate},
                       lastMergeCommit={"commitId": self.merge})
        os.environ.update(BUILD_SOURCEBRANCH=self.pr["sourceRefName"],
                          BUILD_SOURCEVERSION=self.candidate)
        self.assertEqual(self.capture()[0], self.merge)
        self.tag()
        self.assertEqual(self.g("rev-parse", "v1.2.1^{}"), self.merge)

    def test_release_branch_v_prefix(self):
        self.assertEqual(artifact.identity()["version"], "1.2.0")
        os.environ["BUILD_SOURCEBRANCH"] = "refs/heads/release/1.2.0"
        with self.assertRaises(ValueError):
            artifact.identity()

    def test_original_repository_is_rejected(self):
        os.environ["BUILD_REPOSITORY_NAME"] = "cicd-demo"
        with self.assertRaisesRegex(ValueError, "only in Azure Repos"):
            promote.require_mock_repository()

    def test_same_release_artifact_is_accepted_after_main_merge(self):
        folder = self.repo / "release-output"
        folder.mkdir()
        (folder / "webapp.zip").write_bytes(b"same-built-package")
        record = {**artifact.identity(), "sha256": artifact.digest(folder / "webapp.zip")}
        (folder / "release.json").write_text(json.dumps(record))
        self.write("later.txt", "main advanced after UAT")
        self.assertEqual(artifact.verify(folder)["commitSha"], self.candidate)

    def test_artifact_from_different_run_is_rejected(self):
        folder = self.repo / "release-output"
        folder.mkdir()
        (folder / "webapp.zip").write_bytes(b"same-built-package")
        record = {**artifact.identity(), "buildId": "999",
                  "sha256": artifact.digest(folder / "webapp.zip")}
        (folder / "release.json").write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, "selected Pipeline run"):
            artifact.verify(folder)


class FakeAzureRepos:
    """API wrapper mock; commits and annotated tag creation use real local Git."""
    def __init__(self, case):
        self.case, self.creations, self.duplicate = case, 0, False

    def completed_pull_requests(self, branch):
        return [self.case.pr] * (2 if self.duplicate else 1)

    def pull_request(self, number):
        return self.case.pr

    def commit(self, sha):
        return self.case.commit(sha)

    def find_tag(self, name):
        if name not in self.case.g("tag", "--list").splitlines():
            return None
        return {"name": name,
                "taggedObject": {"objectId": self.case.g("rev-parse", name + "^{}")},
                "message": self.case.g("for-each-ref", "--format=%(contents)", "refs/tags/" + name)}

    def create_tag(self, payload):
        self.case.g("tag", "-a", payload["name"], payload["taggedObject"]["objectId"],
                    "-m", payload["message"])
        self.creations += 1
        return payload


if __name__ == "__main__":
    unittest.main()
