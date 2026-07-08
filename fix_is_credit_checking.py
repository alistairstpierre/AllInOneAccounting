#!/usr/bin/env python3
"""
One-time fix: reverse is_credit for checking-account transactions in storage.

The processor previously used is_credit = (amount < 0), but for these CSVs
positive amount = credit (money in), negative = debit (expense). So expenses
were wrongly marked as credits. This script flips is_credit for checking
accounts only (account number format 01-0142-0771521-00 or 06-0441-...).

Skips any transaction that has updated_at set (the app sets this when a user
has manually edited the transaction, e.g. category or is_credit).

Usage: python3 fix_is_credit_checking.py
"""

import json
import re
from pathlib import Path


def is_checking_account(account: str) -> bool:
    if not account:
        return False
    normalized = account.replace(' ', '')
    return bool(re.match(r'^\d{2}-\d{4}-\d{7}-\d{2}$', normalized))


def main():
    root = Path(__file__).resolve().parent
    storage_dir = root / 'storage' / 'transactions'
    if not storage_dir.exists():
        print("No storage/transactions dir")
        return
    for path in sorted(storage_dir.glob('*.json')):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except Exception as e:
            print(f"Skip {path.name}: {e}")
            continue
        changed = 0
        skipped_manual = 0
        for t in data:
            if not is_checking_account(t.get('account') or ''):
                continue
            if t.get('is_transfer'):
                continue
            if t.get('updated_at'):
                skipped_manual += 1
                continue
            old_val = t.get('is_credit', False)
            t['is_credit'] = not old_val
            changed += 1
        if changed or skipped_manual:
            if changed:
                path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
            print(f"{path.name}: flipped {changed}, skipped {skipped_manual} manual")
    print("Done.")


if __name__ == '__main__':
    main()
