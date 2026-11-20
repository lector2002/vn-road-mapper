import argparse
import csv
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from xml.sax.saxutils import quoteattr

OSM_API = "https://api.openstreetmap.org/api/0.6"
USER_AGENT = "vn-road-mapper/0.1"
PAVED = {"paved", "asphalt", "concrete", "concrete:plates", "concrete:lanes", "paving_stones", "sett", "chipseal",
         "metal", "bricks"}
UNPAVED = {"unpaved", "dirt", "earth", "ground", "gravel", "fine_gravel", "compacted", "mud", "sand", "grass",
           "pebblestone", "rock"}
NEW_TAG = {"paved": "paved", "dirt": "unpaved", "mud": "unpaved"}
CSV_FIELDS = ["way_id", "status", "current_surface", "proposed_surface", "surface", "agreement", "votes",
              "water_share", "width_m", "name", "highway"]
COLORS = {"add": "#1f45cf", "change": "#c4452f", "agree": "#2f8a3c", "weak": "#9a9a9a", "unknown": "#b8890f"}


def decide(fused, current, min_agreement, min_votes):
    """Status of one way: add / change / agree / weak / unknown, and the surface tag to write."""
    if not fused["surface"] or float(fused["agreement"]) < min_agreement or int(fused["votes"]) < min_votes:
        return "weak", ""
    family = PAVED if fused["surface"] == "paved" else UNPAVED
    other = UNPAVED if family is PAVED else PAVED
    if not current:
        return "add", NEW_TAG[fused["surface"]]
    if current in family:
        return "agree", ""
    if current in other:
        return "change", NEW_TAG[fused["surface"]]
    return "unknown", ""


def fetch_way(way_id):
    req = urllib.request.Request(f"{OSM_API}/way/{way_id}/full.json", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        elements = json.load(resp)["elements"]
    nodes = {e["id"]: (e["lat"], e["lon"]) for e in elements if e["type"] == "node"}
    way = next(e for e in elements if e["type"] == "way")
    return {"id": way["id"], "version": way["version"], "nodes": way["nodes"], "tags": way.get("tags", {}),
            "coords": [nodes[n] for n in way["nodes"]]}


def osm_change(edits):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<osmChange version="0.6" generator="vn-road-mapper">', "<modify>"]
    for way, tags in edits:
        lines.append(f'  <way id="{way["id"]}" version="{way["version"]}">')
        lines += [f'    <nd ref="{n}"/>' for n in way["nodes"]]
        lines += [f"    <tag k={quoteattr(k)} v={quoteattr(v)}/>" for k, v in sorted(tags.items())]
        lines.append("  </way>")
    lines += ["</modify>", "</osmChange>", ""]
    return "\n".join(lines)


def review_geojson(rows, ways):
    features = [{
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in ways[r["way_id"]]["coords"]]},
        "properties": {**r, "color": COLORS[r["status"]]},
    } for r in rows if r["way_id"] in ways]
    return {"type": "FeatureCollection", "features": features}


def review_page(geojson):
    template = (Path(__file__).parent / "review_template.html").read_text(encoding="utf-8")
    return template.replace("/*GEOJSON*/null", json.dumps(geojson).replace("</", "<\\/"))


def run(ways_csv, out_dir, min_agreement=0.7, min_votes=5, fetch=fetch_way):
    with open(ways_csv, encoding="utf-8") as f:
        fused = list(csv.DictReader(f))
    ways, rows, edits = {}, [], []
    for w in fused:
        way = fetch(w["way_id"])
        ways[w["way_id"]] = way
        current = way["tags"].get("surface", "")
        status, new = decide(w, current, min_agreement, min_votes)
        rows.append({"way_id": w["way_id"], "status": status, "current_surface": current, "proposed_surface": new,
                     "surface": w["surface"], "agreement": w["agreement"], "votes": w["votes"],
                     "water_share": w["water_share"], "width_m": w.get("width_m", ""), "name": way["tags"].get("name", ""),
                     "highway": way["tags"].get("highway", "")})
        if new:
            edits.append((way, {**way["tags"], "surface": new}))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "proposals.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (out_dir / "changes.osc").write_text(osm_change(edits), encoding="utf-8")
    (out_dir / "review.html").write_text(review_page(review_geojson(rows, ways)), encoding="utf-8")
    return rows


def main(argv=None):
    p = argparse.ArgumentParser(description="Turn fused way surfaces into reviewable OSM edit proposals.")
    p.add_argument("ways_csv", type=Path, help="ways.csv from pipeline.fusion")
    p.add_argument("--out", type=Path, required=True, help="output folder (gets proposals.csv, changes.osc, review.html)")
    p.add_argument("--min-agreement", type=float, default=0.7)
    p.add_argument("--min-votes", type=int, default=5)
    args = p.parse_args(argv)
    try:
        rows = run(args.ways_csv, args.out, args.min_agreement, args.min_votes)
    except (urllib.error.URLError, FileNotFoundError) as e:
        sys.exit(f"error: {e}")
    counts = {s: sum(r["status"] == s for r in rows) for s in COLORS}
    print(f"{len(rows)} ways -> {args.out} " + ", ".join(f"{k} {v}" for k, v in counts.items()))


if __name__ == "__main__":
    main()
