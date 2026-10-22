"""Run on the deployment workstation after dependency installation. Fails closed.

No Microsoft/Claude calls and no secrets are read. Live acceptance remains separate.
"""
import importlib.metadata as metadata
import os
from pathlib import Path
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
os.chdir(root)
required={"mcp":"2.3.0","msal":"1.39.0","pypdf":"6.21.2"}
for package,version in required.items():
    try: actual=metadata.version(package)
    except metadata.PackageNotFoundError: raise SystemExit(f"Missing {package}; install requirements before release.")
    if actual!=version: raise SystemExit(f"{package}: expected {version}; found {actual}. Review before release.")
subprocess.run([sys.executable,"-m","pip","check"],check=True)
environment={**os.environ,"REQUIRE_SDK_TESTS":"1"}
subprocess.run([sys.executable,"-m","pytest","-q","--junitxml=reports/deployment-tests.xml"],env=environment,check=True)
subprocess.run([sys.executable,"-m","compileall","-q","src"],check=True)
print("Local installation and SDK tests passed. Tenant/Claude live acceptance is STILL required.")
