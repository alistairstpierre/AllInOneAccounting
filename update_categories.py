#!/usr/bin/env python3
"""
Update Categories Script

Migrates old personal categories to the new consolidated categories.
Updates both transaction files and categorization_rules.json.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any

# Category mapping: old category -> new category
CATEGORY_MAPPING = {
    # Food
    'Food': 'Food & Dining',
    
    # Entertainment
    'Entertainment/Recreation': 'Entertainment',
    
    # Personal Care
    'Personal Care/Items': 'Personal Care',
    'Pet Care': 'Personal Care',  # Pet care goes to Personal Care
    
    # Housing (consolidated from multiple categories)
    'Bills/Utilities': 'Housing',
    'Utilities': 'Housing',
    'Home/Home Improvement': 'Housing',
    
    # Debt
    'Debt Repayment': 'Debt Payment',
    
    # Gifts
    'Gifts and Donations': 'Gifts & Donations',
    
    # Additional categories found in data
    'Health and Medical': 'Healthcare',
    'Travel/Vacation': 'Travel',
    'Clothing': 'Shopping',
    'Unknown': 'Uncategorized',
    'Error': 'Uncategorized',
    
    # Categories that stay the same (no mapping needed)
    # 'Transportation', 'Healthcare', 'Education', 'Travel', 
    # 'Shopping', 'Savings/Investing', 'Insurance', 'Uncategorized'
}

# New valid categories
NEW_PERSONAL_CATEGORIES = [
    'Housing',
    'Transportation',
    'Food & Dining',
    'Healthcare',
    'Personal Care',
    'Entertainment',
    'Shopping',
    'Insurance',
    'Savings/Investing',
    'Debt Payment',
    'Education',
    'Travel',
    'Gifts & Donations',
    'Uncategorized',
]

def save_json_safely(file_path: Path, data: Any) -> None:
    """Safely save JSON data with atomic write."""
    temp_path = file_path.with_suffix('.tmp')
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Validate the JSON by reading it back
        with open(temp_path, 'r', encoding='utf-8') as f:
            json.load(f)
        
        # Atomic replace
        temp_path.replace(file_path)
        print(f"[OK] Successfully updated {file_path.name}")
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise e

def update_transaction_category(category: str | None) -> str | None:
    """Update a single category using the mapping."""
    if category is None:
        return None
    
    # If category is in mapping, use the new category
    if category in CATEGORY_MAPPING:
        return CATEGORY_MAPPING[category]
    
    # If category is already a new category, keep it
    if category in NEW_PERSONAL_CATEGORIES:
        return category
    
    # If category is not recognized, set to Uncategorized
    # Only print warning once per unique category to avoid spam
    if not hasattr(update_transaction_category, '_warned_categories'):
        update_transaction_category._warned_categories = set()
    if category not in update_transaction_category._warned_categories:
        print(f"  Warning: Unknown category '{category}' will be set to 'Uncategorized'")
        update_transaction_category._warned_categories.add(category)
    return 'Uncategorized'

def update_transactions() -> None:
    """Update all transaction files."""
    project_root = Path(__file__).parent
    transactions_dir = project_root / 'storage' / 'transactions'
    
    if not transactions_dir.exists():
        print(f"Error: Transactions directory not found: {transactions_dir}")
        return
    
    transaction_files = list(transactions_dir.glob('*.json'))
    
    if not transaction_files:
        print("No transaction files found.")
        return
    
    print(f"Found {len(transaction_files)} transaction file(s)")
    print()
    
    total_updated = 0
    
    for file_path in transaction_files:
        print(f"Processing {file_path.name}...")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                transactions = json.load(f)
            
            if not isinstance(transactions, list):
                print(f"  Skipping: File is not a JSON array")
                continue
            
            file_updated = 0
            
            for transaction in transactions:
                if not isinstance(transaction, dict):
                    continue
                
                old_category = transaction.get('category')
                new_category = update_transaction_category(old_category)
                
                if old_category != new_category:
                    transaction['category'] = new_category
                    file_updated += 1
            
            if file_updated > 0:
                save_json_safely(file_path, transactions)
                total_updated += file_updated
                print(f"  Updated {file_updated} transaction(s)")
            else:
                print(f"  No updates needed")
            
        except json.JSONDecodeError as e:
            print(f"  Error: Invalid JSON - {e}")
        except Exception as e:
            print(f"  Error: {e}")
        
        print()
    
    print(f"Total transactions updated: {total_updated}")

def update_categorization_rules() -> None:
    """Update categorization_rules.json file."""
    project_root = Path(__file__).parent
    rules_file = project_root / 'storage' / 'categorization_rules.json'
    
    if not rules_file.exists():
        print(f"Categorization rules file not found: {rules_file}")
        print("Skipping categorization rules update.")
        return
    
    print(f"Processing categorization_rules.json...")
    
    try:
        with open(rules_file, 'r', encoding='utf-8') as f:
            rules = json.load(f)
        
        if not isinstance(rules, dict):
            print("  Error: Rules file is not a JSON object")
            return
        
        updated_count = 0
        
        for merchant_key, rule_data in rules.items():
            if not isinstance(rule_data, dict):
                continue
            
            old_category = rule_data.get('category')
            if old_category is None:
                continue
            
            new_category = update_transaction_category(old_category)
            
            if old_category != new_category:
                rule_data['category'] = new_category
                updated_count += 1
        
        if updated_count > 0:
            save_json_safely(rules_file, rules)
            print(f"  Updated {updated_count} rule(s)")
        else:
            print(f"  No updates needed")
        
    except json.JSONDecodeError as e:
        print(f"  Error: Invalid JSON - {e}")
    except Exception as e:
        print(f"  Error: {e}")

def main():
    """Main function."""
    print("=" * 60)
    print("Category Migration Script")
    print("=" * 60)
    print()
    print("Category mappings:")
    for old, new in CATEGORY_MAPPING.items():
        print(f"  {old} -> {new}")
    print()
    print("=" * 60)
    print()
    
    # Update transactions
    update_transactions()
    print()
    
    # Update categorization rules
    update_categorization_rules()
    print()
    
    print("=" * 60)
    print("Migration complete!")
    print("=" * 60)

if __name__ == '__main__':
    main()

