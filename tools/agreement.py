"""Compare a second person's surface labels with an existing label file, photo by photo.

Used for the owner spot check: if 45 of 50 checked photos agree (90%), the existing file is kept as test data.
"""
import argparse
import json
import sys
from collections import Counter

from tools import sources
from tools.benchmark import load_labels

CLEAR = {"paved", "unpaved", "mud", "water"}
FAMILY = {"paved": "paved", "unpaved": "unpaved", "mud": "unpaved", "water": "water", "unclear": "unclear"}


key = sources.key


def compare(reference, check, pass_share=0.9):
    """Agreement on photos both files call clear; mud counts as unpaved, as in the benchmark."""
    rows = {key(r): r for r in reference}
    ref = {k: r["surface_by_eye"] for k, r in rows.items()}
    pairs = [(k, ref[k], c["surface_by_eye"]) for c in check for k in [key(c)] if k in ref]
    clear = [(k, a, b) for k, a, b in pairs if a in CLEAR and b in CLEAR]
    disagree = [(k, a, b) for k, a, b in clear if FAMILY[a] != FAMILY[b]]
    agreed = len(clear) - len(disagree)
    return {
        "checked": len(pairs),
        "not_in_reference": len(check) - len(pairs),
        "unclear_to_either": len(pairs) - len(clear),
        "compared": len(clear),
        "agree": agreed,
        "passes": bool(clear) and agreed >= pass_share * len(clear),
        "pairs": dict(Counter(f"{FAMILY.get(a, 'unclear')} -> {FAMILY.get(b, 'unclear')}" for _, a, b in pairs)),
        "disagreements": [
            {f"{sources.source(rows[k])}_sequence": sources.sequence(rows[k]), "photo": k[1], "reference": a, "check": b}
            for k, a, b in disagree
        ],
    }


def report(result, pass_share=0.9):
    lines = [
        f"{result['checked']} photos checked, {result['compared']} clear to both",
        f"agree: {result['agree']} of {result['compared']}"
        f" -> {'PASS' if result['passes'] else 'FAIL'} (needs {pass_share:.0%})",
    ]
    if result["unclear_to_either"]:
        lines.append(f"unclear to either: {result['unclear_to_either']}")
    if result["not_in_reference"]:
        lines.append(f"not in the reference file: {result['not_in_reference']}")
    for d in result["disagreements"]:
        sequence = sources.sequence(d)
        lines.append(f"  {sequence}/{d['photo']}: reference {d['reference']}, check {d['check']}")
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("reference_csv", help="existing labels")
    p.add_argument("check_csv", help="the second person's labels, e.g. from the label page")
    p.add_argument("--pass-share", type=float, default=0.9)
    p.add_argument("--json", action="store_true", help="print the full result as JSON")
    args = p.parse_args(argv)
    result = compare(load_labels(args.reference_csv), load_labels(args.check_csv), args.pass_share)
    print(json.dumps(result, indent=2) if args.json else report(result, args.pass_share))
    return 0 if result["passes"] else 1


if __name__ == "__main__":
    sys.exit(main())
