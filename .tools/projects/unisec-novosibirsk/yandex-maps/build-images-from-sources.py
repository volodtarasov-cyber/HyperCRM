from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path


CLIENT_DIR = Path(__file__).resolve().parents[4] / "clients" / "unisec-novosibirsk"
ASSET_DIR = CLIENT_DIR / "assets" / "yandex-maps-services"
SOURCE_DIR = ASSET_DIR / "source"
SERVICE_CSV = CLIENT_DIR / "yandex-maps-services-working.csv"
FILENAME_CSV = CLIENT_DIR / "yandex-maps-image-filenames.csv"
BUILDER = Path(__file__).resolve().parent / "build-service-image.py"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def unique_keywords(*groups: str) -> str:
    result: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group.split(";"):
            value = item.strip()
            normalized = value.casefold()
            if value and normalized not in seen:
                seen.add(normalized)
                result.append(value)
    return "; ".join(result)


def main() -> None:
    services = {
        row["primary_keyword"].casefold(): row
        for row in read_rows(SERVICE_CSV)
        if row["status"] == "publish"
    }

    built = 0
    skipped: list[str] = []
    for mapping in read_rows(FILENAME_CSV):
        keyword = mapping["primary_keyword"]
        filename = mapping["image_filename"]
        row = services[keyword.casefold()]
        source = SOURCE_DIR / f"{Path(filename).stem}_source.png"
        if not source.exists():
            skipped.append(source.name)
            continue

        title = keyword[:1].upper() + keyword[1:]
        keywords = unique_keywords(
            keyword,
            row["supporting_keywords"],
            "UNISEC; Новосибирск",
        )
        subprocess.run(
            [
                sys.executable,
                str(BUILDER),
                str(source),
                str(ASSET_DIR / filename),
                "--title",
                title,
                "--description",
                row["description"],
                "--keywords",
                keywords,
            ],
            check=True,
        )
        built += 1

    print(f"Built: {built}")
    print(f"Skipped without source: {len(skipped)}")
    for name in skipped:
        print(name)


if __name__ == "__main__":
    main()
