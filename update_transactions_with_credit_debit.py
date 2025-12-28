#!/usr/bin/env python3
"""
Update Existing Transactions with Credit/Debit Information

This script updates existing transaction JSON files to add the `is_credit` field
based on transaction patterns and merchant names. It processes all transaction
files in storage/transactions/ and adds the field where missing.
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, List

def is_credit_transaction(transaction: Dict[str, Any]) -> bool:
    """
    Determine if a transaction is a credit (income) or debit (expense).
    
    Credits are identified by:
    - Merchant names containing credit/deposit keywords
    - Category descriptions containing credit keywords
    - Common income patterns
    """
    merchant = (transaction.get('identified_business') or transaction.get('merchant') or '').lower()
    description = (transaction.get('category_description') or '').lower()
    
    # Credit/income indicators
    credit_keywords = [
        'deposit',
        'credit',
        'salary',
        'wage',
        'income',
        'payment received',
        'refund',
        'transfer credit',
        'payment from',
        'century digital',  # Salary from Century Digital
    ]
    
    # Check if merchant or description contains credit keywords
    for keyword in credit_keywords:
        if keyword in merchant or keyword in description:
            return True
    
    # Check for common credit patterns in merchant names
    credit_patterns = [
        r'credit\s+to',
        r'deposit',
        r'salary',
        r'wage',
        r'income',
    ]
    
    for pattern in credit_patterns:
        if re.search(pattern, merchant, re.IGNORECASE):
            return True
    
    return False

def update_transaction_file(file_path: Path) -> tuple[int, int]:
    """
    Update a single transaction file to add is_credit field.
    
    Returns:
        (updated_count, total_count) tuple
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            transactions = json.load(f)
        
        if not isinstance(transactions, list):
            print(f"  Warning: {file_path.name} does not contain a list of transactions")
            return (0, 0)
        
        updated_count = 0
        total_count = len(transactions)
        
        for transaction in transactions:
            # Only update if is_credit field is missing
            if 'is_credit' not in transaction:
                transaction['is_credit'] = is_credit_transaction(transaction)
                updated_count += 1
        
        if updated_count > 0:
            # Write back to file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(transactions, f, indent=2, ensure_ascii=False)
        
        return (updated_count, total_count)
    
    except Exception as e:
        print(f"  Error processing {file_path.name}: {e}")
        return (0, 0)

def main():
    """Main function to update all transaction files."""
    # Get project root (parent of this script)
    script_path = Path(__file__).resolve()
    project_root = script_path.parent
    
    # Path to transactions directory
    transactions_dir = project_root / 'storage' / 'transactions'
    
    if not transactions_dir.exists():
        print(f"Error: Transactions directory not found: {transactions_dir}")
        return
    
    # Find all JSON files
    json_files = list(transactions_dir.glob('*.json'))
    
    if not json_files:
        print("No transaction files found.")
        return
    
    print(f"Found {len(json_files)} transaction file(s)")
    print()
    
    total_updated = 0
    total_transactions = 0
    
    for json_file in sorted(json_files):
        print(f"Processing {json_file.name}...")
        updated, total = update_transaction_file(json_file)
        total_updated += updated
        total_transactions += total
        print(f"  Updated {updated} of {total} transaction(s)")
    
    print()
    print(f"Summary:")
    print(f"  Total transactions processed: {total_transactions}")
    print(f"  Transactions updated: {total_updated}")
    print(f"  Files processed: {len(json_files)}")

if __name__ == '__main__':
    main()

