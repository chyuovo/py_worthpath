"""Reject sensitive paths and accidentally staged real environment values."""
from pathlib import Path
import re, subprocess
files=subprocess.check_output(["git","diff","--cached","--name-only","--diff-filter=ACMR","-z"]).decode().split(chr(0))
bad=[]
for name in filter(None,files):
    path=Path(name)
    if (path.name.startswith(".env") and path.name!=".env.example") or any(x in path.parts for x in ("backups","node_modules",".venv","runtime","data")) or path.suffix in (".pem",".key",".pfx",".p12",".sql",".dump"):
        bad.append(name)
    content=subprocess.check_output(["git","show",":"+name])
    if re.search(rb"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----",content): bad.append(name)
    if re.search(rb"mysql(?:\+pymysql)?://(?!USER:|USER@|<)[^\s\x22]+:[^\s\x22]+@",content): bad.append(name)
if bad: raise SystemExit("Sensitive staged files: "+", ".join(bad))
print("Staged secret/path check passed ("+str(len(list(filter(None,files))))+" files)")
