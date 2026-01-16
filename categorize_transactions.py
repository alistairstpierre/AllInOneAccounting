#!/usr/bin/env python3
"""
Transaction Processor

Processes CSV files from data/{AccountName}/csv/ folders and converts them
into transaction JSON files in storage/transactions/.

Supports:
- Debit/Checking accounts (CSV files)
- Credit card accounts (CSV files)
- Account type detection (Personal vs Business) from storage/accounts.json
- Transfer detection for checking accounts
- Card number extraction from CSV files
- Duplicate detection using composite key hashing
"""

import json
import re
import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from get_account_type import get_account_type, is_business_account
import os
import time
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    if OPENAI_API_KEY:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
    else:
        openai_client = None
        print("Warning: OPENAI_API_KEY not found in environment. LLM categorization will be skipped.")
except ImportError:
    OPENAI_AVAILABLE = False
    openai_client = None
    print("Warning: openai library not installed. Install with: pip install openai")
except Exception as e:
    OPENAI_AVAILABLE = False
    openai_client = None
    print(f"Warning: Failed to initialize OpenAI client: {e}")

# Category sets (matching web/app/lib/categories.ts)
PERSONAL_CATEGORIES = [
    'Housing',
    'Transportation',
    'Groceries',
    'Dining & Takeout',
    'Medical & Healthcare',
    'Fitness & Wellness',
    'Personal Care & Grooming',
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

def load_prompt_template(prompt_file: Path) -> str:
    """Load prompt template from file."""
    if not prompt_file.exists():
        return ""
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"  Warning: Could not load prompt file {prompt_file}: {e}")
        return ""

def looks_like_person_name(text: str) -> bool:
    """
    Check if text looks like a person's name.
    
    Person names typically:
    - Have 2-4 words (first name, last name, sometimes middle name or title)
    - Start with capital letters
    - Don't contain common business keywords
    - Don't contain numbers (except in rare cases)
    """
    if not text or len(text.strip()) < 3:
        return False
    
    text = text.strip()
    
    # Check for business keywords that indicate it's not a person
    business_keywords = ['ltd', 'limited', 'inc', 'incorporated', 'llc', 'llp', 'corp', 'corporation',
                        'company', 'co', 'services', 'group', 'holdings', 'enterprises', 'solutions',
                        'systems', 'technologies', 'consulting', 'associates', 'partners', 'capital',
                        'bank', 'credit', 'insurance', 'agency', 'agency', 'store', 'shop', 'restaurant',
                        'cafe', 'bar', 'hotel', 'motel', 'apartment', 'building', 'street', 'road',
                        'avenue', 'drive', 'lane', 'way', 'plaza', 'mall', 'center', 'centre']
    
    text_lower = text.lower()
    if any(keyword in text_lower for keyword in business_keywords):
        return False
    
    # Check if it contains numbers (unlikely to be a person name)
    if re.search(r'\d', text):
        return False
    
    # Check if it looks like a name pattern (2-4 words, each starting with capital)
    words = text.split()
    if len(words) < 2 or len(words) > 4:
        return False
    
    # Most words should start with capital letters
    capital_words = sum(1 for word in words if word and word[0].isupper())
    if capital_words < len(words) * 0.7:  # At least 70% should be capitalized
        return False
    
    # Check for common name patterns
    # First word should be a name (not a title like "Mr", "Dr", etc. - though we allow those)
    # Last word should be a name
    return True

def build_llm_prompt(merchant: str, amount: float, date: str, account_type: str, prompt_template: str, categories: List[str], transaction_context: Optional[Dict[str, Any]] = None) -> str:
    """
    Build the LLM prompt for identifying and categorizing a transaction.
    
    Args:
        merchant: Merchant name
        amount: Transaction amount
        date: Transaction date
        account_type: 'Business' or 'Personal'
        prompt_template: Base prompt template
        categories: List of available categories
        transaction_context: Optional dict with 'details', 'particulars', 'code', 'reference' for checking accounts
    """
    categories_list = '\n'.join([f"- {cat}" for cat in categories])
    
    # Build context information if available
    context_info = ""
    if transaction_context:
        details = (transaction_context.get('details') or '').strip()
        particulars = (transaction_context.get('particulars') or '').strip()
        code = (transaction_context.get('code') or '').strip()
        reference = (transaction_context.get('reference') or '').strip()
        
        context_parts = []
        if particulars and particulars != merchant:
            context_parts.append(f"Particulars: {particulars}")
        if details and details != merchant and not re.search(r'\d{4}-\*{4}-\*{4}-\d{4}', details):
            context_parts.append(f"Details: {details}")
        if code:
            context_parts.append(f"Code: {code}")
        if reference:
            context_parts.append(f"Reference: {reference}")
        
        if context_parts:
            context_info = "\n" + "\n".join(context_parts) + "\n"
    
    # Check if merchant looks like a person name
    person_note = ""
    if looks_like_person_name(merchant):
        if amount < 0:
            person_note = "\nNote: The merchant name appears to be a person's name. This is likely a payment TO this person."
        else:
            person_note = "\nNote: The merchant name appears to be a person's name. This is likely a payment FROM this person (income/credit)."
    
    prompt = f"""{prompt_template}

## Transaction to Categorize

Merchant: {merchant}
Amount: ${amount:.2f}
Date: {date}{context_info}{person_note}

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

def identify_and_categorize_transaction_batch(transactions: List[Dict[str, Any]], account_type: str, project_root: Path, verbose: bool = True) -> List[Dict[str, Any]]:
    """
    Identify and categorize multiple transactions in a batch using LLM.
    
    Args:
        transactions: List of transaction dicts with 'merchant', 'amount', 'date', 'transaction_id'
        account_type: 'Business' or 'Personal'
        project_root: Project root directory
        verbose: Whether to print debug information
    
    Returns:
        List of results with 'transaction_id', 'identified_business', 'category', 'category_description'
    """
    if not OPENAI_AVAILABLE or openai_client is None:
        return [{'transaction_id': t['transaction_id'], 'identified_business': None, 'category': None, 'category_description': None} for t in transactions]
    
    # Filter out transfers
    valid_transactions = [t for t in transactions if t.get('merchant') != "Account Transfer"]
    transfers = [t for t in transactions if t.get('merchant') == "Account Transfer"]
    
    # Handle transfers
    transfer_results = [{'transaction_id': t['transaction_id'], 'identified_business': "Account Transfer", 'category': None, 'category_description': None} for t in transfers]
    
    if not valid_transactions:
        return transfer_results
    
    # Determine which prompt and categories to use
    if account_type == 'Business':
        prompt_file = project_root / 'business_categorization_prompt.md'
        categories = BUSINESS_CATEGORIES
    else:
        prompt_file = project_root / 'personal_categorization_prompt.md'
        categories = PERSONAL_CATEGORIES
    
    # Load prompt template
    prompt_template = load_prompt_template(prompt_file)
    if not prompt_template:
        return transfer_results + [{'transaction_id': t['transaction_id'], 'identified_business': None, 'category': None, 'category_description': None} for t in valid_transactions]
    
    # Build batch prompt with transaction context
    transactions_list_parts = []
    for i, t in enumerate(valid_transactions):
        merchant = t['merchant']
        amount = t['amount']
        date = t.get('date') or t.get('transaction_date', '')  # Handle both field names
        
        # Add context information if available
        context = t.get('transaction_context')
        context_str = ""
        if context:
            details = context.get('details', '').strip()
            particulars = context.get('particulars', '').strip()
            code = context.get('code', '').strip()
            reference = context.get('reference', '').strip()
            
            context_parts = []
            if particulars and particulars != merchant:
                context_parts.append(f"Particulars: {particulars}")
            if details and details != merchant and not re.search(r'\d{4}-\*{4}-\*{4}-\d{4}', details):
                context_parts.append(f"Details: {details}")
            if code:
                context_parts.append(f"Code: {code}")
            if reference:
                context_parts.append(f"Reference: {reference}")
            
            if context_parts:
                context_str = " (" + ", ".join(context_parts) + ")"
        
        # Check if merchant looks like a person name
        person_note = ""
        if looks_like_person_name(merchant):
            if amount < 0:
                person_note = " [Note: Appears to be a person's name - likely payment TO this person]"
            else:
                person_note = " [Note: Appears to be a person's name - likely payment FROM this person]"
        
        transactions_list_parts.append(
            f"{i+1}. Merchant: {merchant}, Amount: ${amount:.2f}, Date: {date}{context_str}{person_note}"
        )
    
    transactions_list = "\n".join(transactions_list_parts)
    
    categories_list = '\n'.join([f"- {cat}" for cat in categories])
    
    batch_prompt = f"""{prompt_template}

## Transactions to Categorize

{transactions_list}

## Available Categories

{categories_list}

## Task

For each transaction above, provide:
1. The transaction number
2. The cleaned business name
3. The most appropriate category
4. Brief reasoning

Please respond in the following format for each transaction:
Transaction {valid_transactions[0]['transaction_id'][:20]}...:
Business Name: [cleaned business name]
Category: [category name]
Reasoning: [brief explanation]

