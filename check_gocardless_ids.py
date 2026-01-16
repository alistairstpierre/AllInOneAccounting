#!/usr/bin/env python3
"""Check Gocardless transaction IDs"""

import json
from pathlib import Path
from collections import defaultdict

# Load transactions
temp_file = Path('storage/transactions_temp/Century Digital Main Account.json')
temp_txns = json.load(open(temp_file, encoding='utf-8'))

# Find Gocardless $373.75 transactions
gocardless = [t for t in temp_txns if 'gocardless' in t.get('merchant', '').lower() and t.get('amount') == 373.75]

print(f"Total Gocardless $373.75 in temp: {len(gocardless)}")
print()

# Group by date
by_date = defaultdict(list)
for txn in gocardless:
    date = txn.get('transaction_date', '')
    by_date[date].append(txn)

for date in sorted(by_date.keys()):
    txns = by_date[date]
    print(f"Date: {date} - {len(txns)} transaction(s)")
    for txn in txns:
        print(f"  ID: {txn.get('id', 'N/A')}")
        print(f"  Code: {txn.get('code', 'N/A')}")
        print(f"  Reference: {txn.get('reference', 'N/A')}")
    print()










