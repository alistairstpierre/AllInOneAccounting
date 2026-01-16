#!/usr/bin/env python3
"""
Test script to verify we can read code/reference from CSV files and existing transactions.
"""

import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from categorize_transactions import parse_csv_file

def test_csv_parsing():
    """Test if we can parse code/reference from CSV files."""
    print("=" * 60)
    print("Testing CSV Parsing")
    print("=" * 60)
    
    csv_file = project_root / 'data' / 'Century Digital Main Account' / 'csv' / '01-0142-0771521-00_Transactions_2025-12.csv'
    
    if not csv_file.exists():
        print(f"ERROR: CSV file not found: {csv_file}")
        return
    
    print(f"\nParsing CSV file: {csv_file.name}")
    transactions = parse_csv_file(csv_file, 'CHECKING')
    
    print(f"\nFound {len(transactions)} transactions")
    
    # Find transactions with "If" or "Df" in merchant name
    if_df_transactions = [txn for txn in transactions if txn.get('merchant', '').strip() in ['If', 'Df'] or 'If' in txn.get('merchant', '') or 'Df' in txn.get('merchant', '')]
    
    print(f"\nFound {len(if_df_transactions)} transactions with 'If' or 'Df' in merchant name")
    
    # Show first 10
    for i, txn in enumerate(if_df_transactions[:10], 1):
        print(f"\n{i}. Merchant: '{txn.get('merchant', 'N/A')}'")
        print(f"   Code: '{txn.get('code', 'N/A')}'")
        print(f"   Reference: '{txn.get('reference', 'N/A')}'")
        print(f"   Amount: ${txn.get('amount', 0):.2f}")
        print(f"   Date: {txn.get('transaction_date', 'N/A')}")
        transaction_context = txn.get('transaction_context', {})
        if transaction_context:
            print(f"   Transaction Context: {transaction_context}")
        else:
            print(f"   Transaction Context: None or empty")

def test_existing_transactions():
    """Test if we can read code/reference from existing transactions."""
    print("\n" + "=" * 60)
    print("Testing Existing Transactions")
    print("=" * 60)
    
    transactions_file = project_root / 'storage' / 'transactions' / 'Century Digital Main Account.json'
    
    if not transactions_file.exists():
        print(f"ERROR: Transactions file not found: {transactions_file}")
        return
    
    print(f"\nLoading transactions from: {transactions_file.name}")
    
    with open(transactions_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if isinstance(data, list):
        transactions = data
    elif isinstance(data, dict) and 'transactions' in data:
        transactions = data['transactions']
    else:
        transactions = [data] if data else []
    
    print(f"Loaded {len(transactions)} transactions")
    
    # Find transactions with "If" or "Df" in merchant name
    if_df_transactions = []
    for txn in transactions:
        merchant = txn.get('merchant', '')
        if merchant and ('If' in merchant or 'Df' in merchant):
            if_df_transactions.append(txn)
    
    print(f"\nFound {len(if_df_transactions)} transactions with 'If' or 'Df' in merchant name")
    
    # Show first 10
    for i, txn in enumerate(if_df_transactions[:10], 1):
        print(f"\n{i}. ID: {txn.get('id', 'N/A')}")
        print(f"   Merchant: '{txn.get('merchant', 'N/A')}'")
        print(f"   Code: '{txn.get('code', 'N/A')}'")
        print(f"   Reference: '{txn.get('reference', 'N/A')}'")
        print(f"   Amount: ${txn.get('amount', 0):.2f}")
        print(f"   Date: {txn.get('transaction_date', 'N/A')}")
        transaction_context = txn.get('transaction_context')
        if transaction_context:
            print(f"   Transaction Context: {transaction_context}")
        else:
            print(f"   Transaction Context: None or empty")

def test_transaction_context_building():
    """Test building transaction_context from existing transaction."""
    print("\n" + "=" * 60)
    print("Testing Transaction Context Building")
    print("=" * 60)
    
    transactions_file = project_root / 'storage' / 'transactions' / 'Century Digital Main Account.json'
    
    with open(transactions_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if isinstance(data, list):
        transactions = data
    elif isinstance(data, dict) and 'transactions' in data:
        transactions = data['transactions']
    else:
        transactions = [data] if data else []
    
    # Find a transaction with "If" or "Df" that has code/reference
    test_txn = None
    for txn in transactions:
        merchant = txn.get('merchant', '')
        code = txn.get('code', '')
        if merchant and ('If' in merchant or 'Df' in merchant) and code:
            test_txn = txn
            break
    
    if not test_txn:
        print("No test transaction found with 'If'/'Df' and code field")
        return
    
    print(f"\nTest Transaction:")
    print(f"  ID: {test_txn.get('id')}")
    print(f"  Merchant: '{test_txn.get('merchant')}'")
    print(f"  Code: '{test_txn.get('code')}'")
    print(f"  Reference: '{test_txn.get('reference')}'")
    
    # Simulate building transaction_context
    existing_code = test_txn.get('code') or ''
    existing_ref = test_txn.get('reference') or ''
    
    transaction_context = {
        'details': '',
        'particulars': '',
        'code': existing_code,
        'reference': existing_ref,
    }
    
    print(f"\nBuilt Transaction Context:")
    print(f"  {transaction_context}")
    
    if transaction_context['code'] or transaction_context['reference']:
        print(f"\n[OK] Transaction context has code/reference values!")
    else:
        print(f"\n[ERROR] Transaction context is empty!")

if __name__ == '__main__':
    test_csv_parsing()
    test_existing_transactions()
    test_transaction_context_building()


