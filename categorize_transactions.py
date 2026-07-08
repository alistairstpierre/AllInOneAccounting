#!/usr/bin/env python3
"""
Transaction Processor (simplified).

Single responsibility: go through data (CSVs), and for each transaction:
- If it already exists in storage → skip (same id; duplicate same-day/same-merchant/same-amount rows get ids `_dup2`, `_dup3`, …).
- If it doesn't exist:
  - If storage has a transaction with the same merchant name → copy that transaction's
    category and related attributes.
  - Otherwise → run the transaction through the LLM to categorize and fill attributes.
Then write updated transactions to storage.
"""

import json
import re
import csv
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from get_account_type import get_account_type, is_business_account
import os
import hashlib

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# OpenAI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY')) if os.getenv('OPENAI_API_KEY') else None
except Exception:
    OPENAI_AVAILABLE = False
    openai_client = None

# Category sets (match web/app/lib/categories.ts)
PERSONAL_CATEGORIES = [
    'Housing', 'Transportation', 'Groceries', 'Dining & Takeout', 'Medical & Healthcare',
    'Fitness & Wellness', 'Personal Care & Grooming', 'Entertainment', 'Shopping',
    'Insurance', 'Savings/Investing', 'Debt Payment', 'Education', 'Travel',
    'Gifts & Donations', 'Professional Services', 'Uncategorized',
]
BUSINESS_CATEGORIES = [
    'Office Supplies', 'Software/Subscriptions', 'Marketing/Advertising', 'Professional Services',
    'Travel', 'Meals/Entertainment', 'Equipment', 'Rent/Utilities', 'Insurance',
    'Education/Training', 'Transportation', 'Legal/Accounting', 'Telecommunications',
    'Bank Fees', 'Uncategorized',
]


def parse_csv_date(date_str: str) -> str:
    """Convert CSV date (DD/MM/YYYY) to YYYY-MM-DD."""
    try:
        parts = date_str.split('/')
        if len(parts) == 3:
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
    except Exception:
        pass
    return date_str


def sanitize_account_id(account_id: str) -> str:
    return account_id.replace('*', 'X')


def normalize_merchant_name(merchant: str) -> str:
    normalized = (merchant or '').strip().lower()
    return re.sub(r'\s+', ' ', normalized)


def normalize_optional_text(value: Optional[str]) -> str:
    """Normalize optional string values for stable duplicate detection."""
    return (value or '').strip()


def build_transaction_fingerprint(txn: Dict[str, Any]) -> str:
    """
    Build a fingerprint for overlap detection across files.
    Includes processed_date to avoid collapsing legitimately separate charges that
    happen to share transaction_date/amount/merchant/card.
    """
    parts = [
        str(txn.get('transaction_date', '')).strip(),
        str(round(float(txn.get('amount', 0.0) or 0.0), 2)),
        normalize_merchant_name(str(txn.get('merchant', ''))),
        normalize_optional_text(txn.get('card')),
        normalize_optional_text(txn.get('reference')),
        normalize_optional_text(txn.get('code')),
        str(txn.get('processed_date') or txn.get('transaction_date') or '').strip(),
    ]
    return '|'.join(parts)


def generate_transaction_id(
    account_id: str,
    transaction_date: str,
    amount: float,
    merchant: str,
    card: Optional[str] = None,
    reference: Optional[str] = None,
    code: Optional[str] = None,
) -> str:
    """Stable ID from composite key so 'already in storage' is well-defined."""
    key_parts = [
        account_id,
        transaction_date,
        str(round(amount, 2)),
        normalize_merchant_name(merchant),
    ]
    if card:
        key_parts.append(card.strip())
    if reference:
        key_parts.append(reference.strip())
    if code:
        key_parts.append(code.strip())
    composite = '|'.join(key_parts)
    h = hashlib.sha256(composite.encode('utf-8')).hexdigest()[:16]
    return f"{h}_{sanitize_account_id(account_id)}"


