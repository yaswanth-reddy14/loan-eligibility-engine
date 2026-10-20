"""Build Linux Lambda dependencies using Python over Docker stdin (safe across PowerShell versions)."""

import hashlib
import json
import subprocess
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / ".serverless"
    output.mkdir(exist_ok=True)
    image = "public.ecr.aws/sam/build-python3.12:latest-x86_64"
    code = """import pathlib,shutil,subprocess,sys
package=pathlib.Path('/tmp/package')
package.mkdir()
subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check','--cache-dir','/pip-cache','-r','/input/backend/requirements.txt','-t',str(package)],check=True)
shutil.copytree('/input/backend/app',package/'app',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
shutil.copytree('/input/frontend',package/'frontend',ignore=shutil.ignore_patterns('dist','node_modules'))
shutil.copytree('/input/n8n',package/'n8n')
shutil.make_archive('/output/loan','zip',package)
"""
    args = [
        "docker",
        "run",
        "--rm",
        "-i",
        "--entrypoint",
        "python",
        "-v",
        str(output) + ":/output",
        "-v",
        "loan-engine-lambda-pip-cache:/pip-cache",
    ]
    for folder in ["backend", "frontend", "n8n"]:
        args += ["-v", str(root / folder) + ":/input/" + folder + ":ro"]
    args += [image, "-"]
    result = subprocess.run(args, input=code, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(result.stdout, end="")
    if result.returncode:
        raise SystemExit(result.returncode)
    artifact = output / "loan.zip"
    report = {
        "build_image": image,
        "build_image_id": subprocess.check_output(
            ["docker", "image", "inspect", image, "--format", "{{.Id}}"], text=True
        ).strip(),
        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "bytes": artifact.stat().st_size,
        "scope": "Linux artifact build only; runtime smoke and AWS deployment are separate",
    }
    (root / "reports").mkdir(exist_ok=True)
    (root / "reports/lambda-package.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
