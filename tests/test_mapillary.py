import io
import json

import pytest
from PIL import Image

from tools import agreement, benchmark, candidates, labelpage, mapillary


def image(i, t):
    return {"id": str(i), "captured_at": t, "geometry": {"type": "Point", "coordinates": [104.9, 22.8]},
            "compass_angle": 90, "camera_type": "perspective", "creator": {"username": "rider"}}


def jpeg(width=40, height=30):
    buf = io.BytesIO()
    Image.new("RGB", (width, height), "grey").save(buf, "JPEG")
    return buf.getvalue()


def test_list_photos_sorts_by_capture_time_and_reads_the_token(monkeypatch):
    monkeypatch.setenv("MAPILLARY_ACCESS_TOKEN", "tok")
    urls = []

    def get(url):
        urls.append(url)
        return json.dumps({"data": [image(2, 1700000002000), image(1, 1700000001000)]}).encode()

    monkeypatch.setattr(mapillary, "get", get)
    photos = mapillary.list_photos("seq")
    assert [p["id"] for p in photos] == ["1", "2"]
    assert photos[0]["lat"] == "22.800000" and photos[0]["shotDate"] == "2023-11-14 22:13:21"
    assert "sequence_ids=seq" in urls[0] and "access_token=tok" in urls[0]


def test_missing_token_and_api_errors_are_value_errors(monkeypatch):
    monkeypatch.delenv("MAPILLARY_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("MAPILLARY_TOKEN", raising=False)
    with pytest.raises(ValueError):
        mapillary.token()
    monkeypatch.setenv("MAPILLARY_ACCESS_TOKEN", "tok")
    monkeypatch.setattr(mapillary, "get", lambda url: b'{"error": {"message": "Unsupported get request"}}')
    with pytest.raises(ValueError, match="Unsupported"):
        mapillary.photo_url("1")


def test_candidates_key_mapillary_photos_by_image_id():
    seqs = [{"mapillary_sequence": "abc", "region": "southeast", "split": "dev"}]
    photos = [mapillary.photo(image(i, 1700000000000 + i)) for i in range(10)]
    rows = candidates.candidates(seqs, 2, photos_of=lambda s: photos)
    assert rows[0]["mapillary_sequence"] == "abc" and rows[0]["photo"] == "2"
    assert "kartaview_sequence" not in rows[0]


def mly(photo, eye="unpaved"):
    return {"mapillary_sequence": "abc", "photo": photo, "surface_by_eye": eye}


def test_fetch_frames_saves_mapillary_photos_by_image_id_without_turning(tmp_path):
    def url_of(image_id):
        if image_id == "9":
            raise ValueError("gone")
        return f"https://mly/{image_id}"

    downloaded = []

    def download(url):
        downloaded.append(url)
        return jpeg(30, 40)

    missing = benchmark.fetch_frames([mly("5"), mly("9")], tmp_path, photos_of=lambda s: 1 / 0,
                                     download=download, mapillary_url=url_of)
    assert missing == ["mly_9.jpg"] and downloaded == ["https://mly/5"]
    assert Image.open(tmp_path / "mly_5.jpg").size == (30, 40)


def test_benchmark_reads_several_label_files_and_counts_each_mapillary_ride(tmp_path, monkeypatch):
    kv = tmp_path / "kv.csv"
    kv.write_text("kartaview_sequence,photo,surface_by_eye\n7,1,paved\n")
    ml = tmp_path / "mly.csv"
    ml.write_text("mapillary_sequence,photo,region,surface_by_eye\nabc,5,southeast,unpaved\n")
    monkeypatch.setattr(benchmark, "fetch_frames", lambda labels, frames_dir: [])
    frames = tmp_path / "out" / "frames"
    frames.mkdir(parents=True)
    (frames / "7_00001.jpg").write_bytes(jpeg())
    (frames / "mly_5.jpg").write_bytes(jpeg())

    from tests.test_benchmark import FakeSegmenter
    result = benchmark.run([kv, ml], tmp_path / "out", segmenter=FakeSegmenter())

    assert sorted(w["way_id"] for w in result["per_way"]) == ["7", "abc"]
    assert "southeast" in (tmp_path / "out" / "benchmark.csv").read_text()


def test_label_page_embeds_mapillary_photos_and_keeps_their_columns():
    items, missing = labelpage.items([mly("5")], photos_of=lambda s: 1 / 0, download=lambda url: jpeg(30, 40),
                                     mapillary_url=lambda i: f"https://mly/{i}", link=True)
    assert missing == []
    assert items[0]["fields"] == ["abc", "5"] and items[0]["key"] == "mapillary_5"
    assert items[0]["src"].startswith("data:image/jpeg;base64,")
    assert "Mapillary" in items[0]["credit"]


def test_agreement_matches_mapillary_photos_by_image_id():
    result = agreement.compare([mly("5"), mly("6", "paved")], [mly("5"), mly("6")])
    assert (result["compared"], result["agree"]) == (2, 1)
