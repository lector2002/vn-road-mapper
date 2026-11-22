"""Score the flood-risk layer against public flood maps of Vietnam.

    python -m tools.floodcheck fetch output/flood                          # EMS, UNOSAT, surface water, elevation
    python -m tools.floodcheck ways vietnam-latest.osm.pbf output/flood    # OSM roads inside the EMS areas
    python -m tools.floodcheck build output/flood                          # flood_ways.csv: layers + what flooded
    python -m tools.floodcheck score output/flood/flood_ways.csv

Truth is the flooded area Copernicus EMS mapped in each area of interest (every map of it, merged). The layers
only use flood maps made before that flood. Needs `pip install -r requirements-flood.txt`.
"""
import argparse
import csv
import glob
import json
import math
import re
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from pipeline.flood.risk import FEATURES, RISKS, ROADS, Grid, at, auc, relative_height, risk, samples, way_features

EMS_API = "https://rapidmapping.emergency.copernicus.eu/backend/dashboard-api/public-activations/?code="
HDX_API = "https://data.humdata.org/api/3/action/package_search?fq=organization:unosat&rows=200&q=viet%20nam%20water"
GSW = "https://storage.googleapis.com/global-surface-water/downloads2021/occurrence/occurrence_{}v1_4_2021.tif"
GSW_TILES = ["100E_30N", "100E_20N", "100E_10N", "110E_20N"]
DEM = "https://copernicus-dem-30m.s3.amazonaws.com/{0}/{0}.tif"
# Copernicus EMS flood activations in Vietnam with published maps; the first two are fitted on, the last scored.
EVENTS = {"EMSR754": ("2024-09-09", "dev"), "EMSR844": ("2025-10-08", "dev"), "EMSR848": ("2025-10-29", "test")}
RES = 1e-4  # degrees, about 11 m, for burning flood polygons
REL_RADIUS_M = 500
FLOODED_SAMPLES = 2  # about 25-50 m of road under water
RULES = {"history": 0.2, "rel": -1.0, "z": 5.0, "water": 50}
WAY_FIELDS = ["way_id", "highway", "surface", "bridge", "name", "coords"]
ROW_FIELDS = ["event", "aoi", "split", "way_id", "highway", "length_m"] + FEATURES + ["flooded_share", "flooded"]


