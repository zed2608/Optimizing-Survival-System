"""Read-only integrity and CSV inventory; does not load pickle or train models."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    manifest=json.loads((ROOT/"docs/research-baseline.json").read_text(encoding="utf-8"))
    failures=[]
    for item in manifest["files"]:
        path=ROOT/item["path"]
        if not path.is_file():
            failures.append(item["path"]+": missing")
            continue
        data=path.read_bytes()
        digest=hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
        if digest!=item["git_blob_sha"]:
            failures.append(item["path"]+": changed")
        if path.suffix.lower()==".csv":
            with path.open(encoding="utf-8-sig",newline="") as stream:
                reader=csv.reader(stream)
                headers=next(reader,[])
                count=sum(1 for _ in reader)
            print(f"{item['path']}: {count} rows; {', '.join(headers)}")
    if failures:
        raise SystemExit("\n".join(failures))
    print(f"Verified {len(manifest['files'])} protected research files against baseline.")

if __name__=="__main__":
    main()
