"""Standard backup with a process-scoped dump-client fix for the local Compose DB."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile


def default_bench():
    configured = os.environ.get('BENCH_PATH')
    if configured:
        return Path(configured)
    production = Path('/home/frappe/frappe-bench')
    return production if production.is_dir() else Path('/home/frappe/work/bench')


def backup(bench=None):
    bench = Path(bench) if bench else default_bench()
    site = os.environ.get('SITE_NAME', 'nightjar.localhost')
    config = json.loads((bench/'sites'/site/'site_config.json').read_text())
    common_path = bench/'sites/common_site_config.json'
    common = json.loads(common_path.read_text()) if common_path.exists() else {}
    host = config.get('db_host') or common.get('db_host')
    command = ['bench', '--site', site, 'backup', '--with-files']
    # External hosts retain their existing TLS configuration.
    if host != 'db':
        return subprocess.run(command, cwd=bench).returncode
    binary = shutil.which('mariadb-dump') or shutil.which('mysqldump')
    if not binary:
        raise SystemExit('MariaDB backup client is missing. No update was applied.')
    with tempfile.TemporaryDirectory(prefix='nightjar-local-backup-') as tmp:
        for name in ('mariadb-dump', 'mysqldump'):
            wrapper = Path(tmp)/name
            wrapper.write_text('#!/bin/sh\nexec '+shlex.quote(binary)+' --skip-ssl "$@"\n')
            wrapper.chmod(0o700)
        return subprocess.run(command, cwd=bench, env=dict(os.environ, PATH=tmp+os.pathsep+os.environ['PATH'])).returncode


if __name__ == '__main__':
    raise SystemExit(backup())
