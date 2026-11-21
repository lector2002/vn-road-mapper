from tools import agreement


def label(photo, surface, sequence="7"):
    return {"kartaview_sequence": sequence, "photo": photo, "surface_by_eye": surface}


def test_counts_agreement_on_photos_clear_to_both_and_mud_as_unpaved():
    reference = [label("00001", "paved"), label("00002", "unpaved"), label("00003", "unclear"), label("00004", "paved")]
    check = [label("1", "paved"), label("2", "mud"), label("3", "paved"), label("4", "unpaved"), label("9", "paved")]
    result = agreement.compare(reference, check)
    assert (result["checked"], result["compared"], result["agree"]) == (4, 3, 2)
    assert result["unclear_to_either"] == 1 and result["not_in_reference"] == 1
    assert result["disagreements"] == [{"kartaview_sequence": "7", "photo": 4, "reference": "paved", "check": "unpaved"}]
    assert not result["passes"]


def test_passes_at_45_of_50():
    reference = [label(str(i), "paved") for i in range(50)]
    check = [label(str(i), "paved" if i < 45 else "unpaved") for i in range(50)]
    assert agreement.compare(reference, check)["passes"]
    check[44] = label("44", "unpaved")
    assert not agreement.compare(reference, check)["passes"]


def test_cli_exit_code_and_report(tmp_path, capsys):
    ref, chk = tmp_path / "ref.csv", tmp_path / "chk.csv"
    ref.write_text("kartaview_sequence,photo,osm_way_id,surface_by_eye\n7,00001,5,paved\n")
    chk.write_text("kartaview_sequence,photo,surface_by_eye\n7,00001,paved\n")
    assert agreement.main([str(ref), str(chk)]) == 0
    assert "agree: 1 of 1 -> PASS" in capsys.readouterr().out
