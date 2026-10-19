import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / 'deploy' / 'production'


def test_deployment_shell_scripts_are_valid():
    scripts = [
        PRODUCTION / 'nightjar-deploy',
        PRODUCTION / 'nightjar-ssh-entry',
        PRODUCTION / 'install-ci-deployer.sh',
    ]
    subprocess.run(['bash', '-n', *map(str, scripts)], check=True)


def test_deployer_is_scoped_and_backs_up_before_update():
    script = (PRODUCTION / 'nightjar-deploy').read_text()
    assert 'docker compose -p nightjar-learning' in script
    assert 'backup_local.py' in script
    assert script.index('backup_local.py') < script.index('compose_new=')
    assert 'docker compose down' not in script
    assert 'docker volume' not in script
    assert 'docker system prune' not in script
    assert 'ghcr.io/ahmedgh2000/lms:$commit' in script


def test_deployment_key_allows_probe_but_rejects_other_commands():
    entry = PRODUCTION / 'nightjar-ssh-entry'
    environment = dict(os.environ, SSH_ORIGINAL_COMMAND='nightjar-probe')
    accepted = subprocess.run(
        ['bash', str(entry)], env=environment, text=True, capture_output=True
    )
    assert accepted.returncode == 0
    assert 'accepted' in accepted.stdout

    environment['SSH_ORIGINAL_COMMAND'] = 'bash'
    rejected = subprocess.run(
        ['bash', str(entry)], env=environment, text=True, capture_output=True
    )
    assert rejected.returncode != 0
    assert 'only deploy' in rejected.stderr


def test_workflow_targets_main_and_the_production_environment():
    workflow = (ROOT / '.github' / 'workflows' / 'deploy-production.yml').read_text()
    assert 'branches: [main]' in workflow
    assert 'environment: production' in workflow
    assert 'cancel-in-progress: false' in workflow
    assert 'sudo /usr/local/sbin/nightjar-deploy "$GITHUB_SHA" "$IMAGE"' in workflow


def test_runtime_assets_are_not_shadowed_by_a_host_source_mount():
    compose = (PRODUCTION / 'compose.yaml').read_text()
    assert '../../nightjar_learning/public:' not in compose
