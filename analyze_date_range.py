#!/usr/bin/env python3
"""
Quick script to analyze transactions in a specific date range
"""

import json
from pathlib import Path
from collections import defaultdict

# Load transactions
current_file = Path('storage/transactions/Century Digital Main Account.json')
temp_file = Path('storage/transactions_temp/Century Digital Main Account.json')

current_txns = json.load(open(current_file, encoding='utf-8'))
temp_txns = json.load(open(temp_file, encoding='utf-8'))

# Filter by date range
start_date = '2025-07-01'
end_date = '2025-10-31'

current_filtered = [t for t in current_txns if start_date <= t.get('transaction_date', '') <= end_date]
temp_filtered = [t for t in temp_txns if start_date <= t.get('transaction_date', '') <= end_date]

print(f"Current storage (Jul-Oct): {len(current_filtered)} transactions")
print(f"Temp storage (Jul-Oct): {len(temp_filtered)} transactions")
print()

# Group by date and amount to find potential matches
current_by_date_amount = defaultdict(list)
temp_by_date_amount = defaultdict(list)

for txn in current_filtered:
    key = (txn.get('transaction_date', ''), round(txn.get('amount', 0), 2))
    current_by_date_amount[key].append(txn)

for txn in temp_filtered:
    key = (txn.get('transaction_date', ''), round(txn.get('amount', 0), 2))
    temp_by_date_amount[key].append(txn)

# Find transactions with same date and amount
print("Transactions with same date and amount (potential matches):")
print("=" * 80)
matches = 0
for key in sorted(current_by_date_amount.keys()):
    if key in temp_by_date_amount:
        current_list = current_by_date_amount[key]
        temp_list = temp_by_date_amount[key]
        if len(current_list) == len(temp_list):
            matches += len(current_list)
        else:
            print(f"\nDate: {key[0]}, Amount: ${key[1]:.2f}")
            print(f"  Current: {len(current_list)} occurrence(s)")
            print(f"  Temp: {len(temp_list)} occurrence(s)")
            print(f"  Current merchant(s): {[t.get('merchant', '')[:40] for t in current_list[:3]]}")
            print(f"  Temp merchant(s): {[t.get('merchant', '')[:40] for t in temp_list[:3]]}")

print(f"\nTotal exact date+amount matches: {matches}")
print()

# Show some examples of transactions only in one or the other
print("Sample transactions ONLY in current (first 10):")
print("=" * 80)
current_keys = set(current_by_date_amount.keys())
temp_keys = set(temp_by_date_amount.keys())
only_current = current_keys - temp_keys
count = 0
for key in sorted(only_current)[:10]:
    txn = current_by_date_amount[key][0]
    print(f"  {txn.get('transaction_date')} | ${txn.get('amount', 0):.2f} | {txn.get('merchant', '')[:50]}")
    count += 1

print(f"\nTotal unique date+amount combos only in current: {len(only_current)}")
print()

print("Sample transactions ONLY in temp (first 10):")
print("=" * 80)
only_temp = temp_keys - current_keys
count = 0
for key in sorted(only_temp)[:10]:
    txn = temp_by_date_amount[key][0]
    print(f"  {txn.get('transaction_date')} | ${txn.get('amount', 0):.2f} | {txn.get('merchant', '')[:50]}")
    count += 1

print(f"\nTotal unique date+amount combos only in temp: {len(only_temp)}")










