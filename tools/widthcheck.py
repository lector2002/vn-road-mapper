"""Check width classes against OSM `width` tags on public Mapillary photos.

    python -m tools.widthcheck ways vietnam-latest.osm.pbf --out output/width       # width_ways.csv, neighbours.csv
    python -m tools.widthcheck photos output/width --frames output/width/frames     # photos.csv + downloads
    python -m pipeline.width.estimate output/width/frames --out output/width --camera-height 1.4
    python -m tools.widthcheck score output/width/photos.csv output/width/widths.csv

`ways` needs `pip install osmium` and a Geofabrik extract; `photos` needs MAPILLARY_ACCESS_TOKEN.
"""
import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import median

from pipeline.width.estimate import WIDTH_CLASSES, width_class

MINOR = {"unclassified", "residential", "track", "service", "tertiary", "living_street", "road", "path"}
WAY_FIELDS = ["way_id", "highway", "width", "key", "surface", "name", "coords"]
PHOTO_FIELDS = ["way_id", "osm_width", "osm_class", "split", "image_id", "sequence", "captured_at", "lat", "lon",
                "dist_m", "heading_off"]
MAX_DIST_M = 5
END_M = 15
MAX_HEADING_OFF = 20
CLOSER_BY_M = 3
PER_WAY = 12
PER_SEQUENCE = 3


def metres(value):
    """OSM width value in metres, or None for anything but a plain number (with optional m)."""
    m = re.fullmatch(r"\s*([0-9]+(?:[.,][0-9]+)?)\s*(m|meters|metres)?\s*", value or "")
    if not m:
        return None
    width = float(m.group(1).replace(",", "."))
    return width if 0.5 <= width <= 20 else None


def split(way_id):
    """Fixed half of the ways for picking settings (dev), the other half only for the score (test)."""
    return "test" if int(hashlib.md5(str(way_id).encode()).hexdigest(), 16) % 2 else "dev"


def project(lat, lon, coords):
    """Distance in m from the point to the polyline, metres along it to the nearest point, its length, its bearing there."""
    k = 111320 * math.cos(math.radians(lat))
    best, run = (math.inf, 0.0, 0.0), 0.0
    for (a1, o1), (a2, o2) in zip(coords, coords[1:]):
        ax, ay, bx, by = (o1 - lon) * k, (a1 - lat) * 110540, (o2 - lon) * k, (a2 - lat) * 110540
        dx, dy = bx - ax, by - ay
        seg = math.hypot(dx, dy) or 1e-9
        t = max(0.0, min(1.0, -(ax * dx + ay * dy) / seg ** 2))
        d = math.hypot(ax + t * dx, ay + t * dy)
        if d < best[0]:
            best = (d, run + t * seg, math.degrees(math.atan2(dx, dy)) % 360)
        run += seg
    return best[0], best[1], run, best[2]


def on_way(lat, lon, heading, coords, other_ways):
    """(dist, heading offset) if the photo is taken on this way looking along it, else None.

    Short alleys meet bigger roads at their ends, and a photo near the junction shows the bigger road, so the
    ends are left out, and so is any photo at least as close to another highway."""
    dist, along, length, bearing = project(lat, lon, coords)
    if dist > MAX_DIST_M or length <= 2 * END_M or along < END_M or along > length - END_M:
        return None
    off = abs((heading - bearing + 180) % 360 - 180)
    off = min(off, 180 - off)
    if off > MAX_HEADING_OFF:
        return None
    if any(project(lat, lon, c)[0] < dist + CLOSER_BY_M for c in other_ways):
        return None
    return round(dist, 1), round(off, 1)


