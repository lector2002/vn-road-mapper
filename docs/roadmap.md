# Roadmap

> Written 2026-11-21. Public imagery first; nothing depends on hiring or paying riders or labellers.
> Effort is in Devin sessions (one session is about one engineer-week). Calendar time is mostly waiting on volunteers and the OSM community.

## Where it stands

| Area | State | Evidence |
|---|---|---|
| Pipeline (frames → export) | All 6 stages run end to end | KartaView rides, Thanh Hóa and Cần Thơ |
| Surface on paved roads | Good | 47 of 48 hand sample, 28 of 28 OSM-tagged ways agree |
| Surface on dirt roads | Main weakness | 112 of 142 right; 27 of the 30 errors are dirt called `paved` |
| Mud | Not possible yet | ADE20K has no mud class |
| Flood / water | Untested on real footage | Only false `water` hits so far |
| Width | Unconfirmed | 8 of 235 frames got a width on helmet-camera footage; no ground truth |
| OSM upload | None, on purpose | Community not contacted yet |

Labelled Vietnamese frames are the bottleneck, not code: every accuracy test so far ends with "needs more Vietnamese rides". The 177 Cần Thơ labels were made by Claude in one pass and no person has checked them.

## Phase 0: one-command run and benchmark (done)

- `python -m pipeline.run` runs every stage on a video + GPX or a KartaView sequence.
- `python -m tools.benchmark` downloads the labelled KartaView photos and prints the surface confusion table, frame accuracy and per-way agreement.
- `requirements.txt` holds only what the code imports; model and test extras are separate files.
- A weekly CI job runs the real SegFormer model.
- The KartaView importer loads photos from the CDN: on 2026-11-21 the `storage*.openstreetcam.org` photo hosts resolved to a private address and every download timed out.

**Expect:** no accuracy change. Every later change is measured with the same command.

## Phase 1: a trusted Vietnamese test set (1–2 sessions)

No paid labellers, so:
- **Owner spot check (about 20–30 min):** label 50 of the 177 Cần Thơ photos on the label page, blind to the existing labels. `python -m tools.agreement` compares the two; if 45 or more of the photos clear to both agree, keep the file as test data. *Done 2026-11-21: 38 of 44 agree (86%), so it failed. The 177 Cần Thơ labels are training data only, with the owner's 50 answers (`docs/evaluation/data/2026-11-21-can-tho-owner-spot-check.csv`) replacing them where they overlap.*
- **Label page:** `tools/labelpage.py` builds one HTML file that shows the road box and saves paved / unpaved / mud / water / unclear to CSV. Shareable with OSM Vietnam volunteers. *Done.*
- **Candidate frames:** `docs/evaluation/data/2026-11-21-vn-candidates.csv`, 585 KartaView photos from 13 sequences in 6 provinces and 4 regions (Mekong delta, Central Highlands, North Central, Red River delta), 6 cameras from 2017 to 2026. The split is fixed per rider and day: 180 test, 405 dev (all Cần Thơ in dev since Phase 2, because the hand-labelled Cần Thơ rides share days with the candidates). *Done.*
- **Labels for the candidates:** `docs/evaluation/data/2026-11-21-vn-labels.csv`. Claude labelled each photo twice in a different random order and kept the 568 where both passes agree: 422 paved, 51 unpaved, 95 unclear, no mud or water. The Ninh Bình ride holding most of the dirt moved to test. On the test split SegFormer gets 110 of 128 frames right but calls 17 of 34 unpaved photos paved ([write-up](evaluation/2026-11-21-vn-candidate-labels.md)). Volunteers can label the same file with `--link`. *Done.*
- **Owner spot check of the test split:** 50 test photos, blind. *Done 2026-11-21: 37 of 38 agree (97%), so the test labels pass. 12 Hà Tĩnh photos the labels left `unclear` are clear to the owner (11 unpaved); his answers replace the labels where they overlap ([write-up](evaluation/2026-11-21-vn-test-owner-spot-check.md)).*

Gaps: KartaView has no sequence of 30 or more photos in the northern mountains, and most candidates are on roads near towns. Five sequences were dropped: four come out sideways (turned the wrong way by the portrait fix, which took out the Southeast region) and one has a covered lens. Mapillary covers more rural roads but needs a free access token (`MAPILLARY_TOKEN`, from a free Mapillary account); it is the next source to add when the owner makes one.

**Expect:** the real dirt-versus-paved error rate across Vietnam. It is probably worse than Cần Thơ's 77% (109 of 142), which is one region and one camera (inferred). Without a person checking a sample, label noise limits how far later numbers can be trusted.

## Phase 2: fix dirt called `paved` (1–2 sessions)

