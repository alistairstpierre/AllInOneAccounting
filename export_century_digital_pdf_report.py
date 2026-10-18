# export_century_digital_pdf_report.py — Builds a formatted PDF of Century Digital
# Main Account activity for a date range: income vs expenses, expenses grouped by
# category. Reads storage/transactions/Century Digital Main Account.json and writes
# under storage/. Used for period summaries (e.g. May–Sep 2026).

"""
Usage (PowerShell):
  python3 export_century_digital_pdf_report.py
  python3 export_century_digital_pdf_report.py --start 2026-05-01 --end 2026-09-30
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable,
    PageBreak,
)

REPO = Path(__file__).resolve().parent
TXN_FILE = REPO / "storage" / "transactions" / "Century Digital Main Account.json"
OUT_DIR = REPO / "storage"

INK = colors.HexColor("#1a2332")
MUTED = colors.HexColor("#5a6570")
LINE = colors.HexColor("#d8dde3")
GREEN = colors.HexColor("#1b7a4e")
RED = colors.HexColor("#9b2c2c")
HEADER_BG = colors.HexColor("#243447")
ROW_ALT = colors.HexColor("#f4f6f8")
SECTION_BG = colors.HexColor("#e8eef5")


def parse_iso(d: str) -> date:
    return date.fromisoformat(d)


def money(amount: float) -> str:
    return f"${amount:,.2f}"


def load_period(
    start: date, end: date
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    txns = json.loads(TXN_FILE.read_text(encoding="utf-8"))
    period = []
    for t in txns:
        raw = (t.get("transaction_date") or "").strip()
        if not raw:
            continue
        try:
            d = parse_iso(raw)
        except ValueError:
            continue
        if start <= d <= end:
            period.append(t)
    income = [
        t
        for t in period
        if t.get("is_credit") and not t.get("is_transfer")
    ]
    expenses = [
        t
        for t in period
        if not t.get("is_credit") and not t.get("is_transfer")
    ]
    transfers = [t for t in period if t.get("is_transfer")]
    income.sort(key=lambda t: (t["transaction_date"], t.get("merchant") or ""))
    expenses.sort(key=lambda t: (t["transaction_date"], t.get("merchant") or ""))
    return income, expenses, transfers


def build_styles():
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "TitleCustom",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=20,
            textColor=INK,
            spaceAfter=4,
            alignment=TA_CENTER,
        ),
        "subtitle": ParagraphStyle(
            "SubtitleCustom",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=11,
            textColor=MUTED,
            spaceAfter=16,
            alignment=TA_CENTER,
        ),
        "h2": ParagraphStyle(
            "H2Custom",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=INK,
            spaceBefore=14,
            spaceAfter=8,
        ),
        "body": ParagraphStyle(
            "BodyCustom",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=INK,
            leading=12,
        ),
        "muted": ParagraphStyle(
            "MutedCustom",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=MUTED,
            leading=10,
        ),
        "cell": ParagraphStyle(
            "CellCustom",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=INK,
            leading=10,
        ),
        "cell_right": ParagraphStyle(
            "CellRightCustom",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=INK,
            alignment=TA_RIGHT,
            leading=10,
        ),
        "cell_bold": ParagraphStyle(
            "CellBoldCustom",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=INK,
            leading=10,
        ),
        "cell_header": ParagraphStyle(
            "CellHeaderCustom",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=colors.white,
            leading=10,
        ),
        "cell_header_right": ParagraphStyle(
            "CellHeaderRightCustom",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=colors.white,
            alignment=TA_RIGHT,
            leading=10,
        ),
        "footer": ParagraphStyle(
            "FooterCustom",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
    }
    return styles


def summary_table(income_total: float, expense_total: float, styles) -> Table:
    net = income_total - expense_total
    net_color = GREEN if net >= 0 else RED
    data = [
        [
            Paragraph("<b>Total income</b>", styles["cell"]),
            Paragraph(f'<font color="{GREEN.hexval()}">{money(income_total)}</font>', styles["cell_right"]),
        ],
        [
            Paragraph("<b>Total expenses</b>", styles["cell"]),
            Paragraph(f'<font color="{RED.hexval()}">{money(expense_total)}</font>', styles["cell_right"]),
        ],
        [
            Paragraph("<b>Net (income − expenses)</b>", styles["cell_bold"]),
            Paragraph(
                f'<font color="{net_color.hexval()}"><b>{money(net)}</b></font>',
                styles["cell_right"],
            ),
        ],
    ]
    table = Table(data, colWidths=[120 * mm, 50 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SECTION_BG),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("LINEABOVE", (0, 2), (-1, 2), 1, INK),
            ]
        )
    )
    return table


def category_summary_table(
    by_category: List[Tuple[str, float, int]], expense_total: float, styles
) -> Table:
    header = [
        Paragraph("Category", styles["cell_header"]),
        Paragraph("Transactions", styles["cell_header_right"]),
        Paragraph("Amount", styles["cell_header_right"]),
        Paragraph("% of expenses", styles["cell_header_right"]),
    ]
    rows = [header]
    for cat, total, count in by_category:
        pct = (total / expense_total * 100) if expense_total else 0
        rows.append(
            [
                Paragraph(cat, styles["cell"]),
                Paragraph(str(count), styles["cell_right"]),
                Paragraph(money(total), styles["cell_right"]),
                Paragraph(f"{pct:.1f}%", styles["cell_right"]),
            ]
        )
    rows.append(
        [
            Paragraph("<b>Total expenses</b>", styles["cell_bold"]),
            Paragraph(f"<b>{sum(c for _, _, c in by_category)}</b>", styles["cell_right"]),
            Paragraph(f"<b>{money(expense_total)}</b>", styles["cell_right"]),
            Paragraph("<b>100%</b>", styles["cell_right"]),
        ]
    )
    table = Table(rows, colWidths=[75 * mm, 30 * mm, 35 * mm, 30 * mm])
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("BACKGROUND", (0, -1), (-1, -1), SECTION_BG),
    ]
    for i in range(1, len(rows) - 1):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), ROW_ALT))
    # Fix header text color for Paragraphs inside — set white via rebuilding header
    table.setStyle(TableStyle(style_cmds))
    return table


def txn_table(rows_data: List[List[Any]], styles, amount_color=None) -> Table:
    header = [
        Paragraph("Date", styles["cell_header"]),
        Paragraph("Merchant", styles["cell_header"]),
        Paragraph("Amount", styles["cell_header_right"]),
    ]
    rows = [header]
    for d, merchant, amount in rows_data:
        amt_para = Paragraph(money(amount), styles["cell_right"])
        if amount_color:
            amt_para = Paragraph(
                f'<font color="{amount_color.hexval()}">{money(amount)}</font>',
                styles["cell_right"],
            )
        rows.append(
            [
                Paragraph(d, styles["cell"]),
                Paragraph(merchant or "—", styles["cell"]),
                amt_para,
            ]
        )
    table = Table(rows, colWidths=[28 * mm, 107 * mm, 35 * mm])
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("BOX", (0, 0), (-1, -1), 0.4, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    for i in range(1, len(rows)):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), ROW_ALT))
    table.setStyle(TableStyle(style_cmds))
    return table


def add_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawCentredString(
        A4[0] / 2,
        12 * mm,
        f"Century Digital · Page {doc.page}",
    )
    canvas.restoreState()


def build_pdf(start: date, end: date, out_path: Path) -> Path:
    income, expenses, transfers = load_period(start, end)
    styles = build_styles()

    income_total = sum(float(t["amount"]) for t in income)
    expense_total = sum(float(t["amount"]) for t in expenses)

    by_cat: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for t in expenses:
        by_cat[t.get("category") or "Uncategorized"].append(t)

    category_totals = sorted(
        (
            (cat, sum(float(t["amount"]) for t in items), len(items))
            for cat, items in by_cat.items()
        ),
        key=lambda x: -x[1],
    )

    # Income by merchant
    income_by_merchant: Dict[str, float] = defaultdict(float)
    income_count: Dict[str, int] = defaultdict(int)
    for t in income:
        name = t.get("identified_business") or t.get("merchant") or "Unknown"
        income_by_merchant[name] += float(t["amount"])
        income_count[name] += 1
    income_merchants = sorted(income_by_merchant.items(), key=lambda x: -x[1])

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title=f"Century Digital {start.isoformat()} to {end.isoformat()}",
        author="BudgetOptimizer",
    )

    story: List[Any] = []
    story.append(Paragraph("Century Digital", styles["title"]))
    story.append(
        Paragraph(
            f"Financial summary · {start.strftime('%d %b %Y')} – {end.strftime('%d %b %Y')}",
            styles["subtitle"],
        )
    )
    story.append(
        Paragraph(
            f"Source: Century Digital Main Account · Generated {datetime.now().strftime('%d %b %Y %H:%M')}",
            styles["muted"],
        )
    )
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width="100%", thickness=1, color=INK, spaceAfter=8))

    story.append(Paragraph("Overview", styles["h2"]))
    story.append(summary_table(income_total, expense_total, styles))
    story.append(Spacer(1, 3 * mm))
    story.append(
        Paragraph(
            f"{len(income)} income transactions · {len(expenses)} expense transactions"
            + (f" · {len(transfers)} transfers excluded from totals" if transfers else ""),
            styles["muted"],
        )
    )

    # Income section
    story.append(Paragraph("Income", styles["h2"]))
    story.append(
        Paragraph(
            f"Total income: <b><font color=\"{GREEN.hexval()}\">{money(income_total)}</font></b>",
            styles["body"],
        )
    )
    story.append(Spacer(1, 2 * mm))
    if income_merchants:
        story.append(Paragraph("By source", styles["muted"]))
        story.append(Spacer(1, 1 * mm))
        src_header = [
            Paragraph("Source", styles["cell_header"]),
            Paragraph("Count", styles["cell_header_right"]),
            Paragraph("Amount", styles["cell_header_right"]),
        ]
        src_rows = [src_header]
        for name, total in income_merchants:
            src_rows.append(
                [
                    Paragraph(name, styles["cell"]),
                    Paragraph(str(income_count[name]), styles["cell_right"]),
                    Paragraph(
                        f'<font color="{GREEN.hexval()}">{money(total)}</font>',
                        styles["cell_right"],
                    ),
                ]
            )
        src_table = Table(src_rows, colWidths=[110 * mm, 25 * mm, 35 * mm])
        src_style = [
            ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
            ("BOX", (0, 0), (-1, -1), 0.4, LINE),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, LINE),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]
        for i in range(1, len(src_rows)):
            if i % 2 == 0:
                src_style.append(("BACKGROUND", (0, i), (-1, i), ROW_ALT))
        src_table.setStyle(TableStyle(src_style))
        story.append(src_table)

    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("Income transactions", styles["muted"]))
    story.append(Spacer(1, 1 * mm))
    income_rows = [
        (
            t["transaction_date"],
            t.get("identified_business") or t.get("merchant") or "—",
            float(t["amount"]),
        )
        for t in income
    ]
    if income_rows:
        story.append(txn_table(income_rows, styles, amount_color=GREEN))

    # Expenses overview
    story.append(PageBreak())
    story.append(Paragraph("Expenses by category", styles["h2"]))
    story.append(
        Paragraph(
            f"Total expenses: <b><font color=\"{RED.hexval()}\">{money(expense_total)}</font></b>",
            styles["body"],
        )
    )
    story.append(Spacer(1, 3 * mm))
    if category_totals:
        story.append(category_summary_table(category_totals, expense_total, styles))

    # Detail by category
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Expense detail by category", styles["h2"]))
    for cat, total, count in category_totals:
        items = sorted(
            by_cat[cat],
            key=lambda t: (t["transaction_date"], t.get("merchant") or ""),
        )
        block = [
            Paragraph(
                f"{cat} · {count} transactions · <font color=\"{RED.hexval()}\">{money(total)}</font>",
                styles["h2"],
            ),
            txn_table(
                [
                    (
                        t["transaction_date"],
                        t.get("identified_business") or t.get("merchant") or "—",
                        float(t["amount"]),
                    )
                    for t in items
                ],
                styles,
                amount_color=RED,
            ),
            Spacer(1, 3 * mm),
        ]
        story.append(KeepTogether(block))

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export Century Digital Main Account income/expense PDF report."
    )
    parser.add_argument("--start", default="2026-05-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default="2026-09-30", help="End date YYYY-MM-DD")
    parser.add_argument(
        "--out",
        default="",
        help="Output PDF path (default: storage/century_digital_YYYY-MM-DD_to_YYYY-MM-DD.pdf)",
    )
    args = parser.parse_args()

    start = parse_iso(args.start)
    end = parse_iso(args.end)
    if end < start:
        raise SystemExit("End date must be on or after start date.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out) if args.out else (
        OUT_DIR / f"century_digital_{start.isoformat()}_to_{end.isoformat()}.pdf"
    )

    path = build_pdf(start, end, out_path)
    income, expenses, _ = load_period(start, end)
    print(f"Wrote {path}")
    print(f"  Income:   {len(income)} txns  {money(sum(float(t['amount']) for t in income))}")
    print(f"  Expenses: {len(expenses)} txns  {money(sum(float(t['amount']) for t in expenses))}")


if __name__ == "__main__":
    main()
