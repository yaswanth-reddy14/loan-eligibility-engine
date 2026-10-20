"""Import and exercise the built zip in AWS's local Python 3.12 container, without AWS calls."""

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path


def main():
    artifact = Path(".serverless/loan.zip")
    if not artifact.exists():
        raise SystemExit("Run scripts/package_lambda.ps1 first")
    with zipfile.ZipFile(artifact) as archive:
        compared = [
            "app/main.py",
            "app/ingestion.py",
            "app/matching.py",
            "app/notifications.py",
            "frontend/app.js",
        ]
        for member in compared:
            source = Path("backend") / member if member.startswith("app/") else Path(member)
            assert archive.read(member) == source.read_bytes(), f"Stale artifact member: {member}"
        uncompressed_bytes = sum(item.file_size for item in archive.infolist())
    code = """import json,os,sys,zipfile,platform
from types import SimpleNamespace
with zipfile.ZipFile('/artifacts/loan.zip') as archive:
    names=archive.namelist()
    assert not any(n=='.env' or n.endswith('/.env') or n.endswith('users.csv') for n in names)
    archive.extractall('/tmp/artifact')
os.chdir('/tmp/artifact')
sys.path.insert(0,'/tmp/artifact')
import app.main,app.ingestion,app.cloud,psycopg,pydantic_core
context=SimpleNamespace(aws_request_id='local-artifact-smoke')
event={'version':'2.0','routeKey':'$default','rawPath':'/','rawQueryString':'','headers':{'host':'local.invalid'},'requestContext':{'http':{'method':'GET','path':'/','sourceIp':'127.0.0.1','protocol':'HTTP/1.1','userAgent':'artifact-smoke'},'stage':'$default'},'isBase64Encoded':False}
response=app.main.handler(event,context)
assert response['statusCode']==200 and 'Loan Eligibility Engine' in response['body']
event['rawPath']='/api/dashboard'
event['requestContext']['http']['path']='/api/dashboard'
unauthorized=app.main.handler(event,context)
assert unauthorized['statusCode']==401
assert app.ingestion.process_sqs({'Records':[]})=={'batchItemFailures':[]}
print(json.dumps({'python':platform.python_version(),'architecture':platform.machine(),'artifact_members':len(names),'native_imports':['psycopg','pydantic_core'],'root_status':200,'unauthenticated_api_status':401,'empty_sqs_batch':True,'dispatch_imported':callable(app.cloud.dispatch),'scope':'Local Lambda base-container import/ASGI invocation; no AWS deployment, database connectivity, S3/SQS integration or SES calls'}))
"""
    image = "public.ecr.aws/lambda/python:3.12-x86_64"
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--entrypoint",
            "python",
            "-v",
            str(artifact.parent.resolve()) + ":/artifacts:ro",
            "-e",
            "API_TOKEN=artifact-smoke-only-00000000000",
            "-e",
            "WORKFLOW_SECRET=artifact-secret-only-00000000000",
            "-e",
            "AWS_EC2_METADATA_DISABLED=true",
            image,
            "-c",
            code,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(result.stdout)
    report.update(
        source_members_verified=compared,
        uncompressed_bytes=uncompressed_bytes,
        artifact_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
        artifact_bytes=artifact.stat().st_size,
        runtime_image=image,
        runtime_image_id=subprocess.check_output(
            ["docker", "image", "inspect", image, "--format", "{{.Id}}"], text=True
        ).strip(),
    )
    Path("reports/lambda-artifact.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
