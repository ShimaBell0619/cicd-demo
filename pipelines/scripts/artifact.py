"""The artifact contract: one ZIP, one identity record, one SHA-256."""
import hashlib
import json
import os
from pathlib import Path
import re
import sys

VERSION = r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"


def identity():
    commit = os.environ["BUILD_SOURCEVERSION"]
    build = os.environ["BUILD_BUILDID"]
    if not re.fullmatch(r"[0-9a-f]{40}", commit) or not re.fullmatch(r"[1-9][0-9]*", build):
        raise ValueError("Expected a full commit SHA and numeric Azure Pipelines Run ID")
    version = f"ci-{build}"
    if os.environ.get("RELEASE_BUILD", "false").lower() == "true":
        branch = os.environ["BUILD_SOURCEBRANCH"]
        if not re.fullmatch(r"refs/heads/(release|hotfix)/" + VERSION, branch):
            raise ValueError("Select release/X.Y.Z or hotfix/X.Y.Z (no leading zeroes)")
        version = branch.rsplit("/", 1)[1]
    return {"version": version, "commitSha": commit, "buildId": build}


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify(directory):
    directory = Path(directory)
    metadata = json.loads((directory / "release.json").read_text())
    if any(metadata.get(key) != value for key, value in identity().items()):
        raise ValueError("Artifact identity differs from the selected Pipeline run")
    if metadata.get("sha256") != digest(directory / "webapp.zip"):
        raise ValueError("Artifact ZIP checksum mismatch")
    return metadata


def main():
    action = sys.argv[1]
    if action == "embed":
        Path("app/release-info.generated.js").write_text(
            "// Generated at build time; identical in every environment.\n"
            f"export const releaseInfo = Object.freeze({json.dumps(identity())});\n"
        )
        return
    directory = Path(sys.argv[2])
    if action == "create":
        metadata = {**identity(), "sha256": digest(directory / "webapp.zip")}
        (directory / "release.json").write_text(json.dumps(metadata, indent=2) + "\n")
    elif action == "verify":
        metadata = verify(directory)
    else:
        raise ValueError(f"Unknown artifact action: {action}")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