def pick(photos, per_way=PER_WAY, per_sequence=PER_SEQUENCE):
    """Best-placed photos per way, at most a few from one sequence so one rider does not decide a way."""
    by_way = defaultdict(list)
    for p in photos:
        by_way[p["way_id"]].append(p)
    out = []
    for group in by_way.values():
        group.sort(key=lambda p: (float(p["heading_off"]) + 2 * float(p["dist_m"]), p["image_id"]))
        seen = Counter()
        for p in group:
            if seen[p["sequence"]] < per_sequence and sum(seen.values()) < per_way:
                seen[p["sequence"]] += 1
                out.append(p)
    return out


def score(photos, widths, predict=None):
    """Per-way class (from the median frame width) against the OSM width class, for each split.

    predict(way_id, [width_m, ...]) -> class lets a baseline replace the median rule."""
    width_of = {r["filename"]: r["width_m"] for r in widths}
    frames, ways = defaultdict(list), {}
    for p in photos:
        ways[p["way_id"]] = p
        w = width_of.get(f"{p['image_id']}.jpg", "")
        if w != "":
            frames[p["way_id"]].append(float(w))
    predict = predict or (lambda way, ws: width_class(median(ws)) if ws else "")
    result = {}
    for s in ("dev", "test", "all"):
        chosen = [w for w, p in ways.items() if s == "all" or p["split"] == s]
        confusion = Counter()
        for w in chosen:
            got = predict(w, frames[w])
            if got:
                confusion[(ways[w]["osm_class"], got)] += 1
        classed = sum(confusion.values())
        result[s] = {"ways": len(chosen), "classed": classed,
                     "right": sum(n for (truth, got), n in confusion.items() if truth == got),
                     "confusion": {t: [confusion[(t, g)] for g in WIDTH_CLASSES] for t in WIDTH_CLASSES}}
    return result


def report(result, name):
    lines = []
    for s, r in result.items():
        lines.append(f"{name} {s}: {r['right']} of {r['classed']} classed ways right ({r['ways']} ways)")
        lines += [f"  OSM {t:9s} -> " + " ".join(f"{g} {n}" for g, n in zip(WIDTH_CLASSES, row))
                  for t, row in r["confusion"].items()]
    return "\n".join(lines)


def extract_ways(pbf, out_dir):
    import osmium

    class Width(osmium.SimpleHandler):
        def __init__(self):
            super().__init__()
            self.rows = []

        def way(self, w):
            t = w.tags
            width = metres(t.get("width")) or metres(t.get("est_width"))
            if t.get("highway") not in MINOR or width is None:
                return
            try:
                coords = [(n.lat, n.lon) for n in w.nodes]
            except osmium.InvalidLocationError:
                return
            self.rows.append({"way_id": w.id, "highway": t.get("highway"), "width": width,
                              "key": "width" if metres(t.get("width")) else "est_width",
                              "surface": t.get("surface", ""), "name": t.get("name", ""), "coords": json.dumps(coords)})

    width = Width()
    width.apply_file(str(pbf), locations=True, idx="flex_mem")
    cells = {(int(la * 100) + i, int(lo * 100) + j)
             for r in width.rows for la, lo in json.loads(r["coords"]) for i in (-1, 0, 1) for j in (-1, 0, 1)}

    class Near(osmium.SimpleHandler):
        def __init__(self):
            super().__init__()
            self.rows = []

        def way(self, w):
            if "highway" not in w.tags:
                return
            try:
                coords = [(n.lat, n.lon) for n in w.nodes]
            except osmium.InvalidLocationError:
                return
            if any((int(la * 100), int(lo * 100)) in cells for la, lo in coords):
                self.rows.append({"way_id": w.id, "coords": json.dumps(coords)})

    near = Near()
    near.apply_file(str(pbf), locations=True, idx="flex_mem")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write(out_dir / "width_ways.csv", width.rows, WAY_FIELDS)
    write(out_dir / "neighbours.csv", near.rows, ["way_id", "coords"])
    return width.rows, near.rows


