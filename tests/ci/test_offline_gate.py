"""Run the real policy in isolated tiny pytest projects, including failure cases."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def run_case(tmp_path, body, *args, env=None):
    shutil.copyfile(ROOT / 'tests/conftest.py', tmp_path / 'conftest.py')
    (tmp_path / 'test_policy.py').write_text(body)
    return subprocess.run([sys.executable, '-m', 'pytest', '-q', *args, str(tmp_path)],
                          cwd=tmp_path, capture_output=True, text=True, env=env)


def test_strict_offline_gate_rejects_skipped_tests(tmp_path):
    result = run_case(tmp_path, 'import pytest\ndef test_skips(): pytest.skip("fixture missing")\n',
                      '--strict-offline', '--disable-socket', '--allow-unix-socket')
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'strict offline gate rejects skipped/xfail tests' in result.stdout


def test_strict_offline_gate_requires_network_guard(tmp_path):
    result = run_case(tmp_path, 'def test_ok(): pass\n', '--strict-offline')
    assert result.returncode != 0
    assert 'requires --disable-socket' in result.stderr


def test_python_inet_socket_cannot_be_opened(tmp_path):
    result = run_case(tmp_path, '''import socket
import pytest
from pytest_socket import SocketBlockedError

def test_no_socket():
    with pytest.raises(SocketBlockedError):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
''', '--strict-offline', '--disable-socket', '--allow-unix-socket')
    assert result.returncode == 0, result.stdout + result.stderr
    assert '1 passed' in result.stdout
