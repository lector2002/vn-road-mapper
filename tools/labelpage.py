"""Build a self-contained page for labelling road surface on public KartaView, Mapillary and Panoramax photos, blind to any existing label.

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

from tools import mapillary, panoramax, sources
from tools.benchmark import load_labels
from tools.kartaview import get, list_photos, photo_url, upright

TEMPLATE = Path(__file__).with_name("label_template.html")


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


def embed(data, max_width=960, turn=True):
    image = Image.open(io.BytesIO(data))
    image = (upright(image) if turn else None) or image.convert("RGB")
    if image.width > max_width:
        image = image.resize((max_width, round(image.height * max_width / image.width)))
    jpeg = io.BytesIO()
    image.save(jpeg, "JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(jpeg.getvalue()).decode()


def items(rows, photos_of=list_photos, download=get, seed=1, link=False, mapillary_url=mapillary.photo_url,
          panoramax_url=panoramax.photo_url):
    """Mapillary links expire within days, so Mapillary (and Panoramax) photos are always embedded and never turned."""
    by_id = {"mapillary": mapillary_url, "panoramax": panoramax_url}
    columns = sources.key_columns(rows)
    by_sequence = defaultdict(list)
    for row in rows:
        by_sequence[sources.source(row), sources.sequence(row)].append(row)
    out, missing = [], []
    for (source, sequence), group in by_sequence.items():
        photos = {int(p["sequenceIndex"]): p for p in photos_of(sequence)} if source == "kartaview" else {}
        for row in group:
            if source in by_id:
                try:
                    src = embed(download(by_id[source](row["photo"])), turn=False)
                except (ValueError, KeyError, OSError):
                    missing.append(f"{sequence}/{row['photo']}")
                    continue
            else:
                photo = photos.get(int(row["photo"]))
                if photo is None:
                    missing.append(f"{sequence}/{row['photo']}")
                    continue
                src = photo_url(photo) if link else embed(download(photo_url(photo)))
            out.append({
                "key": "_".join(str(k) for k in sources.key(row)),
                "fields": [row.get(c, "") for c in columns],
                "src": src,
                "credit": sources.credit(row),
            })
    random.Random(seed).shuffle(out)
    return out, missing


def render(page_id, title, page_items, columns=("kartaview_sequence", "photo")):
    page = {"id": page_id, "title": title, "columns": list(columns), "items": page_items}
    # "<\/" keeps a "</script>" inside a CSV value from ending the page's script block.
    data = json.dumps(page).replace("</", "<\\/")
    return TEMPLATE.read_text(encoding="utf-8").replace("/*DATA*/null", data)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("labels_csv", type=Path, nargs="+",
                   help="CSVs with kartaview_sequence, mapillary_sequence or panoramax_sequence, and photo (sequenceIndex or image id)")
    p.add_argument("--out", type=Path, required=True, help="HTML file to write; keep it out of the repo")
    p.add_argument("--sample", type=int, help="label only this many rows, spread over the existing labels")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--title", default="Road surface labels")
    p.add_argument("--link", action="store_true",
                   help="point at KartaView's CDN instead of embedding photos: a small file for hundreds of photos, "
                        "but it needs the network and portrait shots stay on their side")
    args = p.parse_args(argv)
    rows = sample(load_labels(*args.labels_csv), args.sample, args.seed)
    page_items, missing = items(rows, seed=args.seed, link=args.link)
    if missing:
        print(f"no longer online: {', '.join(missing)}", file=sys.stderr)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    page_id = "+".join(path.stem for path in args.labels_csv)
    args.out.write_text(render(page_id, args.title, page_items, sources.key_columns(rows)), encoding="utf-8")
    print(f"{len(page_items)} photos -> {args.out}")


if __name__ == "__main__":
    main()
