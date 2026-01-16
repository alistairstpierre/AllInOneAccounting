#!/usr/bin/env python3
"""Check Gocardless transactions in CSV files"""

import csv
from pathlib import Path
from collections import defaultdict

csv_files = [
    'data/Century Digital Main Account/csv/01-0142-0771521-00_Transactions_2025-08.csv',
    'data/Century Digital Main Account/csv/01-0142-0771521-00_Transactions_2025-10.csv',
]

for csv_file in csv_files:
    print(f"\n{'='*80}")
    print(f"File: {csv_file}")
    print('='*80)
    
    gocardless_txns = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            details = row.get('Details', '').strip()
            if 'gocardless' in details.lower():
                gocardless_txns.append({
                    'date': row.get('Date', ''),
                    'amount': row.get('Amount', ''),
                    'details': details,
                    'code': row.get('Code', ''),
                    'reference': row.get('Reference', ''),
                    'type': row.get('Type', ''),
                })
    
    print(f"Found {len(gocardless_txns)} Gocardless transactions:")
    for i, txn in enumerate(gocardless_txns, 1):
        print(f"  {i}. Date: {txn['date']}, Amount: {txn['amount']}, Code: {txn['code']}, Reference: {txn['reference']}")










