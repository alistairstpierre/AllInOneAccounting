#!/usr/bin/env python3
"""Check Gocardless transaction duplicates"""

import json
from pathlib import Path

# Load transactions
current_file = Path('storage/transactions/Century Digital Main Account.json')
temp_file = Path('storage/transactions_temp/Century Digital Main Account.json')

current_txns = json.load(open(current_file, encoding='utf-8'))
temp_txns = json.load(open(temp_file, encoding='utf-8'))

# Find Gocardless $373.75 transactions
current_gocardless = [t for t in current_txns if 'gocardless' in t.get('merchant', '').lower() and t.get('amount') == 373.75]
temp_gocardless = [t for t in temp_txns if 'gocardless' in t.get('merchant', '').lower() and t.get('amount') == 373.75]

print("=" * 80)
print("Current Storage - Gocardless $373.75 transactions:")
print("=" * 80)
for txn in sorted(current_gocardless, key=lambda x: (x.get('transaction_date', ''), x.get('transaction_id', ''))):
    print(f"Date: {txn.get('transaction_date')}")
    print(f"  ID: {txn.get('transaction_id', '')}")
    print(f"  Merchant: {txn.get('merchant', '')}")
    print(f"  Reference: {txn.get('reference', 'N/A')}")
    print(f"  Code: {txn.get('code', 'N/A')}")
    print(f"  Card: {txn.get('card', 'N/A')}")
    print()

print("=" * 80)
print("Temp Storage - Gocardless $373.75 transactions:")
print("=" * 80)
for txn in sorted(temp_gocardless, key=lambda x: (x.get('transaction_date', ''), x.get('transaction_id', ''))):
    print(f"Date: {txn.get('transaction_date')}")
    print(f"  ID: {txn.get('transaction_id', '')}")
    print(f"  Merchant: {txn.get('merchant', '')}")
    print(f"  Reference: {txn.get('reference', 'N/A')}")
    print(f"  Code: {txn.get('code', 'N/A')}")
    print(f"  Card: {txn.get('card', 'N/A')}")
    print()

# Group by date
from collections import defaultdict
current_by_date = defaultdict(list)
temp_by_date = defaultdict(list)

for txn in current_gocardless:
    current_by_date[txn.get('transaction_date', '')].append(txn)
for txn in temp_gocardless:
    temp_by_date[txn.get('transaction_date', '')].append(txn)

print("=" * 80)
print("Count by Date:")
print("=" * 80)
for date in sorted(set(list(current_by_date.keys()) + list(temp_by_date.keys()))):
    current_count = len(current_by_date.get(date, []))
    temp_count = len(temp_by_date.get(date, []))
    print(f"{date}: Current={current_count}, Temp={temp_count}")










