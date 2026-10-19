import importlib.util
import json
import os
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('local_backup',Path(__file__).parents[1]/'deploy/backup_local.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

@pytest.mark.parametrize('host,skip_tls',[('db',True),('remote.example.invalid',False)])
def test_local_only_tls_override_and_cleanup(tmp_path,monkeypatch,host,skip_tls):
    bench=tmp_path/'bench';site=bench/'sites/nightjar.localhost';site.mkdir(parents=True)
    (site/'site_config.json').write_text(json.dumps({'db_host':host}))
    binary=tmp_path/'bin';binary.mkdir()
    (binary/'bench').write_text('#!/bin/sh\nexec mariadb-dump --user=test --single-transaction\n')
    (binary/'mariadb-dump').write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$BACKUP_TEST_OUTPUT"\nexit "${BACKUP_TEST_STATUS:-0}"\n')
    for p in binary.iterdir():p.chmod(0o755)
    monkeypatch.setenv('PATH',str(binary)+os.pathsep+os.environ['PATH'])
    monkeypatch.setenv('BACKUP_TEST_OUTPUT',str(tmp_path/'arguments'))
    monkeypatch.setenv('BACKUP_TEST_STATUS','9')
    original=os.environ['PATH']
    assert module.backup(bench)==9
    args=(tmp_path/'arguments').read_text().splitlines()
    assert ('--skip-ssl' in args)==skip_tls
    assert '--single-transaction' in args and os.environ['PATH']==original
    assert not (bench/'.my.cnf').exists()
