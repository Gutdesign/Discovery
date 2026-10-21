"""Run the expert-posts pipeline for all remaining companies, batch by batch (each batch: tasks 3 -> 4 -> 5).

Usage: python scripts/linkedin_experts_all.py <raw_dir> <companies_input.csv> <batch_size> <first_batch_no> [skip names...]
Companies already present in any <raw_dir>/*/company_match.csv or pilot are skipped.
"""
import csv
import pathlib
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parent.parent


def main():
    raw, inp, size, first = pathlib.Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    skip = set(sys.argv[5:])
    for f in raw.glob("*/company_match.csv"):
        skip |= {r["компания"] for r in csv.DictReader(open(f, encoding="utf-8-sig"), delimiter=";")}
    names = [r["компания"] for r in csv.DictReader(open(inp, encoding="utf-8-sig"), delimiter=";") if r["компания"] not in skip]
    print(f"{len(names)} companies to run")
    for i in range(0, len(names), size):
        d = raw / f"batch_{first + i // size:02d}"
        print(f"=== {d.name}: {names[i:i + size]}", flush=True)
        r = subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "linkedin_experts_batch.py"), str(d)] + names[i:i + size])
        print(f"=== {d.name} exit {r.returncode}", flush=True)


if __name__ == "__main__":
    main()
