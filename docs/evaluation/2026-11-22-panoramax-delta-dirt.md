# Mekong delta dirt photos from Panoramax (2026-11-22)

All 36 unpaved photos in the Mapillary Mekong set (`2026-11-22-mekong-dirt.md`) come from one 2 km area in Đức Hòa, and they show sand fill near factories, not grassy delta tracks. This adds a second delta test set from Panoramax, a free public street-imagery service (CC BY-SA 4.0, no token):

- `data/2026-11-22-panoramax-delta-dirt-sequences.csv`: 14 Panoramax sequences (collections), all from one ride by user `Dodko` on 2025-02-15, split `test`.
- `data/2026-11-22-panoramax-delta-dirt-candidates.csv`: 189 photos; `photo` is the Panoramax item id.
- `data/2026-11-22-panoramax-delta-dirt-owner-spot-check.csv`: the owner's blind answers for 50 of them.
- `data/2026-11-22-panoramax-delta-dirt-labels.csv`: the same 189 photos labelled, with photographer and license for the credit line: 128 paved, 35 unpaved, 1 mud, 25 unclear.

**Trust status: trusted test data.** The owner's blind spot check agrees on 42 of the 43 photos both call clear (98%, the bar is 90%). His answers win where they overlap (`tools.benchmark --prefer`).

## Where the photos come from

The Panoramax API (`api.panoramax.xyz`) lists 62 collections in the delta box (8.5–11.1 N, 104.4–106.9 E). Most are a few photos, panoramas or city streets. One motorbike ride by `Dodko` has about 6,700 photos across the former Bến Tre and Trà Vinh provinces (now Vĩnh Long), 9.74–10.25 N, 106.10–106.35 E. That is 70–125 km south of Đức Hòa. It runs on many narrow lanes through coconut, banana and rice land, including grassy dirt tracks, red earth on new embankments and gravel fill.

Contact sheets of the whole ride were reviewed, and 189 photos were picked from 14 of its collections. Picks were weighted toward the stretches with dirt, but the concrete lanes and asphalt in those stretches were kept.

Limits:

- **One rider, one day, one camera.** All 14 collections are the same ride, so a per-ride score counts the same rider 14 times.
- **The handlebars and a phone are in every frame.** It is a wide-angle camera mounted behind the bars (1920×1080, served at 1024×576). The box the surface stage reads (bottom 40%, middle 60%) is mostly the dashboard, the phone and the mirrors here, not the road.
- Concrete lanes are still the most common surface. Real dirt is about one photo in five.

## How the labels were made

Pass 1 labelled all 189 photos from the road ahead (rows 48–80%, columns 22–78% of the frame, above the dashboard) at 360 px, in random order. Every photo called unpaved or mud was then looked at again, larger (480 px), and 2 narrow light-grey lanes that could be concrete were moved to `unclear`. Paved calls were not looked at a second time. This is lighter than the two-pass rule of the earlier sets, so the owner check carries more weight here.

| sequence | paved | unpaved | mud | unclear |
|---|---|---|---|---|
| `409d8b71` (Trà Vinh) | 36 | 8 | 0 | 5 |
| `36d8d04a` | 18 | 9 | 0 | 4 |
| `54793533` | 8 | 5 | 0 | 7 |
| `1eb20567` | 16 | 2 | 0 | 2 |
| `c321f9d0` | 10 | 6 | 0 | 1 |
| `65e2bc00` (Bến Tre) | 0 | 5 | 1 | 0 |
| 8 other collections | 40 | 0 | 0 | 6 |

## How the current model scores

`python -m tools.benchmark docs/evaluation/data/2026-11-22-panoramax-delta-dirt-labels.csv --out output/panoramax-delta` (add `--no-probe` for SegFormer alone). Each collection counts as one way. These are scores against the label file before the owner check; `--prefer docs/evaluation/data/2026-11-22-panoramax-delta-dirt-owner-spot-check.csv` applies his answers, which changes one unpaved frame to paved.

| | SegFormer alone | With the dirt probe |
|---|---|---|
| Clear frames that vote | 42 of 163 | 42 of 163 |
| Voting frames right | 35 of 42 | 30 of 42 |
| Unpaved called paved | 1 of 35 | 0 of 35 |
| Paved called unpaved | 6 of 128 | 12 of 128 |
| Collections right (eye majority) | 10 of 14 | 8 of 14 |

- **Almost nothing votes.** 121 of 163 clear frames give no surface: 85 come out `vegetation` (60 paved, 25 unpaved) 35 `other`, mostly the dashboard and phone filling the box, and 1 is below the confidence cut.
- **Grassy delta dirt is called vegetation.** Only 7 of the 35 unpaved frames are called dirt with the probe (6 without); 25 are `vegetation`. This is the Hà Tĩnh and Đức Hòa failure again, on a new place and camera.
- **The dirt probe hurts here.** It turns 6 more paved frames into dirt, likely from the earth verges and handlebar shadows in the box; it was trained on other cameras.

So the set is useful mainly as a hard test: to score it fairly, the surface stage needs a box that skips the dashboard on handlebar cameras.

## Owner spot check

50 of the 189 photos, spread over the labels, are on a blind page: `python -m tools.labelpage docs/evaluation/data/2026-11-22-panoramax-delta-dirt-labels.csv --sample 50 --title "Panoramax delta dirt: blind spot check" --out panoramax-spot-check.html`. Agreement: `python -m tools.agreement docs/evaluation/data/2026-11-22-panoramax-delta-dirt-labels.csv docs/evaluation/data/2026-11-22-panoramax-delta-dirt-owner-spot-check.csv`.

- 50 checked, 43 clear to both: **42 agree (98%), so the labels pass**.
- The other 7 were unclear in the labels; the owner also called one of them unclear.
- The one disagreement was unpaved in the labels and paved for the owner: a grey, dusty lane between banana plants and a house (`36d8d04a-3796-435d-8544-9fd841f6dc80` / `09b0bfce-cdd1-4d5d-9d1f-7182e607ef57`), most likely worn concrete.
