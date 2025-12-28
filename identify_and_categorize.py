#!/usr/bin/env python3
"""
Identify and Categorize Transactions by Entity Type

This script identifies business names and categorizes transactions based on the entity type.
- If transaction is assigned to a Business entity: uses business prompt and business categories
- If transaction is assigned to a Personal entity: uses personal prompt and personal categories
- If transaction is not assigned to an entity: uses account_type to determine prompt

This script processes transactions that have been assigned to entities and generates
the identified_business name and category based on the entity type.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import re

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, will use environment variables directly

# OpenAI integration
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
except ImportError:
    OPENAI_AVAILABLE = False
    OPENAI_API_KEY = None
    print("Warning: openai library not installed. Install with: pip install openai")
except Exception as e:
    OPENAI_AVAILABLE = False
    OPENAI_API_KEY = None

# Category sets (matching web/app/lib/categories.ts)
PERSONAL_CATEGORIES = [
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

BUSINESS_CATEGORIES = [
    'Office Supplies',
    'Software/Subscriptions',
    'Marketing/Advertising',
    'Professional Services',
    'Travel',
    'Meals/Entertainment',
    'Equipment',
    'Rent/Utilities',
    'Insurance',
    'Education/Training',
    'Transportation',
    'Legal/Accounting',
    'Telecommunications',
    'Bank Fees',
    'Uncategorized',
]

def get_transaction_id(transaction: Dict[str, Any]) -> str:
    """Get transaction ID from transaction object."""
    return transaction.get('id') or f"{transaction.get('merchant', '')}_{transaction.get('amount', 0)}_{transaction.get('transaction_date', '')}"

def load_entities(project_root: Path) -> List[Dict[str, Any]]:
    """Load entities from storage/entities.json."""
    entities_file = project_root / 'storage' / 'entities.json'
    if not entities_file.exists():
        return []
    
    with open(entities_file, 'r', encoding='utf-8') as f:
        entities = json.load(f)
    
    # Ensure all entities have a type field
    for entity in entities:
        if 'type' not in entity:
            entity['type'] = 'Personal'
    
    return entities

def load_transactions(project_root: Path) -> Dict[str, List[Dict[str, Any]]]:
    """Load all transactions from storage/transactions/ directory."""
    transactions_dir = project_root / 'storage' / 'transactions'
    if not transactions_dir.exists():
        return {}
    
    all_transactions = {}
    for json_file in transactions_dir.glob('*.json'):
        account_name = json_file.stem
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                transactions = json.load(f)
                all_transactions[account_name] = transactions
        except Exception as e:
            print(f"Error loading {json_file}: {e}")
    
    return all_transactions

def get_entity_for_transaction(transaction_id: str, entities: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Find which entity a transaction belongs to."""
    for entity in entities:
        if transaction_id in entity.get('transactions', []):
            return entity
    return None

def load_prompt(prompt_file: Path) -> str:
    """Load prompt template from file."""
    if not prompt_file.exists():
        return ""
    
    with open(prompt_file, 'r', encoding='utf-8') as f:
        return f.read()

def build_llm_prompt(merchant: str, amount: float, date: str, entity_type: str, prompt_template: str, categories: List[str]) -> str:
    """Build the LLM prompt for identifying and categorizing a transaction."""
    categories_list = '\n'.join([f"- {cat}" for cat in categories])
    
    prompt = f"""{prompt_template}

## Transaction to Categorize

Merchant: {merchant}
Amount: ${amount:.2f}
Date: {date}

## Available Categories

{categories_list}

## Task

1. Identify the business name (clean up the merchant name, removing transaction codes, locations that are just identifiers, etc.)
2. Select the most appropriate category from the list above
3. Provide a brief reasoning for your choice

Please respond in the following format:
Business Name: [cleaned business name]
Category: [category name]
Reasoning: [brief explanation]
"""
    return prompt

def parse_llm_response(response_text: str) -> Dict[str, Optional[str]]:
    """Parse LLM response to extract business name, category, and reasoning."""
    result = {
        'identified_business': None,
        'category': None,
        'category_description': None
    }
    
    # Try to extract Business Name
    business_match = re.search(r'Business Name:\s*(.+?)(?:\n|$)', response_text, re.IGNORECASE)
    if business_match:
        result['identified_business'] = business_match.group(1).strip()
    
    # Try to extract Category
    category_match = re.search(r'Category:\s*(.+?)(?:\n|$)', response_text, re.IGNORECASE)
    if category_match:
        result['category'] = category_match.group(1).strip()
    
    # Try to extract Reasoning
    reasoning_match = re.search(r'Reasoning:\s*(.+?)(?:\n\n|\Z)', response_text, re.IGNORECASE | re.DOTALL)
    if reasoning_match:
        result['category_description'] = reasoning_match.group(1).strip()
    
    return result

