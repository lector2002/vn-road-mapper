import io
import json

import pytest
from PIL import Image

from tools import kartaview


def photo(index, shot="2021-09-19 23:29:55.000", lat="19.787238", lng="105.877722"):
    return {"id": str(100 + index), "sequenceIndex": str(index), "shotDate": shot, "lat": lat, "lng": lng,
            "heading": "330.81", "wayId": "850282873", "fileurlLTh": f"https://example.test/{index}.jpg"}


def test_frame_row_matches_frames_stage_columns():
    row = kartaview.frame_row(0, photo(0))
    assert row == {"filename": "000001.jpg", "timestamp": "2021-09-19T23:29:55.000Z",
                   "lat": "19.787238", "lon": "105.877722", "heading": "330.81"}


def test_photos_come_back_in_sequence_order_across_pages(monkeypatch):
    pages = {1: [photo(2), photo(0)], 2: [photo(1)]}

    def fake_get(url):
        page = int(url.split("page=")[1])
        return json.dumps({"status": {"apiCode": 600, "apiMessage": "ok"},
                           "result": {"data": pages[page], "hasMoreData": page == 1}}).encode()

    monkeypatch.setattr(kartaview, "get", fake_get)
    assert [p["sequenceIndex"] for p in kartaview.list_photos("1")] == ["0", "1", "2"]


def test_api_error_in_body_is_raised(monkeypatch):
    monkeypatch.setattr(kartaview, "get", lambda url: json.dumps(
        {"status": {"apiCode": 613, "apiMessage": "itemsPerPage max is 150"}}).encode())
    with pytest.raises(ValueError, match="itemsPerPage"):
        kartaview.list_photos("1")


def jpeg(width, height, right_half="black"):
    image = Image.new("RGB", (width, height), "black")
    image.paste(Image.new("RGB", (width // 2, height), right_half), (width // 2, 0))
    buf = io.BytesIO()
    image.save(buf, "JPEG")
    return buf.getvalue()


def test_run_writes_frames_csv_and_kartaview_way_ids(tmp_path, monkeypatch):
    landscape = jpeg(64, 36)
    monkeypatch.setattr(kartaview, "list_photos", lambda sid: [photo(0), photo(1, shot="2021-09-19 23:29:58.000")])
    monkeypatch.setattr(kartaview, "get", lambda url: landscape)

    rows = kartaview.run("1", tmp_path)

    assert [r["timestamp"] for r in rows] == ["2021-09-19T23:29:55.000Z", "2021-09-19T23:29:58.000Z"]
    assert (tmp_path / "frames" / "000002.jpg").read_bytes() == landscape
    assert "850282873" in (tmp_path / "kartaview.csv").read_text(encoding="utf-8")


def test_portrait_photo_with_sky_on_the_right_is_turned_upright(tmp_path, monkeypatch):
    monkeypatch.setattr(kartaview, "list_photos", lambda sid: [photo(0)])
    monkeypatch.setattr(kartaview, "get", lambda url: jpeg(36, 64, right_half="white"))

    kartaview.run("1", tmp_path)

    frame = Image.open(tmp_path / "frames" / "000001.jpg").convert("L")
    assert frame.size == (64, 36)
    assert frame.getpixel((32, 2)) > 200
    assert frame.getpixel((32, 33)) < 50


def test_photo_url_prefers_the_cdn_copy():
    assert kartaview.photo_url({**photo(0), "imageLthUrl": "https://cdn.test/0"}) == "https://cdn.test/0"
    assert kartaview.photo_url(photo(0)) == "https://example.test/0.jpg"
