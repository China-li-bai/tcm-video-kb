"""Opt-in CI gate for the full offline suite; interactive/local subsets stay usable."""
import shutil

import pytest


def pytest_addoption(parser):
    parser.addoption('--strict-offline', action='store_true', default=False,
                     help='Require local tools, disabled network sockets, and zero skip/xfail results')


def pytest_sessionstart(session):
    if not session.config.getoption('--strict-offline'):
        return
    if not session.config.getoption('--disable-socket', default=False):
        raise pytest.UsageError('--strict-offline requires --disable-socket (pytest-socket dev dependency)')
    missing = [tool for tool in ('ffmpeg', 'ffprobe', 'git') if shutil.which(tool) is None]
    if missing:
        raise pytest.UsageError('strict offline prerequisites missing: ' + ', '.join(missing))


def pytest_sessionfinish(session, exitstatus):
    if not session.config.getoption('--strict-offline'):
        return
    terminal = session.config.pluginmanager.get_plugin('terminalreporter')
    if terminal and any(terminal.stats.get(key) for key in ('skipped', 'xfailed', 'xpassed')):
        terminal.write_sep('=', 'strict offline gate rejects skipped/xfail tests; fix fixtures or explicitly separate integration')
        if exitstatus == pytest.ExitCode.OK:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
