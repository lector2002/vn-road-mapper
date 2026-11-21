"""Pick a small pilot of untagged OSM ways and write it as a MapRoulette Tag Fix challenge.

Nothing here edits OSM: a person checks each way against its photos in MapRoulette, and MapRoulette uploads only
what they approve, under their own account.
"""
import argparse
import csv
import json
import sys
import urllib.error
from collections import Counter, defaultdict
from pathlib import Path

from pipeline.export import export

RURAL = {"unclassified", "residential", "track", "service", "tertiary", "living_street", "road"}
FAMILY = {"paved": "paved", "dirt": "unpaved", "mud": "unpaved"}
PHOTOS_PER_WAY = 3
RS = "\x1e"
FIELDS = ["way_id", "osm", "highway", "name", "proposed_surface", "agreement", "votes", "photos", "decision", "note"]
ACCEPT = {"accept", "accepted", "yes", "fixed"}
# MapRoulette's CSV export writes TaskStatus as Fixed, Not_An_Issue, Too_Hard, Skipped, Already_Fixed, ...
REJECT = {"reject", "rejected", "no", "not_an_issue", "not an issue", "false_positive", "false positive"}
BAR = 0.9


def read(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def photo_link(ref):
    if not ref.get("sequence_id"):
        return ""
    return f"https://kartaview.org/details/{ref['sequence_id']}/{ref['sequence_index']}/track-info"


def photos_by_way(run_dirs):
    """Per way and surface family, links to the KartaView photos whose label voted for that family."""
    found = defaultdict(lambda: defaultdict(list))
    for run in map(Path, run_dirs):
        labels = {r["filename"]: r["label"] for r in read(run / "segmentation.csv")}
        refs = {r["filename"]: r for r in read(run / "kartaview.csv")} if (run / "kartaview.csv").exists() else {}
        for m in read(run / "matches.csv"):
            family = FAMILY.get(labels.get(m["filename"], ""))
            link = photo_link(refs.get(m["filename"], {}))
            if m["way_id"] and family and link:
                found[m["way_id"]][family].append(link)
    return found


def spread(items, n):
    """n items evenly spaced along the list, so the photos show the whole way, not one end."""
    if len(items) <= n:
        return items
    return [items[round(i * (len(items) - 1) / (n - 1))] for i in range(n)]


def pick(proposals, photos, highways=RURAL):
    """Ways OSM has no surface for, on small roads, with photos; unpaved first, then by votes."""
    rows = [p for p in proposals if p["status"] == "add" and p["highway"] in highways
            and photos.get(p["way_id"], {}).get(p["proposed_surface"])]
    rows.sort(key=lambda p: (p["proposed_surface"] != "unpaved", -int(p["votes"]), p["way_id"]))
    return [{"way_id": p["way_id"], "osm": f"https://www.openstreetmap.org/way/{p['way_id']}",
             "highway": p["highway"], "name": p["name"], "proposed_surface": p["proposed_surface"],
             "agreement": p["agreement"], "votes": p["votes"],
             "photos": " ".join(spread(photos[p["way_id"]][p["proposed_surface"]], PHOTOS_PER_WAY)),
             "decision": "", "note": ""} for p in rows]


def still_untagged(rows, fetch, limit):
    """The first `limit` ways that still exist and have no surface tag now, with their current OSM data."""
    keep, ways = [], {}
    for r in rows:
        if len(keep) == limit:
            break
        try:
            way = fetch(r["way_id"])
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                continue
            raise
        if "surface" not in way["tags"]:
            keep.append(r)
            ways[r["way_id"]] = way
    return keep, ways


def task(row, way):
    """One line-by-line GeoJSON task: the way, and a Tag Fix that sets surface=<proposal>."""
    osm_id = f"way/{row['way_id']}"
    props = {"id": osm_id, "proposed_surface": row["proposed_surface"], "highway": row["highway"],
             "name": row["name"], "votes": int(row["votes"]), "agreement": row["agreement"]}
    for i, link in enumerate(row["photos"].split(), 1):
        props[f"photo_{i}"] = link
    feature = {"type": "Feature", "properties": props,
               "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in way["coords"]]}}
    work = {"meta": {"version": 2, "type": 1}, "operations": [{
        "operationType": "modifyElement",
        "data": {"id": osm_id, "operations": [{"operation": "setTags", "data": {"surface": row["proposed_surface"]}}]},
    }]}
    return {"type": "FeatureCollection", "features": [feature], "cooperativeWork": work}


def write(rows, ways, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "pilot.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with open(out_dir / "challenge.geojson", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(RS + json.dumps(task(r, ways[r["way_id"]]), ensure_ascii=False) + "\n")
    review = [{**r, "status": "add", "surface": r["proposed_surface"]} for r in rows]
    (out_dir / "review.html").write_text(export.review_page(export.review_geojson(review, ways)), encoding="utf-8")


def build(proposals_csv, run_dirs, out_dir, limit=100, fetch=export.fetch_way):
    rows = pick(read(proposals_csv), photos_by_way(run_dirs))
    rows, ways = still_untagged(rows, fetch, limit)
    write(rows, ways, out_dir)
    return rows


def score(path, column=None):
    """Acceptance from a filled-in pilot.csv or a MapRoulette CSV export."""
    rows = read(path)
    if not rows:
        return {"accepted": 0, "rejected": 0, "undecided": 0, "rate": None, "passes": False}
    if column is None:
        names = {k.lower().replace(" ", ""): k for k in rows[0]}
        column = next((names[c] for c in ("decision", "taskstatus", "status") if c in names), None)
        if column is None:
            raise ValueError(f"{path}: no decision or status column; pass --column")
    values = Counter(r[column].strip().lower() for r in rows)
    accepted = sum(n for v, n in values.items() if v in ACCEPT)
    rejected = sum(n for v, n in values.items() if v in REJECT)
    decided = accepted + rejected
    rate = accepted / decided if decided else None
    return {"accepted": accepted, "rejected": rejected, "undecided": len(rows) - decided,
            "rate": rate, "passes": rate is not None and rate >= BAR}


def main(argv=None):
    p = argparse.ArgumentParser(description="Build or score a small human-reviewed OSM surface pilot.")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="pick untagged ways and write challenge.geojson, pilot.csv and review.html")
    b.add_argument("proposals_csv", type=Path, help="proposals.csv from pipeline.export (on fused ways)")
    b.add_argument("runs", type=Path, nargs="+", help="the run folders the proposals came from (for photo links)")
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--limit", type=int, default=100)
    s = sub.add_parser("score", help="acceptance rate from a filled-in pilot.csv or a MapRoulette CSV export")
    s.add_argument("csv", type=Path)
    s.add_argument("--column", help="the decision column (default: decision, TaskStatus or status)")
    args = p.parse_args(argv)
    try:
        if args.cmd == "build":
            rows = build(args.proposals_csv, args.runs, args.out, args.limit)
            kinds = Counter(r["proposed_surface"] for r in rows)
            print(f"{len(rows)} ways -> {args.out} ({', '.join(f'{k} {v}' for k, v in sorted(kinds.items()))})")
        else:
            r = score(args.csv, args.column)
            rate = "n/a" if r["rate"] is None else f"{r['rate']:.0%}"
            verdict = "PASS" if r["passes"] else "FAIL"
            print(f"accepted {r['accepted']}, rejected {r['rejected']}, undecided {r['undecided']}: "
                  f"{rate} -> {verdict} (needs {BAR:.0%})")
    except (ValueError, FileNotFoundError, urllib.error.URLError) as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
