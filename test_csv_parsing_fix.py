#!/usr/bin/env python3
"""Test if CSV parsing now correctly extracts merchant from Code field."""

from pathlib import Path
import sys
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from categorize_transactions import parse_csv_file

csv_file = project_root / 'data' / 'Century Digital Main Account' / 'csv' / '01-0142-0771521-00_Transactions_2025-12.csv'
txns = parse_csv_file(csv_file, 'CHECKING')

# Find transactions that should have Code as merchant
visa_purchases = [t for t in txns if t.get('transaction_type', '').upper() == 'VISA PURCHASE']

print(f"Found {len(visa_purchases)} Visa Purchase transactions")
print("\nFirst 10 Visa Purchase transactions:")
for i, t in enumerate(visa_purchases[:10], 1):
    print(f"{i}. Merchant: '{t.get('merchant')}' | Code: '{t.get('code')}' | Reference: '{t.get('reference')}'")

# Check if any still have "If" or "Df" as merchant
bad_merchants = [t for t in visa_purchases if t.get('merchant', '').strip() in ['If', 'Df']]
if bad_merchants:
    print(f"\n[ERROR] Found {len(bad_merchants)} transactions with 'If' or 'Df' as merchant!")
    for t in bad_merchants[:5]:
        print(f"  Merchant: '{t.get('merchant')}' | Code: '{t.get('code')}'")
else:
    print("\n[OK] No transactions with 'If' or 'Df' as merchant name!")


