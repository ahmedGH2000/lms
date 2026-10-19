"""Reproduce partial upgrades and exercise the actual updater without Docker."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import pytest

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('verify_release', ROOT/'deploy/verify_release.py')
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


def release(tmp_path):
    root = tmp_path/'new'
    for name in ('nightjar_learning','frontend/src','deploy','scripts','docs','tests','licenses'):
        (root/name).mkdir(parents=True)
    (root/'nightjar_learning/accounts.py').write_text('def login(): pass\ndef register(): pass\n')
    (root/'nightjar_learning/community.py').write_text('def reviews(): pass\n')
    (root/'frontend/src/api.js').write_text('rpc("accounts.login"); rpc("accounts.register"); rpc("community.reviews");')
    for name in ('pyproject.toml','package.json','README.md','LICENSE','THIRD-PARTY-NOTICES.md'):
        (root/name).write_text('fixture')
    for name in ('verify_release.py','update-local.sh','backup_local.py'):
        shutil.copyfile(ROOT/'deploy'/name,root/'deploy'/name)
    (root/'deploy/compose.yaml').write_text('operator config')
    (root/'deploy/.env.example').write_text('template')
    verify.build(root)
    return root


def test_complete_release_and_all_frontend_methods(tmp_path):
    root = release(tmp_path)
    assert verify.verify(root)['api_methods'] == 3
    # Deployment configuration is user-owned, so local port/image changes are allowed.
    (root/'deploy/compose.yaml').write_text('local configuration')
    assert verify.verify(root)['files'] > 0


@pytest.mark.parametrize('name', ['nightjar_learning/accounts.py','nightjar_learning/community.py'])
def test_mixed_or_missing_backend_stops_release(tmp_path, name):
    root = release(tmp_path)
    (root/name).write_text('old backend without the new methods')
    with pytest.raises(RuntimeError, match='Different release'):
        verify.verify(root)
    (root/name).unlink()
    with pytest.raises(RuntimeError, match='Missing file'):
        verify.verify(root)


@pytest.mark.parametrize('fault', ['missing_method','wrong_install','unregistered'])
def test_import_check_detects_stale_python_package(tmp_path, monkeypatch, fault):
    from types import SimpleNamespace
    root = release(tmp_path)
    allowed = set()
    for name, methods in {'accounts':['login','register'], 'community':['reviews']}.items():
        module = SimpleNamespace(__file__=str(root/'nightjar_learning'/f'{name}.py'))
        for method in methods:
            function = lambda: None
            setattr(module,method,function)
            allowed.add(function)
        if name == 'accounts':
            if fault == 'missing_method': del module.login
            if fault == 'wrong_install': module.__file__=str(tmp_path/'old/accounts.py')
            if fault == 'unregistered': allowed.remove(module.login)
        monkeypatch.setitem(sys.modules,'nightjar_learning.'+name,module)
    monkeypatch.setitem(sys.modules,'frappe',SimpleNamespace(whitelisted=allowed))
    with pytest.raises(RuntimeError, match='different installation|unregistered API'):
        verify.verify(root,imports=True)


def updater(tmp_path):
    source = release(tmp_path)
    target = tmp_path/'existing'
    (target/'deploy').mkdir(parents=True)
    (target/'nightjar_learning').mkdir()
    (target/'nightjar_learning/accounts.py').write_text('old backend')
    (target/'deploy/.env').write_text('private-environment')
    (target/'deploy/compose.yaml').write_text('private-compose')
    (target/'keep.txt').write_text('user-file')
    binary = tmp_path/'bin'; binary.mkdir()
    docker = binary/'docker'
    docker.write_text('#!'+sys.executable+'\n'+'''
import json, os, sys
from pathlib import Path
args=sys.argv[1:]
with open(os.environ['CALLS'],'a') as f: f.write(json.dumps(args)+'\\n')
if 'config' in args:
    command=['bash','/workspace/deploy/init.sh'] if not os.environ.get('BAD_COMMAND') else ['bench','start']
    print(json.dumps({'services':{'app':{'command':command,'volumes':[{'type':'bind','source':str(Path.cwd()),'target':'/workspace'}]}}}))
if 'exec' in args and os.environ.get('FAIL_BACKUP'): sys.exit(9)
if 'cp' in args: Path(args[-1]).mkdir()
''')
    docker.chmod(0o755)
    env=dict(os.environ,PATH=str(binary)+os.pathsep+os.environ['PATH'],CALLS=str(tmp_path/'calls.jsonl'))
    return source,target,env


def test_updater_preserves_environment_and_exports_backup(tmp_path):
    source,target,env=updater(tmp_path)
    p=subprocess.run(['bash',str(source/'deploy/update-local.sh'),str(target)],env=env,capture_output=True,text=True)
    assert p.returncode == 0,p.stdout+p.stderr
    assert 'def login' in (target/'nightjar_learning/accounts.py').read_text()
    assert (target/'nightjar_learning/community.py').exists()
    assert (target/'deploy/.env').read_text() == 'private-environment'
    assert (target/'deploy/compose.yaml').read_text() == 'private-compose'
    assert (target/'keep.txt').read_text() == 'user-file'
    backup=next(tmp_path.glob('existing-before-update-*'))
    assert (backup/'site-backups').is_dir()
    assert (backup/'source/nightjar_learning/accounts.py').read_text() == 'old backend'
    calls=[json.loads(s) for s in Path(env['CALLS']).read_text().splitlines()]
    assert any('--force-recreate' in c for c in calls)
    assert not any('down' in c for c in calls)
    verify.verify(target)


@pytest.mark.parametrize('failure', ['FAIL_BACKUP','BAD_COMMAND'])
def test_updater_stops_before_copying_if_preflight_or_backup_fails(tmp_path,failure):
    source,target,env=updater(tmp_path)
    p=subprocess.run(['bash',str(source/'deploy/update-local.sh'),str(target)],env=dict(env,**{failure:'1'}),capture_output=True,text=True)
    assert p.returncode != 0
    assert (target/'nightjar_learning/accounts.py').read_text() == 'old backend'
    calls=[json.loads(s) for s in Path(env['CALLS']).read_text().splitlines()]
    assert not any('stop' in c or 'up' in c for c in calls)
