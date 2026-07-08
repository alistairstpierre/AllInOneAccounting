# export_century_6788_expenses.py — Writes CSV exports of transactions assigned to the
# "Century" entity on card *6788 from storage/transactions + storage/entities.json.
# Run from repo root after assignments are saved. Outputs land in storage/.

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent
ENTITIES = REPO / "storage" / "entities.json"
JOINT_CC = REPO / "storage" / "transactions" / "Alistair & Phoebe Joint Credit Card.json"
OUT_DIR = REPO / "storage"
ENTITY_NAME = "Century"
CARD_SUFFIX = "6788"


def canon_tx_id(tx_id: str) -> str:
    """Align entity.json keys (9554XXXXXXXX6788) with transaction id suffixes."""
    return (
        tx_id.replace("9554XXXXXXXX6788", "9554-XXXX-XXXX-6788")
        .replace("9554xxxxxxxx6788", "9554-XXXX-XXXX-6788")
    )


def parse_iso(d: str) -> date:
    y, m, day = map(int, d.split("-"))
    return date(y, m, day)


def in_half_open(d: date, start: date, end: date) -> bool:
    return start <= d < end


@dataclass(frozen=True)
class ExportWindow:
    label: str
    start: date
    end: date
    filename: str


WINDOWS = (
    ExportWindow(
        "2024-05-01 → 2025-05-01",
        date(2024, 5, 1),
        date(2025, 5, 1),
        "century_credit_6788_expenses_2024-05-01_to_2025-05-01.csv",
    ),
    ExportWindow(
        "2025-05-01 → 2026-05-01",
        date(2025, 5, 1),
        date(2026, 5, 1),
        "century_credit_6788_expenses_2025-05-01_to_2026-05-01.csv",
    ),
)

CSV_FIELDS = [
    "transaction_date",
    "amount",
    "merchant",
    "category",
    "account",
    "card",
]


def main() -> None:
    entities = json.loads(ENTITIES.read_text(encoding="utf-8"))
    century = next(e for e in entities if e.get("name") == ENTITY_NAME)
    century_ids = {canon_tx_id(tid) for tid in century["transactions"]}

    txs = json.loads(JOINT_CC.read_text(encoding="utf-8"))
    pool = [
        t
        for t in txs
        if (t.get("account") or "").endswith(CARD_SUFFIX)
        and canon_tx_id(t["id"]) in century_ids
    ]
    pool.sort(key=lambda t: (t["transaction_date"], t["id"]))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for w in WINDOWS:
        rows = [
            {k: t.get(k, "") for k in CSV_FIELDS}
            for t in pool
            if in_half_open(parse_iso(t["transaction_date"]), w.start, w.end)
        ]
        out = OUT_DIR / w.filename
        with out.open("w", newline="", encoding="utf-8") as f:
            wtr = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            wtr.writeheader()
            wtr.writerows(rows)
        print(f"{w.label}: {len(rows)} row(s) -> {out.relative_to(REPO)}")


if __name__ == "__main__":
    main()