def get(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": "vn-road-mapper/0.1"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        Path(path).write_bytes(resp.read())


def fetch(out):
    out = Path(out)
    jobs = []
    for code in EVENTS:
        (out / "ems").mkdir(parents=True, exist_ok=True)
        get(EMS_API + code, out / "ems" / f"{code}.json")
        for aoi in json.loads((out / "ems" / f"{code}.json").read_text())["results"][0]["aois"]:
            for p in aoi["products"]:
                if p["type"] == "DEL" and p["version"]["statusCode"] == "F":
                    jobs.append((p["downloadPath"], out / "ems" / p["downloadPath"].rsplit("/", 1)[1]))
    (out / "unosat").mkdir(exist_ok=True)
    get(HDX_API, out / "unosat" / "hdx.json")
    for p in json.loads((out / "unosat" / "hdx.json").read_text())["result"]["results"]:
        if "viet" in (p["name"] + p["title"]).lower():
            jobs += [(r["url"], out / "unosat" / r["url"].rsplit("/", 1)[1]) for r in p["resources"] if r["format"] == "SHP"]
    (out / "gsw").mkdir(exist_ok=True)
    jobs += [(GSW.format(t), out / "gsw" / GSW.format(t).rsplit("/", 1)[1]) for t in GSW_TILES]
    (out / "dem").mkdir(exist_ok=True)
    for la, lo in sorted({t for a in load_ems(out, polygons=False) for t in tiles(a["bounds"])}):
        name = f"Copernicus_DSM_COG_10_N{la:02d}_00_E{lo:03d}_00_DEM"
        jobs.append((DEM.format(name), out / "dem" / f"{name}.tif"))
    jobs = list({str(p): (u, p) for u, p in jobs if not Path(p).exists()}.values())
    with ThreadPoolExecutor(6) as pool:
        list(pool.map(lambda j: get(*j), jobs))
    import zipfile
    for z in glob.glob(str(out / "unosat" / "*.zip")) + glob.glob(str(out / "ems" / "*.zip")):
        with zipfile.ZipFile(z) as f:
            f.extractall(Path(z).with_suffix(""))


def tiles(bounds):
    w, s, e, n = bounds
    return {(la, lo) for la in range(math.floor(s), math.floor(n) + 1) for lo in range(math.floor(w), math.floor(e) + 1)}


def features_of(path, keep=lambda p: True):
    from shapely.geometry import shape
    return [shape(f["geometry"]) for f in json.loads(Path(path).read_text())["features"]
            if f["geometry"] and keep(f["properties"])]


def load_ems(out, polygons=True):
    """One entry per EMS area of interest: its outline and everything any of its maps shows flooded."""
    from shapely.geometry import shape
    from shapely.ops import unary_union
    areas = {}
    for code, (date, split) in EVENTS.items():
        activation = json.loads((Path(out) / "ems" / f"{code}.json").read_text())["results"][0]
        for aoi in activation["aois"]:
            key = (code, aoi["number"])
            dirs = sorted(glob.glob(str(Path(out) / "ems" / f"{code}_AOI{aoi['number']:02d}_DEL_*")))
            dirs = [d for d in dirs if Path(d).is_dir()]
            if polygons and not dirs:
                continue
            area = {"event": code, "aoi": f"{aoi['number']:02d} {aoi['name']}", "date": date, "split": split,
                    "bounds": shape({"type": "Polygon", "coordinates": [[[float(v) for v in xy.split()]
                                    for xy in re.findall(r"-?[\d.]+ -?[\d.]+", aoi["extent"] or
                                                         aoi["products"][0]["extent"])]]}).bounds}
            if polygons:
                outline = unary_union([g for d in dirs for g in features_of(glob.glob(f"{d}/*areaOfInterestA*.json")[0])])
                flooded = [g for d in dirs for g in features_of(glob.glob(f"{d}/*observedEventA*.json")[0],
                                                                 lambda p: p.get("notation") == "Flooded area")]
                area.update(outline=outline, flooded=flooded, bounds=outline.bounds)
            areas[key] = area
    return list(areas.values())


def unosat_maps(out):
    """(date, path, bounds) for every UNOSAT flood-water layer, dated by the satellite pass in its file name."""
    import pyogrio
    maps = []
    for path in sorted(glob.glob(str(Path(out) / "unosat" / "**" / "*.shp"), recursive=True)):
        name = Path(path).stem
        if not re.search(r"Flood(Extent|Water|_Water)|_Flood$|PostFlood$|SurfaceWaterExtent", name) or "Analysis" in name:
            continue
        d = re.search(r"(20\d{2})(\d{2})(\d{2})", name)
        maps.append((f"{d[1]}-{d[2]}-{d[3]}", path, tuple(pyogrio.read_info(path, force_total_bounds=True)["total_bounds"])))
    return maps


def read_near(path, bounds):
    import pyogrio
    import shapely
    geoms = pyogrio.raw.read(path, bbox=bounds, columns=[])[2]
    return [g for g in shapely.from_wkb(geoms) if g is not None]


def overlaps(a, b):
    return a[0] <= b[2] and a[2] >= b[0] and a[1] <= b[3] and a[3] >= b[1]


def burn(geoms, bounds):
    from rasterio.features import rasterize
    from rasterio.transform import from_origin
    from shapely import clip_by_rect
    w, s, e, n = bounds
    shape = (math.ceil(round((n - s) / RES, 6)), math.ceil(round((e - w) / RES, 6)))
    transform = from_origin(w, n, RES, RES)
    near = [g for g in geoms if g.bounds[0] <= e and g.bounds[2] >= w and g.bounds[1] <= n and g.bounds[3] >= s]
    clipped = [g for g in (clip_by_rect(g, w, s, e, n) for g in near) if not g.is_empty]
    array = rasterize(clipped, out_shape=shape, transform=transform, dtype="uint8") if clipped else np.zeros(shape, "uint8")
    return Grid(array, transform, None)


def mosaic(paths, bounds):
    import rasterio
    from rasterio.merge import merge
    sources = [rasterio.open(p) for p in paths]
    array, transform = merge(sources, bounds=bounds)
    nodata = sources[0].nodata
    return Grid(array[0], transform, nodata)


def build(out, log=print):
    out = Path(out)
    with open(out / "aoi_ways.csv", encoding="utf-8") as f:
        ways = [w for w in csv.DictReader(f) if w["highway"] in ROADS and w["bridge"] in ("", "no")]
    for w in ways:
        w["coords"] = json.loads(w["coords"])
        la, lo = [c[0] for c in w["coords"]], [c[1] for c in w["coords"]]
        w["box"] = (min(lo), min(la), max(lo), max(la))
    areas, unosat = load_ems(out), unosat_maps(out)
    log(f"{len(ways)} roads, {len(areas)} EMS areas, {len(unosat)} UNOSAT maps")
    rows = []
    for area in areas:
        w, s, e, n = area["bounds"]
        pad = (w - 0.01, s - 0.01, e + 0.01, n + 0.01)
        before = [g for d, path, b in unosat if d < area["date"] and overlaps(b, pad) for g in read_near(path, pad)]
        before += [g for other in areas if other["date"] < area["date"] for g in other["flooded"]]
        history, truth, inside = burn(before, pad), burn(area["flooded"], pad), burn([area["outline"]], pad)
        dem = mosaic([p for la, lo in tiles(pad) for p in
                      glob.glob(str(out / "dem" / f"Copernicus_DSM_COG_10_N{la:02d}_00_E{lo:03d}_00_DEM.tif"))], pad)
        z = np.where(dem.array == dem.nodata, np.nan, dem.array) if dem.nodata is not None else dem.array.astype(float)
        rel = Grid(relative_height(z, round(REL_RADIUS_M / (abs(dem.transform.a) * 111_320))), dem.transform, None)
        water = mosaic(sorted(glob.glob(str(out / "gsw" / "occurrence_*.tif"))), pad)
        mine = [x for x in ways if x["box"][0] >= w and x["box"][2] <= e and x["box"][1] >= s and x["box"][3] <= n]
        kept = 0
        for x in mine:
            pts = samples(x["coords"])
            if np.nanmin(at(inside, pts)) < 1:
                continue
            f = way_features(x["coords"], history, water, dem, rel)
            wet = at(truth, pts) > 0
            rows.append({"event": area["event"], "aoi": area["aoi"], "split": area["split"], "way_id": x["way_id"],
                         "highway": x["highway"], "length_m": round((len(pts) - 1) * 25), **f,
                         "flooded_share": round(float(wet.mean()), 3), "flooded": int(wet.sum() >= FLOODED_SAMPLES)})
            kept += 1
        log(f"{area['event']} {area['aoi']}: {kept} roads, {sum(r['flooded'] for r in rows[-kept:]) if kept else 0} flooded,"
            f" {len(before)} earlier flood polygons")
    merged = {}
    for r in rows:  # areas of one activation overlap: a road counts once, flooded if any map shows it flooded
        key = (r["event"], r["way_id"])
        if key in merged:
            m = merged[key]
            m["flooded"], m["flooded_share"] = max(m["flooded"], r["flooded"]), max(m["flooded_share"], r["flooded_share"])
        else:
            merged[key] = r
    rows = list(merged.values())
    with open(out / "flood_ways.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, ROW_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def read_rows(path):
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in FEATURES:
            r[k] = float(r[k]) if r[k] != "" else ""
        r["flooded"] = int(r["flooded"])
    return rows


def score(rows, rules=RULES):
    """Per risk class: roads, how many flooded; plus the share of flooded roads the high class catches."""
    by = defaultdict(Counter)
    for r in rows:
        c = risk(r, rules)
        by[c]["roads"] += 1
        by[c]["flooded"] += r["flooded"]
    flooded = sum(r["flooded"] for r in rows)
    ranked = [r for r in rows if r["z_min"] != "" and r["rel_min"] != ""]
    order = {"high": 2, "medium": 1, "low": 0}
    return {"roads": len(rows), "flooded": flooded, "classes": {c: dict(by[c]) for c in (*RISKS, "")},
            "caught": by["high"]["flooded"] / flooded if flooded else float("nan"),
            "auc": auc([order[risk(r, rules)] for r in ranked], [r["flooded"] for r in ranked]),
            "auc_single": {k: auc([(r[k] if r[k] != "" else 0) * (-1 if k in ("z_min", "rel_min") else 1)
                                   for r in ranked], [r["flooded"] for r in ranked])
                           for k in ("history", "water", "z_min", "rel_min")}}


def fit(rows, min_caught=0.25):
    """Rules with the best class AUC on `rows` whose high class still catches `min_caught` of the flooded roads.
    There are almost no earlier flood maps for the dev areas, so the history threshold stays at its default."""
    best = None
    for z in (3, 5, 8, 12, 20):
        for rel in (-0.5, -1, -2, -3):
            for water in (10, 25, 50, 75):
                rules = dict(RULES, z=z, rel=rel, water=water)
                result = score(rows, rules)
                if result["caught"] >= min_caught and (best is None or result["auc"] > best[0]):
                    best = (result["auc"], rules)
    return best[1] if best else RULES


def report(result, name):
    lines = [f"{name}: {result['roads']} roads, {result['flooded']} flooded "
             f"({result['flooded'] / max(result['roads'], 1):.1%})"]
    for c, n in result["classes"].items():
        if n.get("roads"):
            lines.append(f"  {c or 'blank':<7} {n['roads']:>7} roads  {n.get('flooded', 0):>6} flooded "
                         f"({n.get('flooded', 0) / n['roads']:.1%})")
    lines.append(f"  high catches {result['caught']:.1%} of flooded roads; class AUC {result['auc']:.3f}")
    lines.append("  single-layer AUC: " + ", ".join(f"{k} {v:.3f}" for k, v in result["auc_single"].items()))
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch").add_argument("out", type=Path)
    w = sub.add_parser("ways")
    w.add_argument("pbf", type=Path)
    w.add_argument("out", type=Path)
    sub.add_parser("build").add_argument("out", type=Path)
    s = sub.add_parser("score")
    s.add_argument("rows", type=Path)
    args = p.parse_args(argv)
    if args.cmd == "fetch":
        fetch(args.out)
    elif args.cmd == "ways":
        extract_ways(args.pbf, args.out)
    elif args.cmd == "build":
        build(args.out)
    else:
        rows = read_rows(args.rows)
        rules = fit([r for r in rows if r["split"] == "dev"])
        print("rules fitted on dev:", rules)
        for split in ("dev", "test"):
            print(report(score([r for r in rows if r["split"] == split], rules), split))
            for area in sorted({(r["event"], r["aoi"]) for r in rows if r["split"] == split}):
                print(report(score([r for r in rows if (r["event"], r["aoi"]) == area], rules), "  " + " ".join(area)))
        with open(args.rows.with_name("flood_risk.csv"), "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["way_id", "flood_risk"])
            writer.writerows(sorted({(r["way_id"], risk(r, rules)) for r in rows}))


def extract_ways(pbf, out):
    """Every OSM highway whose bounding box overlaps an EMS area, written to aoi_ways.csv."""
    import osmium
    boxes = [a["bounds"] for a in load_ems(out)]

    class Ways(osmium.SimpleHandler):
        def __init__(self):
            super().__init__()
            self.rows = []

        def way(self, w):
            if w.tags.get("highway") not in ROADS:
                return
            try:
                c = [(n.lat, n.lon) for n in w.nodes]
            except osmium.InvalidLocationError:
                return
            la, lo = [x[0] for x in c], [x[1] for x in c]
            if any(min(lo) <= b[2] and max(lo) >= b[0] and min(la) <= b[3] and max(la) >= b[1] for b in boxes):
                self.rows.append({"way_id": w.id, "highway": w.tags["highway"], "surface": w.tags.get("surface", ""),
                                  "bridge": w.tags.get("bridge", ""), "name": w.tags.get("name", ""),
                                  "coords": json.dumps([[round(a, 6), round(b, 6)] for a, b in c])})

    ways = Ways()
    ways.apply_file(str(pbf), locations=True, idx="flex_mem")
    with open(Path(out) / "aoi_ways.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, WAY_FIELDS)
        writer.writeheader()
        writer.writerows(ways.rows)


if __name__ == "__main__":
    main()
