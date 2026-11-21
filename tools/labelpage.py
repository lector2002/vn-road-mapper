"""Build a self-contained page for labelling road surface on public KartaView photos, blind to any existing label.

The page embeds the photos, draws the box the surface stage reads, saves paved / unpaved / mud / water / unclear in the
browser and gives back a CSV in the hand-label format. Nothing is uploaded; send the CSV back by hand.
"""
import argparse
import base64
import io
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image

from tools.benchmark import load_labels
from tools.kartaview import get, list_photos, photo_url, upright

TEMPLATE = Path(__file__).with_name("label_template.html")
KEY_COLUMNS = ["kartaview_sequence", "photo"]


def sample(rows, n, seed=1):
    """Pick n rows spread evenly over the existing labels, so a spot check sees each kind in proportion."""
    if n is None or n >= len(rows):
        return list(rows)
    rng = random.Random(seed)
    groups = defaultdict(list)
    for row in rows:
        groups[row.get("surface_by_eye", "")].append(row)
    picked = []
    for _, group in sorted(groups.items()):
        picked += rng.sample(group, round(n * len(group) / len(rows)))
    rest = [r for r in rows if r not in picked]
    picked += rng.sample(rest, n - len(picked)) if len(picked) < n else []
    return picked[:n]


def embed(data, max_width=960):
    image = Image.open(io.BytesIO(data))
    image = upright(image) or image.convert("RGB")
    if image.width > max_width:
        image = image.resize((max_width, round(image.height * max_width / image.width)))
    jpeg = io.BytesIO()
    image.save(jpeg, "JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(jpeg.getvalue()).decode()


def items(rows, photos_of=list_photos, download=get, seed=1, link=False):
    by_sequence = defaultdict(list)
    for row in rows:
        by_sequence[row["kartaview_sequence"]].append(row)
    out, missing = [], []
    for sequence, group in by_sequence.items():
        photos = {int(p["sequenceIndex"]): p for p in photos_of(sequence)}
        for row in group:
            photo = photos.get(int(row["photo"]))
            if photo is None:
                missing.append(f"{sequence}/{row['photo']}")
                continue
            out.append({
                "key": f"{sequence}_{int(row['photo'])}",
                "fields": [sequence, row["photo"]],
                "src": photo_url(photo) if link else embed(download(photo_url(photo))),
                "credit": f"KartaView sequence {sequence}, photo {row['photo']}, CC BY-SA 4.0",
            })
    random.Random(seed).shuffle(out)
    return out, missing


def render(page_id, title, page_items):
    page = {"id": page_id, "title": title, "columns": KEY_COLUMNS, "items": page_items}
    return TEMPLATE.read_text(encoding="utf-8").replace("/*DATA*/null", json.dumps(page))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("labels_csv", type=Path, help="CSV with kartaview_sequence and photo (KartaView sequenceIndex)")
    p.add_argument("--out", type=Path, required=True, help="HTML file to write; keep it out of the repo")
    p.add_argument("--sample", type=int, help="label only this many rows, spread over the existing labels")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--title", default="Road surface labels")
    p.add_argument("--link", action="store_true",
                   help="point at KartaView's CDN instead of embedding photos: a small file for hundreds of photos, "
                        "but it needs the network and portrait shots stay on their side")
    args = p.parse_args(argv)
    rows = sample(load_labels(args.labels_csv), args.sample, args.seed)
    page_items, missing = items(rows, seed=args.seed, link=args.link)
    if missing:
        print(f"not on KartaView any more: {', '.join(missing)}", file=sys.stderr)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(args.labels_csv.stem, args.title, page_items), encoding="utf-8")
    print(f"{len(page_items)} photos -> {args.out}")


if __name__ == "__main__":
    main()