[Repeat for each transaction]
"""
    
    if verbose:
        print(f"      [LLM] Processing batch of {len(valid_transactions)} transactions ({account_type} account)")
    
    try:
        # Call OpenAI API
        if verbose:
            print(f"      [LLM] Calling OpenAI API...")
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that identifies business names and categorizes expenses. Always respond in the exact format requested for each transaction."},
                {"role": "user", "content": batch_prompt}
            ],
            temperature=0.3,
            max_tokens=min(4000, 300 * len(valid_transactions))  # Scale tokens with batch size
        )
        
        response_text = response.choices[0].message.content
        
        if verbose:
            print(f"      [LLM] Response received")
        
        # Parse batch response - try to extract each transaction's results
        results = []
        parsing_failures = []
        for i, txn in enumerate(valid_transactions):
            # Try multiple strategies to find this transaction's results
            txn_num = i + 1
            txn_merchant = txn['merchant'][:40]
            txn_id_prefix = txn['transaction_id'][:20]  # First 20 chars of transaction ID
            
            # Strategy 1: Look for transaction ID format (what LLM actually returns)
            # Format: "Transaction {id}...:" or "Transaction {id}:" or "Transaction {id}_01:"
            pattern = rf'Transaction\s+{re.escape(txn_id_prefix)}[^:]*:.*?Business Name:\s*(.+?)(?:\n|Category:)'
            business_match = re.search(pattern, response_text, re.IGNORECASE | re.DOTALL)
            
            # Strategy 2: Look for transaction number
            if not business_match:
                pattern = rf'{txn_num}\.?\s+Merchant:\s*{re.escape(txn_merchant)}.*?Business Name:\s*(.+?)(?:\n|Category:)'
                business_match = re.search(pattern, response_text, re.IGNORECASE | re.DOTALL)
            
            # Strategy 3: Look for merchant name directly
            if not business_match:
                pattern = rf'{re.escape(txn_merchant)}.*?Business Name:\s*(.+?)(?:\n|Category:)'
                business_match = re.search(pattern, response_text, re.IGNORECASE | re.DOTALL)
            
            # Strategy 4: Look for numbered list item
            if not business_match:
                pattern = rf'{txn_num}\.?\s+.*?Business Name:\s*(.+?)(?:\n|Category:)'
                business_match = re.search(pattern, response_text, re.IGNORECASE | re.DOTALL)
            
            business_name = business_match.group(1).strip() if business_match else None
            
            # Extract category and reasoning
            if business_match:
                # Find the section for this transaction
                start_pos = business_match.start()
                # Look for next transaction (by ID or number) or end of response
                section_end = len(response_text)
                
                # Try to find next transaction by ID first
                if i + 1 < len(valid_transactions):
                    next_txn_id_prefix = valid_transactions[i + 1]['transaction_id'][:20]
                    next_txn_id_match = re.search(rf'Transaction\s+{re.escape(next_txn_id_prefix)}', response_text[start_pos:], re.IGNORECASE)
                    if next_txn_id_match:
                        section_end = start_pos + next_txn_id_match.start()
                
                # If not found by ID, try by number
                if section_end == len(response_text):
                    next_txn_match = re.search(rf'Transaction\s+.*?:\s*\n|{txn_num + 1}\.?\s+', response_text[start_pos:], re.IGNORECASE)
                    if next_txn_match:
                        section_end = start_pos + next_txn_match.start()
                
                section = response_text[start_pos:section_end]
                
                category_match = re.search(r'Category:\s*(.+?)(?:\n|Reasoning:)', section, re.IGNORECASE)
                category = category_match.group(1).strip() if category_match else None
                
                if category_match:
                    reasoning_match = re.search(r'Reasoning:\s*(.+?)(?:\n\n|\nTransaction\s+|\n\d+\.|\Z)', section[category_match.end():], re.IGNORECASE | re.DOTALL)
                    reasoning = reasoning_match.group(1).strip() if reasoning_match else None
                else:
                    reasoning = None
            else:
                category = None
                reasoning = None
            
            # Validate category
            if category and category not in categories:
                category = 'Uncategorized'
            
            results.append({
                'transaction_id': txn['transaction_id'],
                'identified_business': business_name,
                'category': category,
                'category_description': reasoning
            })
            
            if verbose:
                status = "✓" if (business_name or category) else "⚠"
                print(f"      [LLM] {status} {txn['merchant'][:40]}: {business_name or 'N/A'} → {category or 'N/A'}")
                if not business_name and not category:
                    parsing_failures.append(txn['merchant'][:40])
        
        # If many parsing failures, show debug info
        if verbose and len(parsing_failures) > len(valid_transactions) * 0.5:  # More than 50% failed
            print(f"      [LLM] Warning: {len(parsing_failures)}/{len(valid_transactions)} transactions failed to parse")
            print(f"      [LLM] Debug - First 800 chars of response:")
            print(f"      {response_text[:800]}")
            print(f"      [LLM] Debug - Last 400 chars of response:")
            print(f"      {response_text[-400:]}")
        
        return transfer_results + results
        
    except Exception as e:
        if verbose:
            print(f"      [LLM] ✗ Error: {e}")
        # Return empty results on error
        return transfer_results + [{'transaction_id': t['transaction_id'], 'identified_business': None, 'category': None, 'category_description': None} for t in valid_transactions]

def identify_and_categorize_transaction(merchant: str, amount: float, date: str, account_type: str, project_root: Path, verbose: bool = True, transaction_context: Optional[Dict[str, Any]] = None) -> Dict[str, Optional[str]]:
    """
    Identify business name and categorize transaction using LLM.
    
    Args:
        merchant: Merchant name from transaction
        amount: Transaction amount
        date: Transaction date
        account_type: 'Business' or 'Personal'
        project_root: Project root directory
        verbose: Whether to print debug information
        transaction_context: Optional dict with 'details', 'particulars', 'code', 'reference' for checking accounts
    
    Returns:
        {
            'identified_business': str or None,
            'category': str or None,
            'category_description': str or None
        }
    """
    # Skip if OpenAI is not available
    if not OPENAI_AVAILABLE or openai_client is None:
        if verbose:
            print(f"      [SKIP] No OpenAI client available for: {merchant[:50]}")
        return {
            'identified_business': None,
            'category': None,
            'category_description': None
        }
    
    # Skip transfers
    if merchant == "Account Transfer":
        if verbose:
            print(f"      [SKIP] Transfer transaction")
        return {
            'identified_business': "Account Transfer",
            'category': None,
            'category_description': None
        }
    
    # Determine which prompt and categories to use
    if account_type == 'Business':
        prompt_file = project_root / 'business_categorization_prompt.md'
        categories = BUSINESS_CATEGORIES
    else:
        prompt_file = project_root / 'personal_categorization_prompt.md'
        categories = PERSONAL_CATEGORIES
    
    # Load prompt template
    prompt_template = load_prompt_template(prompt_file)
    if not prompt_template:
        return {
            'identified_business': None,
            'category': None,
            'category_description': None
        }
    
    # Build the prompt
    full_prompt = build_llm_prompt(merchant, amount, date, account_type, prompt_template, categories, transaction_context)
    
    try:
        # Call OpenAI API
        response = openai_client.chat.completions.create(
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
            result['category'] = 'Uncategorized'
        
        return result
        
    except Exception as e:
        pass  # Errors are handled by caller
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

def get_transaction_id(transaction: Dict[str, Any]) -> str:
    """Get transaction ID from transaction object."""
    return transaction.get('id') or f"{transaction.get('merchant', '')}_{transaction.get('amount', 0)}_{transaction.get('transaction_date', '')}"

def load_entities(project_root: Path) -> List[Dict[str, Any]]:
    """Load entities from storage/entities.json."""
    entities_file = project_root / 'storage' / 'entities.json'
    if not entities_file.exists():
        return []
    
    try:
        with open(entities_file, 'r', encoding='utf-8') as f:
            entities = json.load(f)
        
        # Ensure all entities have required fields
        for entity in entities:
            if 'transactions' not in entity:
                entity['transactions'] = []
            if 'cards' not in entity:
                entity['cards'] = []
        
        return entities
    except Exception as e:
        print(f"Warning: Failed to load entities: {e}")
        return []

def save_entities(project_root: Path, entities: List[Dict[str, Any]]) -> None:
    """Save entities to storage/entities.json."""
    entities_file = project_root / 'storage' / 'entities.json'
    try:
        save_json_safely(entities_file, entities)
    except Exception as e:
        print(f"Warning: Failed to save entities: {e}")

def normalize_card_number(card: str) -> str:
    """Normalize card number by removing spaces and hyphens, keeping only digits and stars."""
    if not card:
        return ''
    # Remove all spaces and hyphens, keep only alphanumeric and stars
    normalized = ''.join(c for c in card.strip() if c.isalnum() or c == '*')
    return normalized

def assign_transactions_to_entities_by_card(transactions: List[Dict[str, Any]], project_root: Path) -> int:
    """
    Assign transactions to entities based on credit card numbers.
    
    For each transaction with a card number, check if any entity has that card
    in their cards array. If found, assign the transaction to that entity.
    
    Returns:
        Number of transactions assigned
    """
    entities = load_entities(project_root)
    if not entities:
        return 0
    
    # Build a map of normalized card -> entity for quick lookup
    # Also store original card formats for each entity
    card_to_entity = {}
    entity_cards_map = {}  # entity_id -> set of normalized cards
    
    for entity in entities:
        entity_normalized_cards = set()
        for card in entity.get('cards', []):
            if card and card.strip():
                normalized_card = normalize_card_number(card)
                if normalized_card:
                    card_to_entity[normalized_card] = entity
                    entity_normalized_cards.add(normalized_card)
                    # Also store original format variants for matching
                    card_to_entity[card.strip()] = entity
                    card_to_entity[card.strip().replace(' ', '-')] = entity
                    card_to_entity[card.strip().replace('-', ' ')] = entity
        entity_cards_map[entity['id']] = entity_normalized_cards  # Use entity ID as key
    
    if not card_to_entity:
        return 0
    
    assigned_count = 0
    entities_modified = False
    
    for transaction in transactions:
        transaction_card = transaction.get('card')
        if not transaction_card:
            continue
        
        # Normalize the transaction's card number
        normalized_transaction_card = normalize_card_number(transaction_card)
        transaction_card_stripped = transaction_card.strip()
        
        # Try to find matching entity using normalized card
        matching_entity = None
        if normalized_transaction_card in card_to_entity:
            matching_entity = card_to_entity[normalized_transaction_card]
        elif transaction_card_stripped in card_to_entity:
            matching_entity = card_to_entity[transaction_card_stripped]
        else:
            # Try variants
            for variant in [transaction_card_stripped.replace(' ', '-'),
                           transaction_card_stripped.replace('-', ' ')]:
                if variant in card_to_entity:
                    matching_entity = card_to_entity[variant]
                    break
        
        if matching_entity:
            transaction_id = get_transaction_id(transaction)
            
            # Check if transaction is already assigned to this entity
            if transaction_id not in matching_entity.get('transactions', []):
                # Check if transaction is assigned to a different entity
                current_entity = None
                for entity in entities:
                    if transaction_id in entity.get('transactions', []):
                        current_entity = entity
                        break
                
                # Only reassign if:
                # 1. Transaction is not assigned to any entity, OR
                # 2. Transaction is assigned to an entity that doesn't have this card
                should_reassign = True
                if current_entity:
                    # Check if current entity has this card (using normalized comparison)
                    current_entity_normalized_cards = entity_cards_map.get(current_entity.get('id'), set())
                    if normalized_transaction_card in current_entity_normalized_cards:
                        should_reassign = False
                
                if should_reassign:
                    # Remove from current entity if assigned elsewhere
                    if current_entity:
                        current_entity['transactions'].remove(transaction_id)
                        entities_modified = True
                    
                    # Add to matching entity
                    if 'transactions' not in matching_entity:
                        matching_entity['transactions'] = []
                    matching_entity['transactions'].append(transaction_id)
                    entities_modified = True
                    assigned_count += 1
    
    # Save entities if any changes were made
    if entities_modified:
        save_entities(project_root, entities)
    
    return assigned_count

def _save_progress_incremental(existing_transactions: List[Dict], processed_transactions: List[Dict], reprocessed_existing_ids: set, account_type_label: str, output_file: Path) -> None:
    """Save transactions incrementally during processing."""
    try:
        # Filter out reprocessed transactions
        existing_transactions_filtered = [
            txn for txn in existing_transactions 
            if txn.get('id') not in reprocessed_existing_ids
        ]
        # Merge with existing transactions (excluding reprocessed ones)
        all_processed = existing_transactions_filtered + processed_transactions
        
        # Ensure account_type is ALWAYS set correctly and categories are never null
        for txn in all_processed:
            if txn.get('account_type') != account_type_label:
                txn['account_type'] = account_type_label
            if not txn.get('category'):
                txn['category'] = 'Uncategorized'
            txn.pop('_needs_category', None)
        
        # Deduplicate by ID
        seen_ids = set()
        unique_transactions = []
        for txn in all_processed:
            txn_id = txn.get('id')
            if txn_id and txn_id not in seen_ids:
                seen_ids.add(txn_id)
                unique_transactions.append(txn)
        
        # Sort by transaction date (newest first)
        unique_transactions.sort(key=lambda x: x.get('transaction_date', ''), reverse=True)
        
        # Save incrementally (silently, don't print every time)
        save_json_safely(output_file, unique_transactions)
    except Exception as e:
        # Don't fail the whole process if incremental save fails
        pass


def parse_csv_date(date_str: str) -> str:
    """Convert CSV date format (DD/MM/YYYY) to YYYY-MM-DD."""
    try:
        parts = date_str.split('/')
        if len(parts) == 3:
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
    except:
        pass
    return date_str

def sanitize_account_id(account_id: str) -> str:
    """Sanitize account ID by replacing * with X for use in transaction IDs."""
    return account_id.replace('*', 'X')

def is_masked_card(name: str) -> bool:
    """Check if NAME field is a masked card number."""
    # Pattern: 4 digits, spaces, 4 stars, spaces, 4 stars, spaces, 4 digits
    pattern = r'^\d{4}\s+\*{4}\s+\*{4}\s+\d{4}'
    return bool(re.match(pattern, name.strip()))

def extract_card_number(name: str) -> Optional[str]:
    """Extract card number from NAME field (convert spaces to hyphens)."""
    if is_masked_card(name):
        # Extract just the card number part (4 digits, stars, 4 digits)
        # Handle cases like "4037 **** **** 6505" -> "4037-****-****-6505"
        match = re.match(r'^(\d{4}\s+\*{4}\s+\*{4}\s+\d{4})', name.strip())
        if match:
            return match.group(1).replace(' ', '-')
    return None

def is_transfer(memo: str, name: str, account_id: str) -> bool:
    """
    Detect if a transaction is a transfer based on patterns.
    
    Transactions that look like account numbers are usually transfers.
    """
    if not memo:
        memo = ""
    memo = memo.strip()
    name = name.strip()
    
    # Combine memo and name for checking (merchant field might be in either)
    combined = f"{memo} {name}".strip()
    
    # Check for account number pattern (with spaces): "01 0142 0771521 00"
    account_pattern_spaces = r'\b\d{2}\s+\d{4}\s+\d{7}\s+\d{2}\b'
    if re.search(account_pattern_spaces, combined):
        return True
    
    # Check for account number pattern (with dashes): "01-0142-0771521-00"
    account_pattern_dashes = r'\b\d{2}-\d{4}-\d{7}-\d{2}\b'
    if re.search(account_pattern_dashes, combined):
        return True
    
    # Check for account number pattern (no separators): "010142077152100" (15 digits)
    account_pattern_no_sep = r'\b\d{2}\d{4}\d{7}\d{2}\b'
    if re.search(account_pattern_no_sep, combined):
        return True
    
    # Check if the entire merchant/name field is an account number pattern
    # Format: 2 digits, 4 digits, 7 digits, 2 digits (with spaces, dashes, or no separators)
    if re.match(r'^\d{2}[\s-]?\d{4}[\s-]?\d{7}[\s-]?\d{2}$', name) or \
       re.match(r'^\d{2}[\s-]?\d{4}[\s-]?\d{7}[\s-]?\d{2}$', memo):
        return True
    
    # Check for masked card pattern in MEMO
    card_pattern = r'\d{4}\s*\*{4}\s*\*{4}\s*\d{4}'
    if re.search(card_pattern, combined):
        return True
    
    # Check for transfer keywords
    transfer_keywords = [
        'Transfer',
        'Transfer Debit Transfer',
        'Payment To',
        'Credit To',
        'Account Transfer'
    ]
    combined_lower = combined.lower()
    if any(keyword.lower() in combined_lower for keyword in transfer_keywords):
        return True
    
    # Check if MEMO is very short (likely a transfer code)
    if len(memo) < 5 and memo:
        return True
    
    # Check if MEMO or NAME is mostly numeric (account numbers, codes, etc.)
    # This catches things like "06-0441-0179990-00" or "9554-****-****-6788"
    if re.match(r'^[\d\s\*-]+$', memo) and len(memo) > 5:
        return True
    if re.match(r'^[\d\s\*-]+$', name) and len(name) > 5:
        return True
    
    return False

def normalize_merchant_name(merchant: str) -> str:
    """Normalize merchant name for matching."""
    # Remove extra whitespace, lowercase, and normalize
    normalized = merchant.strip().lower()
    # Replace multiple spaces with single space
    normalized = re.sub(r'\s+', ' ', normalized)
    # Keep the core merchant name for matching
    return normalized

def generate_transaction_id_from_csv(
    account_id: str,
    transaction_date: str,
    amount: float,
    merchant: str,
    card: Optional[str] = None,
    reference: Optional[str] = None,
    code: Optional[str] = None
) -> str:
    """
    Generate a unique transaction ID from CSV data using a composite key.
    
    Uses multiple fields to create a hash-based ID that handles:
    - Same date, same amount, different merchants (different IDs)
    - Same date, same amount, same merchant (same ID, unless reference/code differs)
    - Handles cases where 2 transactions on same date for same amount exist
    
    Args:
        account_id: Account identifier
        transaction_date: Transaction date (YYYY-MM-DD)
        amount: Transaction amount
        merchant: Merchant name (normalized)
        card: Card number (if available)
        reference: Reference number (if available)
        code: Code field (if available)
    
    Returns:
        Transaction ID in format: hash_{sanitized_account_id}
    """
    # Normalize merchant name
    normalized_merchant = normalize_merchant_name(merchant)
    
    # Round amount to 2 decimal places for consistency (handles floating point issues)
    rounded_amount = round(amount, 2)
        
    # Build composite key from all available fields
    # Include reference and code if available to distinguish legitimate duplicates
    key_parts = [
        account_id,
        transaction_date,
        str(rounded_amount),
        normalized_merchant,
    ]
    
    # Add optional fields if available
    if card:
        key_parts.append(card.strip())
    if reference:
        key_parts.append(reference.strip())
    if code:
        key_parts.append(code.strip())
    
    # Create hash from composite key
    composite_key = '|'.join(key_parts)
    hash_obj = hashlib.sha256(composite_key.encode('utf-8'))
    hash_hex = hash_obj.hexdigest()[:16]  # Use first 16 chars of hash
    
    # Sanitize account ID for use in filename-safe ID
    sanitized_account_id = sanitize_account_id(account_id)
    
    return f"{hash_hex}_{sanitized_account_id}"

def is_duplicate_transaction(
    new_txn: Dict[str, Any],
    existing_txn: Dict[str, Any],
    amount_tolerance: float = 0.01
) -> bool:
    """
    Check if two transactions are duplicates using fuzzy matching.
    
    Two transactions are considered duplicates if:
    - Same account
    - Same date
    - Same amount (within tolerance)
    - Same merchant (normalized, fuzzy match)
    - Same card (if both have cards)
    - Same reference/code (if both have them)
    
    Args:
        new_txn: New transaction to check
        existing_txn: Existing transaction to compare against
        amount_tolerance: Tolerance for amount comparison (default 0.01)
    
    Returns:
        True if transactions are duplicates, False otherwise
    """
    # Must be same account
    if new_txn.get('account') != existing_txn.get('account'):
        return False
    
    # Must be same date
    if new_txn.get('transaction_date') != existing_txn.get('transaction_date'):
        return False
    
    # Amount must match within tolerance
    new_amount = new_txn.get('amount', 0.0)
    existing_amount = existing_txn.get('amount', 0.0)
    if abs(new_amount - existing_amount) > amount_tolerance:
        return False
    
    # Merchant must match (normalized)
    new_merchant = normalize_merchant_name(new_txn.get('merchant', ''))
    existing_merchant = normalize_merchant_name(existing_txn.get('merchant', ''))
    if new_merchant != existing_merchant:
        return False
    
    # If both have cards, they must match
    new_card = new_txn.get('card')
    existing_card = existing_txn.get('card')
    if new_card and existing_card and new_card != existing_card:
        return False
    
    # If both have reference, they should match (but allow if one is missing)
    new_ref = new_txn.get('reference')
    existing_ref = existing_txn.get('reference')
    if new_ref and existing_ref and new_ref != existing_ref:
        # Different reference suggests different transactions
        return False
    
    # If both have code, they should match (but allow if one is missing)
    new_code = new_txn.get('code')
    existing_code = existing_txn.get('code')
    if new_code and existing_code and new_code != existing_code:
        # Different code suggests different transactions
        return False
    
    # All checks passed - likely duplicate
    return True


def parse_csv_file(csv_path: Path, account_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Parse a CSV file and extract transactions.
    
    Supports two CSV formats:
    1. Credit card format: Card, Type, Amount, Details, TransactionDate, ProcessedDate
    2. Checking account format: Type, Details, Particulars, Code, Reference, Amount, Date, ForeignCurrencyAmount, ConversionCharge
    
    Args:
        csv_path: Path to CSV file
        account_type: 'CREDITCARD' or 'CHECKING' (auto-detected if not provided)
    
    Returns:
        List of transaction dictionaries
    """
    transactions = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            # Read first line to detect format
            first_line = f.readline().strip()
            f.seek(0)  # Reset to beginning
            
            reader = csv.DictReader(f)
            
            # Simple format detection: If "Card" column exists, it's a credit card CSV
            # Otherwise, it's a checking account CSV
            has_card_column = 'Card' in reader.fieldnames
            
            # If account_type is provided, use it; otherwise auto-detect
            if account_type == 'CREDITCARD' or (account_type is None and has_card_column):
                # Credit card CSV format
                for row in reader:
                    transaction_type = row.get('Type', '').strip().upper()
                    card = row.get('Card', '').strip()
                    amount = row.get('Amount', '').strip()
                    details = row.get('Details', '').strip()
                    transaction_date = row.get('TransactionDate', '').strip()
                    processed_date = row.get('ProcessedDate', '').strip()
                    
                    try:
                        amount_float = float(amount) if amount else 0.0
                    except:
                        amount_float = 0.0
                    
                    # Credit card logic:
                    # Type "C" = transfer (payment to card) - skip these
                    # Type "D" = expense (debit)
                    # Positive amount = debit, Negative amount = credit (but Type "C" already handled)
                    is_transfer_txn = transaction_type == 'C'
                    is_credit = False  # Credit card expenses are always debits
                    
                    # Skip transfers (Type "C")
                    if is_transfer_txn:
                        continue
                    
                    # For credit cards, create transaction context from available fields
                    # Credit card CSVs have: Card, Type, Amount, Details, TransactionDate, ProcessedDate
                    # Details contains the merchant name and sometimes additional information
                    transaction_context = {
                        'details': details,
                        'particulars': '',  # Credit cards don't have this field
                        'code': '',  # Credit cards don't have this field
                        'reference': '',  # Credit cards don't have this field
                    }
                    
                    # Store amount as positive for consistency
                    transaction = {
                        'card': card if card else None,
                        'amount': abs(amount_float),
                        'merchant': details.strip(),
                        'transaction_date': parse_csv_date(transaction_date),
                        'processed_date': parse_csv_date(processed_date) if processed_date else None,
                        'transaction_type': transaction_type,
                        'is_transfer': is_transfer_txn,
                        'is_credit': is_credit,
                        'csv_format': 'credit_card',
                        'transaction_context': transaction_context,  # Store context for categorization
                    }
                    
                    transactions.append(transaction)
            
            else:
                # Checking account CSV format (no "Card" column)
                for row in reader:
                    transaction_type = row.get('Type', '').strip()
                    details = row.get('Details', '').strip()
                    particulars = row.get('Particulars', '').strip()
                    code = row.get('Code', '').strip()
                    reference = row.get('Reference', '').strip()
                    amount = row.get('Amount', '').strip()
                    date = row.get('Date', '').strip()
                    foreign_currency = row.get('ForeignCurrencyAmount', '').strip()
                    conversion_charge = row.get('ConversionCharge', '').strip()
                    
                    try:
                        amount_float = float(amount) if amount else 0.0
                    except:
                        amount_float = 0.0
                    
                    # Checking account logic:
                    # Positive amount = debit (expense/outgoing)
                    # Negative amount = credit (revenue/incoming)
                    # Type "Transfer" = transfer transaction
                    is_transfer_txn = transaction_type.upper() == 'TRANSFER'
                    is_credit = amount_float < 0  # Negative = credit (revenue/incoming)
                    
                    # Extract merchant name and card number
                    # For Visa Purchase: card number is in Details field, merchant is in Particulars field
                    # For other types: merchant might be in Details or Particulars
                    if transaction_type.upper() == 'VISA PURCHASE':
                        # Extract card number from Details if present (format: "4037-****-****-6505")
                        card_match = re.search(r'(\d{4}-\*{4}-\*{4}-\d{4})', details)
                        card_number = card_match.group(1) if card_match else None
                        # Merchant name priority for Visa Purchase:
                        # 1. Code field (most reliable - contains actual merchant name like "Openai *Chat")
                        # 2. Particulars field (but check if it's just a number/conversion rate)
                        # 3. Details field (last resort, contains card number)
                        merchant = None
                        if code and code.strip():
                            # Code field has the merchant name
                            merchant = code.strip()
                        elif particulars and particulars.strip():
                            # Check if Particulars is just a number (conversion rate) - if so, skip it
                            particulars_clean = particulars.strip()
                            try:
                                # If it's a valid number, it's probably a conversion rate, not a merchant name
                                float(particulars_clean)
                                # It's a number, so skip Particulars and use Code if available
                                if code and code.strip():
                                    merchant = code.strip()
                                else:
                                    # No code, so use Details as last resort
                                    merchant = details
                                    if card_number and merchant.startswith(card_number):
                                        merchant = merchant.replace(card_number, '', 1).strip()
                            except ValueError:
                                # Not a number, so use Particulars as merchant name
                                merchant = particulars.strip()
                        else:
                            # Last resort: use Details but clean it up
                            merchant = details
                            # Clean up merchant name - remove any card number remnants
                            if card_number and merchant.startswith(card_number):
                                merchant = merchant.replace(card_number, '', 1).strip()
                        
                        # Debug: Log if we had to fall back to Details (shouldn't happen for proper CSV files)
                        if not (code and code.strip()) and not (particulars and particulars.strip()):
                            print(f"      [WARNING] Visa Purchase: Code='{code}', Particulars='{particulars}', falling back to Details='{details[:50]}'")
                    else:
                        # For other transaction types, use Details or Particulars
                        merchant = details if details else particulars
                        card_number = None
                        # Check if Details contains a card number pattern (for transfers or other types)
                        card_match = re.search(r'(\d{4}-\*{4}-\*{4}-\d{4})', details)
                        if card_match:
                            card_number = card_match.group(1)
                    
                    # For checking accounts, check Details, Code, and Reference to understand transaction context
                    # If merchant looks like a person name, it might be a payment to/from them
                    # This will be used later for categorization
                    transaction_context = {
                        'details': details,
                        'particulars': particulars,
                        'code': code,
                        'reference': reference,
                    }
                    
                    transaction = {
                        'card': card_number,
                        'amount': abs(amount_float),  # Store as positive for consistency
                        'merchant': merchant.strip(),
                        'transaction_date': parse_csv_date(date),
                        'processed_date': parse_csv_date(date),  # Use same date if no processed date
                        'reference': reference if reference else None,
                        'code': code if code else None,
                        'transaction_type': transaction_type,
                        'foreign_currency': foreign_currency if foreign_currency else None,
                        'conversion_charge': conversion_charge if conversion_charge else None,
                        'csv_format': 'checking',
                        'is_transfer': is_transfer_txn,
                        'is_credit': is_credit,  # Negative amount = credit (revenue/incoming)
                        'transaction_context': transaction_context,  # Store context for categorization
                    }
                    
                    transactions.append(transaction)
    
    except Exception as e:
        print(f"  Error parsing CSV file {csv_path.name}: {e}")
        import traceback
        traceback.print_exc()
    
    return transactions