def parse_csv_file(csv_path: Path, account_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Parse one CSV. Supports:
    - Credit card: Card, Type, Amount, Details, TransactionDate, ProcessedDate
    - Checking: Type, Details, Particulars, Code, Reference, Amount, Date, ...
    """
    transactions = []
    try:
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            first_line = f.readline().strip()
            f.seek(0)
            reader = csv.DictReader(f)
            has_card = 'Card' in (reader.fieldnames or [])
            is_credit_card = account_type == 'CREDITCARD' or (account_type is None and has_card)

            if is_credit_card:
                for row in reader:
                    if (row.get('Type', '').strip().upper()) == 'C':
                        continue
                    card = row.get('Card', '').strip()
                    details = row.get('Details', '').strip()
                    try:
                        amount_float = float(row.get('Amount', '') or 0)
                    except ValueError:
                        amount_float = 0.0
                    transactions.append({
                        'card': card or None,
                        'amount': abs(amount_float),
                        'merchant': details,
                        'transaction_date': parse_csv_date(row.get('TransactionDate', '')),
                        'processed_date': parse_csv_date(row.get('ProcessedDate', '')) or None,
                        'is_transfer': False,
                        'is_credit': False,
                        'transaction_context': {'details': details, 'particulars': '', 'code': '', 'reference': ''},
                    })
            else:
                for row in reader:
                    transaction_type = (row.get('Type', '') or '').strip()
                    details = (row.get('Details', '') or '').strip()
                    particulars = (row.get('Particulars', '') or '').strip()
                    code = (row.get('Code', '') or '').strip()
                    reference = (row.get('Reference', '') or '').strip()
                    try:
                        amount_float = float(row.get('Amount', '') or 0)
                    except ValueError:
                        amount_float = 0.0
                    date_str = (row.get('Date', '') or '').strip()
                    is_transfer_txn = transaction_type.upper() == 'TRANSFER'
                    # Checking CSV: positive amount = money in (credit), negative = money out (debit/expense)
                    is_credit = amount_float > 0

                    merchant = details
                    card_number = None
                    if transaction_type.upper() == 'VISA PURCHASE':
                        card_match = re.search(r'(\d{4}-\*{4}-\*{4}-\d{4})', details)
                        card_number = card_match.group(1) if card_match else None
                        if code and code.strip():
                            merchant = code.strip()
                        elif particulars and particulars.strip():
                            try:
                                float(particulars.strip())
                                merchant = code.strip() if code and code.strip() else details
                                if card_number and merchant.startswith(card_number):
                                    merchant = merchant.replace(card_number, '', 1).strip()
                            except ValueError:
                                merchant = particulars.strip()
                        else:
                            merchant = details
                            if card_number and merchant.startswith(card_number):
                                merchant = merchant.replace(card_number, '', 1).strip()
                    else:
                        merchant = details or particulars
                        card_match = re.search(r'(\d{4}-\*{4}-\*{4}-\d{4})', details)
                        if card_match:
                            card_number = card_match.group(1)

                    transactions.append({
                        'card': card_number,
                        'amount': abs(amount_float),
                        'merchant': (merchant or '').strip(),
                        'transaction_date': parse_csv_date(date_str),
                        'processed_date': parse_csv_date(date_str),
                        'reference': reference or None,
                        'code': code or None,
                        'foreign_currency': (row.get('ForeignCurrencyAmount', '') or '').strip() or None,
                        'is_transfer': is_transfer_txn,
                        'is_credit': is_credit,
                        'transaction_context': {
                            'details': details,
                            'particulars': particulars,
                            'code': code,
                            'reference': reference,
                        },
                    })
    except Exception as e:
        print(f"  Error parsing {csv_path.name}: {e}")
    return transactions


def load_prompt_template(prompt_file: Path) -> str:
    if not prompt_file.exists():
        return ""
    try:
        return prompt_file.read_text(encoding='utf-8')
    except Exception as e:
        print(f"  Warning: Could not load prompt: {e}")
        return ""


def build_llm_prompt(
    merchant: str,
    amount: float,
    date: str,
    account_type: str,
    prompt_template: str,
    categories: List[str],
    transaction_context: Optional[Dict[str, Any]] = None,
) -> str:
    categories_list = '\n'.join([f"- {c}" for c in categories])
    context_info = ""
    if transaction_context:
        parts = []
        p = (transaction_context.get('particulars') or '').strip()
        if p and p != merchant:
            parts.append(f"Particulars: {p}")
        d = (transaction_context.get('details') or '').strip()
        if d and d != merchant and not re.search(r'\d{4}-\*{4}-\*{4}-\d{4}', d):
            parts.append(f"Details: {d}")
        if (transaction_context.get('code') or '').strip():
            parts.append(f"Code: {transaction_context.get('code', '').strip()}")
        if (transaction_context.get('reference') or '').strip():
            parts.append(f"Reference: {transaction_context.get('reference', '').strip()}")
        if parts:
            context_info = "\n" + "\n".join(parts) + "\n"
    return f"""{prompt_template}

## Transaction to Categorize

**This is an EXPENSE (debit/purchase) to categorize, not income.**

Merchant: {merchant}
Amount: ${abs(amount):.2f}
Date: {date}{context_info}

## Available Categories

{categories_list}

## Task

1. Identify the business name (clean the merchant name).
2. Select the most appropriate category from the list.
3. Provide brief reasoning.

Please respond in the following format:
Business Name: [cleaned business name]
Category: [category name]
Reasoning: [brief explanation]
"""


def parse_llm_response(response_text: str) -> Dict[str, Optional[str]]:
    out = {'identified_business': None, 'category': None, 'category_description': None}
    m = re.search(r'Business Name:\s*(.+?)(?:\n|$)', response_text, re.IGNORECASE)
    if m:
        out['identified_business'] = m.group(1).strip()
    m = re.search(r'Category:\s*(.+?)(?:\n|$)', response_text, re.IGNORECASE)
    if m:
        out['category'] = m.group(1).strip()
    m = re.search(r'Reasoning:\s*(.+?)(?:\n\n|```|\Z)', response_text, re.IGNORECASE | re.DOTALL)
    if m:
        out['category_description'] = re.sub(r'```\s*$', '', m.group(1).strip()).strip()
    return out


def categorize_with_llm(
    merchant: str,
    amount: float,
    date: str,
    account_type: str,
    project_root: Path,
    transaction_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Optional[str]]:
    """Call LLM once for one transaction. Returns identified_business, category, category_description."""
    if not OPENAI_AVAILABLE or not openai_client:
        return {'identified_business': None, 'category': 'Uncategorized', 'category_description': None}
    if (merchant or '').strip() == 'Account Transfer':
        return {'identified_business': 'Account Transfer', 'category': None, 'category_description': None}
    is_business = account_type == 'Business'
    prompt_file = project_root / ('business_categorization_prompt.md' if is_business else 'personal_categorization_prompt.md')
    categories = BUSINESS_CATEGORIES if is_business else PERSONAL_CATEGORIES
    template = load_prompt_template(prompt_file)
    if not template:
        return {'identified_business': None, 'category': 'Uncategorized', 'category_description': None}
    prompt = build_llm_prompt(merchant, amount, date, account_type, template, categories, transaction_context)
    try:
        response = openai_client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {"role": "system", "content": "You identify business names and categorize expenses. Respond in the exact format requested."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=600,
        )
        result = parse_llm_response(response.choices[0].message.content or '')
        if result.get('category') and result['category'] not in categories:
            result['category'] = 'Uncategorized'
        return result
    except Exception as e:
        print(f"  [LLM] Error: {e}")
        return {'identified_business': None, 'category': 'Uncategorized', 'category_description': None}


def save_json_safely(file_path: Path, data: Any) -> None:
    tmp = file_path.with_suffix('.tmp')
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        with open(tmp, 'r', encoding='utf-8') as f:
            json.load(f)
        tmp.replace(file_path)
    except Exception as e:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise e


def process_account(account_folder: Path, project_root: Path) -> None:
    """
    Single pipeline:
    - Load storage for this account.
    - Parse all CSVs under data/<AccountName>/csv/.
    - For each row: if id already in storage → skip. Else:
      - If storage has a transaction with same merchant name → copy its category/attributes.
      - Else → call LLM to categorize.
    - Merge existing + new, dedupe by id, sort by date, save.
    """
    account_name = account_folder.name
    csv_dir = account_folder / 'csv'
    if not csv_dir.exists():
        print(f"  Skip (no csv dir): {account_name}")
        return

    is_business = is_business_account(account_name, project_root)
    account_type_label = 'Business' if is_business else 'Personal'
    output_file = project_root / 'storage' / 'transactions' / f"{account_name}.json"

    # Load existing storage
    existing_list: List[Dict[str, Any]] = []
    existing_ids: set = set()
    merchant_lookup: Dict[str, Dict[str, Any]] = {}  # normalized_merchant -> category info

    if output_file.exists():
        try:
            existing_list = json.loads(output_file.read_text(encoding='utf-8'))
            for t in existing_list:
                tid = t.get('id')
                if tid:
                    existing_ids.add(tid)
                merchant = (t.get('merchant') or '').strip()
                if merchant:
                    nm = normalize_merchant_name(merchant)
                    cat = t.get('category')
                    if nm not in merchant_lookup or (cat and cat != 'Uncategorized'):
                        merchant_lookup[nm] = {
                            'category': cat or 'Uncategorized',
                            'identified_business': t.get('identified_business'),
                            'category_description': t.get('category_description'),
                            'categorized': t.get('categorized', False),
                            'categorized_at': t.get('categorized_at'),
                        }
        except Exception as e:
            print(f"  Warning loading storage: {e}")

    # Account ID for generating transaction ids
    account_id = None
    if existing_list and existing_list[0].get('account'):
        account_id = existing_list[0]['account']
    if not account_id:
        csv_files_for_id = sorted(csv_dir.glob('*.csv'))
        if csv_files_for_id:
            # Checking account: 01-0142-0771521-00 style; credit card: 9554-xxxx-xxxx-6788
            m = re.search(r'(\d{2}-\d{4}-\d{7}-\d{2})', csv_files_for_id[0].name)
            if m:
                account_id = m.group(1)
            else:
                m = re.search(r'(\d{4}-xxxx-xxxx-\d{4})', csv_files_for_id[0].name)
                account_id = m.group(1).replace('xxxx', '****') if m else account_name.replace(' ', '-')
        else:
            account_id = account_name.replace(' ', '-')

    csv_files = sorted(csv_dir.glob('*.csv'))
    if not csv_files:
        print(f"  No CSVs: {account_name}")
        return

    # Collect all rows from all CSVs (format auto-detected per file from headers)
    all_rows: List[Dict[str, Any]] = []
    for cf in csv_files:
        rows = parse_csv_file(cf)
        for r in rows:
            r['source_file'] = cf.name
            all_rows.append(r)

    if not all_rows:
        print(f"  No transactions in CSVs: {account_name}")
        return

    new_by_id: Dict[str, Dict[str, Any]] = {}
    copied = 0
    llm_count = 0

    # Track first-seen source file for each fingerprint; used to skip cross-file overlap duplicates.
    # We still preserve true duplicates inside the same source file.
    existing_fingerprint_to_source: Dict[str, str] = {}
    for t in existing_list:
        fp = build_transaction_fingerprint(t)
        src = (t.get('source_file') or '').strip()
        if fp not in existing_fingerprint_to_source:
            existing_fingerprint_to_source[fp] = src

    seen_fingerprint_to_source: Dict[str, str] = {}

    # Same base id within the same source file gets _dup2/_dup3/etc.
    occurrence_by_base_tid_and_source: Dict[tuple[str, str], int] = defaultdict(int)

    for csv_txn in all_rows:
        source_file = (csv_txn.get('source_file') or '').strip()
        fingerprint = build_transaction_fingerprint(csv_txn)

        # If the same fingerprint already exists from a different source file,
        # treat this as an overlap duplicate between CSV windows and skip it.
        existing_source = existing_fingerprint_to_source.get(fingerprint)
        if existing_source and existing_source != source_file:
            continue

        seen_source = seen_fingerprint_to_source.get(fingerprint)
        if seen_source and seen_source != source_file:
            continue

        if fingerprint not in seen_fingerprint_to_source:
            seen_fingerprint_to_source[fingerprint] = source_file

        base_tid = generate_transaction_id(
            account_id=account_id,
            transaction_date=csv_txn.get('transaction_date', ''),
            amount=csv_txn.get('amount', 0.0),
            merchant=csv_txn.get('merchant', ''),
            card=csv_txn.get('card'),
            reference=csv_txn.get('reference'),
            code=csv_txn.get('code'),
        )
        occ_key = (base_tid, source_file)
        k = occurrence_by_base_tid_and_source[occ_key]
        occurrence_by_base_tid_and_source[occ_key] += 1
        tid = base_tid if k == 0 else f"{base_tid}_dup{k + 1}"

        if tid in existing_ids or tid in new_by_id:
            continue

        is_transfer = csv_txn.get('is_transfer', False)
        is_credit = csv_txn.get('is_credit', False)
        ctx = csv_txn.get('transaction_context') or {
            'details': '', 'particulars': '', 'code': csv_txn.get('code') or '', 'reference': csv_txn.get('reference') or '',
        }

        category = None
        identified_business = None
        category_description = None
        categorized = False
        categorized_at = None

        if not is_transfer:
            nm = normalize_merchant_name(csv_txn.get('merchant', ''))
            if nm in merchant_lookup:
                info = merchant_lookup[nm]
                category = info.get('category') or 'Uncategorized'
                identified_business = info.get('identified_business')
                category_description = info.get('category_description')
                categorized = info.get('categorized', False)
                categorized_at = info.get('categorized_at')
                copied += 1
            if not category:
                result = categorize_with_llm(
                    csv_txn.get('merchant', ''),
                    csv_txn.get('amount', 0.0),
                    csv_txn.get('transaction_date', ''),
                    account_type_label,
                    project_root,
                    ctx,
                )
                identified_business = result.get('identified_business') or identified_business
                category = result.get('category') or 'Uncategorized'
                category_description = result.get('category_description') or category_description
                categorized = True
                categorized_at = datetime.now().isoformat()
                llm_count += 1
        else:
            category = 'Uncategorized'

        if not category:
            category = 'Uncategorized'

        processed = {
            'id': tid,
            'account': account_id,
            'card': csv_txn.get('card'),
            'amount': csv_txn.get('amount', 0.0),
            'merchant': (csv_txn.get('merchant') or '').strip(),
            'identified_business': identified_business,
            'transaction_date': csv_txn.get('transaction_date', ''),
            'processed_date': csv_txn.get('processed_date') or csv_txn.get('transaction_date', ''),
            'foreign_currency': csv_txn.get('foreign_currency'),
            'source_file': csv_txn.get('source_file', ''),
            'categorized': categorized,
            'category': category,
            'category_description': category_description,
            'categorized_at': categorized_at,
            'is_transfer': is_transfer,
            'is_credit': is_credit,
            'account_type': account_type_label,
            'reference': csv_txn.get('reference'),
            'code': csv_txn.get('code'),
            'transaction_context': ctx,
        }
        new_by_id[tid] = processed

    if copied:
        print(f"  [OK] Reused category for {copied} transaction(s) (same merchant name)")
    if llm_count:
        print(f"  [OK] Categorized {llm_count} transaction(s) via LLM")

    # Merge: existing + new, dedupe by id, sort by date desc
    by_id = {t.get('id'): t for t in existing_list if t.get('id')}
    for tid, t in new_by_id.items():
        by_id[tid] = t
    merged = list(by_id.values())
    for t in merged:
        if not t.get('category'):
            t['category'] = 'Uncategorized'
    merged.sort(key=lambda t: t.get('transaction_date', ''), reverse=True)

    save_json_safely(output_file, merged)
    print(f"  [OK] Saved {len(merged)} transaction(s) ({len(new_by_id)} new)")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description='Process transaction CSVs into storage')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    args = parser.parse_args()
    if args.verbose:
        os.environ['VERBOSE'] = '1'

    project_root = Path(__file__).resolve().parent
    data_dir = project_root / 'data'
    if not data_dir.exists():
        print(f"Error: {data_dir} not found")
        return
    (project_root / 'storage' / 'transactions').mkdir(parents=True, exist_ok=True)
    account_folders = sorted([d for d in data_dir.iterdir() if d.is_dir()], reverse=True)
    if not account_folders:
        print("No account folders in data/")
        return
    print("Transaction processor (data → storage, match by name or LLM)")
    print("=" * 60)
    for account_folder in account_folders:
        print(f"\nProcessing: {account_folder.name}")
        process_account(account_folder, project_root)

    # Assign transactions to entities by card (4037 → Century, 4055/4835 → Alistair, etc.)
    try:
        from assign_transactions_by_card import (
            assign_transactions_to_entities_by_card,
            load_all_transactions,
        )
        all_txns = load_all_transactions(project_root)
        if all_txns:
            stats = assign_transactions_to_entities_by_card(all_txns, project_root)
            if stats.get('assigned', 0) > 0:
                print(f"\n  [OK] Assigned {stats['assigned']} transaction(s) to entities by card")
    except Exception as e:
        print(f"\n  [Warning] Entity assignment by card skipped: {e}")

    print("\nDone.")


if __name__ == '__main__':
    main()
