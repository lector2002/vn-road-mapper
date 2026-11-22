# Phase 6: one whole province (Hà Tĩnh) from public imagery

> 2026-11-22. Public data only: Mapillary (CC BY-SA 4.0) and KartaView photos, Geofabrik's OSM Vietnam extract, and the Phase 5 flood layers (UNOSAT, Copernicus EMS, JRC surface water, Copernicus DEM). Self-hosted Valhalla and PostGIS in Docker. No rides, no partners, no paid labelling, nothing uploaded to OSM.

## Result

Every public street photo in Tỉnh Hà Tĩnh (the OSM `admin_level=4` outline) went through the pipeline in **3 h 51 min** on one 8-core CPU machine with no GPU, at **no data or software cost**. It gave a surface call on **669 roads, 635 km of the province's 16,289 km**, and **79 review proposals** (75 `paved`, 4 `unpaved`), with flood risk on all 61,573 roads, all loaded into PostGIS.

Coverage follows the imagery: over a third of the trunk road length has a call, but 1.3% of residential roads and 0.5% of tracks, which are the rural lanes the project is for.

## Run

```bash
P=output/province/ha-tinh
python -m tools.province boundary $P --name "Tỉnh Hà Tĩnh" --pbf vietnam-latest.osm.pbf
docker run -d --name valhalla -p 8002:8002 -v $PWD/$P/valhalla:/custom_files \
  -e build_admins=False -e build_elevation=False -e build_time_zones=False \
  ghcr.io/valhalla/valhalla-scripted:latest
for step in imagery frames segment match; do python -m tools.province $step $P; done
python -m tools.province flood $P --flood-dir output/flood
python -m tools.province fuse $P
python -m tools.province db $P --dsn postgresql://postgres:roads@localhost:5432/roads
python -m tools.province summary $P
```

Hà Tĩnh was picked because it is a rural, flood-prone central province with good Mapillary coverage, and earlier public flood maps cover parts of it.

### Imagery

| | Mapillary | KartaView |
|---|---|---|
| Photos inside the outline | 54,676 (330 sequences, 10 contributors) | 532 (from 468 sequences that touch it, out of 83,554 in Vietnam) |
| Kept, newest per 50 m cell | 11,045 | 372 |
| Matched to an OSM way | 9,050 | 7 |

Mapillary is listed from its public vector tiles (z12 `sequence` layer to find covered tiles, z14 `image` layer for the photos), which takes seconds for a province; panoramas are dropped. KartaView is listed from its sequence API, with every sequence's photo list cached. Thinning to one photo per 50 m cell keeps the newest photo, so one road driven many times does not take the run. Photos date from 2016 to June 2026; 66% are from 2025.

KartaView adds almost nothing here: most of its sequences pass through the province with only one or two kept photos, which Valhalla cannot match as a track.

### Time

| Step | Seconds | What it does |
|---|---|---|
| boundary | 28 | Province outline and `osmium extract` for Valhalla and the roads |
| imagery | 335 | List and thin public photos |
| frames | 1,131 | Download 11,420 photos (686 MB), 8 at a time |
| segment | 12,319 | SegFormer + dirt probe on CPU: 3,981 s one process (about 2,200 photos), then 8,338 s two processes (9,219 photos, 0.9 s per photo) |
| match | 4 | Self-hosted Valhalla, 140 stretches, 3 failed |
| flood | 53 | Phase 5 flood risk for all 61,573 roads |
| fuse + export | 5 | Votes per way, proposals, `changes.osc`, `review.html` |
| db | 8 | Load PostGIS |
| **Total** | **13,883 (3 h 51 min)** | |

Segmentation is 89% of the time. The first hour ran one process and was switched to two processes with 4 threads each, which halved the time per photo; started that way, the whole run would take about 3 h 15 min. A GPU would cut segmentation to minutes; this machine has none.

One-off setup not in the table: listing all 83,554 KartaView sequences in Vietnam (cached for later provinces), pulling the Valhalla and PostGIS images, and Valhalla's tile build for the province (4 s).

Rerunning a step skips what is done: with no new imagery, `frames`, `segment` and `match` took 0, 0 and 1 s. When new imagery appears, `imagery` lists it again and only the new photos are downloaded, segmented and matched.

### Cost

- **Data and software:** none. Every source is public and free (the Mapillary token is a free account token), and Valhalla, PostGIS, SegFormer and CLIP are open source.
- **Compute:** this machine (8 CPU cores, 31 GB RAM, no GPU) for 3 h 51 min; 755 MB of disk for photos and outputs, plus 69 MB for the PostGIS database.
- **Devin:** the session's usage is metered in ACUs, and the session that ran this also did Phases 0 to 5, so this run's share is not separable; the dollar amount is ACUs × the account's contracted per-ACU rate.

## Output

| | Count |
|---|---|
| Ways with fused votes | 669 (635 km) |
| Surface call | 356 paved, 19 dirt, 294 too few or split votes |
| Proposals in `proposals.csv` | 77 `add` (no surface tag yet), 2 `change`, 69 `agree`, 521 `weak` |
| Ways in `changes.osc` | 79 (75 `paved`, 4 `unpaved`) |
| PostGIS rows | `roads` 61,573, `votes` 669, `proposals` 669, `flood` 61,573 |

Road length with a call, by OSM class:

| Class | km | km with a call | Share |
|---|---|---|---|
| trunk | 511 | 186 | 36% |
| secondary | 417 | 109 | 26% |
| primary | 378 | 57 | 15% |
| tertiary | 1,557 | 109 | 7% |
| unclassified | 1,149 | 30 | 2.6% |
| residential | 10,668 | 136 | 1.3% |
| track | 1,522 | 7 | 0.5% |
| All | 16,289 | 635 | 3.9% |

The roads with a call are more flood-prone than the province: 60% of them are `high` flood risk against 25% of all roads, because the imaged main roads run along the coastal plain. In PostGIS that is one join, for example paved and dirt calls on `high` roads:

```sql
select v.surface, count(*), round(sum(ST_Length(r.geom::geography)) / 1000) as km
from votes v join roads r using (way_id) join flood f using (way_id)
where v.surface <> '' and f.flood_risk = 'high' group by 1;
-- paved 250 roads, 338 km; dirt 10 roads, 15 km
```

The two `change` proposals call roads tagged `asphalt` unpaved; like every proposal they go through `review.html` and a person before anything reaches OSM.

## Caveats

- Surface calls carry the Phase 2 accuracy (119 of 129 clear test frames, 8 of 36 dirt called paved), measured on a test split a person spot-checked; nobody has checked the Hà Tĩnh calls.
- Width stays blank on public imagery (Phase 4), and flood risk is mapped satellite water, not passability (Phase 5).
- Coverage is where public imagery exists. Rural lanes stay thin until a partner offers footage, as the roadmap expected.