def identify_and_categorize_with_llm(merchant: str, amount: float, date: str, entity_type: str, project_root: Path, client: Optional[Any] = None) -> Dict[str, Optional[str]]:
    """
    Identify business name and categorize transaction using LLM.
    
    Returns:
        {
            'identified_business': str or None,
            'category': str or None,
            'category_description': str or None
        }
    """
    # Determine which prompt and categories to use
    if entity_type == 'Business':
        prompt_file = project_root / 'business_categorization_prompt.md'
        categories = BUSINESS_CATEGORIES
    else:
        prompt_file = project_root / 'personal_categorization_prompt.md'
        categories = PERSONAL_CATEGORIES
    
    # Load prompt template
    prompt_template = load_prompt(prompt_file)
    if not prompt_template:
        print(f"Warning: Prompt file not found: {prompt_file}")
        return {
            'identified_business': None,
            'category': None,
            'category_description': None
        }
    
    # Build the prompt
    full_prompt = build_llm_prompt(merchant, amount, date, entity_type, prompt_template, categories)
    
    # If OpenAI is not available or no client provided, return None
    if not OPENAI_AVAILABLE or client is None:
        if not OPENAI_AVAILABLE:
            print(f"Warning: OpenAI library not available for transaction: {merchant}")
        return {
            'identified_business': None,
            'category': None,
            'category_description': None
        }
    
    try:
        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Using a cost-effective model
            messages=[
                {"role": "system", "content": "You are a helpful assistant that identifies business names and categorizes expenses. Always respond in the exact format requested."},
                {"role": "user", "content": full_prompt}
            ],
            temperature=0.3,  # Lower temperature for more consistent results
            max_tokens=300
        )
        
        response_text = response.choices[0].message.content
        
        # Parse the response
        result = parse_llm_response(response_text)
        
        # Validate category is in the allowed list
        if result['category'] and result['category'] not in categories:
            print(f"Warning: LLM returned invalid category '{result['category']}' for {merchant}, using 'Uncategorized'")
            result['category'] = 'Uncategorized'
        
        return result
        
    except Exception as e:
        print(f"Error calling OpenAI API for {merchant}: {e}")
        return {
            'identified_business': None,
            'category': None,
            'category_description': None
        }

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
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise e

