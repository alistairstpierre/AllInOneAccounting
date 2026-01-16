#!/usr/bin/env python3
"""
Trace the complete flow of how CSV data flows to the AI.
"""

import json
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from categorize_transactions import parse_csv_file

print("=" * 80)
print("STEP 1: CSV PARSING")
print("=" * 80)

csv_file = project_root / 'data' / 'Century Digital Main Account' / 'csv' / '01-0142-0771521-00_Transactions_2025-12.csv'
txns = parse_csv_file(csv_file, 'CHECKING')

# Find a Visa Purchase transaction with code/reference
visa_txn = None
for txn in txns:
    if txn.get('transaction_type', '').upper() == 'VISA PURCHASE' and txn.get('code'):
        visa_txn = txn
        break

if visa_txn:
    print(f"\nFound Visa Purchase transaction:")
    print(f"  Merchant: '{visa_txn.get('merchant')}'")
    print(f"  Code: '{visa_txn.get('code')}'")
    print(f"  Reference: '{visa_txn.get('reference')}'")
    print(f"  Transaction Context: {visa_txn.get('transaction_context')}")
    print(f"  Has transaction_context key: {'transaction_context' in visa_txn}")
else:
    print("\nNo Visa Purchase transaction found with code field")
    if txns:
        print(f"\nFirst transaction:")
        print(f"  Keys: {list(txns[0].keys())}")
        print(f"  Transaction: {json.dumps(txns[0], indent=2, default=str)}")

print("\n" + "=" * 80)
print("STEP 2: CHECKING EXISTING TRANSACTIONS")
print("=" * 80)

transactions_file = project_root / 'storage' / 'transactions' / 'Century Digital Main Account.json'
with open(transactions_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

if isinstance(data, list):
    transactions = data
elif isinstance(data, dict) and 'transactions' in data:
    transactions = data['transactions']
else:
    transactions = [data] if data else []

# Find an existing transaction with "If" or "Df" that has code/reference
existing_if_df = None
for txn in transactions:
    merchant = txn.get('merchant', '')
    if merchant and ('If' in merchant or 'Df' in merchant) and txn.get('code'):
        existing_if_df = txn
        break

if existing_if_df:
    print(f"\nFound existing transaction with 'If'/'Df':")
    print(f"  ID: {existing_if_df.get('id')}")
    print(f"  Merchant: '{existing_if_df.get('merchant')}'")
    print(f"  Code: '{existing_if_df.get('code')}'")
    print(f"  Reference: '{existing_if_df.get('reference')}'")
    print(f"  Transaction Context: {existing_if_df.get('transaction_context')}")
    print(f"  Has transaction_context key: {'transaction_context' in existing_if_df}")
    print(f"  Keys in transaction: {list(existing_if_df.keys())}")
else:
    print("\nNo existing transaction found with 'If'/'Df' and code field")

print("\n" + "=" * 80)
print("STEP 3: SIMULATING PROCESSED_TXN CREATION")
print("=" * 80)

if visa_txn and existing_if_df:
    print("\nSimulating how processed_txn would be created:")
    print(f"\nFrom CSV transaction:")
    print(f"  csv_txn.get('code'): {visa_txn.get('code')}")
    print(f"  csv_txn.get('reference'): {visa_txn.get('reference')}")
    print(f"  csv_txn.get('transaction_context'): {visa_txn.get('transaction_context')}")
    
    print(f"\nFrom Existing transaction:")
    print(f"  existing_txn.get('code'): {existing_if_df.get('code')}")
    print(f"  existing_txn.get('reference'): {existing_if_df.get('reference')}")
    print(f"  existing_txn.get('transaction_context'): {existing_if_df.get('transaction_context')}")
    
    # Simulate the logic from lines 1808-1824
    csv_txn = visa_txn
    existing_txn = existing_if_df
    
    transaction_context = csv_txn.get('transaction_context')
    print(f"\nStep 1: Get transaction_context from csv_txn: {transaction_context}")
    
    if not transaction_context:
        print("Step 2: transaction_context is None/empty, building from existing_txn")
        existing_code = existing_txn.get('code') or ''
        existing_ref = existing_txn.get('reference') or ''
        csv_code = csv_txn.get('code') or ''
        csv_ref = csv_txn.get('reference') or ''
        
        transaction_context = {
            'details': existing_txn.get('transaction_context', {}).get('details', '') if isinstance(existing_txn.get('transaction_context'), dict) else '',
            'particulars': existing_txn.get('transaction_context', {}).get('particulars', '') if isinstance(existing_txn.get('transaction_context'), dict) else '',
            'code': existing_code or csv_code,
            'reference': existing_ref or csv_ref,
        }
        print(f"Step 3: Built transaction_context: {transaction_context}")
    else:
        print(f"Step 2: transaction_context exists: {transaction_context}")
    
    # Simulate processed_txn
    processed_txn = {
        'code': csv_txn.get('code') or (existing_txn.get('code') if existing_txn else None),
        'reference': csv_txn.get('reference') or (existing_txn.get('reference') if existing_txn else None),
        'transaction_context': transaction_context,
    }
    print(f"\nStep 4: processed_txn would have:")
    print(f"  code: {processed_txn['code']}")
    print(f"  reference: {processed_txn['reference']}")
    print(f"  transaction_context: {processed_txn['transaction_context']}")

print("\n" + "=" * 80)
print("STEP 4: CHECKING WHAT GETS PASSED TO AI")
print("=" * 80)

if visa_txn and existing_if_df:
    # Simulate what happens in the AI processing section
    processed_txn = {
        'code': existing_if_df.get('code'),
        'reference': existing_if_df.get('reference'),
        'transaction_context': {
            'code': existing_if_df.get('code') or '',
            'reference': existing_if_df.get('reference') or '',
            'details': '',
            'particulars': '',
        }
    }
    
    print(f"\nWhen processing transaction for AI:")
    print(f"  txn.get('code'): {processed_txn.get('code')}")
    print(f"  txn.get('reference'): {processed_txn.get('reference')}")
    print(f"  txn.get('transaction_context'): {processed_txn.get('transaction_context')}")
    
    # Simulate the check
    transaction_context = processed_txn.get('transaction_context')
    if transaction_context:
        if isinstance(transaction_context, dict):
            is_empty = (
                (transaction_context.get('code') or '').strip() == '' and
                (transaction_context.get('reference') or '').strip() == ''
            )
            print(f"\n  Is transaction_context empty? {is_empty}")
            print(f"  transaction_context.get('code'): '{transaction_context.get('code')}'")
            print(f"  transaction_context.get('reference'): '{transaction_context.get('reference')}'")
    
    # Check what would be passed to build_llm_prompt
    if transaction_context:
        code = (transaction_context.get('code') or '').strip()
        reference = (transaction_context.get('reference') or '').strip()
        print(f"\n  What would be in the prompt:")
        print(f"    Code: '{code}'")
        print(f"    Reference: '{reference}'")


