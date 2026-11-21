"""Label rows name their photo source by column: kartaview_sequence + photo (sequenceIndex) for KartaView,
mapillary_sequence + photo (image id) for Mapillary."""

SEQUENCE_COLUMNS = ["kartaview_sequence", "mapillary_sequence"]


def source(row):
    return "mapillary" if row.get("mapillary_sequence") else "kartaview"


def sequence(row):
    return row.get("mapillary_sequence") or row["kartaview_sequence"]


def key(row):
    """KartaView photos are numbered within a sequence; Mapillary image ids are unique on their own."""
    if source(row) == "mapillary":
        return "mapillary", str(row["photo"])
    return row["kartaview_sequence"], int(row["photo"])


def frame_name(row):
    if source(row) == "mapillary":
        return f"mly_{row['photo']}.jpg"
    return f"{row['kartaview_sequence']}_{int(row['photo']):05d}.jpg"


def credit(row):
    if source(row) == "mapillary":
        return f"Mapillary image {row['photo']}, sequence {row['mapillary_sequence']}, CC BY-SA 4.0"
    return f"KartaView sequence {row['kartaview_sequence']}, photo {row['photo']}, CC BY-SA 4.0"


def key_columns(rows):
    return [c for c in SEQUENCE_COLUMNS if any(r.get(c) for r in rows)] + ["photo"]