def process_transactions(project_root: Path, dry_run: bool = True) -> None:
    """Process all transactions and identify/categorize based on entity type."""
    print("=" * 60)
    print("Identify and Categorize Transactions by Entity Type")
    print("=" * 60)
    print()
    
    # Initialize OpenAI client if available
    client = None
    if OPENAI_AVAILABLE and not dry_run:
        if OPENAI_API_KEY:
            try:
                client = OpenAI(api_key=OPENAI_API_KEY)
                print("OpenAI client initialized")
            except Exception as e:
                print(f"Warning: Failed to initialize OpenAI client: {e}")
                print("Continuing without LLM integration...")
        else:
            print("Warning: OPENAI_API_KEY not found in environment. LLM categorization will be skipped.")
    elif dry_run:
        print("DRY RUN MODE - OpenAI API will not be called")
    else:
        print("Warning: OpenAI library not available. Install with: pip install openai")
    
    print()
    
    # Load entities and transactions
    entities = load_entities(project_root)
    all_transactions = load_transactions(project_root)
    
    print(f"Loaded {len(entities)} entities")
    print(f"Loaded transactions from {len(all_transactions)} accounts")
    print()
    
    # Count transactions by entity type
    business_entity_transactions = 0
    personal_entity_transactions = 0
    unassigned_transactions = 0
    
    # Track updates
    updated_count = 0
    skipped_count = 0
    
    # Process each account's transactions
    for account_name, transactions in all_transactions.items():
        print(f"\nProcessing account: {account_name}")
        print(f"  Total transactions: {len(transactions)}")
        
        account_business_count = 0
        account_personal_count = 0
        account_unassigned_count = 0
        account_updated = 0
        
        transactions_modified = False
        
        for transaction in transactions:
            transaction_id = get_transaction_id(transaction)
            entity = get_entity_for_transaction(transaction_id, entities)
            
            # Skip if already has identified_business and category (unless we want to re-process)
            if transaction.get('identified_business') and transaction.get('category'):
                skipped_count += 1
                continue
            
            if entity:
                entity_type = entity.get('type', 'Personal')
                entity_name = entity.get('name', 'Unknown')
                
                if entity_type == 'Business':
                    account_business_count += 1
                    business_entity_transactions += 1
                    print(f"  [Business Entity: {entity_name}] Processing: {transaction.get('merchant', 'Unknown')[:50]}")
                    
                    # Use business prompt
                    if not dry_run and client:
                        result = identify_and_categorize_with_llm(
                            transaction.get('merchant', ''),
                            transaction.get('amount', 0.0),
                            transaction.get('transaction_date', ''),
                            'Business',
                            project_root,
                            client
                        )
                        
                        # Update transaction with results
                        if result['identified_business']:
                            transaction['identified_business'] = result['identified_business']
                            transactions_modified = True
                        if result['category']:
                            transaction['category'] = result['category']
                            transaction['categorized'] = True
                            transaction['categorized_at'] = datetime.now().isoformat()
                            transactions_modified = True
                        if result['category_description']:
                            transaction['category_description'] = result['category_description']
                            transactions_modified = True
                        
                        if result['identified_business'] or result['category']:
                            account_updated += 1
                            updated_count += 1
                else:
                    account_personal_count += 1
                    personal_entity_transactions += 1
                    print(f"  [Personal Entity: {entity_name}] Processing: {transaction.get('merchant', 'Unknown')[:50]}")
                    
                    # Use personal prompt
                    if not dry_run and client:
                        result = identify_and_categorize_with_llm(
                            transaction.get('merchant', ''),
                            transaction.get('amount', 0.0),
                            transaction.get('transaction_date', ''),
                            'Personal',
                            project_root,
                            client
                        )
                        
                        # Update transaction with results
                        if result['identified_business']:
                            transaction['identified_business'] = result['identified_business']
                            transactions_modified = True
                        if result['category']:
                            transaction['category'] = result['category']
                            transaction['categorized'] = True
                            transaction['categorized_at'] = datetime.now().isoformat()
                            transactions_modified = True
                        if result['category_description']:
                            transaction['category_description'] = result['category_description']
                            transactions_modified = True
                        
                        if result['identified_business'] or result['category']:
                            account_updated += 1
                            updated_count += 1
            else:
                # No entity assigned - use account_type
                account_type = transaction.get('account_type', 'Personal')
                account_unassigned_count += 1
                unassigned_transactions += 1
                print(f"  [No Entity - Using Account Type: {account_type}] Processing: {transaction.get('merchant', 'Unknown')[:50]}")
                
                if not dry_run and client:
                    result = identify_and_categorize_with_llm(
                        transaction.get('merchant', ''),
                        transaction.get('amount', 0.0),
                        transaction.get('transaction_date', ''),
                        account_type,
                        project_root,
                        client
                    )
                    
                    # Update transaction with results
                    if result['identified_business']:
                        transaction['identified_business'] = result['identified_business']
                        transactions_modified = True
                    if result['category']:
                        transaction['category'] = result['category']
                        transaction['categorized'] = True
                        transaction['categorized_at'] = json.dumps({})  # Will be set to ISO string
                        transactions_modified = True
                    if result['category_description']:
                        transaction['category_description'] = result['category_description']
                        transactions_modified = True
                    
                    if result['identified_business'] or result['category']:
                        account_updated += 1
                        updated_count += 1
        
        # Save transactions if modified
        if transactions_modified and not dry_run:
            transactions_file = project_root / 'storage' / 'transactions' / f"{account_name}.json"
            save_json_safely(transactions_file, transactions)
            print(f"  ✓ Saved {account_updated} updated transactions")
        
        print(f"  Business entity transactions: {account_business_count}")
        print(f"  Personal entity transactions: {account_personal_count}")
        print(f"  Unassigned transactions: {account_unassigned_count}")
    
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Total business entity transactions: {business_entity_transactions}")
    print(f"Total personal entity transactions: {personal_entity_transactions}")
    print(f"Total unassigned transactions: {unassigned_transactions}")
    print(f"Transactions updated: {updated_count}")
    print(f"Transactions skipped (already categorized): {skipped_count}")
    print()
    
    if dry_run:
        print("DRY RUN MODE - No changes made")
        print("Run with --no-dry-run to actually process transactions")
    else:
        print("Processing complete!")
        if updated_count > 0:
            print(f"✓ Successfully updated {updated_count} transactions")

def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Identify and categorize transactions by entity type')
    parser.add_argument('--no-dry-run', action='store_true', help='Actually process transactions (default is dry run)')
    args = parser.parse_args()
    
    project_root = Path(__file__).parent
    process_transactions(project_root, dry_run=not args.no_dry_run)

if __name__ == '__main__':
    main()

