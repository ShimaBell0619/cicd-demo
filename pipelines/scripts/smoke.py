"""Poll a health endpoint for this artifact AND the intended environment."""
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_health(url):
    request = urllib.request.Request(url.rstrip("/") + "/api/health",
                                     headers={"Cache-Control": "no-cache"})
    with urllib.request.build_opener(NoRedirect).open(request, timeout=10) as response:
        if response.status != 200:
            raise ValueError(f"Health returned HTTP {response.status}")
        body = json.load(response)
    if not isinstance(body, dict):
        raise ValueError("Health must return a JSON object")
    return body


def matches(body, metadata, environment):
    expected = {"status": "ok", "service": "cicd-demo-nextjs",
                "environment": environment,
                **{key: metadata[key] for key in ("version", "commitSha", "buildId")}}
    return all(body.get(key) == value for key, value in expected.items())


def smoke(url, metadata, environment, attempts=30, delay=5):
    for attempt in range(1, attempts + 1):
        try:
            body = read_health(url)
            if matches(body, metadata, environment):
                print(json.dumps(body))
                return
        except (OSError, ValueError, urllib.error.URLError) as error:
            print(f"Health unavailable: {type(error).__name__}")
        print(f"Waiting for {environment}: run {metadata['buildId']} ({attempt}/{attempts})")
        if attempt < attempts:
            time.sleep(delay)
    raise RuntimeError("Expected artifact identity did not become healthy; stop promotion")


if __name__ == "__main__":
    smoke(sys.argv[1], json.loads(Path(sys.argv[2]).read_text()), sys.argv[3])
