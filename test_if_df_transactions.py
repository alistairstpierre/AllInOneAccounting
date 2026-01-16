#!/usr/bin/env python3
"""
Test script to debug transactions with "If" or "Df" in merchant names.

This script will:
1. Load transactions from Century Digital Main Account.json
2. Find transactions with "If" or "Df" in merchant names
3. Try to re-process them with AI
4. Show what's happening step by step
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, List

# Add project root to path
import sys
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import the categorization function
from categorize_transactions import identify_and_categorize_transaction

def load_transactions(file_path: Path) -> List[Dict[str, Any]]:
    """Load transactions from JSON file."""
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Handle both array format and single object
    if isinstance(data, list):
        return data
    elif isinstance(data, dict) and 'transactions' in data:
        return data['transactions']
    else:
        return [data] if data else []

def find_if_df_transactions(transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Find transactions with 'If' or 'Df' in merchant names."""
    found = []
    for txn in transactions:
        merchant = txn.get('merchant', '')
        if merchant and re.search(r'\b(If|Df)\b', merchant, re.IGNORECASE):
            found.append(txn)
    return found

def main():
    project_root = Path(__file__).parent
    transactions_file = project_root / 'storage' / 'transactions' / 'Century Digital Main Account.json'
    
    print("=" * 60)
    print("Testing 'If'/'Df' Transaction Re-processing")
    print("=" * 60)
    
    # Load transactions
    print(f"\nLoading transactions from: {transactions_file}")
    all_transactions = load_transactions(transactions_file)
    print(f"  Loaded {len(all_transactions)} total transactions")
    
    # Find transactions with "If" or "Df"
    if_df_transactions = find_if_df_transactions(all_transactions)
    print(f"\nFound {len(if_df_transactions)} transactions with 'If' or 'Df' in merchant name")
    
    if not if_df_transactions:
        print("\nNo transactions with 'If' or 'Df' found. Exiting.")
        return
    
    # Show the transactions we found
    print("\n" + "=" * 60)
    print("Transactions with 'If' or 'Df':")
    print("=" * 60)
    for i, txn in enumerate(if_df_transactions[:10], 1):  # Show first 10
        print(f"\n{i}. ID: {txn.get('id', 'N/A')}")
        print(f"   Merchant: '{txn.get('merchant', 'N/A')}'")
        print(f"   Code: {txn.get('code', 'N/A')}")
        print(f"   Amount: ${txn.get('amount', 0):.2f}")
        print(f"   Date: {txn.get('transaction_date', 'N/A')}")
        print(f"   Category: {txn.get('category', 'N/A')}")
        print(f"   Is Transfer: {txn.get('is_transfer', False)}")
        print(f"   Identified Business: {txn.get('identified_business', 'N/A')}")
    
    if len(if_df_transactions) > 10:
        print(f"\n... and {len(if_df_transactions) - 10} more")
    
    # Test processing one transaction
    print("\n" + "=" * 60)
    print("Testing AI re-processing for first transaction:")
    print("=" * 60)
    
    test_txn = if_df_transactions[0]
    print(f"\nTransaction ID: {test_txn.get('id')}")
    print(f"Current Merchant: '{test_txn.get('merchant')}'")
    print(f"Code: {test_txn.get('code')}")
    print(f"Reference: {test_txn.get('reference')}")
    print(f"Amount: ${test_txn.get('amount', 0):.2f}")
    print(f"Date: {test_txn.get('transaction_date')}")
    
    # Build transaction context
    transaction_context = {
        'details': '',  # We don't have this in saved transaction
        'particulars': '',
        'code': test_txn.get('code') or '',
        'reference': test_txn.get('reference') or '',
    }
    
    print(f"\nTransaction Context: {transaction_context}")
    print(f"\nCalling AI with merchant='{test_txn.get('merchant')}' and context...")
    
    try:
        result = identify_and_categorize_transaction(
            merchant=test_txn.get('merchant', ''),
            amount=test_txn.get('amount', 0.0),
            date=test_txn.get('transaction_date', ''),
            account_type='Business',
            project_root=project_root,
            verbose=True,
            transaction_context=transaction_context
        )
        
        print("\n" + "=" * 60)
        print("AI Results:")
        print("=" * 60)
        print(f"  Identified Business: {result.get('identified_business', 'None')}")
        print(f"  Category: {result.get('category', 'None')}")
        print(f"  Category Description: {result.get('category_description', 'None')}")
        
        if result.get('identified_business'):
            print(f"\n[OK] Would update merchant from '{test_txn.get('merchant')}' to '{result.get('identified_business')}'")
        else:
            print(f"\n[ERROR] No identified_business returned - merchant name won't be updated")
            
    except Exception as e:
        print(f"\n[ERROR] Error processing transaction: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()

