# Handoff: starting the repo

## 1. Push to GitHub (5 min)

1. Create a new public repo on github.com named `vn-road-mapper` (no README, it's already here).
2. Unzip this folder, then from inside it:

```bash
git init
git add .
git commit -m "Initial plan + skeleton"
git branch -M main
git remote add origin https://github.com/<your-username>/vn-road-mapper.git
git push -u origin main
```

## 2. Record a sample clip (10 min)

- Mount phone on motorbike, record 1–2 min of a dirt/rural road (1080p, 30fps).
- Turn on a GPS logger at the same time (e.g. any GPX logger app).
- Upload a short clip (<25 MB) to `data/samples/` or link it in the README.

## 3. Send to Poke

> repo's up 👉 https://github.com/<your-username>/vn-road-mapper — sample clip in data/samples. starting the frame pipeline with Devin now

## 4. Prompt to paste into Devin

```
Repo: https://github.com/<your-username>/vn-road-mapper
Read README.md for the full plan.

Task 1 (pipeline/frames):
- Python CLI: input = video file + GPX file
- Extract frames at 2 fps with ffmpeg
- Interpolate GPS position for each frame timestamp
- Output: frames/*.jpg + frames.csv (filename, timestamp, lat, lon, heading)
- Add a test using a short sample in data/samples
- Update pipeline/frames/README.md with usage

Task 2 (pipeline/segmentation):
- Load SegFormer-B2 pretrained on Mapillary Vistas (Hugging Face)
- Run on extracted frames, map classes to: paved / dirt / mud / water / vegetation / other
- Output per-frame road-surface label + confidence to CSV
- Save a few overlay images for visual check

Keep it simple, CPU-runnable on small samples. Open a PR per task.
```
