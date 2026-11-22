"""Label rows name their photo source by column: kartaview_sequence + photo (sequenceIndex) for KartaView,
mapillary_sequence + photo (image id) for Mapillary, panoramax_sequence + photo (item UUID) for Panoramax."""

SEQUENCE_COLUMNS = ["kartaview_sequence", "mapillary_sequence", "panoramax_sequence"]
BY_ID = {"mapillary": "mly", "panoramax": "pmx"}
NAMES = {"kartaview": "KartaView", "mapillary": "Mapillary", "panoramax": "Panoramax"}


def source(row):
    for name in BY_ID:
        if row.get(f"{name}_sequence"):
            return name
    return "kartaview"


def sequence(row):
    return row[f"{source(row)}_sequence"]


def key(row):
    """KartaView photos are numbered within a sequence; Mapillary image ids and Panoramax item ids are unique on their own."""
    if source(row) in BY_ID:
        return source(row), str(row["photo"])
    return row["kartaview_sequence"], int(row["photo"])


def frame_name(row):
    if source(row) in BY_ID:
        return f"{BY_ID[source(row)]}_{row['photo']}.jpg"
    return f"{row['kartaview_sequence']}_{int(row['photo']):05d}.jpg"


def credit(row):
    name = source(row)
    if name in BY_ID:
        return f"{NAMES[name]} image {row['photo']}, sequence {sequence(row)}, CC BY-SA 4.0"
    return f"KartaView sequence {row['kartaview_sequence']}, photo {row['photo']}, CC BY-SA 4.0"


def key_columns(rows):
    return [c for c in SEQUENCE_COLUMNS if any(r.get(c) for r in rows)] + ["photo"]
