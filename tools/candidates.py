"""Pick evenly spaced photos from a list of public KartaView, Mapillary or Panoramax sequences, as the frames to label for a test set.

The sequence list says each sequence's region and split; the split is fixed per ride (same rider and day), so no
ride has photos on both sides. Writes kartaview_sequence, mapillary_sequence or panoramax_sequence and photo (KartaView sequenceIndex,
Mapillary image id or Panoramax item id) plus where and when.
"""
import argparse
import csv
from pathlib import Path

from tools import kartaview, mapillary, panoramax, sources
from tools.benchmark import load_labels

FIELDS = ["photo", "region", "split", "lat", "lon", "shot_date"]
LISTERS = {"kartaview": kartaview.list_photos, "mapillary": mapillary.list_photos, "panoramax": panoramax.list_photos}


def spaced(photos, n):
    """n photos spread evenly over the sequence; neighbours a few metres apart show the same road."""
    if len(photos) <= n:
        return list(photos)
    step = len(photos) / n
    return [photos[int(step * i + step / 2)] for i in range(n)]


def candidates(sequences, per_sequence, photos_of=None):
    rows = []
    for seq in sequences:
        source = sources.source(seq)
        column = f"{source}_sequence"
        lister = photos_of or LISTERS[source]
        for photo in spaced(lister(seq[column]), per_sequence):
            rows.append({
                column: seq[column],
                "photo": f"{int(photo['sequenceIndex']):05d}" if source == "kartaview" else photo["id"],
                "region": seq["region"],
                "split": seq["split"],
                "lat": photo["lat"],
                "lon": photo["lng"],
                "shot_date": photo.get("shotDate", "")[:10],
            })
    return rows


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("sequences_csv", help="kartaview_sequence, mapillary_sequence or panoramax_sequence, region, split per row")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--per-sequence", type=int, default=45)
    args = p.parse_args(argv)
    rows = candidates(load_labels(args.sequences_csv), args.per_sequence)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=sources.key_columns(rows)[:-1] + FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    by_split = {s: sum(r["split"] == s for r in rows) for s in sorted({r["split"] for r in rows})}
    print(f"{len(rows)} photos from {len({sources.sequence(r) for r in rows})} sequences {by_split} -> {args.out}")


if __name__ == "__main__":
    main()
