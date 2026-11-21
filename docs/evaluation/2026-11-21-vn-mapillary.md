# Mapillary photos for the Vietnamese test set (2026-11-21)

The KartaView set (`2026-11-21-vn-labels.csv`) has no Southeast or northern mountain rides, and 41 of its 51 unpaved photos come from one Ninh Bình ride. This adds public Mapillary photos for those gaps, in separate files so tools that read the KartaView files keep working:

- `data/2026-11-21-vn-mapillary-sequences.csv`: 17 sequences, with region, province, camera, date, Mapillary user and split.
- `data/2026-11-21-vn-mapillary-candidates.csv`: 255 photos (15 per sequence), `photo` is the Mapillary image id.
- `data/2026-11-21-vn-mapillary-labels.csv`: 202 labelled photos (`mapillary_sequence, photo, region, split, surface_by_eye`).

Mapillary imagery is CC BY-SA 4.0. Downloading photos needs a free Mapillary client token in `MAPILLARY_ACCESS_TOKEN`.

## Does Mapillary cover the gaps?

Yes. In Mapillary's public coverage tiles there are about 21,800 sequences in the Southeast (9,200 not panoramic) and 34,200 in the northern mountains (19,300 not panoramic). To find dirt, each sequence's track was compared with OSM `surface=*` tags from the Geofabrik Vietnam extract (133,890 ways tagged unpaved); sequences that run mostly along unpaved ways were picked first. Four of the best northern dirt matches turned out to be in Laos (Phongsaly, Houaphanh) and were dropped, so the northern mountains got less dirt than the Southeast.

Dropped after a look at the photos: two train rides and one drone flight (not road photos), and five rides shot only out of a side window.

## How the labels were made

Same rule as the KartaView set: Claude labelled every photo twice, in two different random orders, and only photos with the same label both times are kept. Pass 1 used the whole frame, pass 2 the road part (bottom 45%, middle 70%).

- Labelled twice: 255. Same label both times: 202. Two photos were called unpaved in pass 1 and paved in pass 2 and were dropped; the other 51 differences were a clear label against `unclear`, mostly frames where a dashboard fills the road box (the Sơn La ride lost all 15 photos this way).
- Kept: 129 paved, 37 unpaved, 36 unclear.
- These are provisional until a person checks a sample: `python -m tools.labelpage docs/evaluation/data/2026-11-21-vn-mapillary-labels.csv --sample 50 --out output/vn-mapillary-check.html`, then `tools.agreement`.

## Counts (paved / unpaved / unclear)

| region | KartaView (before) | Mapillary added | after |
|---|---|---|---|
| mekong | 190 / 10 / 20 | 0 / 0 / 0 | 190 / 10 / 20 |
| southeast | 0 / 0 / 0 | 49 / 16 / 3 | 49 / 16 / 3 |
| highlands | 90 / 0 / 0 | 30 / 0 / 0 | 120 / 0 / 0 |
| south_central | 0 / 0 / 0 | 1 / 4 / 8 | 1 / 4 / 8 |
| north_central | 79 / 0 / 51 | 0 / 8 / 16 | 79 / 8 / 67 |
| red_river | 63 / 41 / 24 | 0 / 0 / 0 | 63 / 41 / 24 |
| north_mountains | 0 / 0 / 0 | 49 / 9 / 9 | 49 / 9 / 9 |
| all | 422 / 51 / 95 | 129 / 37 / 36 | 551 / 88 / 131 |

The 37 new unpaved photos come from 6 sequences by 5 riders in 5 provinces; the largest share is 16 from one Đồng Nai rider (VPTD). The split stays per rider and day: Mapillary test has 65 paved, 29 unpaved, 12 unclear; dev has 64 paved, 8 unpaved, 24 unclear.

## Benchmark

To score both sources together:

```
python -m tools.benchmark docs/evaluation/data/2026-11-21-vn-labels.csv docs/evaluation/data/2026-11-21-vn-mapillary-labels.csv --out output/vn-all
```
