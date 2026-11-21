# Phase 3: OSM community pilot kit

Everything here is a draft for the repo owner to read, edit and send under their own name. Nothing in this repo posts, publishes or edits OSM.

## What the pilot is

- **Area:** the former Ô Môn district of Cần Thơ (around Long Hưng and Phước Thới), from two public KartaView rides shot in May 2023 with a 360° camera (sequences [8293225](https://kartaview.org/details/8293225/0/track-info) and [8308169](https://kartaview.org/details/8308169/0/track-info)).
- **Ways:** up to 100 small roads (`highway=unclassified/residential/track/service/tertiary/living_street/road`) that OSM has no `surface` tag for, where at least 5 photos voted and at least 70% agreed. The proposals are listed in [`data/pilot.csv`](data/pilot.csv) and shown on the map in [`data/review.html`](data/review.html).
- **Tag:** only `surface=paved` or `surface=unpaved`. It never overwrites a tag that is already there.
- **Who edits:** a person checks each way against its photos in MapRoulette and approves, changes or rejects the tag. MapRoulette uploads only what they approve, under their own account. There is no script upload.
- **Bar:** reviewers accept 90% or more of the proposals. Below that, stop and fix the model before doing more.

## Steps for the owner (in this order)

| # | What | Where | Time |
|---|---|---|---|
| 1 | Read and adjust the wiki page draft, then create it and add a row to the activities list | [`wiki-activity-page.wiki`](wiki-activity-page.wiki) → [Organised Editing/Activities](https://wiki.openstreetmap.org/wiki/Organised_Editing/Activities) | 20 min |
| 2 | Post the announcement in English and Vietnamese | [`announcement.md`](announcement.md) → [OSM forum, General talk](https://community.openstreetmap.org/c/general/38), the [talk-vi list](https://lists.openstreetmap.org/listinfo/talk-vi/), the [OSM Vietnam Facebook group](https://www.facebook.com/groups/openstreetmapvietnam/) | 15 min |
| 3 | Wait at least 2 weeks and answer questions. Change the plan if the community asks for it (fewer roads, other tags, no pilot) | the same threads | 2–6 weeks |
| 4 | Create the MapRoulette challenge from the drafted text and `data/challenge.geojson` (rebuild it first, see below) | [`maproulette-challenge.md`](maproulette-challenge.md) → [maproulette.org](https://maproulette.org) | 20 min |
| 5 | Ask 2–3 local mappers to do the tasks; doing some yourself is fine | the forum thread | 1–3 weeks |
| 6 | Export the challenge as CSV and score it: `python -m tools.pilot score export.csv` | MapRoulette challenge page, cog menu, Export CSV | 5 min |
| 7 | Post the result on the wiki page and in the thread | | 10 min |

The Organised Editing Guidelines ask for the wiki page first, then the announcement on the channel the local community uses most, at least two weeks before the activity starts. The forum has no Vietnam category, so the draft goes to General talk with the Facebook group and talk-vi pointing to it. Facebook needs an account to read, so it should not be the only place.

## Rebuild the pilot just before step 4

OSM changes while the community discusses. Rebuilding drops ways someone has tagged in the meantime:

```bash
python -m pipeline.run --kartaview 8293225 --every 2 --out output/pilot/kv-8293225 --no-export
python -m pipeline.run --kartaview 8308169 --every 2 --out output/pilot/kv-8308169 --no-export
python -m pipeline.fusion.fuse output/pilot/kv-8293225 output/pilot/kv-8308169 --out output/pilot/fused
python -m pipeline.export.export output/pilot/fused/ways.csv --out output/pilot/fused
python -m tools.pilot build output/pilot/fused/proposals.csv output/pilot/kv-8293225 output/pilot/kv-8308169 --out docs/pilot/data
```

The two rides take about an hour each on a laptop CPU (2,700 and 3,600 photos). Only the last two commands are needed when the rides have already run.

## What to say about accuracy

On the Vietnamese test split (4 public rides), with the owner's spot-check answers included, the model gets 119 of 129 clear photos right: 8 of 36 unpaved photos are called paved and 2 of 93 paved photos are called unpaved, and 3 of the 4 rides get the right majority ([PR #6](https://github.com/lector2002/vn-road-mapper/pull/6); before the owner's answers it was 120 of 128). The labels were made in two passes by the project; the owner then checked a blind sample of 50 and agreed on 37 of the 38 they found clear (97%, the bar is 90%). The ride it gets wrong is a Hà Tĩnh dirt road where most photos come out as vegetation or other and so cast no vote: that makes the pilot propose fewer unpaved roads, not wrong ones. None of the test rides is in the Mekong delta (they are in Ninh Bình, Hà Tĩnh and Gia Lai), so dirt accuracy in the Mekong delta is not measured yet: the pilot is that measurement.
