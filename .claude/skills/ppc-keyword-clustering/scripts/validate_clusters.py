#!/usr/bin/env python3
"""Validate completeness and structural invariants of PPC clusters.csv."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path


REQUIRED = {
    "keyword", "normalized", "cluster_id", "platform", "campaign", "ad_group",
    "intent", "offer", "landing_page", "status", "confidence", "reason",
}
STATUSES = {"active", "excluded", "review"}
CONFIDENCE = {"high", "medium", "low"}
PLATFORMS = {"yandex", "google", "both", "none"}


def read_csv(path: Path) -> tuple[list[dict[str, str]], set[str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [{k: (v or "").strip() for k, v in row.items()} for row in reader]
        return rows, set(reader.fieldnames or [])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", required=True)
    parser.add_argument("--clusters", required=True)
    args = parser.parse_args()

    prepared, prepared_fields = read_csv(Path(args.prepared))
    clusters, cluster_fields = read_csv(Path(args.clusters))
    errors: list[str] = []
    warnings: list[str] = []

    if "normalized" not in prepared_fields:
        errors.append("prepared CSV has no normalized column")
    missing_fields = sorted(REQUIRED - cluster_fields)
    if missing_fields:
        errors.append("clusters CSV missing columns: " + ", ".join(missing_fields))
        print("\n".join(f"ERROR: {e}" for e in errors))
        return 1

    prepared_keys = {row["normalized"] for row in prepared if row.get("normalized")}
    occurrences: defaultdict[str, list[int]] = defaultdict(list)
    groups: defaultdict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)

    for line, row in enumerate(clusters, start=2):
        key = row["normalized"]
        if not key:
            errors.append(f"line {line}: normalized is empty")
            continue
        occurrences[key].append(line)
        if row["status"] not in STATUSES:
            errors.append(f"line {line}: invalid status {row['status']!r}")
        if row["confidence"] not in CONFIDENCE:
            errors.append(f"line {line}: invalid confidence {row['confidence']!r}")
        if row["platform"] not in PLATFORMS:
            errors.append(f"line {line}: invalid platform {row['platform']!r}")
        if row["status"] == "active":
            for field in ("cluster_id", "campaign", "ad_group", "intent", "offer"):
                if not row[field]:
                    errors.append(f"line {line}: active row has empty {field}")
            if not row["landing_page"]:
                warnings.append(f"line {line}: active row has no landing_page")
            groups[(row["campaign"], row["ad_group"])].append(row)
        elif not row["reason"]:
            errors.append(f"line {line}: {row['status']} row has no reason")

    for key, lines in occurrences.items():
        if len(lines) > 1:
            errors.append(f"normalized keyword {key!r} appears on lines {lines}")
    missing = sorted(prepared_keys - set(occurrences))
    unknown = sorted(set(occurrences) - prepared_keys)
    if missing:
        errors.append(f"{len(missing)} prepared keywords are missing from clusters; examples: {missing[:5]}")
    if unknown:
        warnings.append(f"{len(unknown)} cluster keywords are absent from prepared; examples: {unknown[:5]}")

    for (campaign, ad_group), rows in groups.items():
        landings = {row["landing_page"] for row in rows if row["landing_page"]}
        offers = {row["offer"] for row in rows if row["offer"]}
        intents = {row["intent"] for row in rows if row["intent"]}
        label = f"{campaign} / {ad_group}"
        if len(landings) > 1:
            errors.append(f"group {label!r} has multiple landing pages: {sorted(landings)}")
        if len(offers) > 1:
            warnings.append(f"group {label!r} has multiple offers: {sorted(offers)}")
        if len(intents) > 1:
            warnings.append(f"group {label!r} mixes intents: {sorted(intents)}")
        if len(rows) > 30:
            warnings.append(f"group {label!r} has {len(rows)} active keywords; recheck message homogeneity")

    print(f"prepared={len(prepared_keys)} clustered={len(occurrences)} active_groups={len(groups)} errors={len(errors)} warnings={len(warnings)}")
    for message in errors:
        print(f"ERROR: {message}")
    for message in warnings:
        print(f"WARNING: {message}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