*Done 2026-11-21 ([write-up](evaluation/2026-11-21-phase2-dirt-probe.md)):* a CLIP probe on the road crop rechecks frames SegFormer calls paved. Test split: 110 → 120 of 128 frames right, unpaved called paved 17 → 6 of 34, paved called unpaved 1 → 2 of 94, rides 3 → 4 of 4, 0 of 465 Thanh Hóa paved frames switched. Option 1 got only 113 of 128. With the owner's test spot check answers: 119 of 129, unpaved called paved 8 of 36, paved called unpaved 2 of 93, rides 3 of 4; the Hà Tĩnh dirt ride is called paved because its grassy dirt frames come out `vegetation` and do not vote ([spot check](evaluation/2026-11-21-vn-test-owner-spot-check.md)).

In order of cost:
1. The linear probe on SegFormer features (122–126 of 142 with 5 rides), retrained on Phase 1 data.
2. A stronger frozen backbone on the road crop (DINOv2 or CLIP features) as a second opinion.
3. Fine-tune the SegFormer decoder, with a real `mud` class once there are mud labels.

Pass rule stays: no new paved roads called unpaved, no Thanh Hóa way changes.

**Expect:** frame accuracy on clear frames from about 77% (109 of 142) to about 88–92%, with paved called unpaved at 3% or less (inferred from the probe trend, not measured). Way-level accuracy is higher because fusion votes. If it stalls in the mid-80s, export `unpaved` only where two or more rides agree.

## Phase 3: OSM community and a small pilot (1 session, then 2–6 weeks of community time)

- Post the method, benchmark numbers and sample proposals on the OSM Vietnam forum and Telegram before any edit. Follow the OSM Automated Edits code of conduct and write an organised-editing wiki page.
- Pilot: 50–100 untagged ways in one district, from imagery from 2023 or later. People make the edits from the review map or a MapRoulette challenge; no script upload.

**Expect:** the main risk is social, not technical. The community may narrow which roads and tags are welcome. Reviewers accepting 90% or more of proposals is the bar for going further.

**Status:** the kit is in [docs/pilot](pilot/README.md): announcement (English and Vietnamese), organised-editing wiki page, MapRoulette challenge text and file, and PILOT_N proposals in the former Ô Môn district of Cần Thơ from two May 2023 KartaView rides. `python -m tools.pilot score` checks the 90% bar. The owner sends it; nothing has been posted or edited.

## Phase 4: width as classes (1 session)

Public imagery has unknown camera height and lens, so metric width within 0.5 m is out of reach. Riders and ambulances need a class: **motorbike only (under 2.5 m) / one car (2.5–4 m) / two cars (over 4 m)**.

- Scale each sequence from objects of known size (motorbikes, lane markings), or classify from the road-mask shape without a camera height.
- Check against the about 1,400 width-tagged minor roads in OSM Vietnam.

**Expect:** a usable 3-class width on straight narrow roads; most frames still get none (bends, wide roads).

## Phase 5: flood-risk layer (2–4 sessions)

Public imagery is rarely taken during floods, and water depth is not visible in a frame, so video alone cannot say "passable in flood season". Build it from layers instead:
1. Flood history from satellite flood maps (Sentinel-1 radar, Copernicus EMS, Global Flood Database) on OSM ways, in PostGIS.
2. Road height against its surroundings from a public elevation model (raised roads in the Mekong delta).
3. Water seen on the road in dated imagery, once Phase 1 has water labels.
4. Later, with partners: which roads closed in the last flood, from commune health stations or the Red Cross.

**Expect:** layers 1 and 2 give a district "likely cut off in floods" map without new footage. Layer 3 stays sparse. Checking the map needs partner reports.

## Phase 6: one province (2–3 sessions)

- Self-hosted Valhalla with a Vietnam extract (the public server is not for bulk use).
- Batch run over all KartaView and Mapillary sequences in one province; a GPU instead of 1.3 s per frame on CPU.
- PostGIS for ways, votes and flood layers; re-run when new imagery appears.

**Expect:** coverage only where public imagery exists, which favours main roads; HeiGIT's model covers 5.3% of Vietnam's road length for the same reason. Rural lanes, the project's target, stay thin until a partner offers footage.

## Summary

| Phase | Effort | Needs a person | What changes |
|---|---|---|---|
| 0 Run + benchmark | done | No | Same command measures every change |
| 1 Trusted test set | 1–2 sessions | Owner, 30 min | Real error rate across regions |
| 2 Dirt vs paved | 1–2 sessions | No | About 77% → about 90% (target) |
| 3 OSM pilot | 1 session | OSM volunteers | First accepted edits |
| 4 Width classes | 1 session | No | 3-class width on narrow roads |
| 5 Flood layer | 2–4 sessions | Partners to check | District flood-risk map |
| 6 One province | 2–3 sessions | No | Province coverage where imagery exists |
