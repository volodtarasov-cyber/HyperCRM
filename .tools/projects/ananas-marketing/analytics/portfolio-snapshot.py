#!/usr/bin/env python3
"""Срез чеков из read-only выгрузки Sheets; не считает их фактической выручкой.

Вход: JSON {checked, sheets: [{spreadsheet_id, sheet, data}]}.
Таблица оплат: A — клиент, K — сколько оплатил, M — общий месячный чек.
В подсчёт входят только именованные строки с числовым чеком. Безымянные
подытоги и новые клиенты ниже итога обрабатываются без двойного счёта.
Сырьё и результат хранить в игнорируемой .tools/snapshots/.
"""

import argparse
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

PAYMENTS_ID = "10xd7G1w6T9xBIVoyc5fE8WUFnK6ntqhu_WrmWM2TaBA"
OWNERS_ID = "1i_n6AIgoGdGdafu9grvu03C9ZJjP37J4l5NC-JLx8mA"


def cell(row, index):
    return str(row[index]).strip() if len(row) > index else ""


def number(value):
    value = value.replace(" ", "").replace("\u00a0", "").replace(",", ".")
    return Decimal(value) if re.fullmatch(r"-?\d+(?:\.\d+)?", value) else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    source = json.loads(args.source.read_text(encoding="utf-8-sig"))
    payments = next(s for s in source["sheets"] if s["spreadsheet_id"] == PAYMENTS_ID)
    owners = next(s for s in source["sheets"] if s["spreadsheet_id"] == OWNERS_ID)
    clients, unnamed = [], []
    for index, row in enumerate(payments["data"], 1):
        name, fee = cell(row, 0), number(cell(row, 12))
        if fee is None:
            continue
        if not name:
            unnamed.append({"row": index, "amount": str(fee)})
            continue
        paid = number(cell(row, 10))
        clients.append({"row": index, "client": name, "fee": str(fee),
                        "paid_cell": str(paid) if paid is not None else None})
    names = [c["client"].casefold() for c in clients]
    if len(names) != len(set(names)):
        raise ValueError("Повтор клиентского имени: нужно проверить группировку строк")
    total = sum((Decimal(c["fee"]) for c in clients), Decimal(0))
    positive = [c for c in clients if Decimal(c["fee"]) > 0]
    average = total / len(positive) if positive else Decimal(0)
    paid = sum((Decimal(c["paid_cell"]) for c in clients if c["paid_cell"] is not None), Decimal(0))
    owner_count = sum(bool(re.fullmatch(r"\d+", cell(r, 0))) for r in owners["data"])
    result = {
        "checked": source["checked"], "sheet": payments["sheet"],
        "contract_clients": len(positive), "owner_clients": owner_count,
        "monthly_fees": str(total),
        "average_fee": str(average.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        "recorded_paid_cells": str(paid),
        "gap_to_million_fees": str(Decimal(1_000_000) - total),
        "unnamed_amounts_excluded": unnamed, "clients": clients,
        "note": "Чеки — договорная база; пустая ячейка оплаты не означает неоплату. Заполненные оплаты не равны закрытому P&L."
    }
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    summary = {k: v for k, v in result.items() if k != "clients"}
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
