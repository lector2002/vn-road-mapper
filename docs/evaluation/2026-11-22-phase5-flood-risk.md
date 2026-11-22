# Phase 5: flood-risk layer, scored against public flood maps

> 2026-11-22. Public data only: Copernicus EMS rapid mapping, UNOSAT flood maps on HDX, JRC Global Surface Water, the Copernicus 30 m DEM and Geofabrik's OSM Vietnam extract. No rides, no partners, no paid labelling.

## Result

On the held-out flood (EMSR848, central Vietnam, late October 2025), 12.6% of the 173,444 roads in the mapped areas were under water. Of the roads the layer calls `high`, 35.0% were, 2.8 times the base rate, and `high` holds 43% of all flooded roads in 16% of the roads.

| Test split, EMSR848 | Roads | Flooded | Share flooded |
|---|---|---|---|
| `high` | 26,884 | 9,421 | 35.0% |
| `medium` | 17,891 | 3,120 | 17.4% |
| `low` | 128,669 | 9,251 | 7.2% |
| All | 173,444 | 21,792 | 12.6% |

Ranking roads by class (`high` > `medium` > `low`) gives an AUC of 0.69: a flooded road outranks a dry one 69% of the time. Layer by layer on test:

| Layer, test split | AUC | Note |
|---|---|---|
| Earlier flood maps (history) | 0.68 | 7,950 roads with 20% or more of their length in an earlier map: 74.2% flooded |
| Lowest elevation (lower = riskier) | 0.71 | Roads at 5 m or less: 26.4% flooded; over 20 m: 3.9% |
| Surface-water occurrence | 0.60 | |
| Height against surroundings | 0.55 | Adds little on its own |
| Combined classes | 0.69 | |

**Flood history is the strongest signal where it exists.** A road that an earlier UNOSAT or EMS map showed under water flooded again three times in four. It needs earlier maps of the same place: on test, 12,834 roads (7%) had any. **Elevation carries the rest.** It covers every road, and on its own it ranks slightly better than the three classes, because the classes cut a smooth signal into three steps. The classes are what a rider or health station can use, so they ship; the evaluation keeps the per-layer AUCs next to them.

On the dev floods (EMSR754 Red River delta, September 2024; EMSR844 Quang Châu in the north, October 2025) only 1.6% of roads flooded, and the layer is much weaker: `high` 2.7% flooded, AUC 0.66. Almost no earlier flood maps cover the north, the EMS maps there are mostly cities, and Nam Định, Ninh Bình and Thái Bình score at chance.

## What ships

- `pipeline/flood/risk.py`: samples each OSM way every 25 m and reads four layers: share of points in an earlier flood map, highest surface-water occurrence, lowest elevation, and lowest height against the ground within 500 m. `risk()` turns them into `high` / `medium` / `low`, blank where there is no elevation.
  - `high`: 20% or more of the way in an earlier flood map, or at 5 m or less and 1 m or more below its surroundings.
  - `medium`: at 5 m or less, or water seen 10% or more of the time since 1984.
  - `low`: everything else.
- `tools/floodcheck.py`: downloads the public layers, extracts the OSM roads, builds the per-road table and scores it.
- `pipeline.export.export --flood flood_risk.csv` adds a `flood_risk` column to `proposals.csv`. It is for riders, health stations and reviewers. It is never an OSM tag and changes no edit.

## Data

**Truth: Copernicus EMS rapid mapping.** The three activations for floods in Vietnam with published delineation maps: EMSR754 (2024-09-09, 11 areas in the Red River delta), EMSR844 (2025-10-08, 1 area) and EMSR848 (2025-10-29, 12 areas from Huế to Nha Trang). Each area's maps, including later monitoring maps, are merged, and only polygons marked `Flooded area` count. A road is flooded when 2 or more of its 25 m sample points fall in that water. Roads must lie wholly inside an area's outline. Areas of one activation overlap (4 around Huế), so each road counts once per activation, flooded if any map shows it flooded.

**Split, fixed before scoring.** EMSR754 and EMSR844 are dev, EMSR848 is test. The thresholds (elevation 5 m, height −1 m, water 10%) were picked on dev as the pair with the best class AUC whose `high` still holds a quarter of the flooded roads. The history threshold stays at its default of 20%, since dev has almost no earlier maps to fit it on. Nothing was tuned on EMSR848.

**Layers.** For each flood, the history layer only uses maps from before it:
- UNOSAT: 48 flood-extent shapefiles from 2015 to 2025 on HDX (Hải Phòng 2015, the south and Quảng Nam 2017, the Mekong delta 2018, central Vietnam 2020 and 2022, the Red River delta 2024, the north 2025). They are dated by the satellite pass in the file name. Pre-flood water and analysis extents are left out.
- Earlier EMS activations: EMSR754 counts as history for the two 2025 floods.
- JRC Global Surface Water occurrence 1984–2021, 30 m.
- Copernicus DEM GLO-30. It is a surface model, so trees and buildings raise it. Height against surroundings is the lowest point of the way minus the mean of the ground within 500 m.