def find_photos(ways, neighbours, search=None):
    """Mapillary photos taken on each width-tagged way, looking along it."""
    from tools import mapillary
    search = search or (lambda bbox: mapillary.graph(
        "images", bbox=bbox, fields="id,captured_at,camera_type,compass_angle,computed_compass_angle,geometry,sequence",
        limit=2000)["data"])
    grid = defaultdict(list)
    for n in neighbours:
        coords = json.loads(n["coords"])
        for cell in {(int(la * 500), int(lo * 500)) for la, lo in coords}:
            grid[cell].append((str(n["way_id"]), coords))

    def one(way):
        coords = json.loads(way["coords"])
        if len(coords) < 2:
            return []
        lats, lons = [c[0] for c in coords], [c[1] for c in coords]
        bbox = f"{min(lons) - 2e-4},{min(lats) - 2e-4},{max(lons) + 2e-4},{max(lats) + 2e-4}"
        rows = []
        for img in search(bbox):
            heading = img.get("computed_compass_angle") or img.get("compass_angle")
            if img.get("camera_type", "perspective") != "perspective" or heading is None:
                continue
            lon, lat = img["geometry"]["coordinates"]
            cell = (int(lat * 500), int(lon * 500))
            others = {wid: c for i in (-1, 0, 1) for j in (-1, 0, 1)
                      for wid, c in grid[(cell[0] + i, cell[1] + j)] if wid != str(way["way_id"])}
            hit = on_way(lat, lon, heading, coords, others.values())
            if hit:
                rows.append({"way_id": way["way_id"], "osm_width": way["width"], "osm_class": width_class(way["width"]),
                             "split": split(way["way_id"]), "image_id": img["id"], "sequence": img.get("sequence", ""),
                             "captured_at": img["captured_at"], "lat": lat, "lon": lon,
                             "dist_m": hit[0], "heading_off": hit[1]})
        return rows

    with ThreadPoolExecutor(8) as ex:
        return [r for rows in ex.map(one, ways) for r in rows]


def download(photos, frames_dir):
    from tools import mapillary
    from tools.kartaview import get
    frames_dir = Path(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)

    def one(p):
        path = frames_dir / f"{p['image_id']}.jpg"
        if not path.exists():
            path.write_bytes(get(mapillary.photo_url(p["image_id"], 1024)))

    with ThreadPoolExecutor(8) as ex:
        list(ex.map(one, photos))


def read(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main(argv=None):
    p = argparse.ArgumentParser(description="Check width classes against OSM width tags on public Mapillary photos.")
    sub = p.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("ways", help="width-tagged minor roads and the highways around them from an .osm.pbf")
    w.add_argument("pbf", type=Path)
    w.add_argument("--out", type=Path, required=True)
    ph = sub.add_parser("photos", help="Mapillary photos on those ways (writes photos.csv), downloaded to --frames")
    ph.add_argument("dir", type=Path, help="folder with width_ways.csv and neighbours.csv")
    ph.add_argument("--frames", type=Path, required=True)
    sc = sub.add_parser("score", help="per-way class from widths.csv against the OSM class")
    sc.add_argument("photos", type=Path)
    sc.add_argument("widths", type=Path)
    args = p.parse_args(argv)
    if args.cmd == "ways":
        ways, near = extract_ways(args.pbf, args.out)
        print(f"{len(ways)} width-tagged minor roads, {len(near)} highways around them -> {args.out}")
    elif args.cmd == "photos":
        photos = pick(find_photos(read(args.dir / "width_ways.csv"), read(args.dir / "neighbours.csv")))
        write(args.dir / "photos.csv", photos, PHOTO_FIELDS)
        download(photos, args.frames)
        print(f"{len(photos)} photos on {len({r['way_id'] for r in photos})} ways -> {args.dir / 'photos.csv'}")
    else:
        photos, widths = read(args.photos), read(args.widths)
        print(report(score(photos, widths), "width"))
        print(report(score(photos, widths, lambda way, ws: "two_cars"), "always two_cars"))


if __name__ == "__main__":
    main()
