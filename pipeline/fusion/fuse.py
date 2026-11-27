import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

from pipeline.width.estimate import width_class

SURFACES = ["paved", "dirt", "mud"]
MIN_CONFIDENCE = 0.5
CSV_FIELDS = ["way_id", "surface", "agreement", "votes", "frames", "passes", "water_share", "width_m", "width_class", "width_frames"]


def load_run(run_dir):
    """Join one run's matches.csv, segmentation.csv and (if present) widths.csv on filename."""
    run_dir = Path(run_dir)
    with open(run_dir / "segmentation.csv", encoding="utf-8") as f:
        labels = {r["filename"]: r for r in csv.DictReader(f)}
    widths = {}
    if (run_dir / "widths.csv").exists():
        with open(run_dir / "widths.csv", encoding="utf-8") as f:
            widths = {r["filename"]: r["width_m"] for r in csv.DictReader(f)}
    with open(run_dir / "matches.csv", encoding="utf-8") as f:
        return [{**labels[m["filename"]], "way_id": m["way_id"], "run": str(run_dir),
                 "width_m": widths.get(m["filename"], "")}
                for m in csv.DictReader(f) if m["way_id"] and m["filename"] in labels]


def fuse(frames, min_confidence=MIN_CONFIDENCE):
    by_way = defaultdict(list)
    for f in frames:
        by_way[f["way_id"]].append(f)
    ways = []
    for way_id, group in by_way.items():
        sure = [f for f in group if 0 < float(f["confidence"]) >= min_confidence]
        votes = Counter(f["label"] for f in sure if f["label"] in SURFACES)
        n_votes = sum(votes.values())
        surface, top = votes.most_common(1)[0] if votes else ("", 0)
        widths = [float(f["width_m"]) for f in group if f.get("width_m")]
        ways.append({
            "way_id": way_id,
            "surface": surface,
            "agreement": round(top / n_votes, 3) if n_votes else "",
            "votes": n_votes,
            "frames": len(group),
            "passes": len({f["run"] for f in group}),
            "water_share": round(sum(f["label"] == "water" for f in sure) / len(sure), 3) if sure else "",
            "width_m": round(median(widths), 1) if widths else "",
            "width_class": width_class(median(widths)) if widths else "",
            "width_frames": len(widths),
        })
    return sorted(ways, key=lambda w: -w["frames"])


def write(ways, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "ways.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(ways)
    return csv_path


def main(argv=None):
    p = argparse.ArgumentParser(description="Combine frame labels from one or more rides into one surface per OSM way.")
    p.add_argument("runs", type=Path, nargs="+", help="run folders, each with matches.csv and segmentation.csv (widths.csv optional)")
    p.add_argument("--out", type=Path, required=True, help="output folder (gets ways.csv)")
    p.add_argument("--min-confidence", type=float, default=MIN_CONFIDENCE, help="frames below this confidence do not vote")
    args = p.parse_args(argv)
    try:
        frames = [f for run in args.runs for f in load_run(run)]
    except FileNotFoundError as e:
        sys.exit(f"error: {e}")
    ways = fuse(frames, args.min_confidence)
    csv_path = write(ways, args.out)
    print(f"{len(frames)} matched frames from {len(args.runs)} run(s) -> {len(ways)} ways -> {csv_path}")


if __name__ == "__main__":
    main()
