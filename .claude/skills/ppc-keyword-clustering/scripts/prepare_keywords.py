#!/usr/bin/env python3
"""Normalize and deduplicate PPC keywords from CSV, TSV, TXT, or XLSX.

The script preserves the first source wording, removes match-type wrappers only
for the normalized key, aggregates factual performance metrics, and emits a
stable CSV for semantic clustering. It does not make clustering decisions.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
import zipfile
from collections import OrderedDict
from pathlib import Path
from xml.etree import ElementTree as ET


KEYWORD_HEADERS = {
    "keyword", "keywords", "query", "search term", "search_term",
    "ключ", "ключи", "ключевая фраза", "поисковый запрос", "запрос", "фраза",
    "наименование услуги",
}

METRIC_HEADERS = {
    "frequency": {"frequency", "freq", "частотность", "wordstat", "частота", "ws"},
    "exact_frequency": {"exact frequency", "exact_frequency", "точная частотность", "[!ws]", "!ws"},
    "impressions": {"impressions", "impr", "показы", "показов"},
    "clicks": {"clicks", "клики", "кликов"},
    "cost": {"cost", "spend", "расход", "затраты", "стоимость"},
    "conversions": {"conversions", "conv", "конверсии", "конверсий"},
}


def header_key(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower().replace("ё", "е"))


def normalize_keyword(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower().replace("ё", "е")
    for left, right in (("[", "]"), ('"', '"'), ("'", "'")):
        if len(text) >= 2 and text.startswith(left) and text.endswith(right):
            text = text[1:-1].strip()
            break
    text = re.sub(r"(?<!\S)[+!]", "", text)
    text = re.sub(r"\s+", " ", text).strip(" ,;\t")
    return text


def number(value: str) -> float | None:
    text = str(value or "").strip().replace("\u00a0", "").replace(" ", "")
    text = re.sub(r"[₽$€%]", "", text)
    if not text:
        return None
    if text.count(",") == 1 and text.count(".") == 0:
        text = text.replace(",", ".")
    else:
        text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def column_index(cell_ref: str) -> int:
    letters = re.match(r"[A-Z]+", cell_ref or "")
    if not letters:
        return 0
    result = 0
    for char in letters.group(0):
        result = result * 26 + ord(char) - 64
    return result - 1


def xlsx_rows(path: Path, sheet_name: str | None) -> list[list[str]]:
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rel_ns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
    office_rel = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"

    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for si in root.findall("x:si", ns):
                shared.append("".join(t.text or "" for t in si.findall(".//x:t", ns)))

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {rel.attrib["Id"]: rel.attrib["Target"] for rel in relationships.findall("r:Relationship", rel_ns)}
        sheets = workbook.findall("x:sheets/x:sheet", ns)
        if not sheets:
            return []
        selected = next((s for s in sheets if s.attrib.get("name") == sheet_name), None) if sheet_name else sheets[0]
        if selected is None:
            names = ", ".join(s.attrib.get("name", "") for s in sheets)
            raise ValueError(f"sheet not found: {sheet_name}; available: {names}")
        target = targets[selected.attrib[office_rel]].replace("\\", "/")
        sheet_path = target.lstrip("/") if target.startswith("/xl/") else f"xl/{target.lstrip('/')}"
        sheet = ET.fromstring(archive.read(sheet_path))

        result: list[list[str]] = []
        for row in sheet.findall(".//x:sheetData/x:row", ns):
            values: dict[int, str] = {}
            for cell in row.findall("x:c", ns):
                idx = column_index(cell.attrib.get("r", ""))
                cell_type = cell.attrib.get("t")
                if cell_type == "inlineStr":
                    value = "".join(t.text or "" for t in cell.findall(".//x:t", ns))
                else:
                    raw = cell.findtext("x:v", default="", namespaces=ns)
                    value = shared[int(raw)] if cell_type == "s" and raw else raw
                values[idx] = value
            if values:
                width = max(values) + 1
                result.append([values.get(i, "") for i in range(width)])
        return result


def delimited_rows(path: Path) -> list[list[str]]:
    data = None
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            data = path.read_text(encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    if data is None:
        raise UnicodeError("cannot decode input as UTF-8 or CP1251")
    if path.suffix.lower() == ".txt" and not any(ch in data.partition("\n")[0] for ch in ",;\t"):
        return [[line.strip()] for line in data.splitlines() if line.strip()]
    try:
        dialect = csv.Sniffer().sniff(data[:4096], delimiters=",;\t")
        return list(csv.reader(data.splitlines(), dialect))
    except csv.Error:
        return [[line.strip()] for line in data.splitlines() if line.strip()]


def find_header(rows: list[list[str]], explicit_keyword: str | None) -> tuple[int | None, int, dict[str, int]]:
    explicit = header_key(explicit_keyword) if explicit_keyword else None
    for row_index, row in enumerate(rows[:30]):
        normalized = [header_key(v) for v in row]
        target = explicit if explicit and explicit in normalized else next((h for h in normalized if h in KEYWORD_HEADERS), None)
        if target:
            keyword_index = normalized.index(target)
            metrics = {}
            for canonical, aliases in METRIC_HEADERS.items():
                match = next((i for i, value in enumerate(normalized) if value in aliases), None)
                if match is not None:
                    metrics[canonical] = match
            return row_index, keyword_index, metrics
    return None, 0, {}


def cell(row: list[str], index: int | None) -> str:
    return row[index] if index is not None and index < len(row) else ""


def prepare(rows: list[list[str]], keyword_column: str | None) -> list[dict[str, object]]:
    header_row, keyword_index, metric_indexes = find_header(rows, keyword_column)
    start = header_row + 1 if header_row is not None else 0
    records: OrderedDict[str, dict[str, object]] = OrderedDict()

    for row_number, row in enumerate(rows[start:], start=start + 1):
        raw = cell(row, keyword_index).strip()
        normalized = normalize_keyword(raw)
        if not normalized:
            continue
        record = records.get(normalized)
        if record is None:
            record = {
                "keyword": raw,
                "normalized": normalized,
                "frequency": None,
                "exact_frequency": None,
                "impressions": 0.0,
                "clicks": 0.0,
                "cost": 0.0,
                "conversions": 0.0,
                "source_rows": [],
                "duplicate_count": 0,
            }
            records[normalized] = record
        record["duplicate_count"] = int(record["duplicate_count"]) + 1
        record["source_rows"].append(str(row_number))
        for metric, index in metric_indexes.items():
            value = number(cell(row, index))
            if value is None:
                continue
            if metric in {"frequency", "exact_frequency"}:
                current = record[metric]
                record[metric] = value if current is None else max(float(current), value)
            else:
                record[metric] = float(record[metric]) + value

    return list(records.values())


def display_number(value: object) -> str:
    if value is None:
        return ""
    numeric = float(value)
    return str(int(numeric)) if numeric.is_integer() else f"{numeric:.4f}".rstrip("0").rstrip(".")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="CSV, TSV, TXT, or XLSX source")
    parser.add_argument("--output", required=True, help="Prepared CSV path")
    parser.add_argument("--keyword-column", help="Exact source header when auto-detection fails")
    parser.add_argument("--sheet", help="XLSX sheet name; defaults to first sheet")
    args = parser.parse_args()

    source = Path(args.input)
    if not source.exists():
        print(f"error: input not found: {source}", file=sys.stderr)
        return 2
    try:
        rows = xlsx_rows(source, args.sheet) if source.suffix.lower() == ".xlsx" else delimited_rows(source)
        records = prepare(rows, args.keyword_column)
    except (OSError, ValueError, UnicodeError, zipfile.BadZipFile) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not records:
        print("error: no keywords found; specify --keyword-column if the file has headers", file=sys.stderr)
        return 2

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["keyword", "normalized", "frequency", "exact_frequency", "impressions", "clicks", "cost", "conversions", "source_rows", "duplicate_count"]
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            row = dict(record)
            for metric in ("frequency", "exact_frequency", "impressions", "clicks", "cost", "conversions"):
                row[metric] = display_number(row[metric])
            row["source_rows"] = ";".join(row["source_rows"])
            writer.writerow(row)

    detected_header, _, _ = find_header(rows, args.keyword_column)
    data_start = detected_header + 1 if detected_header is not None else 0
    summary = {
        "source_rows": max(0, len(rows) - data_start),
        "unique_keywords": len(records),
        "duplicates_merged": sum(int(r["duplicate_count"]) - 1 for r in records),
        "output": str(output),
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

