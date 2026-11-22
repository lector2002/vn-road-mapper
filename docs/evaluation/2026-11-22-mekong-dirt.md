# Mekong dirt test set from Mapillary (2026-11-22)

No test ride covered unpaved roads in the Mekong delta: the KartaView set has 10 unpaved Mekong photos, the first Mapillary set none, and the Cần Thơ labels are training-only. This adds a dirt-weighted Mekong test set from public Mapillary photos (CC BY-SA 4.0):

- `data/2026-11-22-mekong-dirt-sequences.csv`: 18 sequences, with province, camera, date, Mapillary user and split (all `test`).
- `data/2026-11-22-mekong-dirt-candidates.csv`: 190 photos, `photo` is the Mapillary image id.
- `data/2026-11-22-mekong-dirt-labels.csv`: 143 labelled photos: 88 paved, 36 unpaved, 19 unclear.
- `data/2026-11-22-mekong-dirt-owner-spot-check.csv`: the owner's blind labels for 50 of them.

**Trust status: trusted test data.** The owner's blind spot check agrees on 40 of the 43 photos both call clear (93%, the bar is 90%). His answers win where they overlap (`tools.benchmark --prefer`).

## How the photos were picked

Mapillary's coverage tiles list 19,611 sequences in the delta box (9,734 not panoramic). Each sequence's track was matched against OSM `surface=*` and `highway=track` in the Geofabrik Vietnam extract, clipped to the delta provinces (An Giang, Cà Mau, Cần Thơ, Vĩnh Long, Đồng Tháp and the former Long An part of Tây Ninh), and the 182 best-matching sequences were looked at on contact sheets.

What the photos showed:

- **Real dirt is rare on public delta imagery.** Most rural lanes are concrete. The OSM match is a weak guide: the sequence with the highest unpaved share (67%, Cà Mau, `JAtB8OiwYlfQpnPEjT0abS`) is a concrete lane.
- **Brown lanes in Cà Mau are concrete.** Five Cà Mau rides (user `hoangvietanh`) look like dirt tracks on thumbnails, but full-size frames show slab joints. They are kept as hard paved negatives (8 photos each).
- **All 36 unpaved photos come from one place.** They are dirt and gravel side lanes at the ends of seven rides by one user (`VPTD`) in Đức Hòa (former Long An, now Tây Ninh), all within about 2 km (10.84–10.86 N, 106.48–106.49 E). Photos were sampled densely in those dirt stretches. This is a narrow sample: sand-coloured fill and gravel near new factories, not delta mud or grassy tracks.
- Rural asphalt and concrete rides (Vĩnh Long, Cà Mau, Tây Ninh) fill out the paved side.

## How the labels were made

Same rule as the earlier sets: every photo was labelled twice by Claude, in two different random orders, and only photos with the same label both times are kept. Pass 1 used the road part (bottom 45%, middle 70%) at 400 px wide, pass 2 the whole frame. Thumbnails were not used for labels because they make concrete look like dirt.

- Labelled twice: 190. Same label both times: 143.
- 46 differences were a clear label against `unclear` (28 paved, 18 unpaved), mostly blurred or dark frames and broken asphalt that could be gravel. One photo was paved in one pass and unpaved in the other and was dropped.

| sequences | paved | unpaved | unclear |
|---|---|---|---|
| Đức Hòa dirt-lane rides (7, VPTD) | 20 | 35 | 18 |
| Cà Mau concrete lanes (9, hoangvietanh) | 56 | 0 | 0 |
| Cà Mau concrete lane (1, thanh_hang) | 7 | 0 | 1 |
| Vĩnh Long rural asphalt (1, gabriel_oliveira) | 5 | 1 | 0 |

## How the current model scores

`python -m tools.benchmark docs/evaluation/data/2026-11-22-mekong-dirt-labels.csv --out output/mekong-dirt` (add `--no-probe` for SegFormer alone). Each ride counts as one way.

| | SegFormer alone | With the dirt probe |
|---|---|---|
| Clear frames that vote | 55 of 124 | 55 of 124 |
| Voting frames right | 45 of 55 | 47 of 55 |
| Unpaved called paved | 8 of 36 | 6 of 36 |
| Paved called unpaved | 2 of 88 | 2 of 88 |
| Rides right (eye majority) | 9 of 18 | 9 of 18 |

The headline number hides two failures:

- **Concrete lanes in greenery do not vote.** 55 of the 88 paved frames come out `vegetation`, including 50 of the 56 Cà Mau concrete frames; six Cà Mau rides get no surface at all. SegFormer sees the verges, not the narrow lane.
- **Delta dirt is missed in a third of frames.** Of the 36 unpaved frames, 18 are called dirt, 6 paved (the probe saves 2 more than SegFormer alone), 9 `vegetation` and 3 fall below the confidence cut. Three of the five Đức Hòa dirt rides are called paved.

So the model rarely calls a paved delta road dirt, but on this set it gives no answer for most concrete lanes and misses or skips half the dirt. Grassy dirt called vegetation is the same failure seen in Hà Tĩnh (`2026-11-21-vn-test-owner-spot-check.md`).

## Owner spot check

50 of the 143 photos, spread over the labels, were put on a blind page: `python -m tools.labelpage docs/evaluation/data/2026-11-22-mekong-dirt-labels.csv --sample 50 --title "Mekong dirt test: blind spot check" --out mekong-spot-check.html`. Agreement: `python -m tools.agreement docs/evaluation/data/2026-11-22-mekong-dirt-labels.csv docs/evaluation/data/2026-11-22-mekong-dirt-owner-spot-check.csv`.

- 50 checked, 43 clear to both: **40 agree (93%), so the labels pass**.
- 7 were unclear to one side. The owner called 4 Đức Hòa dirt frames `mud`, which counts as unpaved.
- All 3 disagreements were paved in the labels and unpaved for the owner. Two are broken asphalt in Đức Hòa (`aS5pH0NdJs4v3wfAO6qLID` 682333564496261 and 1334347720976341), worn down to gravel with puddles. The third is a Cà Mau concrete lane (`zbGrLmHk6Mq5CPQOuYjx43` 883940156455271) whose slab joints are faint at 1024 px.

Scores with the owner's answers winning (`--prefer docs/evaluation/data/2026-11-22-mekong-dirt-owner-spot-check.csv`). After the swap, 85 frames are paved by eye, 41 unpaved and 4 mud; the benchmark counts the mud frames separately.

| | SegFormer alone | With the dirt probe |
|---|---|---|
| Clear frames that vote | 55 of 126 | 55 of 126 |
| Voting frames right | 40 of 55 | 42 of 55 |
| Unpaved called paved | 13 of 41 | 11 of 41 |
| Paved called unpaved | 2 of 85 | 2 of 85 |
| Rides right (eye majority) | 9 of 18 | 9 of 18 |

Unpaved called paved goes up from 6 to 11 because the photos the owner moved to unpaved (broken asphalt and a lane he read as earth) are ones the model calls paved. The two failures above still hold: concrete lanes come out `vegetation` (54 of 85 paved frames), and the model misses about a third of delta dirt.
