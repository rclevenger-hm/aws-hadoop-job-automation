"""Build an explicit Lambda artifact without tests, credentials or local config."""
import pathlib
import shutil
import subprocess
import sys
import zipfile

root = pathlib.Path(__file__).resolve().parents[1]
output = root / 'build' / 'lambda'
shutil.rmtree(output, ignore_errors=True)
output.mkdir(parents=True)
subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-compile', '--no-deps', '--require-hashes', '-r', str(root / 'requirements.txt'), '--target', str(output)], check=True)
shutil.copytree(root / 'app', output / 'app', ignore=shutil.ignore_patterns('__pycache__'))
(root / 'artifacts').mkdir(exist_ok=True)
with zipfile.ZipFile(root / 'artifacts' / 'lambda.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
    for file in sorted(output.rglob('*')):
        if file.is_file() and '__pycache__' not in file.parts and file.suffix != '.pyc':
            entry = zipfile.ZipInfo(file.relative_to(output).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, file.read_bytes())
print('Created artifacts/lambda.zip')
