"""Run the pipeline over one whole province from public KartaView and Mapillary imagery.

Steps, each re-runnable; a re-run keeps what is already downloaded or labelled and only adds new imagery:

    boundary  province outline and OSM extract from a Geofabrik Vietnam extract
    imagery   every public photo inside the outline, thinned to the newest one per grid cell
    frames    downloads the thinned photos, one run folder per sequence
    segment   SegFormer + dirt probe on every run that has new frames
    match     snaps each run onto OSM ways with a (self-hosted) Valhalla server
    flood     flood-risk class for every road in the province (Phase 5 layers)
    fuse      fuses all runs into ways.csv and writes proposals from the local OSM extract
    summary   coverage, proposals and step times in summary.json
    db        loads roads, fused votes, proposals and flood classes into PostGIS (replacing the province's rows)

Nothing here edits OSM. Timings for each step are appended to timings.csv.
"""
import argparse
import csv
import json
import math
import os
import subprocess
import sys
import time
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from pipeline.flood.risk import ROADS, Grid, along_m, relative_height, risk, way_features
from tools import kartaview, mapillary

KV_SEQUENCES = "https://api.kartaview.org/2.0/sequence/?countryCode=VN&itemsPerPage=100&page={}"
MLY_TILES = "https://tiles.mapillary.com/maps/vtp/mly1_public/2/{}/{}/{}?access_token={}"
CELL_M = 50
MAX_GAP_M = 1000
KV_MAX_AGE_DAYS = 7
IMAGERY_FIELDS = ["source", "sequence", "photo_id", "sequence_index", "lat", "lon", "captured_at", "heading", "url"]
FLOOD_FIELDS = ["way_id", "highway", "surface", "length_m", "history", "water", "z_min", "rel_min", "gfd", "gfd_events",
                "flood_risk"]


