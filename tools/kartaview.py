"""Turn a public KartaView photo sequence into the frames stage's output, to test the pipeline on real street imagery.

KartaView imagery is CC BY-SA 4.0. Keep downloaded frames out of the repo.
"""
import argparse
import csv
import io
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


API = "https://api.kartaview.org/2.0/photo/"
USER_AGENT = "vn-road-mapper/0.1"
FRAME_FIELDS = ["filename", "timestamp", "lat", "lon", "heading"]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def list_photos(sequence_id):
    photos, page = [], 1
    while True:
        body = json.loads(get(f"{API}?sequenceId={sequence_id}&itemsPerPage=100&page={page}"))
        if body["status"]["apiCode"] != 600:
            raise ValueError(f"KartaView: {body['status']['apiMessage']}")
        result = body["result"]
        photos += result["data"]
        if not result.get("hasMoreData"):
            break
        page += 1
    return sorted(photos, key=lambda p: int(p["sequenceIndex"]))


def photo_url(photo):
    # On 2026-11-21 the storage*.openstreetcam.org hosts in fileurlLTh resolved to a private address; the CDN copy loaded.
    return photo.get("imageLthUrl") or photo["fileurlLTh"]


def upright(image):
    """The capture app saved some landscape shots as portrait images with the scene on its side; turn them back.

    On two Thanh Hoa rides 64 of 76 had the sky on the right and come out upright; the other 12 come out upside down
    and give no vote. The photos carry no orientation tag to tell the two apart.
    """
    return image.convert("RGB").rotate(90, expand=True) if image.height > image.width else None


def save_frame(data, target):
    turned = upright(Image.open(io.BytesIO(data)))
    if turned is not None:
        turned.save(target, quality=95)
    else:
        target.write_bytes(data)


def frame_row(index, photo):
    # KartaView shot dates carry no timezone; only differences between frames matter downstream.
    t = datetime.strptime(photo["shotDate"][:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return {
        "filename": f"{index + 1:06d}.jpg",
        "timestamp": t.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "lat": photo["lat"],
        "lon": photo["lng"],
        "heading": photo.get("heading") or "",
    }


def run(sequence_id, out_dir, every=1):
    photos = list_photos(sequence_id)[::every]
    if not photos:
        raise ValueError(f"sequence {sequence_id} has no photos")
    out_dir = Path(out_dir)
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    rows, refs = [], []
    for i, photo in enumerate(photos):
        row = frame_row(i, photo)
        target = frames_dir / row["filename"]
        if not target.exists():
            save_frame(get(photo_url(photo)), target)
        rows.append(row)
        refs.append({"filename": row["filename"], "photo_id": photo["id"], "kartaview_way_id": photo.get("wayId") or ""})
    for name, fields, data in [("frames.csv", FRAME_FIELDS, rows),
                               ("kartaview.csv", ["filename", "photo_id", "kartaview_way_id"], refs)]:
        with open(out_dir / name, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(data)
    return rows


def main(argv=None):
    p = argparse.ArgumentParser(description="Download a KartaView sequence as frames + frames.csv.")
    p.add_argument("sequence_id")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--every", type=int, default=1, help="keep every n-th photo")
    args = p.parse_args(argv)
    try:
        rows = run(args.sequence_id, args.out, every=args.every)
    except (ValueError, OSError) as e:
        sys.exit(f"error: {e}")
    print(f"{len(rows)} frames -> {args.out}")


if __name__ == "__main__":
    main()
