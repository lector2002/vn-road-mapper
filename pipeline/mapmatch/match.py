import argparse
import csv
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

DEFAULT_URL = "https://valhalla1.openstreetmap.de"
CSV_FIELDS = ["filename", "way_id", "matched_lat", "matched_lon", "distance_m"]
USER_AGENT = "vn-road-mapper/0.1 (+https://github.com/lector2002/vn-road-mapper)"


def build_request(rows, costing):
    shape = [
        {"lat": float(r["lat"]), "lon": float(r["lon"]),
         "time": int(datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00")).timestamp())}
        for r in rows
    ]
    return {
        "shape": shape,
        "costing": costing,
        "shape_match": "map_snap",
        "filters": {
            "attributes": ["edge.way_id", "matched.point", "matched.edge_index", "matched.type",
                           "matched.distance_from_trace_point"],
            "action": "include",
        },
    }


def parse_response(rows, response):
    edges = response["edges"]
    out = []
    for row, point in zip(rows, response["matched_points"], strict=True):
        i = point.get("edge_index")
        matched = point["type"] != "unmatched" and i is not None and i < len(edges)
        out.append({
            "filename": row["filename"],
            "way_id": edges[i]["way_id"] if matched else "",
            "matched_lat": point["lat"] if matched else "",
            "matched_lon": point["lon"] if matched else "",
            "distance_m": round(point.get("distance_from_trace_point", 0), 1) if matched else "",
        })
    return out


def post_trace(url, body):
    req = urllib.request.Request(
        url.rstrip("/") + "/trace_attributes", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        raise ValueError(f"map matching failed ({e.code}): {e.read()[:300].decode(errors='replace')}") from e


def run(frames_csv, out_dir, url=DEFAULT_URL, costing="auto"):
    with open(frames_csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    located = [r for r in rows if r["lat"]]
    if len(located) < 2:
        raise ValueError(f"{frames_csv}: need at least 2 frames with a GPS position")
    by_name = {m["filename"]: m for m in parse_response(located, post_trace(url, build_request(located, costing)))}
    empty = dict.fromkeys(CSV_FIELDS[1:], "")
    matches = [by_name.get(r["filename"], {"filename": r["filename"], **empty}) for r in rows]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "matches.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(matches)
    return csv_path, matches


def main(argv=None):
    p = argparse.ArgumentParser(description="Snap each GPS-tagged frame onto an OpenStreetMap way.")
    p.add_argument("frames_csv", type=Path, help="frames.csv from pipeline.frames")
    p.add_argument("--out", type=Path, required=True, help="output folder (gets matches.csv)")
    p.add_argument("--url", default=DEFAULT_URL, help="Valhalla server; the default is the public FOSSGIS server")
    p.add_argument("--costing", default="auto", help="Valhalla costing model (auto, motor_scooter, bicycle, ...)")
    args = p.parse_args(argv)
    try:
        csv_path, matches = run(args.frames_csv, args.out, args.url, args.costing)
    except (ValueError, urllib.error.URLError) as e:
        sys.exit(f"error: {e}")
    ways = {m["way_id"] for m in matches if m["way_id"]}
    unmatched = sum(1 for m in matches if not m["way_id"])
    print(f"{len(matches)} frames -> {csv_path} ({len(ways)} ways, {unmatched} frames unmatched)")


if __name__ == "__main__":
    main()
