"""CI configuration is a tested contract, not a list of selected happy paths."""
from pathlib import Path
import shlex

import yaml

ROOT = Path(__file__).resolve().parents[2]


def workflow():
    return yaml.safe_load((ROOT / '.github/workflows/ci.yml').read_text())


def commands(job):
    return [step['run'] for step in workflow()['jobs'][job]['steps'] if 'run' in step]


def test_python_runs_entire_unit_and_ci_directories_without_selection():
    runs = commands('python')
    tests = [shlex.split(run) for run in runs if 'pytest' in run]
    assert len(tests) == 1
    command = tests[0]
    assert 'tests/unit' in command and 'tests/ci' in command
    assert not any(arg.endswith('.py') for arg in command)
    assert not {'-k', '-m', '--ignore', '--ignore-glob', '--deselect'} & set(command)
    assert {'--strict-offline', '--disable-socket', '--allow-unix-socket'} <= set(command)


def test_dependencies_are_locked_without_asr_extra():
    runs = commands('python')
    assert 'uv sync --locked' in runs
    assert all('--no-sync' in run for run in runs if 'uv run' in run)
    assert not any('--extra' in run or '--all-extras' in run for run in runs)
    setup = next(s for s in workflow()['jobs']['python']['steps'] if s.get('uses', '').startswith('astral-sh/setup-uv@'))
    assert setup['with']['python-version'] == '3.12'
    assert setup['with']['version'] == '0.13.7'


def test_local_integration_prerequisites_installed_and_checked():
    joined = '\n'.join(commands('python'))
    assert 'apt-get install' in joined and 'ffmpeg' in joined
    assert all(f'{tool} -version' in joined for tool in ('ffmpeg', 'ffprobe'))
    assert 'git --version' in joined


def test_no_job_or_step_hides_failures():
    for job in workflow()['jobs'].values():
        assert not job.get('continue-on-error')
        for step in job['steps']:
            assert not step.get('continue-on-error')
            command = step.get('run', '')
            assert '|| true' not in command and '|| exit 0' not in command


def test_publish_and_frontend_regression_gates_are_retained():
    assert 'python3 web/scripts/publish_manifest.py --check' in commands('python')
    assert 'python3 -m unittest discover -s tests/publish -v' in commands('python')
    assert {'npm ci', 'npm test', 'npm run build'} <= set(commands('web'))


def test_real_question_validator_is_a_strict_offline_ci_gate():
    runs = commands('python')
    assert 'python3 scripts/eval/validate_qa.py --strict-kp --json' in runs