def read(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write(path, fields, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def outline(out):
    from shapely.geometry import shape
    return shape(json.loads((Path(out) / "boundary.geojson").read_text())["features"][0]["geometry"])


def boundary(name, pbf, out):
    """The admin_level=4 area called `name`, and an OSM extract of it for Valhalla and the local way lookup."""
    import osmium
    from shapely import wkb
    from shapely.geometry import mapping
    factory = osmium.geom.WKBFactory()
    found = []

    class Areas(osmium.SimpleHandler):
        def area(self, a):
            if not a.from_way() and a.tags.get("admin_level") == "4" and a.tags.get("name") == name:
                found.append(wkb.loads(factory.create_multipolygon(a), hex=True))

    Areas().apply_file(str(pbf), locations=True, idx="flex_mem")
    if not found:
        raise ValueError(f"no admin_level=4 area named {name!r} in {pbf}")
    out = Path(out)
    (out / "valhalla").mkdir(parents=True, exist_ok=True)
    feature = {"type": "Feature", "properties": {"name": name}, "geometry": mapping(found[0].simplify(0.0005))}
    (out / "boundary.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [feature]}, ensure_ascii=False))
    subprocess.run(["osmium", "extract", "-p", str(out / "boundary.geojson"), str(pbf),
                    "-o", str(out / "valhalla" / "province.osm.pbf"), "--overwrite"], check=True)


def tile_get(z, x, y, token):
    import mapbox_vector_tile
    for attempt in range(4):
        try:
            with urllib.request.urlopen(MLY_TILES.format(z, x, y, token), timeout=60) as r:
                return mapbox_vector_tile.decode(r.read())
        except OSError:
            time.sleep(2 * (attempt + 1))
    return {}


def mapillary_photos(area):
    """Every public Mapillary image inside `area`, from the coverage vector tiles (z12 to find coverage, z14 images)."""
    import mercantile
    from shapely.geometry import Point, box
    from shapely.prepared import prep
    inside, token = prep(area), mapillary.token()
    w, s, e, n = area.bounds
    z12 = [t for t in mercantile.tiles(w, s, e, n, 12) if inside.intersects(box(*mercantile.bounds(t)))]
    with ThreadPoolExecutor(16) as ex:
        found = list(ex.map(lambda t: (t, tile_get(t.z, t.x, t.y, token)), z12))
    z14 = [c for t, d in found if d.get("sequence", {}).get("features")
           for c in mercantile.children(t, zoom=14) if inside.intersects(box(*mercantile.bounds(c)))]
    rows = {}
    with ThreadPoolExecutor(16) as ex:
        for t, d in ex.map(lambda t: (t, tile_get(t.z, t.x, t.y, token)), z14):
            b = mercantile.bounds(t)
            layer = d.get("image", {})
            extent = layer.get("extent", 4096)
            for f in layer.get("features", []):
                x, y = f["geometry"]["coordinates"]
                lon, lat = b.west + (b.east - b.west) * x / extent, b.south + (b.north - b.south) * y / extent
                p = f["properties"]
                if p.get("is_pano") or not inside.contains(Point(lon, lat)):
                    continue
                rows[p["id"]] = {"source": "mapillary", "sequence": p["sequence_id"], "photo_id": p["id"], "sequence_index": "",
                                 "lat": round(lat, 6), "lon": round(lon, 6), "captured_at": p["captured_at"],
                                 "heading": p.get("compass_angle", ""), "url": ""}
    return list(rows.values())


def kartaview_sequences(cache, max_age_days=KV_MAX_AGE_DAYS):
    """Every KartaView sequence in Vietnam, cached; listed again once the cache is older than max_age_days."""
    if cache.exists() and time.time() - cache.stat().st_mtime < max_age_days * 86400:
        return json.loads(cache.read_text())
    seqs, page = [], 1
    while True:
        result = json.loads(kartaview.get(KV_SEQUENCES.format(page)))["result"]
        seqs += [{k: s.get(k) for k in ("id", "nwLat", "nwLng", "seLat", "seLng", "currentLat", "currentLng")}
                 for s in result["data"]]
        if not result.get("hasMoreData"):
            break
        page += 1
    cache.write_text(json.dumps(seqs))
    return seqs


def kartaview_photos(area, cache):
    from shapely.geometry import Point, box
    from shapely.prepared import prep
    inside = prep(area)
    rows, skipped = [], []
    for s in kartaview_sequences(cache):
        corners = [float(s[k] or 0) for k in ("nwLng", "seLat", "seLng", "nwLat")]
        if not all(corners) or not inside.intersects(box(*corners)):
            continue
        photos = sequence_photos(s["id"], cache.parent / "kartaview_photos")
        if photos is None:
            skipped.append(s["id"])
            continue
        for p in photos:
            lat, lon = float(p["lat"]), float(p["lng"])
            if inside.contains(Point(lon, lat)):
                shot = datetime.strptime(p["shotDate"][:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                rows.append({"source": "kartaview", "sequence": s["id"], "photo_id": p["id"],
                             "sequence_index": p["sequenceIndex"], "lat": lat, "lon": lon,
                             "captured_at": int(shot.timestamp() * 1000), "heading": p.get("heading") or "",
                             "url": kartaview.photo_url(p)})
    if skipped:
        print(f"kartaview: skipped {len(skipped)} sequences the API would not list: {' '.join(map(str, skipped))}")
    return rows


def sequence_photos(sequence_id, cache_dir, tries=3):
    """One KartaView sequence's photos, cached so a re-run only lists new sequences; None if the API keeps failing."""
    path = Path(cache_dir) / f"{sequence_id}.json"
    if path.exists():
        return json.loads(path.read_text())
    for attempt in range(tries):
        try:
            photos = kartaview.list_photos(sequence_id)
            break
        except (OSError, ValueError):
            time.sleep(5 * (attempt + 1))
    else:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(photos))
    return photos


def thin(rows, cell_m=CELL_M):
    """The newest photo per cell_m grid cell, so dense city sequences do not swamp the run."""
    d = cell_m / 111_320
    best = {}
    for r in rows:
        cell = (round(float(r["lat"]) / d), round(float(r["lon"]) / (d / math.cos(math.radians(float(r["lat"]))))))
        if cell not in best or int(r["captured_at"]) > int(best[cell]["captured_at"]):
            best[cell] = r
    return sorted(best.values(), key=lambda r: (r["source"], str(r["sequence"]), int(r["captured_at"])))


def imagery(out, cell_m=CELL_M, sources=("mapillary", "kartaview"), log=print):
    out = Path(out)
    area = outline(out)
    found = []
    for name in sources:
        rows = mapillary_photos(area) if name == "mapillary" else kartaview_photos(area, out.parent / "kartaview_sequences.json")
        log(f"{name}: {len(rows)} photos in {len({r['sequence'] for r in rows})} sequences")
        found += rows
    kept = thin(found, cell_m)
    write(out / "imagery.csv", IMAGERY_FIELDS, kept)
    log(f"kept {len(kept)} photos, one per {cell_m} m cell")
    return kept


def run_name(row):
    return f"{row['source']}-{row['sequence']}"


def download(row, target):
    url = row["url"] or mapillary.photo_url(row["photo_id"])
    data = kartaview.get(url)
    if row["source"] == "kartaview":
        kartaview.save_frame(data, target)
    else:
        target.write_bytes(data)


def frames(out, workers=8, log=print):
    """One run folder per sequence: frames/*.jpg, frames.csv and the photo references the pilot tools read."""
    out = Path(out)
    runs = defaultdict(list)
    for r in read(out / "imagery.csv"):
        runs[run_name(r)].append(r)
    jobs = []
    for name, rows in runs.items():
        folder = out / "runs" / name
        (folder / "frames").mkdir(parents=True, exist_ok=True)
        frame_rows, refs = [], []
        for r in rows:
            filename = f"{r['photo_id']}.jpg"
            t = datetime.fromtimestamp(int(r["captured_at"]) / 1000, timezone.utc)
            frame_rows.append({"filename": filename, "timestamp": t.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                               "lat": r["lat"], "lon": r["lon"], "heading": r["heading"]})
            refs.append({"filename": filename, "photo_id": r["photo_id"], "kartaview_way_id": "",
                         "sequence_id": r["sequence"] if r["source"] == "kartaview" else "",
                         "sequence_index": r["sequence_index"], "mapillary_id": r["photo_id"] if r["source"] == "mapillary" else ""})
            if not (folder / "frames" / filename).exists():
                jobs.append((r, folder / "frames" / filename))
        write(folder / "frames.csv", ["filename", "timestamp", "lat", "lon", "heading"], frame_rows)
        write(folder / "kartaview.csv", ["filename", "photo_id", "kartaview_way_id", "sequence_id", "sequence_index",
                                         "mapillary_id"], refs)

    def fetch(job):
        try:
            download(*job)
            return True
        except (OSError, ValueError):
            return False

    with ThreadPoolExecutor(workers) as ex:
        ok = sum(ex.map(fetch, jobs))
    log(f"{len(runs)} runs, {ok} of {len(jobs)} new photos downloaded")
    return runs


def runs_of(out):
    """Run folders of the sequences in the current imagery.csv; runs a refresh dropped stay on disk but are left out."""
    out = Path(out)
    current = {run_name(r) for r in read(out / "imagery.csv")} if (out / "imagery.csv").exists() else None
    return sorted(p for p in (out / "runs").iterdir()
                  if (p / "frames.csv").exists() and (current is None or p.name in current))


def present(folder):
    """frames.csv rows whose photo downloaded."""
    return [r for r in read(folder / "frames.csv") if (folder / "frames" / r["filename"]).exists()]


_worker = {}


def _segment_init(threads):
    import torch
    from pipeline.segmentation import probe
    from pipeline.segmentation import segment as seg
    torch.set_num_threads(threads)
    _worker.update(probe=probe.load_default(), segmenter=seg.Segmenter(seg.DEFAULT_MODEL))


def _segment_one(folder):
    from pipeline.segmentation import segment as seg
    started = time.perf_counter()
    rows = seg.run(folder / "frames", folder, overlays=0, probe=_worker["probe"], segmenter=_worker["segmenter"])[1]
    return folder.name, len(rows), time.perf_counter() - started


def labelled_frames(path):
    """Filenames with a complete streamed segmentation row; `p_unpaved` is legitimately blank sometimes."""
    from pipeline.segmentation.segment import CSV_FIELDS

    return {r["filename"] for r in read(path)
            if all(r.get(field) not in (None, "") for field in CSV_FIELDS[:-1])}


def pending_segmentation(out):
    """Runs whose downloaded photos are not all labelled yet, largest first so workers finish together."""
    todo = []
    for folder in runs_of(out):
        names = {r["filename"] for r in present(folder)}
        labelled = folder / "segmentation.csv"
        if names and not (labelled.exists() and names <= labelled_frames(labelled)):
            todo.append((len(names), folder))
    return [f for _, f in sorted(todo, key=lambda t: (-t[0], t[1].name))]


def segment(out, workers=2, log=print):
    """SegFormer + dirt probe on CPU; `workers` processes share the cores, which beats one process on all of them."""
    import multiprocessing
    from concurrent.futures import ProcessPoolExecutor
    todo = pending_segmentation(out)
    threads = max(1, (os.cpu_count() or 1) // workers)
    done = 0
    with ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context("spawn"),
                             initializer=_segment_init, initargs=(threads,)) as ex:
        for name, n, seconds in ex.map(_segment_one, todo, chunksize=1):
            done += n
            log(f"segment {name}: {n} frames in {seconds:.0f} s ({done} so far)")
    return len(todo), done


def gap_m(a, b):
    lat = math.radians((float(a["lat"]) + float(b["lat"])) / 2)
    return 111_320 * math.hypot(float(a["lat"]) - float(b["lat"]), (float(a["lon"]) - float(b["lon"])) * math.cos(lat))


def pieces(rows, max_gap_m=MAX_GAP_M):
    """Split a thinned sequence where photos are far apart, so Valhalla matches each stretch on its own."""
    out = [[rows[0]]] if rows else []
    for a, b in zip(rows, rows[1:]):
        if gap_m(a, b) > max_gap_m:
            out.append([])
        out[-1].append(b)
    return out


def match(out, url, log=print):
    from pipeline.mapmatch import match as mm
    matched = failed = 0
    for folder in runs_of(out):
        rows = sorted(present(folder), key=lambda r: r["timestamp"])
        names = {r["filename"] for r in rows}
        if len(rows) < 2 or ((folder / "matches.csv").exists()
                             and {m["filename"] for m in read(folder / "matches.csv")} == names):
            continue
        empty = dict.fromkeys(mm.CSV_FIELDS[1:], "")
        result = []
        todo = pieces(rows)
        while todo:
            piece = todo.pop(0)
            if len(piece) < 2:
                result += [{"filename": r["filename"], **empty} for r in piece]
                continue
            write(folder / "piece.csv", ["filename", "timestamp", "lat", "lon", "heading"], piece)
            try:
                result += mm.run(folder / "piece.csv", folder / "piece", url, costing="motor_scooter")[1]
                matched += 1
            except ValueError as e:  # Valhalla answered but could not match; an OSError (server down) stops the step
                if len(piece) >= 4:  # one bad stretch should not lose the rest: retry each half
                    half = len(piece) // 2
                    todo[:0] = [piece[:half], piece[half:]]
                    continue
                failed += 1
                result += [{"filename": r["filename"], **empty} for r in piece]
                log(f"match {folder.name}: {len(piece)} photos unmatched: {str(e)[:120]}")
        write(folder / "matches.csv", mm.CSV_FIELDS, result)
    log(f"matched {matched} stretches, {failed} failed")
    return matched, failed


class Ways:
    """Highways from the province extract: tags, node ids and coordinates, as export.fetch_way returns them."""

    def __init__(self, pbf):
        import osmium
        self.ways = {}
        ways = self.ways

        class Handler(osmium.SimpleHandler):
            def way(self, w):
                if "highway" not in w.tags:
                    return
                try:
                    coords = [(n.lat, n.lon) for n in w.nodes]
                except osmium.InvalidLocationError:
                    return
                ways[str(w.id)] = {"id": w.id, "version": w.version, "nodes": [n.ref for n in w.nodes],
                                   "tags": dict(w.tags), "coords": coords}

        Handler().apply_file(str(pbf), locations=True)

    def __call__(self, way_id):
        return self.ways[str(way_id)]


def flood(out, flood_dir, rules=None, log=print):
    """Phase 5 flood class for every road in the province; history is every public flood map that covers it."""
    from tools import floodcheck as fc
    import glob
    out, flood_dir = Path(out), Path(flood_dir)
    rules = rules or fc.RULES
    area = outline(out)
    w, s, e, n = area.bounds
    pad = (w - 0.01, s - 0.01, e + 0.01, n + 0.01)
    maps = [g for _, path, b in fc.unosat_maps(flood_dir) if fc.overlaps(b, pad) for g in fc.read_near(path, pad)]
    maps += [g for a in fc.load_ems(flood_dir) if fc.overlaps(a["bounds"], pad) for g in a["flooded"]]
    history = fc.burn(maps, pad)
    dem_paths = [p for la, lo in fc.tiles(pad) for p in
                 glob.glob(str(flood_dir / "dem" / f"Copernicus_DSM_COG_10_N{la:02d}_00_E{lo:03d}_00_DEM.tif"))]
    dem = fc.mosaic(dem_paths, pad)
    z = np.where(dem.array == dem.nodata, np.nan, dem.array) if dem.nodata is not None else dem.array.astype(float)
    rel = Grid(relative_height(z, round(fc.REL_RADIUS_M / (abs(dem.transform.a) * 111_320))), dem.transform, None)
    water = fc.mosaic(sorted(glob.glob(str(flood_dir / "gsw" / "occurrence_*.tif"))), pad)
    events = fc.gfd_counts([m for m in fc.gfd_maps(flood_dir) if fc.overlaps(m[2], pad)], pad)
    rows = []
    for way in Ways(out / "valhalla" / "province.osm.pbf").ways.values():
        if way["tags"].get("highway") not in ROADS or len(way["coords"]) < 2:
            continue
        f = way_features(way["coords"], history, water, dem, rel, events)
        rows.append({"way_id": way["id"], "highway": way["tags"]["highway"], "surface": way["tags"].get("surface", ""),
                     "length_m": round(float(along_m(way["coords"])[-1])), **f, "flood_risk": risk(f, rules)})
    write(out / "flood_risk.csv", FLOOD_FIELDS, rows)
    log(f"flood: {len(rows)} roads, {len(maps)} flood polygons from {len(dem_paths)} DEM tiles")
    return rows


def fuse(out, log=print):
    from pipeline.export import export
    from pipeline.fusion import fuse as fu
    out = Path(out)
    frames_ = [f for folder in runs_of(out) if (folder / "matches.csv").exists() and (folder / "segmentation.csv").exists()
               for f in fu.load_run(folder)]
    ways = fu.fuse(frames_)
    fu.write(ways, out)
    flood_csv = out / "flood_risk.csv"
    rows = export.run(out / "ways.csv", out, fetch=Ways(out / "valhalla" / "province.osm.pbf"),
                      flood_csv=flood_csv if flood_csv.exists() else None)
    log(f"fuse: {len(frames_)} matched frames on {len(ways)} ways")
    return rows


DB_TABLES = {
    "roads": "way_id bigint, province text, highway text, surface text, name text, geom geometry(LineString, 4326)",
    "votes": "way_id bigint, province text, surface text, agreement real, votes int, frames int, passes int",
    "proposals": "way_id bigint, province text, status text, current_surface text, proposed_surface text",
    "flood": "way_id bigint, province text, history real, water real, z_min real, rel_min real, flood_risk text",
}


def number(value):
    return None if value in ("", None) else float(value)


def db_rows(out):
    """Rows for each PostGIS table, from the files the other steps wrote."""
    out = Path(out)
    province = outline_name(out)
    ways = Ways(out / "valhalla" / "province.osm.pbf").ways
    rows = {"roads": [(w["id"], province, w["tags"]["highway"], w["tags"].get("surface", ""), w["tags"].get("name", ""),
                       "LINESTRING(" + ",".join(f"{lon} {lat}" for lat, lon in w["coords"]) + ")")
                      for w in ways.values() if w["tags"].get("highway") in ROADS and len(w["coords"]) >= 2]}
    rows["votes"] = [(int(r["way_id"]), province, r["surface"], number(r["agreement"]), int(r["votes"]), int(r["frames"]),
                      int(r["passes"])) for r in read(out / "ways.csv")] if (out / "ways.csv").exists() else []
    rows["proposals"] = [(int(r["way_id"]), province, r["status"], r["current_surface"], r["proposed_surface"])
                         for r in read(out / "proposals.csv")] if (out / "proposals.csv").exists() else []
    rows["flood"] = [(int(r["way_id"]), province, number(r["history"]), number(r["water"]), number(r["z_min"]),
                      number(r["rel_min"]), r["flood_risk"]) for r in read(out / "flood_risk.csv")] \
        if (out / "flood_risk.csv").exists() else []
    return rows


def outline_name(out):
    return json.loads((Path(out) / "boundary.geojson").read_text())["features"][0]["properties"].get("name", "")


def db(out, dsn, log=print):
    import psycopg2
    from psycopg2.extras import execute_values
    rows = db_rows(out)
    province = outline_name(out)
    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        for table, columns in DB_TABLES.items():
            cur.execute(f"CREATE TABLE IF NOT EXISTS {table} ({columns})")
            cur.execute(f"DELETE FROM {table} WHERE province = %s", (province,))
            template = "(%s, %s, %s, %s, %s, ST_GeomFromText(%s, 4326))" if table == "roads" else None
            execute_values(cur, f"INSERT INTO {table} VALUES %s", rows[table], template=template, page_size=5000)
        cur.execute("CREATE INDEX IF NOT EXISTS roads_geom ON roads USING gist (geom)")
    log("db: " + ", ".join(f"{len(v)} {k}" for k, v in rows.items()))
    return rows


def summary(out, log=print):
    """What the run covered: photos, matched frames, road length with a fused call by class, proposals, step times."""
    from collections import Counter
    out = Path(out)
    roads = {r["way_id"]: r for r in read(out / "flood_risk.csv")}
    fused = {r["way_id"]: r for r in read(out / "ways.csv")}
    proposals = read(out / "proposals.csv")
    imagery_rows = read(out / "imagery.csv")
    km = defaultdict(lambda: [0.0, 0.0])
    for way_id, r in roads.items():
        km[r["highway"]][0] += float(r["length_m"]) / 1000
        if way_id in fused:
            km[r["highway"]][1] += float(r["length_m"]) / 1000
    total, seen = sum(v[0] for v in km.values()), sum(v[1] for v in km.values())
    matched = sum(1 for folder in runs_of(out) if (folder / "matches.csv").exists()
                  for m in read(folder / "matches.csv") if m["way_id"])
    result = {
        "photos": dict(Counter(r["source"] for r in imagery_rows)),
        "runs": len(runs_of(out)),
        "matched_frames": matched,
        "ways_with_call": len(fused),
        "road_km": round(total, 1),
        "road_km_with_call": round(seen, 1),
        "km_by_highway": {k: [round(v[0], 1), round(v[1], 1)] for k, v in sorted(km.items(), key=lambda kv: -kv[1][0])},
        "surface_calls": dict(Counter(r["surface"] for r in fused.values())),
        "proposals": dict(Counter(r["status"] for r in proposals)),
        "proposed_tags": dict(Counter(r["proposed_surface"] for r in proposals if r["proposed_surface"])),
        "flood_risk_all": dict(Counter(r["flood_risk"] for r in roads.values())),
        "flood_risk_with_call": dict(Counter(roads[w]["flood_risk"] for w in fused if w in roads)),
        "seconds": seconds_by_step(out),
    }
    (out / "summary.json").write_text(json.dumps(result, indent=1, ensure_ascii=False))
    log(json.dumps(result, ensure_ascii=False))
    return result


def seconds_by_step(out):
    """Seconds spent on each step, summed over every time it was run."""
    total = defaultdict(int)
    for r in read(Path(out) / "timings.csv"):
        total[r["step"]] += int(r["seconds"])
    return dict(total)


def timed(out, step, fn, *args):
    started = time.perf_counter()
    result = fn(*args)
    seconds = round(time.perf_counter() - started)
    path = Path(out) / "timings.csv"
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new:
            writer.writerow(["step", "seconds", "finished"])
        writer.writerow([step, seconds, datetime.now(timezone.utc).isoformat(timespec="seconds")])
    print(f"{step}: {seconds} s")
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description="Run the pipeline over one province from public imagery.")
    p.add_argument("step", choices=["boundary", "imagery", "frames", "segment", "match", "flood", "fuse", "summary", "db"])
    p.add_argument("out", type=Path)
    p.add_argument("--name", help="boundary: the province's OSM name, e.g. 'Tỉnh Hà Tĩnh'")
    p.add_argument("--pbf", type=Path, help="boundary: Geofabrik Vietnam extract")
    p.add_argument("--cell", type=int, default=CELL_M, help="imagery: keep the newest photo per cell of this many metres")
    p.add_argument("--sources", default="mapillary,kartaview", help="imagery: comma-separated public sources")
    p.add_argument("--workers", type=int, default=2, help="segment: processes sharing the CPU cores")
    p.add_argument("--valhalla", default="http://localhost:8002", help="match: Valhalla server built from valhalla/")
    p.add_argument("--dsn", default=os.environ.get("PROVINCE_DSN", ""), help="db: PostGIS connection string")
    p.add_argument("--flood-dir", type=Path, default=Path("output/flood"), help="flood: the floodcheck fetch folder")
    args = p.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    steps = {
        "boundary": lambda: boundary(args.name, args.pbf, args.out),
        "imagery": lambda: imagery(args.out, args.cell, args.sources.split(",")),
        "frames": lambda: frames(args.out),
        "segment": lambda: segment(args.out, args.workers),
        "match": lambda: match(args.out, args.valhalla),
        "flood": lambda: flood(args.out, args.flood_dir),
        "fuse": lambda: fuse(args.out),
        "summary": lambda: summary(args.out),
        "db": lambda: db(args.out, args.dsn),
    }
    if args.step == "boundary" and not (args.name and args.pbf):
        p.error("boundary needs --name and --pbf")
    try:
        timed(args.out, args.step, steps[args.step])
    except (ValueError, OSError, mapillary.MissingToken, subprocess.CalledProcessError) as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
