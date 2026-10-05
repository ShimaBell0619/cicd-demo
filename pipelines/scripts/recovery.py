"""Operator recovery: select an exact retained Run; never build or create a tag."""
import json
import os
import re
import sys
import urllib.request

from artifact import verify
from promote import verify_tag_response
from smoke import read_health


def ado(path):
    base = os.environ['SYSTEM_COLLECTIONURI'] + os.environ['SYSTEM_TEAMPROJECTID'] + '/_apis/'
    request = urllib.request.Request(base + path, headers={'Authorization': 'Bearer ' + os.environ['SYSTEM_ACCESSTOKEN']})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def selected(directory):
    run_id = os.environ['SELECTED_RUN']
    if not re.fullmatch(r'[1-9][0-9]*', run_id):
        raise ValueError('Select a numeric original Release Run ID')
    source = ado('build/builds/' + run_id + '?api-version=7.1')
    if str(source['definition']['id']) != os.environ['SELECTED_PIPELINE'] or source['status'] != 'completed':
        raise ValueError('Original Run is not completed or belongs to another Pipeline')
    os.environ.update(RELEASE_BUILD='true', BUILD_SOURCEBRANCH=source['sourceBranch'],
                      BUILD_SOURCEVERSION=source['sourceVersion'], BUILD_BUILDID=run_id)
    metadata = verify(directory)
    repo = 'git/repositories/' + os.environ['BUILD_REPOSITORY_ID']
    name = 'v' + metadata['version']
    refs = ado(repo + '/refs?filter=tags/' + name + '&api-version=7.1')
    exact = [x for x in refs.get('value', []) if x['name'] == 'refs/tags/' + name]
    if len(exact) != 1:
        raise ValueError('Original Artifact must have exactly one retained annotated tag')
    tag = ado(repo + '/annotatedtags/' + exact[0]['objectId'] + '?api-version=7.1')
    verify_tag_response(tag, metadata)
    print('Verified exact source Run, ZIP and unchanged annotated tag:', json.dumps(metadata))
    return metadata


def before_production(directory, url):
    metadata = selected(directory)
    mode = os.environ['RECOVERY_MODE']
    if mode not in ('rollback', 'dr-only'):
        raise ValueError('Unknown recovery mode')
    if not re.fullmatch(r'[1-9][0-9]*', os.environ['EXPECTED_CURRENT_RUN']):
        raise ValueError('Select the expected current PROD Run ID explicitly')
    if mode == 'rollback' and os.environ.get('SYSTEM_STAGEATTEMPT', '1') != '1':
        raise ValueError('Do not retry a stage that can swap PROD')
    try:
        current = read_health(url)
    except (OSError, ValueError):
        raise ValueError('Cannot read current PROD identity') from None
    if (current.get('status') != 'ok' or current.get('environment') != 'prod'
            or current.get('service') != 'cicd-demo-nextjs'
            or current.get('buildId') != os.environ['EXPECTED_CURRENT_RUN']):
        raise ValueError('Current PROD differs from the operator-selected expected Run')
    if mode == 'dr-only':
        if any(current.get(key) != metadata[key] for key in ['version', 'commitSha', 'buildId']):
            raise ValueError('DR recovery Artifact is not current PROD')
    elif mode == 'rollback':
        if current['buildId'] == metadata['buildId']:
            raise ValueError('PROD is already the rollback Run; do not swap twice')
    print('Recovery current-PROD guard passed:', current['buildId'], mode)


if __name__ == '__main__':
    action, directory, url = sys.argv[1:]
    if action == 'before-prod':
        before_production(directory, url)
    elif action == 'before-dr':
        metadata = selected(directory)
        current = read_health(url)
        if (current.get('environment') != 'prod' or current.get('status') != 'ok'
                or current.get('service') != 'cicd-demo-nextjs'
                or any(current.get(k) != metadata[k] for k in ['version', 'commitSha', 'buildId'])):
            raise ValueError('Selected DR Artifact no longer matches current PROD')
        print('Current PROD matches selected original Artifact; DR-only write allowed')
    else:
        raise ValueError('Unknown recovery action')
