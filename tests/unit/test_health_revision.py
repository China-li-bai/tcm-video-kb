"""Build/HTTP/Worker-entry contracts; all temporary, no cloud or external network."""
import copy
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import types

from fastapi.testclient import TestClient
import pytest
from tcmkb_api.app import create_app

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / 'services/worker/build_metadata.py'
UNKNOWN = {'status': 'ok', 'git_sha': 'unknown', 'git_dirty': None, 'content_revision': 'unknown'}
VALID = {'schema': 'tcm-build/1', 'git_sha': 'a'*40, 'git_dirty': False, 'content_revision': 'b'*64}


def test_default_health_keeps_status_and_explicit_unknown_without_injection(monkeypatch):
    monkeypatch.setenv('GITHUB_SHA', 'c'*40)
    assert TestClient(create_app()).get('/health').json() == UNKNOWN


@pytest.mark.parametrize('metadata', [None, {}, {'schema': 'future'}, [], 'private/path', 4])
def test_missing_or_invalid_metadata_shape_is_safe_unknown(metadata):
    response = TestClient(create_app(build_info=metadata)).get('/health')
    assert response.status_code == 200
    assert response.json() == UNKNOWN


@pytest.mark.parametrize('field,value,expected', [
    ('git_sha', 'main', 'unknown'), ('git_sha', '../private/key', 'unknown'),
    ('git_sha', 'A'*40, 'unknown'), ('content_revision', 123, 'unknown'),
    ('content_revision', '2026-11-09T13:00:00', 'unknown'),
    ('content_revision', 'z'*64, 'unknown'), ('git_dirty', 'false', None),
    ('git_dirty', 0, None), ('git_dirty', True, True),
])
def test_invalid_fields_never_become_claimed_versions(field, value, expected):
    metadata = {**VALID, field: value}
    body = TestClient(create_app(build_info=metadata)).get('/health').json()
    assert body[field] == expected and body['status'] == 'ok'
    assert set(body) == set(UNKNOWN)


def test_injected_info_is_copied_and_extra_keys_or_environment_never_leak(monkeypatch):
    monkeypatch.setenv('PRIVATE_BUILD_TOKEN', 'fixture-must-not-leak')
    metadata = {**VALID, 'status': 'deployed', 'token': 'fixture-must-not-leak', 'path': '/private/build'}
    before = copy.deepcopy(metadata)
    client = TestClient(create_app(build_info=metadata))
    assert metadata == before
    metadata['git_sha'] = 'd'*40
    assert client.get('/health').json() == {'status': 'ok', **{k: VALID[k] for k in ('git_sha', 'git_dirty', 'content_revision')}}


def cmd(*args, cwd=None, env=None):
    return subprocess.run(list(map(str, args)), cwd=cwd, env=env, capture_output=True, text=True)


@pytest.fixture
def publication(tmp_path):
    root = tmp_path/'publication'; root.mkdir()
    def put(name, obj):
        path = root/name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, ensure_ascii=False))
    vid = 'shl-001'
    put('web/src/data/lectures.json', {'lectures': [{'id': vid, 'series': 'shl', 'youtubeId': 'abcdefghijk'}]})
    for folder, key, rows in [('transcripts', 'segments', [{'seq': 0, 'start_s': 0.5, 'end_s': 3, 'text': '真实临时发布测试'}]), ('knowledge', 'points', []), ('entities', 'mentions', [])]:
        put(f'web/public/{folder}/{vid}.json', {'video_id': vid, key: rows})
    put(f'web/src/data/chapters/{vid}.json', [{'video_id': vid, 'chapter_id': vid+'.c01', 'start_s': 0.5, 'end_s': 3}])
    result = cmd(sys.executable, ROOT/'web/scripts/publish_manifest.py', '--root', root)
    assert result.returncode == 0, result.stderr
    return root


def generate(root, *, env=None):
    out = root/'services/worker/src/build_info.py'
    result = cmd(sys.executable, GENERATOR, '--root', root, '--out', out, env=env)
    assert result.returncode == 0, result.stderr
    return out, runpy.run_path(str(out))['BUILD_INFO']


