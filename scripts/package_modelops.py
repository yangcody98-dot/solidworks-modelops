"""Build a source-only skill ZIP from the Git index, with a SHA-256 manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {"SKILL.md", "README.md", "NOTICE.md", "LICENSE", "scripts/sw_modeling.py",
            "scripts/sw_checkpoints.py", "scripts/sw_modeling_regression.py"}
NATIVE = {".sldprt", ".sldasm", ".slddrw", ".step", ".stp", ".stl", ".iges", ".igs", ".dwg", ".dxf", ".bmp"}
SECRET = re.compile(rb"(?:ghp_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")


def package(output):
    output = Path(output).resolve()
    manifest_path = output.with_suffix(".manifest.json")
    if output.exists() or manifest_path.exists():
        raise FileExistsError("Use new ZIP and manifest paths")
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True)
    names = sorted(n.decode("utf-8") for n in result.stdout.split(b"\0") if n)
    if not REQUIRED.issubset(names):
        raise ValueError("Stage the complete source package with git add before packaging")
    records, payloads = [], {}
    for name in names:
        path = ROOT / name
        path.resolve().relative_to(ROOT.resolve())
        if (path.suffix.lower() in NATIVE or any(p in {".git", "__pycache__", "output", "checkpoints", ".venv"} for p in Path(name).parts)
                or path.name == ".env" or path.name.startswith(".env.")):
            raise ValueError(f"Generated/private artifact is staged: {name}")
        data = path.read_bytes()
        if SECRET.search(data):
            raise ValueError(f"Credential-like material is staged: {name}")
        payloads[name] = data
        records.append({"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in payloads.items():
            archive.writestr("solidworks-modelops/" + name, data)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP CRC verification failed")
        for record in records:
            content = archive.read("solidworks-modelops/" + record["path"])
            if hashlib.sha256(content).hexdigest() != record["sha256"]:
                raise RuntimeError("ZIP content differs from source manifest")
    summary = {"name": "solidworks-modelops", "version": "0.1.0", "files": len(records),
               "zip_sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "entries": records}
    with manifest_path.open("x", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
    return {"zip": str(output), "manifest": str(manifest_path), "files": len(records), "sha256": summary["zip_sha256"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    print(json.dumps(package(parser.parse_args().output), ensure_ascii=False))
