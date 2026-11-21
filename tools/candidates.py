"""Pick evenly spaced photos from a list of public KartaView sequences, as the frames to label for a test set.

The sequence list says each sequence's region and split; the split is fixed per ride (same rider and day), so no
ride has photos on both sides. Writes kartaview_sequence and photo (KartaView sequenceIndex) plus where and when.
"""
import argparse
import csv
from pathlib import Path

from tools.benchmark import load_labels
from tools.kartaview import list_photos

FIELDS = ["kartaview_sequence", "photo", "region", "split", "lat", "lon", "shot_date"]


def spaced(photos, n):
    """n photos spread evenly over the sequence; neighbours a few metres apart show the same road."""
    if len(photos) <= n:
        return list(photos)
    step = len(photos) / n
    return [photos[int(step * i + step / 2)] for i in range(n)]


def candidates(sequences, per_sequence, photos_of=list_photos):
    rows = []
    for seq in sequences:
        for photo in spaced(photos_of(seq["kartaview_sequence"]), per_sequence):
            rows.append({
                "kartaview_sequence": seq["kartaview_sequence"],
                "photo": f"{int(photo['sequenceIndex']):05d}",
                "region": seq["region"],
                "split": seq["split"],
                "lat": photo["lat"],
                "lon": photo["lng"],
                "shot_date": photo.get("shotDate", "")[:10],
            })
    return rows


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("sequences_csv", help="kartaview_sequence, region, split per row")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--per-sequence", type=int, default=45)
    args = p.parse_args(argv)
    rows = candidates(load_labels(args.sequences_csv), args.per_sequence)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    by_split = {s: sum(r["split"] == s for r in rows) for s in sorted({r["split"] for r in rows})}
    print(f"{len(rows)} photos from {len({r['kartaview_sequence'] for r in rows})} sequences {by_split} -> {args.out}")


if __name__ == "__main__":
    main()
