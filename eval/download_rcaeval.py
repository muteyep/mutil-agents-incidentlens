"""Download RCAEval data with resume support.

Examples:
    python -m eval.download_rcaeval --sample
    python -m eval.download_rcaeval --url https://zenodo.org/records/14590730/files/RE2-OB.zip?download=1
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

SAMPLE_URL = (
    "https://github.com/phamquiluan/RCAEval/releases/download/0.2.0/multi-source-data.zip"
)
CHUNK = 1024 * 1024


def download(url: str, dest: Path, retries: int = 5) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, retries + 1):
        existing = part.stat().st_size if part.exists() else 0
        headers = {"Range": f"bytes={existing}-"} if existing else {}
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                mode = "ab" if existing and response.status == 206 else "wb"
                if mode == "wb":
                    existing = 0
                total = int(response.headers.get("Content-Length", 0)) + existing
                with part.open(mode) as handle:
                    while True:
                        chunk = response.read(CHUNK)
                        if not chunk:
                            break
                        handle.write(chunk)
                        existing += len(chunk)
                        if total:
                            print(f"\r{existing / total:6.1%}", end="", file=sys.stderr)
            part.rename(dest)
            print(f"\ndownloaded {dest} ({dest.stat().st_size / 1024 / 1024:.1f} MB)")
            return dest
        except Exception as exc:
            print(f"\nattempt {attempt}/{retries} failed: {exc}", file=sys.stderr)
            if attempt == retries:
                raise
            time.sleep(2 * attempt)
    raise RuntimeError("unreachable")


def extract(zip_path: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            target = (out_dir / member.filename).resolve()
            if not str(target).startswith(str(out_dir.resolve())):
                raise RuntimeError(f"unsafe path in zip: {member.filename}")
        archive.extractall(out_dir)
    print(f"extracted to {out_dir}")
    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Download RCAEval data")
    parser.add_argument("--sample", action="store_true", help="download the 12MB multi-source sample")
    parser.add_argument("--url", default="", help="custom zip URL")
    parser.add_argument("--out", default=Path("data/rcaeval_raw"), type=Path)
    parser.add_argument("--extract", action="store_true")
    args = parser.parse_args()

    url = args.url or (SAMPLE_URL if args.sample else "")
    if not url:
        parser.error("pass --sample or --url")

    name = url.split("/")[-1].split("?")[0] or "rcaeval.zip"
    zip_path = args.out / name
    download(url, zip_path)
    if args.extract or args.sample:
        extract(zip_path, args.out)
        print(
            "\nnext:\n"
            f"  python -m eval.rcaeval_adapter --root {args.out} --out data/cases --limit 40\n"
            "  python -m eval.runner"
        )


if __name__ == "__main__":
    main()
