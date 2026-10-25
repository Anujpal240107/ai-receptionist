"""Check the pinned runtime graph against OSV; fail closed on incomplete results."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import httpx

def main():
    packages=[]
    for line in Path("requirements.txt").read_text(encoding="utf-8-sig").splitlines():
        if "==" in line and not line.startswith("#"):
            name,version=line.split("==",1)
            packages.append((name,version))
    queries=[{"package":{"name":name,"ecosystem":"PyPI"},"version":version} for name,version in packages]
    r=httpx.post("https://api.osv.dev/v1/querybatch",json={"queries":queries},timeout=30,follow_redirects=False)
    r.raise_for_status()
    results=r.json()["results"]
    if len(results)!=len(packages):raise RuntimeError("Incomplete advisory results")
    findings=[{"name":name,"version":version,"vulnerabilities":item.get("vulns",[])}
              for (name,version),item in zip(packages,results)]
    proof={"generatedAt":datetime.now(timezone.utc).isoformat(),"service":"OSV","packages":findings}
    Path("evidence").mkdir(exist_ok=True)
    Path("evidence/runtime-osv-audit.json").write_text(json.dumps(proof,indent=2),encoding="utf-8")
    count=sum(bool(f["vulnerabilities"]) for f in findings)
    print(f"Checked {len(packages)} runtime packages; {count} have published advisories.")
    return 1 if count else 0

if __name__=="__main__":
    try:sys.exit(main())
    except Exception:
        print("Dependency audit unavailable or incomplete. Release is blocked.",file=sys.stderr)
        sys.exit(2)

