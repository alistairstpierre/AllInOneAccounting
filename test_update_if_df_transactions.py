#!/usr/bin/env python3
"""
Test script to update transactions with "If" or "Df" in merchant names.

This script will:
1. Load transactions from Century Digital Main Account.json
2. Find a few transactions with "If" or "Df" in merchant names
3. Re-process them with AI
4. Update the JSON file with corrected merchant names and categories
5. Show what changed
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

# Add project root to path
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

def save_transactions(file_path: Path, transactions: List[Dict[str, Any]]) -> None:
    """Save transactions to JSON file."""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(transactions, f, indent=2, ensure_ascii=False)

def find_if_df_transactions(transactions: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    """Find transactions with 'If' or 'Df' in merchant names."""
    found = []
    for txn in transactions:
        merchant = txn.get('merchant', '')
        if merchant and re.search(r'\b(If|Df)\b', merchant, re.IGNORECASE):
            found.append(txn)
            if len(found) >= limit:
                break
    return found

def main():
    project_root = Path(__file__).parent
    transactions_file = project_root / 'storage' / 'transactions' / 'Century Digital Main Account.json'
    
    print("=" * 60)
    print("Testing 'If'/'Df' Transaction Updates")
    print("=" * 60)
    
    # Load transactions
    print(f"\nLoading transactions from: {transactions_file}")
    all_transactions = load_transactions(transactions_file)
    print(f"  Loaded {len(all_transactions)} total transactions")
    
    # Find a few transactions with "If" or "Df"
    if_df_transactions = find_if_df_transactions(all_transactions, limit=5)
    print(f"\nFound {len(if_df_transactions)} transactions with 'If' or 'Df' to test")
    
    if not if_df_transactions:
        print("\nNo transactions with 'If' or 'Df' found. Exiting.")
        return
    
    # Show what we're going to update
    print("\n" + "=" * 60)
    print("Transactions to Update:")
    print("=" * 60)
    for i, txn in enumerate(if_df_transactions, 1):
        print(f"\n{i}. ID: {txn.get('id', 'N/A')}")
        print(f"   Current Merchant: '{txn.get('merchant', 'N/A')}'")
        print(f"   Code: {txn.get('code', 'N/A')}")
        print(f"   Amount: ${txn.get('amount', 0):.2f}")
        print(f"   Date: {txn.get('transaction_date', 'N/A')}")
        print(f"   Current Category: {txn.get('category', 'N/A')}")
        print(f"   Is Transfer: {txn.get('is_transfer', False)}")
    
    # Process automatically (no confirmation needed for test script)
    print("\n" + "=" * 60)
    print(f"Processing {len(if_df_transactions)} transactions automatically...")
    
    # Process each transaction
    print("\n" + "=" * 60)
    print("Processing Transactions:")
    print("=" * 60)
    
    updated_count = 0
    transaction_map = {txn.get('id'): i for i, txn in enumerate(all_transactions)}
    
    for i, txn in enumerate(if_df_transactions, 1):
        txn_id = txn.get('id')
        print(f"\n[{i}/{len(if_df_transactions)}] Processing: {txn_id}")
        print(f"  Current Merchant: '{txn.get('merchant')}'")
        print(f"  Code: {txn.get('code')}")
        
        # Build transaction context
        transaction_context = {
            'details': '',
            'particulars': '',
            'code': txn.get('code') or '',
            'reference': txn.get('reference') or '',
        }
        
        try:
            result = identify_and_categorize_transaction(
                merchant=txn.get('merchant', ''),
                amount=txn.get('amount', 0.0),
                date=txn.get('transaction_date', ''),
                account_type='Business',
                project_root=project_root,
                verbose=True,
                transaction_context=transaction_context
            )
            
            # Update the transaction
            original_merchant = txn.get('merchant', '')
            original_category = txn.get('category', '')
            
            # Update merchant name if AI identified a business
            if result.get('identified_business'):
                txn['merchant'] = result['identified_business']
                txn['identified_business'] = result['identified_business']
                print(f"  [UPDATED] Merchant: '{original_merchant}' -> '{result['identified_business']}'")
            
            # Update category
            if result.get('category'):
                txn['category'] = result['category']
                txn['categorized'] = True
                txn['categorized_at'] = datetime.now().isoformat()
                print(f"  [UPDATED] Category: '{original_category}' -> '{result['category']}'")
            
            # Update category description
            if result.get('category_description'):
                txn['category_description'] = result['category_description']
            
            # Clear transfer flag if merchant was wrong
            if original_merchant in ['If', 'Df'] and txn.get('is_transfer', False):
                txn['is_transfer'] = False
                print(f"  [UPDATED] Is Transfer: True -> False (merchant was incorrectly identified)")
            
            # Update in the main transactions list
            if txn_id in transaction_map:
                all_transactions[transaction_map[txn_id]] = txn
                updated_count += 1
                print(f"  [OK] Transaction updated in memory")
            else:
                print(f"  [WARNING] Transaction ID not found in main list")
                
        except Exception as e:
            print(f"  [ERROR] Error processing transaction: {e}")
            import traceback
            traceback.print_exc()
    
    # Save updated transactions
    if updated_count > 0:
        print("\n" + "=" * 60)
        print(f"Saving {updated_count} updated transaction(s)...")
        print("=" * 60)
        
        # Save updated transactions
        save_transactions(transactions_file, all_transactions)
        print(f"Saved updated transactions to: {transactions_file}")
        print(f"\n[SUCCESS] Updated {updated_count} transaction(s)")
    else:
        print("\n[INFO] No transactions were updated")

if __name__ == '__main__':
    main()

