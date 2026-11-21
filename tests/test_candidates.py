from tools import candidates


def photos(n):
    return [{"sequenceIndex": str(i), "lat": "10.0", "lng": "105.7", "shotDate": "2023-11-20 08:00:00"} for i in range(n)]


def test_spaced_spreads_photos_over_the_whole_sequence():
    picked = [int(p["sequenceIndex"]) for p in candidates.spaced(photos(100), 4)]
    assert picked == [12, 37, 62, 87]
    assert len(candidates.spaced(photos(3), 10)) == 3


def test_candidates_carry_region_split_and_label_page_keys():
    seqs = [{"kartaview_sequence": "5", "region": "mekong", "split": "test"}]
    rows = candidates.candidates(seqs, 2, photos_of=lambda s: photos(10))
    assert rows[0] == {"kartaview_sequence": "5", "photo": "00002", "region": "mekong", "split": "test",
                       "lat": "10.0", "lon": "105.7", "shot_date": "2023-11-20"}
    assert len(rows) == 2