**Roads.** OSM highways from `trunk` down to `track` and `path`, without `service`, `footway` or bridges: 340,319 ways whose bounding box overlaps an EMS area, 271,573 inside one.

## Per area

| Split | Area | Roads | Flooded | `high` roads | `high` flooded | `high` catches | AUC | Roads with history |
|---|---|---|---|---|---|---|---|---|
| dev | EMSR754 01 Cổ Tiết | 1,852 | 1 (0.1%) | 0 | – | 0% | 0.98 | 0 |
| dev | EMSR754 02 Nông Trang | 10,692 | 285 (2.7%) | 0 | – | 0% | 0.60 | 0 |
| dev | EMSR754 03 Hà Nội | 27,784 | 373 (1.3%) | 742 | 15.2% | 30% | 0.81 | 0 |
| dev | EMSR754 04 Hạ Long | 5,487 | 7 (0.1%) | 2,107 | 0.3% | 100% | 0.81 | 1,030 |
| dev | EMSR754 05 Hải Phòng | 4,480 | 5 (0.1%) | 2,096 | 0.2% | 100% | 0.77 | 1,330 |
| dev | EMSR754 06 Thái Bình | 6,059 | 0 | 1,048 | 0.0% | – | – | 0 |
| dev | EMSR754 07 Nam Định | 3,979 | 49 (1.2%) | 1,056 | 0.5% | 10% | 0.47 | 0 |
| dev | EMSR754 08 Thanh Hóa | 5,444 | 1 (0.0%) | 1,694 | 0.0% | 0% | 0.53 | 0 |
| dev | EMSR754 09 Ninh Bình | 9,842 | 64 (0.7%) | 2,484 | 0.4% | 14% | 0.47 | 0 |
| dev | EMSR754 10 Hải Dương | 6,901 | 437 (6.3%) | 1,914 | 5.9% | 26% | 0.55 | 0 |
| dev | EMSR754 11 Chí Linh | 9,281 | 202 (2.2%) | 1,357 | 7.2% | 49% | 0.74 | 0 |
| dev | EMSR844 01 Quang Châu | 6,331 | 127 (2.0%) | 1,186 | 6.8% | 64% | 0.76 | 186 |
| test | EMSR848 01 Quảng Ngãi | 32,652 | 3,131 (9.6%) | 3,305 | 38.6% | 41% | 0.72 | 1,179 |
| test | EMSR848 02 Tam Kỳ | 19,646 | 948 (4.8%) | 2,302 | 31.0% | 75% | 0.86 | 1,683 |
| test | EMSR848 03 Đà Nẵng | 38,743 | 3,382 (8.7%) | 7,911 | 26.7% | 62% | 0.77 | 3,776 |
| test | EMSR848 04–07 Huế | 21,029 | 3,040 (14.5%) | 6,363 | 35.3% | 74% | 0.81 | 2,627 |
| test | EMSR848 16 Quy Nhơn | 30,357 | 8,605 (28.3%) | 3,650 | 66.6% | 28% | 0.64 | 2,509 |
| test | EMSR848 17 Tuy Hòa | 13,239 | 1,892 (14.3%) | 1,370 | 42.3% | 31% | 0.67 | 771 |
| test | EMSR848 18 Nha Trang | 10,513 | 190 (1.8%) | 1,983 | 3.1% | 33% | 0.58 | 0 |
| test | EMSR848 19 Kim Châu | 7,265 | 604 (8.3%) | 0 | – | 0% | 0.59 | 0 |

The layer works best where 2020 UNOSAT maps already covered the same river plains (Tam Kỳ, Huế, Đà Nẵng: AUC 0.77–0.86) and worst where no earlier map exists (Nha Trang, Kim Châu: 0.58–0.59).

## Caveats

- **The truth is a satellite map, not a road report.** Radar and optical maps miss water under trees and in narrow streets, and show one moment of the flood. A road outside the mapped water may still have been cut off, so a `low` road is not confirmed safe. Checking passability still needs partner reports (layer 4).
- **One test flood.** All test roads come from one event in one region. The north, the Mekong delta and flash floods in the mountains are not tested.
- **Elevation is a surface model.** Raised roads, the main reason for the height layer, are often narrower than a 30 m pixel, so the layer sees the paddy beside them. That is likely why height against surroundings adds little.
- **Water depth is unknown.** "Flooded" means any visible water on 25–50 m of the road, whether 5 cm or 2 m.
- **Layer 3, water seen in dated photos, is not in.** Phase 1 has no water labels yet.
- **Not used:** the Global Flood Database (2000–2018 MODIS, 250 m, about 17.5 GB) would add history in the Mekong delta and the north, where dev was weakest. It is added in [the follow-up](2026-11-22-gfd-north.md).

## Reproduce

A few GB of downloads; `build` and `score` take about 10 minutes on a laptop.

```bash
pip install -r requirements-flood.txt
python -m tools.floodcheck fetch output/flood
python -m tools.floodcheck ways vietnam-latest.osm.pbf output/flood   # Geofabrik extract
python -m tools.floodcheck build output/flood
python -m tools.floodcheck score output/flood/flood_ways.csv           # also writes flood_risk.csv
```
