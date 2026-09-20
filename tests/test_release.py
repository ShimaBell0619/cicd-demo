"""Regression cases that could deploy a wrong artifact or overwrite newer PROD."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipelines/scripts"))
import artifact
import promote
import smoke


class ArtifactTests(unittest.TestCase):
    def test_reject_corruption_and_wrong_run(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {
            "BUILD_SOURCEVERSION": "a" * 40, "BUILD_BUILDID": "42", "RELEASE_BUILD": "true",
            "BUILD_SOURCEBRANCH": "refs/heads/release/1.2.3",
        }):
            directory = Path(root)
            package = directory / "webapp.zip"
            package.write_bytes(b"built-once")
            metadata = {**artifact.identity(), "sha256": artifact.digest(package)}
            (directory / "release.json").write_text(json.dumps(metadata))
            self.assertEqual(artifact.verify(directory), metadata)
            with patch.dict(os.environ, {"BUILD_BUILDID": "43"}):
                with self.assertRaisesRegex(ValueError, "identity"):
                    artifact.verify(directory)
            package.write_bytes(b"corrupted")
            with self.assertRaisesRegex(ValueError, "checksum"):
                artifact.verify(directory)

    def test_release_names_are_stable_semver(self):
        with patch.dict(os.environ, {"BUILD_SOURCEVERSION": "a" * 40,
                                    "BUILD_BUILDID": "42", "RELEASE_BUILD": "true"}):
            for branch in ("feature/1.2.3", "release/01.2.3", "hotfix/1.2.3-rc.1", "main"):
                with self.subTest(branch=branch), patch.dict(os.environ, {
                    "BUILD_SOURCEBRANCH": "refs/heads/" + branch,
                }), self.assertRaises(ValueError):
                    artifact.identity()
            for kind in ("release", "hotfix"):
                with patch.dict(os.environ, {"BUILD_SOURCEBRANCH": f"refs/heads/{kind}/1.2.3"}):
                    self.assertEqual(artifact.identity()["version"], "1.2.3")


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.previous_directory = os.getcwd()
        os.chdir(self.directory.name)
        self.addCleanup(os.chdir, self.previous_directory)
        self.env = patch.dict(os.environ, {"SYSTEM_STAGEATTEMPT": "1"})
        self.env.start()
        self.addCleanup(self.env.stop)
        subprocess.run(["git", "init", "--bare", "origin.git"], check=True, capture_output=True)
        Path("work").mkdir()
        os.chdir("work")
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("remote", "add", "origin", "../origin.git")
        self.base = self.commit("initial production", "base")
        self.git("switch", "-c", "release/1.1.0")
        self.source = self.commit("candidate", "candidate")
        self.git("switch", "main")
        self.git("merge", "--no-ff", "release/1.1.0", "-m", "Reviewed release PR")
        self.git("push", "origin", "main")
        self.metadata = {"version": "1.1.0", "commitSha": self.source, "buildId": "42", "sha256": "b" * 64}
        self.current = {"status": "ok", "service": "cicd-demo-nextjs", "environment": "prod",
                        "version": "1.0.0", "commitSha": self.base, "buildId": "40"}

    def git(self, *args):
        return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL).strip()

    def commit(self, message, content):
        Path("app.txt").write_text(content)
        self.git("add", ".")
        self.git("commit", "-m", message)
        return self.git("rev-parse", "HEAD")

    def guard(self, current=None, first=False):
        with patch.object(promote, "read_health", return_value=current or self.current):
            promote.guard(self.metadata, "https://prod.invalid", first)

    def test_accept_reviewed_merge(self):
        self.guard()

    def test_reject_main_change_after_uat(self):
        self.commit("hotfix overtakes release", "hotfix")
        self.git("push", "origin", "main")
        with self.assertRaisesRegex(ValueError, "main differs"):
            self.guard()

    def test_reject_unmerged_candidate(self):
        self.git("switch", "release/1.1.0")
        self.metadata["commitSha"] = self.commit("change after UAT", "changed")
        with self.assertRaises(subprocess.CalledProcessError):
            self.guard()

    def test_numeric_versions_block_reuse_and_downgrade(self):
        self.assertGreater(promote.version_tuple("1.10.0"), promote.version_tuple("1.9.0"))
        self.git("tag", "v1.10.0", self.base)
        self.git("push", "origin", "v1.10.0")
        with self.assertRaisesRegex(ValueError, "greater"):
            self.guard()

    def test_already_swapped_but_not_tagged_is_not_redeployed(self):
        current = {**self.current, **self.metadata}
        with self.assertRaisesRegex(ValueError, "already runs"):
            self.guard(current)

    def test_current_prod_must_be_in_candidate_history(self):
        self.git("switch", "-c", "other-production", self.base)
        unrelated_sha = self.commit("separate hotfix", "other")
        with self.assertRaises(subprocess.CalledProcessError):
            self.guard({**self.current, "commitSha": unrelated_sha})

    def test_first_deployment_is_explicit_and_cannot_ignore_existing_tags(self):
        with patch.object(promote, "read_health", side_effect=OSError("unreachable")):
            with self.assertRaisesRegex(ValueError, "Cannot read"):
                promote.guard(self.metadata, "https://prod.invalid")
            promote.guard(self.metadata, "https://prod.invalid", first_release=True)
            self.git("tag", "v1.0.0", self.base)
            with self.assertRaisesRegex(ValueError, "Cannot read"):
                promote.guard(self.metadata, "https://prod.invalid", first_release=True)

    def test_production_stage_retry_is_blocked(self):
        with patch.dict(os.environ, {"SYSTEM_STAGEATTEMPT": "2"}):
            with self.assertRaisesRegex(ValueError, "Do not rerun"):
                self.guard()


class SmokeAndTagTests(unittest.TestCase):
    def setUp(self):
        self.metadata = {"version": "1.1.0", "commitSha": "a" * 40,
                         "buildId": "42", "sha256": "b" * 64}
        self.healthy = {**self.metadata, "status": "ok", "service": "cicd-demo-nextjs", "environment": "prod"}

    def test_wrong_slot_and_stale_artifact_do_not_pass(self):
        for field, value in (("environment", "prod-staging"), ("commitSha", "c" * 40),
                             ("buildId", "41"), ("version", "1.0.0"), ("status", "failed")):
            with self.subTest(field=field), patch.object(smoke, "read_health", return_value={
                **self.healthy, field: value,
            }), self.assertRaises(RuntimeError):
                smoke.smoke("https://prod.invalid", self.metadata, "prod", attempts=1)

    def test_smoke_waits_for_new_identity(self):
        with patch.object(smoke, "read_health", side_effect=[
            {**self.healthy, "buildId": "41"}, self.healthy,
        ]) as request:
            smoke.smoke("https://prod.invalid", self.metadata, "prod", attempts=2, delay=0)
            self.assertEqual(request.call_count, 2)

    def test_tag_uses_annotated_tags_api_and_verifies_response(self):
        response = {"name": "refs/tags/v1.1.0", "taggedObject": {"objectId": "a" * 40},
                    "message": "pipelineRun=42; sha256=" + "b" * 64}
        with patch.dict(os.environ, {"SYSTEM_COLLECTIONURI": "https://dev.azure.com/example/",
                                    "SYSTEM_TEAMPROJECTID": "project", "BUILD_REPOSITORY_ID": "repo"}), \
                patch.object(promote.subprocess, "check_output", return_value=json.dumps(response)) as az:
            promote.create_tag(self.metadata)
            command = az.call_args.args[0]
            payload = json.loads(command[command.index("--body") + 1])
            self.assertEqual(payload["taggedObject"]["objectId"], self.metadata["commitSha"])
            self.assertEqual(payload["message"], response["message"])
            response["taggedObject"]["objectId"] = "c" * 40
            az.return_value = json.dumps(response)
            with self.assertRaisesRegex(ValueError, "differs"):
                promote.create_tag(self.metadata)


if __name__ == "__main__":
    unittest.main()
