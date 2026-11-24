"""Download RCAEval cases one by one from HuggingFace.

The HF copy stores Parquet per case, so we never download the whole 3.4GB
dataset. Default endpoint is the China mirror; override with HF_ENDPOINT.
"""

from __future__ import annotations

import argparse
import os
from collections import defaultdict
from pathlib import Path

import httpx

from eval.hf_adapter import parse_hf_case_name

DATASET = "phamquiluan/RCAEval"
DEFAULT_ENDPOINT = "https://hf-mirror.com"


def endpoint() -> str:
    return os.getenv("HF_ENDPOINT", DEFAULT_ENDPOINT).rstrip("/")


def list_case_dirs(prefix: str = "re2ob_") -> list[str]:
    url = f"{endpoint()}/api/datasets/{DATASET}/tree/main"
    params: dict | None = {"recursive": "true", "limit": "1000"}
    cases: set[str] = set()
    while url:
        response = httpx.get(url, params=params, timeout=90)
        response.raise_for_status()
        for item in response.json():
            path = item.get("path", "")
            if item.get("type") == "file" and "/" in path:
                case = path.split("/")[0]
                if case.startswith(prefix):
                    cases.add(case)
            elif item.get("type") == "directory" and path.startswith(prefix):
                cases.add(path)
        link = response.headers.get("link", "")
        if 'rel="next"' in link:
            url = link.split("<")[1].split(">")[0]
            params = None
        else:
            url = ""
    return sorted(cases)


def select_balanced(cases: list[str], limit: int) -> list[str]:
    groups: dict[str, list[str]] = defaultdict(list)
    for case in cases:
        try:
            groups[parse_hf_case_name(case)["raw_fault"]].append(case)
        except ValueError:
            continue
    selected: list[str] = []
    faults = sorted(groups)
    while len(selected) < limit and any(groups.values()):
        for fault in faults:
            if groups[fault] and len(selected) < limit:
                selected.append(groups[fault].pop(0))
    return selected


def download_file(case: str, filename: str, out_dir: Path) -> Path:
    dest = out_dir / case / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    url = f"{endpoint()}/datasets/{DATASET}/resolve/main/{case}/{filename}"
    with httpx.stream("GET", url, timeout=120, follow_redirects=True) as response:
        response.raise_for_status()
        with dest.open("wb") as handle:
            for chunk in response.iter_bytes(1024 * 1024):
                handle.write(chunk)
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description="Download RCAEval cases from HF")
    parser.add_argument("--prefix", default="re2ob_", help="re1ob_ / re2ob_ / re2ss_ ...")
    parser.add_argument("--limit", default=40, type=int)
    parser.add_argument("--out", default=Path("data/rcaeval_hf_raw"), type=Path)
    parser.add_argument("--with-traces", action="store_true", help="also download 10MB traces.parquet")
    parser.add_argument("--convert", action="store_true", help="convert to data/cases after download")
    args = parser.parse_args()

    cases = select_balanced(list_case_dirs(args.prefix), args.limit)
    print(f"selected {len(cases)} cases from {args.prefix}")
    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] {case}")
        for filename in ("metrics.parquet", "logs.parquet", "inject_time.txt"):
            download_file(case, filename, args.out)
        if args.with_traces:
            download_file(case, "traces.parquet", args.out)

    if args.convert:
        from eval.hf_adapter import prepare_hf_dataset

        written = prepare_hf_dataset(args.out, Path("data/cases"), args.limit)
        print(f"converted {len(written)} cases")


if __name__ == "__main__":
    main()
