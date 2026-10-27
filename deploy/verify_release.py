"""Check release completeness without reading secrets or changing the database."""
import argparse
import hashlib
import importlib
import json
import re
from pathlib import Path


def verify(root, imports=False):
    root = Path(root).resolve()
    manifest = json.loads((root / 'release-manifest.json').read_text())
    problems = []
    for name, digest in manifest['files'].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root):
            raise ValueError('Invalid release path')
        if not path.is_file():
            problems.append('Missing file: ' + name)
        elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            problems.append('Different release or local edits: ' + name)
    if imports and not problems:
        import frappe
        for method in manifest['methods']:
            module_name, name = method.rsplit('.', 1)
            try:
                module = importlib.import_module('nightjar_learning.' + module_name)
                if not Path(module.__file__).resolve().is_relative_to(root):
                    problems.append('Python imports a different installation: ' + module_name)
                function = getattr(module, name, None)
                if not callable(function) or function not in frappe.whitelisted:
                    problems.append('Missing or unregistered API: ' + method)
            except (ImportError, AttributeError) as exc:
                problems.append('Cannot import API ' + method + ': ' + str(exc))
    if problems:
        raise RuntimeError('\n'.join(problems) + '\nInstall the complete matching release before starting Nightjar.')
    return {'release': manifest['release'], 'files': len(manifest['files']), 'api_methods': len(manifest['methods'])}


def build(root):
    root = Path(root).resolve()
    files = {}
    for folder in ('nightjar_learning', 'frontend', 'deploy', 'scripts', '.github'):
        for path in sorted((root / folder).rglob('*')):
            relative = path.relative_to(root)
            if str(relative) in {'deploy/compose.yaml', 'deploy/.env.example'}:
                continue  # Operator-owned deployment configuration, not app code.
            if any(p in {'node_modules', '__pycache__', '.env', '.git'} for p in relative.parts):
                continue
            if path.is_file() and path.suffix not in {'.pyc', '.log'}:
                files[str(relative)] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ('pyproject.toml', 'package.json'):
        files[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    methods = set()
    for path in (root / 'frontend/src').glob('*'):
        if path.suffix in {'.vue', '.js'}:
            methods.update(re.findall(r'rpc\(\s*["\']([a-z_]+\.[a-z_]+)["\']', path.read_text()))
    # Native LMS methods are part of the same deployable API contract.
    patch = root / 'deploy/patches/lms-nightjar-payments.patch'
    if patch.exists():
        methods.update(re.findall(r"nightjar_learning\.(payments\.[a-z_]+)", patch.read_text()))
    manifest = {'release': '2026.10.26-preview.1', 'files': files, 'methods': sorted(methods)}
    (root / 'release-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--imports', action='store_true')
    parser.add_argument('--build', action='store_true', help='For maintainers after reviewing and building intentional source edits')
    args = parser.parse_args()
    if args.build:
        build(args.root)
    print(json.dumps(verify(args.root, args.imports)))