def init_git(root):
    (root/'.gitignore').write_text('/services/worker/src/build_info.py\n')
    (root/'code.py').write_text('VALUE = 1\n')
    for args in [('init', '-q'), ('add', '.'), ('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture')]:
        result = cmd('git', *args, cwd=root)
        assert result.returncode == 0, result.stderr
    return cmd('git', 'rev-parse', 'HEAD', cwd=root).stdout.strip()


def test_build_without_git_or_git_executable_is_explicit_unknown(publication):
    out, info = generate(publication)
    assert info['git_sha'] == 'unknown' and info['git_dirty'] is None
    _, missing_git = generate(publication, env={**os.environ, 'PATH': ''})
    assert missing_git == info
    assert info['content_revision'] == json.loads((publication/'web/src/data/publish-manifest.json').read_text())['content_sha256']
    assert str(publication) not in out.read_text()


def test_clean_build_is_repeatable_and_dirty_tracks_tracked_and_untracked_changes(publication):
    revision = init_git(publication)
    out, info = generate(publication); first = out.read_bytes()
    assert info['git_sha'] == revision and info['git_dirty'] is False
    assert generate(publication)[0].read_bytes() == first
    (publication/'code.py').write_text('VALUE = 2\n')
    assert generate(publication)[1]['git_dirty'] is True
    (publication/'code.py').write_text('VALUE = 1\n')
    (publication/'private-notes.txt').write_text('fixture-not-a-secret')
    assert generate(publication)[1]['git_dirty'] is True
    assert 'private-notes' not in out.read_text()
    (publication/'private-notes.txt').unlink()
    (publication/'code.py').unlink()
    assert generate(publication)[1]['git_dirty'] is True


def test_content_changes_require_fresh_manifest_and_change_hash_not_a_timestamp(publication):
    _, before = generate(publication)
    path = publication/'web/public/transcripts/shl-001.json'
    payload = json.loads(path.read_text()); payload['segments'][0]['text'] += '内容变化'
    path.write_text(json.dumps(payload, ensure_ascii=False))
    failed = cmd(sys.executable, GENERATOR, '--root', publication, '--out', publication/'invalid.py')
    assert failed.returncode != 0 and not (publication/'invalid.py').exists()
    assert str(publication) not in failed.stderr
    assert cmd(sys.executable, ROOT/'web/scripts/publish_manifest.py', '--root', publication).returncode == 0
    _, after = generate(publication)
    assert after['content_revision'] != before['content_revision']
    assert len(after['content_revision']) == 64
    assert after == generate(publication)[1]


def test_missing_manifest_fails_nonzero_without_creating_version(publication):
    (publication/'web/src/data/publish-manifest.json').unlink()
    out = publication/'absent.py'
    result = cmd(sys.executable, GENERATOR, '--root', publication, '--out', out)
    assert result.returncode != 0 and not out.exists()
    assert str(publication) not in result.stderr


def test_worker_entry_imports_same_generated_info_and_missing_injection_is_unknown(publication, monkeypatch):
    out, info = generate(publication)
    monkeypatch.syspath_prepend(str(ROOT/'services/worker/src'))
    monkeypatch.syspath_prepend(str(out.parent))
    monkeypatch.setitem(sys.modules, 'workers', types.SimpleNamespace(asgi=types.SimpleNamespace(entrypoint=lambda app: app)))
    previous = sys.modules.pop('build_info', None)
    try:
        entry = runpy.run_path(str(ROOT/'services/worker/src/entry.py'))
        assert TestClient(entry['app']).get('/health').json() == {'status': 'ok', **{k: info[k] for k in ('git_sha', 'git_dirty', 'content_revision')}}
        sys.modules.pop('build_info', None)
        out.unlink()
        entry = runpy.run_path(str(ROOT/'services/worker/src/entry.py'))
        assert TestClient(entry['app']).get('/health').json() == UNKNOWN
    finally:
        sys.modules.pop('build_info', None)
        if previous is not None:
            sys.modules['build_info'] = previous


def test_build_script_only_injects_after_successful_existing_build_steps():
    script = (ROOT/'services/worker/build.sh').read_text()
    assert 'set -euo pipefail' in script
    clear = script.index('rm -f services/worker/src/build_info.py')
    assert clear < script.index('copy_pkg packages/')
    assert script.index('npm run build --prefix web') < script.index('build_metadata.py')
    assert '--check' in script and 'publish_manifest.py' in script