def normalize_account_for_signature(account_id: str) -> str:
    """Normalize account ID for signature matching (handles different formats)."""
    if not account_id:
        return ''
    # Normalize different formats: "9554********6788" vs "9554-****-****-6788"
    normalized = account_id.replace('-', '').replace(' ', '')
    # Replace multiple asterisks with single pattern
    normalized = re.sub(r'\*+', '****', normalized)
    return normalized

def process_account(account_folder: Path, project_root: Path) -> None:
    """
    Process an account using CSV files.
    
    CSV files are processed directly with composite key hashing for transaction IDs.
    This allows for weekly exports and handles duplicate detection using composite keys
    (date, amount, merchant, card, reference, code).
    
    When processing transactions:
    - Checks existing transactions for categories (merchant matching)
    - If no category found, generates one using AI
    - If not found, processes normally
    
    Args:
        account_folder: Path to account folder (e.g., data/Century Digital Main Account)
        project_root: Project root directory
    """
    account_name = account_folder.name
    
    # Get verbose mode from environment variable
    verbose = os.getenv('VERBOSE', '').lower() in ('1', 'true', 'yes')
    
    print(f"\n{'='*60}")
    print(f"Processing account: {account_name}")
    print(f"{'='*60}")
    
    # Get account type from configuration
    is_business = is_business_account(account_name, project_root)
    account_type_label = "Business" if is_business else "Personal"
    print(f"  Account type: {account_type_label}")
    
    csv_dir = account_folder / 'csv'
    if not csv_dir.exists():
        print(f"  Error: CSV directory not found: {csv_dir}")
        return
    
    categories_merchant_matched_count = 0  # Categories from merchant matching
    categories_generated_count = 0  # Categories generated by AI
    
    # Load existing transactions (from main storage - should be empty after deletion)
    output_file = project_root / 'storage' / 'transactions' / f"{account_name}.json"
    existing_transactions = []
    existing_ids = set()
    existing_transactions_by_id = {}  # {transaction_id: transaction} - for looking up existing transactions
    existing_composite_keys = []  # Store composite keys for duplicate detection
    # Map composite key signatures to existing transaction objects for category preservation
    existing_transactions_by_signature = {}  # {signature_tuple: transaction}
    # Map normalized merchant names to category info for merchant-based category matching
    merchant_category_lookup = {}  # {normalized_merchant: {category, identified_business, category_description}}
    
    if output_file.exists():
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                existing_transactions = json.load(f)
                existing_ids = {t.get('id') for t in existing_transactions if t.get('id')}
                # Build ID-based lookup for checking null categories
                existing_transactions_by_id = {t.get('id'): t for t in existing_transactions if t.get('id')}
                # Build list of existing transactions for duplicate checking
                for txn in existing_transactions:
                    composite_key = {
                        'account': txn.get('account'),
                        'transaction_date': txn.get('transaction_date'),
                        'amount': txn.get('amount', 0.0),
                        'merchant': txn.get('merchant', ''),
                        'card': txn.get('card'),
                        'reference': txn.get('reference'),
                        'code': txn.get('code'),
                    }
                    existing_composite_keys.append(composite_key)
                    
                    # Create signature tuple for matching (same format as in processing loop)
                    account_id = composite_key.get('account', '')
                    normalized_account = normalize_account_for_signature(account_id)
                    signature = (
                        normalized_account,
                        composite_key.get('transaction_date', ''),
                        round(composite_key.get('amount', 0.0), 2),
                        normalize_merchant_name(composite_key.get('merchant', '')),
                        composite_key.get('card') or '',
                        composite_key.get('reference') or '',
                        composite_key.get('code') or '',
                    )
                    # Store transaction for this signature (keep first match)
                    if signature not in existing_transactions_by_signature:
                        existing_transactions_by_signature[signature] = txn
                    
                    # Build merchant category lookup for merchant-based category matching
                    # Only include transactions with valid categories (not null, not empty, not "Uncategorized" unless it's the best we have)
                    merchant = txn.get('merchant', '')
                    if merchant:
                        normalized_merchant = normalize_merchant_name(merchant)
                        txn_category = txn.get('category')
                        # Only add to lookup if it has a valid category (not null, not empty, prefer non-"Uncategorized")
                        if txn_category and txn_category.strip() and txn_category != 'Uncategorized':
                            # If we already have an entry, prefer non-"Uncategorized" categories
                            if normalized_merchant not in merchant_category_lookup:
                                merchant_category_lookup[normalized_merchant] = {
                                    'category': txn_category,
                                    'identified_business': txn.get('identified_business'),
                                    'category_description': txn.get('category_description')
                                }
                            elif merchant_category_lookup[normalized_merchant]['category'] == 'Uncategorized':
                                # Replace "Uncategorized" with a better category
                                merchant_category_lookup[normalized_merchant] = {
                                    'category': txn_category,
                                    'identified_business': txn.get('identified_business'),
                                    'category_description': txn.get('category_description')
                                }
                        elif txn_category == 'Uncategorized' and normalized_merchant not in merchant_category_lookup:
                            # Only add "Uncategorized" if we don't have anything better
                            merchant_category_lookup[normalized_merchant] = {
                                'category': 'Uncategorized',
                                'identified_business': txn.get('identified_business'),
                                'category_description': txn.get('category_description')
                            }
        except Exception as e:
            print(f"  Warning: Could not load existing transactions: {e}")
    
    # Print merchant lookup stats
    if merchant_category_lookup:
        print(f"  Built merchant category lookup with {len(merchant_category_lookup)} merchants")
    
    # Process all CSV files
    csv_files = sorted(csv_dir.glob('*.csv'))
    print(f"  Found {len(csv_files)} CSV file(s)")
    
    if not csv_files:
        print(f"  No CSV files found")
        return
    
    # Determine account type from first CSV file (to know which format to use)
    # Try to detect from folder name or existing transactions
    detected_account_type = None
    if existing_transactions:
        # Check if existing transactions have card numbers (credit card) or account numbers (checking)
        has_cards = any(t.get('card') for t in existing_transactions)
        if has_cards:
            detected_account_type = 'CREDITCARD'
        else:
            detected_account_type = 'CHECKING'
    else:
        # Try to detect from CSV format
        sample_csv = parse_csv_file(csv_files[0])
        if sample_csv:
            if sample_csv[0].get('csv_format') == 'credit_card':
                detected_account_type = 'CREDITCARD'
            else:
                detected_account_type = 'CHECKING'
    
    if not detected_account_type:
        detected_account_type = 'CHECKING'  # Default to checking
    
    print(f"  Detected account type (from CSV): {detected_account_type}")
    
    # Extract account ID from folder name or existing transactions
    account_id = None
    if existing_transactions:
        account_id = existing_transactions[0].get('account')
    
    if not account_id:
        # Try to extract from CSV file name or use folder name
        # For checking accounts, CSV might have account number in filename
        # For credit cards, might have card number in filename
        if detected_account_type == 'CHECKING':
            # Try to extract from filename like "01-0142-0771521-00_Transactions_2025-07.csv"
            filename_match = re.search(r'(\d{2}-\d{4}-\d{7}-\d{2})', csv_files[0].name)
            if filename_match:
                account_id = filename_match.group(1)
        else:
            # Credit card - try to extract card number from filename
            filename_match = re.search(r'(\d{4}-xxxx-xxxx-\d{4})', csv_files[0].name)
            if filename_match:
                account_id = filename_match.group(1).replace('xxxx', '****')
        
        if not account_id:
            # Fallback: use folder name
            account_id = account_name.replace(' ', '-')
    
    print(f"  Account ID: {account_id}")
    
    # Parse all CSV files
    all_csv_transactions = []
    for csv_file in csv_files:
        print(f"    Processing {csv_file.name}...")
        csv_txns = parse_csv_file(csv_file, detected_account_type)
        # Add source file to each transaction
        for txn in csv_txns:
            txn['source_file'] = csv_file.name
        print(f"      Found {len(csv_txns)} transaction(s)")
        all_csv_transactions.extend(csv_txns)
    
    if not all_csv_transactions:
        print(f"  No transactions found in CSV files")
        return
    
    print(f"  Total transactions from CSV: {len(all_csv_transactions)}")
    
    # Process transactions file by file
    # This allows duplicates WITHIN the same file (legitimate separate transactions)
    # but prevents duplicates ACROSS different files (overlapping date ranges)
    # 
    # Matching logic: If File 1 has 2 duplicates and File 2 has 3 duplicates of the same transaction:
    # - File 1: Both saved (2 total)
    # - File 2: First 2 match File 1 → skipped, remaining 1 kept (3-2=1)
    processed_transactions = []
    skipped_count = 0
    duplicate_count = 0
    updated_existing_count = 0  # Count of existing transactions updated with new data
    skipped_by_id = []  # Track transactions skipped by ID
    skipped_by_duplicate = []  # Track transactions skipped as duplicates
    reprocessed_existing_ids = set()  # Track IDs of existing transactions being reprocessed (to remove from existing_transactions)
    
    # Track transactions from OTHER files with counts
    # Key: transaction signature tuple, Value: count of how many times it appears in other files
    # This allows one-to-one matching: if File 1 has 2, File 2 can match up to 2, then keep the rest
    transactions_from_other_files = {}  # {signature: count}
    
    # Group transactions by source file
    transactions_by_file = {}
    for csv_txn in all_csv_transactions:
        source_file = csv_txn.get('source_file', '')
        if source_file not in transactions_by_file:
            transactions_by_file[source_file] = []
        transactions_by_file[source_file].append(csv_txn)
    
    # Process files in sorted order
    for source_file in sorted(transactions_by_file.keys()):
        file_transactions = transactions_by_file[source_file]
        print(f"    Processing transactions from {source_file}...")
        
        # Track transaction IDs within this file to handle duplicates
        # If same transaction appears multiple times in same file, make IDs unique
        file_transaction_ids = {}  # {base_id: count}
        
        # Track transactions processed in THIS file (to avoid matching against them)
        # This allows duplicates within the same file while preventing cross-file duplicates
        current_file_composite_keys = []
        current_file_signatures = {}  # Track signatures from current file separately
        
        for csv_txn in file_transactions:
            # Generate base transaction ID from composite key
            base_transaction_id = generate_transaction_id_from_csv(
                account_id=account_id,
                transaction_date=csv_txn.get('transaction_date', ''),
                amount=csv_txn.get('amount', 0.0),
                merchant=csv_txn.get('merchant', ''),
                card=csv_txn.get('card'),
                reference=csv_txn.get('reference'),
                code=csv_txn.get('code'),
            )
            
            # Handle duplicates within the same file by adding sequence number
            # This ensures duplicates within a file get unique IDs while maintaining
            # the same base ID for cross-file matching
            if base_transaction_id not in file_transaction_ids:
                file_transaction_ids[base_transaction_id] = 0
            file_transaction_ids[base_transaction_id] += 1
            sequence = file_transaction_ids[base_transaction_id]
            
            # If this is a duplicate within the file (sequence > 1), append sequence to ID
            # This makes the ID unique while keeping the base ID for matching
            if sequence > 1:
                transaction_id = f"{base_transaction_id}_dup{sequence}"
            else:
                transaction_id = base_transaction_id
            
            # Check if ID already exists in saved transactions
            # If it exists, check if it has a null category - if so, we still need to process it
            existing_txn = None
            if sequence == 1:
                # For first occurrence, check both full ID and base ID
                if transaction_id in existing_ids:
                    existing_txn = existing_transactions_by_id.get(transaction_id)
                elif base_transaction_id in existing_ids:
                    existing_txn = existing_transactions_by_id.get(base_transaction_id)
            else:
                # For duplicates within file (sequence > 1), only check the full ID
                if transaction_id in existing_ids:
                    existing_txn = existing_transactions_by_id.get(transaction_id)
            
            # If transaction exists, check if it needs category generation
            if existing_txn:
                # Check if category is null/empty, "Uncategorized", or is an old category that needs reprocessing
                category = existing_txn.get('category')
                old_categories_to_reprocess = ['Food & Dining', 'Healthcare', 'Personal Care']
                
                # Treat "Uncategorized" the same as null/empty - it means the transaction needs a category
                needs_category = (
                    not category or 
                    (isinstance(category, str) and category.strip() == '') or 
                    category == 'Uncategorized' or
                    category in old_categories_to_reprocess
                )
                
                # Also check if it's a transfer - transfers don't need categories
                is_transfer_existing = existing_txn.get('is_transfer', False)
                
                if sequence == 1 and base_transaction_id != transaction_id:
                        reprocessed_existing_ids.add(base_transaction_id)
                elif not needs_category and not is_transfer_existing:
                    # Has valid category (not Uncategorized) and not a transfer - skip it
                    skipped_count += 1
                    skipped_by_id.append({
                        'id': transaction_id,
                        'date': csv_txn.get('transaction_date', ''),
                        'amount': csv_txn.get('amount', 0.0),
                        'merchant': csv_txn.get('merchant', ''),
                        'source_file': csv_txn.get('source_file', ''),
                        'reason': 'ID already exists in saved transactions with valid category'
                    })
                    continue  # Skip this transaction - it already has a valid category
            
            # If we get here, we need to process this transaction
            # Mark this ID for removal from existing_transactions (we're creating a new version)
            reprocessed_existing_ids.add(transaction_id)
            if sequence == 1 and base_transaction_id != transaction_id:
                reprocessed_existing_ids.add(base_transaction_id)
            
            # Check for duplicates against:
            # 1. Previously saved transactions (from existing_composite_keys) - these are from OTHER files
            # 2. Transactions from OTHER files (from transactions_from_other_files)
            # BUT NOT against transactions from the same file (allow duplicates within file)
            # 
            # Matching logic: One-to-one matching across files
            # If File 1 has 2 duplicates and File 2 has 3 duplicates of the same transaction:
            # - File 1: Both saved (no cross-file check yet)
            # - File 2: First 2 match File 1 → skipped, remaining 1 kept (3-2=1)
            is_duplicate = False
            matched_existing_txn = None  # Track which existing transaction was matched
            
            # Create signature for matching (use normalized account ID for consistency)
            normalized_account_for_match = normalize_account_for_signature(account_id)
            txn_signature = (
                normalized_account_for_match,
                csv_txn.get('transaction_date', ''),
                round(csv_txn.get('amount', 0.0), 2),
                normalize_merchant_name(csv_txn.get('merchant', '')),
                csv_txn.get('card') or '',
                csv_txn.get('reference') or '',
                csv_txn.get('code') or '',
            )
            
            # Check against saved transactions (from OTHER files only)
            # existing_composite_keys contains transactions from previously saved files,
            # NOT from the current file being processed
            # We do NOT check current_file_composite_keys because we want to allow
            # duplicates within the same file
            # IMPORTANT: Skip duplicate check if this transaction is being reprocessed (already in existing_transactions)
            if transaction_id not in reprocessed_existing_ids and base_transaction_id not in reprocessed_existing_ids:
                for existing_key in existing_composite_keys:
                    if is_duplicate_transaction(csv_txn, existing_key):
                        is_duplicate = True
                        duplicate_count += 1
                        # Try to find the matching existing transaction to preserve categories
                        if txn_signature in existing_transactions_by_signature:
                            matched_existing_txn = existing_transactions_by_signature[txn_signature]
                        # Track this skipped duplicate
                        skipped_by_duplicate.append({
                            'id': transaction_id,
                            'date': csv_txn.get('transaction_date', ''),
                            'amount': csv_txn.get('amount', 0.0),
                            'merchant': csv_txn.get('merchant', ''),
                            'card': csv_txn.get('card', ''),
                            'reference': csv_txn.get('reference', ''),
                            'code': csv_txn.get('code', ''),
                            'source_file': csv_txn.get('source_file', ''),
                            'reason': 'Duplicate transaction found in previously saved transactions',
                            'matched_existing_id': matched_existing_txn.get('id') if matched_existing_txn else None
                        })
                        break
            
            # Check against transactions from other files (already processed)
            # Use one-to-one matching: if File 1 has 2, File 2 can match up to 2, then keep the rest
            # IMPORTANT: Use base_transaction_id for matching, not the sequence-numbered ID
            # This ensures duplicates within a file can still match against other files
            if not is_duplicate:
                # Check if this signature exists in OTHER files (not current file) AND we haven't exceeded the count
                # We check transactions_from_other_files which only contains transactions from previously processed files
                # We do NOT check current_file_signatures because we want to allow duplicates within the same file
                if txn_signature in transactions_from_other_files:
                    # This transaction exists in other files
                    # Check if we've already matched all available instances from other files
                    available_count = transactions_from_other_files[txn_signature]
                    if available_count > 0:
                        # Match this one: decrement the count and skip it
                        transactions_from_other_files[txn_signature] = available_count - 1
                        is_duplicate = True
                        duplicate_count += 1
                        # Track this skipped duplicate
                        skipped_by_duplicate.append({
                            'id': transaction_id,
                            'date': csv_txn.get('transaction_date', ''),
                            'amount': csv_txn.get('amount', 0.0),
                            'merchant': csv_txn.get('merchant', ''),
                            'card': csv_txn.get('card', ''),
                            'reference': csv_txn.get('reference', ''),
                            'code': csv_txn.get('code', ''),
                            'source_file': csv_txn.get('source_file', ''),
                            'reason': f'Duplicate transaction found in other CSV files (matched {available_count} of {available_count + 1} instances)'
                        })
                    # If available_count is 0, we've already matched all from other files,
                    # so this one is kept (it's an extra duplicate in the current file)
            
            # If duplicate was found in existing saved transactions, update the existing transaction
            # with new data (like source_file) while preserving ALL categorization fields
            if is_duplicate and matched_existing_txn:
                # IMPORTANT: matched_existing_txn is a reference to the transaction in existing_transactions
                # Modifying it modifies the original, so ALL fields (including categories) are preserved
                # We only update metadata fields like source_file, never categorization fields
                
                # Preserve all categorization fields explicitly (these should never be overwritten)
                preserved_category = matched_existing_txn.get('category')
                preserved_identified_business = matched_existing_txn.get('identified_business')
                preserved_category_description = matched_existing_txn.get('category_description')
                preserved_categorized = matched_existing_txn.get('categorized', False)
                preserved_categorized_at = matched_existing_txn.get('categorized_at')
                
                # Update source file if not already present
                if csv_txn.get('source_file') and csv_txn.get('source_file') not in (matched_existing_txn.get('source_file') or ''):
                    # Add source file if not already present
                    existing_sources = matched_existing_txn.get('source_files', [])
                    if not existing_sources:
                        # Migrate single source_file to source_files array
                        if matched_existing_txn.get('source_file'):
                            existing_sources = [matched_existing_txn.get('source_file')]
                    if csv_txn.get('source_file') not in existing_sources:
                        existing_sources.append(csv_txn.get('source_file'))
                        matched_existing_txn['source_files'] = existing_sources
                        updated_existing_count += 1
                
                # Ensure categorization fields are still present (should be, but double-check)
                matched_existing_txn['category'] = preserved_category
                matched_existing_txn['identified_business'] = preserved_identified_business
                matched_existing_txn['category_description'] = preserved_category_description
                matched_existing_txn['categorized'] = preserved_categorized
                matched_existing_txn['categorized_at'] = preserved_categorized_at
                
                continue
            
            if is_duplicate:
                continue
            
            # Get transfer and credit status from CSV parsing (already correctly set)
            # Checking: Type "Transfer" = transfer, negative amount = credit
            # Credit Card: Type "C" = transfer (filtered out), Type "D" = expense
            is_transfer_txn = csv_txn.get('is_transfer', False)
            is_credit = csv_txn.get('is_credit', False)
            
            # Initialize category fields
            category = None
            identified_business = None
            category_description = None
            categorized = False
            categorized_at = None
            needs_category_generation = False
            
            # If we found an existing transaction, check if we should preserve its category
            if existing_txn:
                existing_category = existing_txn.get('category')
                old_categories_to_reprocess = ['Food & Dining', 'Healthcare', 'Personal Care']
                
                # Normal case - check if category needs to be generated
                existing_needs_category = (
                    not existing_category or 
                    (isinstance(existing_category, str) and existing_category.strip() == '') or 
                    existing_category == 'Uncategorized' or
                    existing_category in old_categories_to_reprocess
                )
                
                if existing_needs_category and not existing_txn.get('is_transfer', False):
                    # Normal case: needs category and not a transfer
                    needs_category_generation = True
                else:
                    # Has valid category - preserve it
                    category = existing_category
                    identified_business = existing_txn.get('identified_business')
                    category_description = existing_txn.get('category_description')
                    categorized = existing_txn.get('categorized', False)
                    categorized_at = existing_txn.get('categorized_at')
            else:
                # New transaction - needs category generation unless it's a transfer
                if not is_transfer_txn:
                    needs_category_generation = True
            
            # Step 1: Check merchant-based category matching
            # Look for existing transactions with the same merchant name that have a category
            # Check if we need merchant matching (no category or Uncategorized)
            needs_merchant_match = (
                not category or 
                (isinstance(category, str) and category.strip() == '') or 
                category == 'Uncategorized'
            )
            if needs_merchant_match:
                merchant = csv_txn.get('merchant', '').strip()
                if merchant:
                    normalized_merchant = normalize_merchant_name(merchant)
                            if normalized_merchant in merchant_category_lookup:
                        # Found a matching merchant with a category - reuse it
                        merchant_match = merchant_category_lookup[normalized_merchant]
                        matched_category = merchant_match['category']
                        # Don't use merchant matching if the category is "Uncategorized" - let AI handle it
                        if matched_category and matched_category != 'Uncategorized':
                            category = matched_category
                            if not identified_business and merchant_match.get('identified_business'):
                                identified_business = merchant_match['identified_business']
                            if not category_description and merchant_match.get('category_description'):
                                category_description = merchant_match['category_description']
                            categorized = True
                            categorized_at = datetime.now().isoformat()
                            needs_category_generation = False
                            categories_merchant_matched_count += 1  # Count as merchant match
                        # If matched category is "Uncategorized", don't use it - let it go to AI
            
            # Step 3: Only use AI if still no category (needs_category_generation is still True)
            
            # Create processed transaction
            final_merchant = csv_txn.get('merchant', '').strip()
            
            # Build transaction_context - prioritize existing transaction fields
            if existing_txn:
                # For existing transactions, prioritize existing fields (they may have correct code/reference)
                existing_code = existing_txn.get('code') or ''
                existing_ref = existing_txn.get('reference') or ''
                
                transaction_context = {
                    'details': existing_txn.get('transaction_context', {}).get('details', '') if isinstance(existing_txn.get('transaction_context'), dict) else '',
                    'particulars': existing_txn.get('transaction_context', {}).get('particulars', '') if isinstance(existing_txn.get('transaction_context'), dict) else '',
                    'code': existing_code,
                    'reference': existing_ref,
                }
                
            else:
                # New transaction - use CSV's transaction_context or build from CSV fields
                transaction_context = csv_txn.get('transaction_context')
                if not transaction_context:
                    transaction_context = {
                        'details': '',
                        'particulars': '',
                        'code': csv_txn.get('code') or '',
                        'reference': csv_txn.get('reference') or '',
                    }
            
            processed_txn = {
                'id': transaction_id,
                'account': account_id,
                'card': csv_txn.get('card'),
                'amount': csv_txn.get('amount', 0.0),
                'merchant': final_merchant,
                'identified_business': identified_business,
                'transaction_date': csv_txn.get('transaction_date', ''),
                'processed_date': csv_txn.get('processed_date') or csv_txn.get('transaction_date', ''),
                'foreign_currency': csv_txn.get('foreign_currency', ''),
                'source_file': csv_txn.get('source_file', ''),
                'categorized': categorized,
                'category': category,
                'category_description': category_description,
                'categorized_at': categorized_at,
                'is_transfer': is_transfer_txn,
                'is_credit': is_credit,
                'account_type': account_type_label,
                'reference': csv_txn.get('reference') or (existing_txn.get('reference') if existing_txn else None),
                'code': csv_txn.get('code') or (existing_txn.get('code') if existing_txn else None),
                'transaction_context': transaction_context,  # Preserve context for categorization
            }
            
            # Mark for category generation if needed (will be processed later)
            if needs_category_generation:
                processed_txn['_needs_category'] = True
            
            processed_transactions.append(processed_txn)
            
            # Create signature for this transaction (for cross-file duplicate detection)
            # We'll add this to transactions_from_other_files AFTER processing all transactions in the current file
            # This ensures duplicates within the same file are allowed
            txn_signature = (
                account_id,
                processed_txn.get('transaction_date', ''),
                round(processed_txn.get('amount', 0.0), 2),
                normalize_merchant_name(processed_txn.get('merchant', '')),
                processed_txn.get('card') or '',
                processed_txn.get('reference') or '',
                processed_txn.get('code') or '',
            )
            
            # Track this transaction for adding to transactions_from_other_files AFTER processing the file
            # Use base signature (without sequence number) for cross-file matching
            # Increment the count for this signature (allows one-to-one matching)
            # If File 1 has 2 duplicates, count will be 2
            # When File 2 processes, it can match up to 2, then keep the rest
            base_signature = (
                account_id,
                processed_txn.get('transaction_date', ''),
                round(processed_txn.get('amount', 0.0), 2),
                normalize_merchant_name(processed_txn.get('merchant', '')),
                processed_txn.get('card') or '',
                processed_txn.get('reference') or '',
                processed_txn.get('code') or '',
            )
            # Store in current_file_composite_keys for later addition to transactions_from_other_files
            # We'll add these AFTER processing all transactions in the current file
            # Track this signature for the current file (will be added to transactions_from_other_files later)
            if base_signature not in current_file_signatures:
                current_file_signatures[base_signature] = 0
            current_file_signatures[base_signature] += 1
            
            # Add to current_file_composite_keys (for tracking, not for duplicate checking)
            # We track these separately so we can add them to existing_composite_keys
            # AFTER processing all transactions in the current file
            # This ensures duplicates within the same file are allowed
            current_file_composite_keys.append({
                'account': account_id,
                'transaction_date': processed_txn.get('transaction_date'),
                'amount': processed_txn.get('amount', 0.0),
                'merchant': processed_txn.get('merchant', ''),
                'card': processed_txn.get('card'),
                'reference': processed_txn.get('reference'),
                'code': processed_txn.get('code'),
            })
        
        # After processing all transactions in the current file, add them to existing_composite_keys
        # This allows future files to check against them, but ensures duplicates within the same file are allowed
        existing_composite_keys.extend(current_file_composite_keys)
        current_file_composite_keys = []  # Reset for next file
        
        # Add current file signatures to transactions_from_other_files AFTER processing all transactions
        # This ensures duplicates within the same file are allowed (they won't match against each other)
        for signature, count in current_file_signatures.items():
            if signature not in transactions_from_other_files:
                transactions_from_other_files[signature] = 0
            transactions_from_other_files[signature] += count
        current_file_signatures = {}  # Reset for next file
    
    if skipped_count > 0:
        print(f"  Skipped {skipped_count} existing transaction(s) (by ID)")
    if duplicate_count > 0:
        print(f"  Skipped {duplicate_count} duplicate transaction(s) (by composite key)")
    if updated_existing_count > 0:
        print(f"  Updated {updated_existing_count} existing transaction(s) with new source file info (categories preserved)")
    
    # Show detailed skip information if verbose mode is enabled
    if verbose:
        if skipped_by_id:
            print(f"\n  === Transactions Skipped by ID ({len(skipped_by_id)}) ===")
            for txn in skipped_by_id[:20]:  # Show first 20
                print(f"    - {txn['date']} | ${txn['amount']:.2f} | {txn['merchant'][:50]} | ID: {txn['id']}")
                print(f"      File: {txn['source_file']} | Reason: {txn['reason']}")
            if len(skipped_by_id) > 20:
                print(f"    ... and {len(skipped_by_id) - 20} more")
        
        if skipped_by_duplicate:
            print(f"\n  === Transactions Skipped as Duplicates ({len(skipped_by_duplicate)}) ===")
            for txn in skipped_by_duplicate[:20]:  # Show first 20
                match_info = f" (matched ID: {txn['matched_existing_id']})" if txn.get('matched_existing_id') else ""
                print(f"    - {txn['date']} | ${txn['amount']:.2f} | {txn['merchant'][:50]}")
                print(f"      File: {txn['source_file']} | Reason: {txn['reason']}{match_info}")
                if txn.get('card'):
                    print(f"      Card: {txn['card']}")
                if txn.get('reference'):
                    print(f"      Reference: {txn['reference']}")
                if txn.get('code'):
                    print(f"      Code: {txn['code']}")
            if len(skipped_by_duplicate) > 20:
                print(f"    ... and {len(skipped_by_duplicate) - 20} more")
    
    if not processed_transactions:
        print(f"  No new transactions to process")
        print(f"  Total transactions: {len(existing_transactions)}")
        return
    
    
    # Generate categories for transactions that need them
    # Collect transactions that need category generation
    transactions_needing_categories = []
    for txn in processed_transactions:
        if txn.get('_needs_category') and not txn.get('is_transfer', False):
            transactions_needing_categories.append(txn)
    
    # Set default category for transfers that need categories (they're excluded from LLM processing)
    for txn in processed_transactions:
        if txn.get('_needs_category') and txn.get('is_transfer', False):
            txn['category'] = 'Uncategorized'
            txn['categorized'] = False
            txn.pop('_needs_category', None)
    if transactions_needing_categories:
        # Check if OpenAI is available
        if not OPENAI_AVAILABLE or openai_client is None:
            print(f"  Warning: OpenAI client not available. Categories will not be generated.")
            print(f"  Install openai library and set OPENAI_API_KEY to generate categories.")
        else:
            # Process transactions one at a time (sequentially)
            # datetime is already imported at the top of the file
            import signal
            import time
            
            # Flag to signal to stop
            stop_processing = False
            
            def signal_handler(signum, frame):
                """Handle Ctrl+C gracefully."""
                nonlocal stop_processing
                print("\n\n  [INTERRUPTED] Stopping processing... (Press Ctrl+C again to force quit)")
                stop_processing = True
            
            # Register signal handler for Ctrl+C
            signal.signal(signal.SIGINT, signal_handler)
            
            try:
                # Process transactions sequentially (one at a time)
                for txn_num, txn in enumerate(transactions_needing_categories, 1):
                    if stop_processing:
                        break
                    
                    try:
                        merchant = txn.get('merchant', '')
                        amount = txn.get('amount', 0.0)
                        date = txn.get('transaction_date', '')
                        
                        # Get transaction context for checking accounts
                        transaction_context = txn.get('transaction_context')
                        
                        # Check if transaction_context is empty (all fields are empty strings)
                        is_empty_context = False
                        if transaction_context:
                            if isinstance(transaction_context, dict):
                                is_empty_context = (
                                    (transaction_context.get('code') or '').strip() == '' and
                                    (transaction_context.get('reference') or '').strip() == '' and
                                    (transaction_context.get('details') or '').strip() == '' and
                                    (transaction_context.get('particulars') or '').strip() == ''
                                )
                            else:
                                is_empty_context = True
                        else:
                            is_empty_context = True
                        
                        # If transaction_context is empty or doesn't exist, build it from transaction's code/reference fields
                        if is_empty_context:
                            code_value = txn.get('code')
                            ref_value = txn.get('reference')
                            
                            code_str = (code_value or '').strip() if code_value is not None else ''
                            ref_str = (ref_value or '').strip() if ref_value is not None else ''
                            
                            transaction_context = {
                                'details': '',
                                'particulars': '',
                                'code': code_str,
                                'reference': ref_str,
                            }
                        
                        # Process single transaction using individual API
                        result = identify_and_categorize_transaction(
                            merchant,
                            amount,
                            date,
                            account_type_label,
                            project_root,
                            verbose=False,
                            transaction_context=transaction_context
                        )
                        
                        # Update transaction with results
                        if result:
                            if result.get('identified_business'):
                                txn['identified_business'] = result['identified_business']
                            
                            # Always set a category - use generated one or default to "Uncategorized"
                            generated_category = result.get('category')
                            if generated_category:
                                txn['category'] = generated_category
                                txn['categorized'] = True
                                txn['categorized_at'] = datetime.now().isoformat()
                                categories_generated_count += 1
                            else:
                                # No category generated - set default
                                txn['category'] = 'Uncategorized'
                                txn['categorized'] = False
                            
                            if result.get('category_description'):
                                txn['category_description'] = result['category_description']
                            
                            # Remove the marker
                            txn.pop('_needs_category', None)
                            
                            # Save progress every 5 transactions
                            if txn_num % 5 == 0 or txn_num == len(transactions_needing_categories):
                                _save_progress_incremental(existing_transactions, processed_transactions, reprocessed_existing_ids, account_type_label, output_file)
                        else:
                            # No result from AI - mark as uncategorized
                            txn['category'] = 'Uncategorized'
                            txn['categorized'] = False
                            txn.pop('_needs_category', None)
                        
                        # Show final outcome
                        final_name = txn.get('identified_business') or merchant
                        final_category = txn.get('category', 'Uncategorized')
                        final_amount = txn.get('amount', 0.0)
                        is_transfer = txn.get('is_transfer', False)
                        is_credit = txn.get('is_credit', False)
                        
                        transfer_str = " [Transfer]" if is_transfer else ""
                        credit_str = " [Credit]" if is_credit else ""
                        print(f"  {final_name[:50]:<50} | {final_category:<25} | ${final_amount:>10.2f}{transfer_str}{credit_str}")
                            
                    except KeyboardInterrupt:
                        stop_processing = True
                        break
                    except Exception as e:
                        txn['category'] = 'Uncategorized'
                        txn['categorized'] = False
                        txn.pop('_needs_category', None)
                        # Show error outcome
                        final_name = txn.get('merchant', 'Unknown')
                        print(f"  {final_name[:50]:<50} | {'Error: ' + str(e)[:20]:<25} | ${txn.get('amount', 0.0):>10.2f}")
                        
            except KeyboardInterrupt:
                stop_processing = True
            
            # Final save
            _save_progress_incremental(existing_transactions, processed_transactions, reprocessed_existing_ids, account_type_label, output_file)
            
            if stop_processing:
                print(f"\n  [STOPPED] Processing was interrupted.")
            else:
                print(f"  [OK] Generated categories for {categories_generated_count} transaction(s)")
    
    # Show category preservation summary
    if categories_merchant_matched_count > 0:
        print(f"  [OK] Reused {categories_merchant_matched_count} category/categories from merchant matching")
    if categories_generated_count > 0:
        print(f"  [OK] Generated {categories_generated_count} category/categories using AI")
    
    # Remove existing transactions that were reprocessed (they're now in processed_transactions with updated categories)
    existing_transactions_filtered = [
        txn for txn in existing_transactions 
        if txn.get('id') not in reprocessed_existing_ids
    ]
    
    # Merge with existing transactions (excluding reprocessed ones)
    all_processed = existing_transactions_filtered + processed_transactions
    
    # Ensure account_type is ALWAYS set correctly based on account configuration
    # This is the source of truth - don't rely on what might be in the transaction
    # Also ensure all transactions have a category (never null)
    for txn in all_processed:
        # Always set account_type from configuration (ensures it's always correct)
        if txn.get('account_type') != account_type_label:
            txn['account_type'] = account_type_label
        # Ensure category is never null - default to "Uncategorized" if missing
        if not txn.get('category'):
            txn['category'] = 'Uncategorized'
        # Remove any temporary markers
        txn.pop('_needs_category', None)
    
    # Deduplicate by ID (final check)
    seen_ids = set()
    unique_transactions = []
    for txn in all_processed:
        txn_id = txn.get('id')
        if txn_id and txn_id not in seen_ids:
            seen_ids.add(txn_id)
            unique_transactions.append(txn)
    
    # Sort by transaction date (newest first)
    unique_transactions.sort(key=lambda x: x.get('transaction_date', ''), reverse=True)
    
    # Assign transactions to entities based on credit cards
    assigned_count = assign_transactions_to_entities_by_card(unique_transactions, project_root)
    if assigned_count > 0:
        print(f"  [OK] Assigned {assigned_count} transaction(s) to entities based on credit cards")
    
    # Save transactions
    print()
    if processed_transactions:
        print(f"  Saving {len(processed_transactions)} new transaction(s)...")
        save_json_safely(output_file, unique_transactions)
        print(f"  [OK] Added {len(processed_transactions)} new transaction(s)")
        print(f"  [OK] Total transactions: {len(unique_transactions)}")
    else:
        print(f"  No new transactions to add")
        print(f"  Total transactions: {len(unique_transactions)}")


def main():
    """Main processing function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Process CSV transaction files')
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Show detailed information about skipped transactions')
    args = parser.parse_args()
    
    # Set verbose mode in environment for access in process_account
    if args.verbose:
        os.environ['VERBOSE'] = '1'
    
    project_root = Path(__file__).parent
    data_dir = project_root / 'data'
    
    if not data_dir.exists():
        print(f"Error: Data directory not found: {data_dir}")
        return
    
    # Create output directory
    output_dir = project_root / 'storage' / 'transactions'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all account folders
    account_folders = [d for d in data_dir.iterdir() if d.is_dir()]
    
    if not account_folders:
        print("No account folders found in data/")
        return
    
    print("=" * 60)
    print("Transaction Processor")
    if args.verbose:
        print("Verbose mode: ON")
    print("=" * 60)
    print(f"Found {len(account_folders)} account folder(s)")
    
    for account_folder in sorted(account_folders):
        process_account(account_folder, project_root)
    
    print("\n" + "=" * 60)
    print("Processing complete!")
    print("=" * 60)

if __name__ == '__main__':
    main()

