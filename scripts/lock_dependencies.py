"""Resolve and hash a lock on an internet-enabled, approved build workstation.

Requires a separately installed uv CLI. Generated locks are not supplied as if
verified: this delivery environment could not access a package index.
"""
import argparse
from pathlib import Path
import subprocess

p=argparse.ArgumentParser(description=__doc__)
p.add_argument("--python-version",default="3.12")
a=p.parse_args()
root=Path(__file__).resolve().parents[1]
subprocess.run(["uv","pip","compile","requirements.txt","--python-version",a.python_version,
                "--generate-hashes","--output-file","requirements.lock"],cwd=root,check=True)
print("Review and commit requirements.lock after a clean installation, security audit, and release tests.")