def test_built_static_bytes_must_match_the_content_revision(publication):
    import shutil
    dist = publication/'web/dist'
    shutil.copytree(publication/'web/public', dist)
    out = publication/'checked.py'
    args = [sys.executable, GENERATOR, '--root', publication, '--dist', dist, '--out', out]
    result = cmd(*args)
    assert result.returncode == 0, result.stderr
    assert runpy.run_path(str(out))['BUILD_INFO']['content_revision'] == generate(publication)[1]['content_revision']
    out.unlink()
    (dist/'transcripts/shl-001.json').write_text('stale static asset')
    result = cmd(*args)
    assert result.returncode != 0 and not out.exists()
    assert str(publication) not in result.stderr
    (dist/'transcripts/shl-001.json').write_bytes((publication/'web/public/transcripts/shl-001.json').read_bytes())
    (dist/'entities/shl-001.json').unlink()
    assert cmd(*args).returncode != 0 and not out.exists()


def test_build_failure_removes_old_identity_and_success_injects_only_final_info(publication, monkeypatch):
    """Real shell+graph builder+metadata+HTTP; npm stand-in only for ordering/failure.

    Actual TS/Vite is a separate regression, not claimed by this harness.
    """
    import shutil
    for name in ['build.sh', 'build_metadata.py']:
        dest = publication/'services/worker'/name; dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT/'services/worker'/name, dest)
    for name in ['publish_manifest.py']:
        dest = publication/'web/scripts'/name; dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT/'web/scripts'/name, dest)
    for name in ['__init__.py', 'build_info.py']:
        dest = publication/'services/api/src/tcmkb_api'/name; dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT/'services/api/src/tcmkb_api'/name, dest)
    for folder in ['packages/tcmkb_core', 'packages/tcmkb_graph']:
        dest = publication/folder; dest.mkdir(parents=True); (dest/'fixture.txt').write_text('packaging ordering only')
    (publication/'.venv/bin').mkdir(parents=True)
    import shlex
    python = publication/'.venv/bin/python'
    python.write_text('#!/bin/bash\nexec ' + shlex.quote(sys.executable) + ' "$@"\n')
    python.chmod(0o755)
    fake_bin = publication/'fake-bin'; fake_bin.mkdir()
    npm = fake_bin/'npm'
    npm.write_text(f'#!{sys.executable}\n' + '''import os,shutil,sys
from pathlib import Path
if sys.argv[1] == 'run':
    if os.environ.get('FIXTURE_BUILD_FAIL') == '1': sys.exit(9)
    shutil.copytree(Path.cwd()/'web/public', Path.cwd()/'web/dist', dirs_exist_ok=True)
''')
    npm.chmod(0o755)
    monkeypatch.setenv('PATH', str(fake_bin)+os.pathsep+os.environ['PATH'])
    out = publication/'services/worker/src/build_info.py'; out.parent.mkdir(parents=True)
    out.write_text("BUILD_INFO = {'stale': True}\n")
    python.rename(python.with_suffix('.disabled'))
    missing_venv = cmd('bash', publication/'services/worker/build.sh')
    assert missing_venv.returncode != 0 and not out.exists(), missing_venv.stderr
    python.with_suffix('.disabled').rename(python)
    out.write_text("BUILD_INFO = {'stale': True}\n")
    monkeypatch.setenv('FIXTURE_BUILD_FAIL', '1')
    failed = cmd('bash', publication/'services/worker/build.sh')
    assert failed.returncode != 0 and not out.exists(), failed.stderr
    monkeypatch.setenv('FIXTURE_BUILD_FAIL', '0')
    succeeded = cmd('bash', publication/'services/worker/build.sh')
    assert succeeded.returncode == 0, succeeded.stderr
    info = runpy.run_path(str(out))['BUILD_INFO']
    assert TestClient(create_app(build_info=info)).get('/health').json()['content_revision'] == json.loads((publication/'web/src/data/publish-manifest.json').read_text())['content_sha256']
