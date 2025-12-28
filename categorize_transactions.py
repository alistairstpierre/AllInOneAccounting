#!/usr/bin/env python3
"""
Transaction Processor

Processes OFX and CSV files from data/{AccountName}/ folders and converts them
into transaction JSON files in storage/transactions/.

Supports:
- Debit/Checking accounts (OFX files)
- Credit card accounts (OFX + CSV files)
- Account type detection (Personal vs Business) from storage/accounts.json
- Transfer detection for checking accounts
- Card number assignment from CSV files
"""

import json
import re
import csv
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from get_account_type import get_account_type, is_business_account
import os
import time
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

def build_llm_prompt(merchant: str, amount: float, date: str, account_type: str, prompt_template: str, categories: List[str]) -> str:
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
    
    # Build batch prompt
    transactions_list = "\n".join([
        f"{i+1}. Merchant: {t['merchant']}, Amount: ${t['amount']:.2f}, Date: {t['date']}"
        for i, t in enumerate(valid_transactions)
    ])
    
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
            # Debug: Show first 500 chars of response if parsing fails
            if len(valid_transactions) > 0:
                debug_response = response_text[:500] if len(response_text) > 500 else response_text
                # Only show if we suspect parsing issues (will check after parsing)
        
        # Parse batch response - try to extract each transaction's results
        results = []
        for i, txn in enumerate(valid_transactions):
            # Try multiple strategies to find this transaction's results
            txn_num = i + 1
            txn_merchant = txn['merchant'][:40]
            
            # Strategy 1: Look for transaction number
            pattern = rf'{txn_num}\.?\s+Merchant:\s*{re.escape(txn_merchant)}.*?Business Name:\s*(.+?)(?:\n|Category:)'
            business_match = re.search(pattern, response_text, re.IGNORECASE | re.DOTALL)
            
            # Strategy 2: Look for merchant name directly
            if not business_match:
                pattern = rf'{re.escape(txn_merchant)}.*?Business Name:\s*(.+?)(?:\n|Category:)'
                business_match = re.search(pattern, response_text, re.IGNORECASE | re.DOTALL)
            
            # Strategy 3: Look for numbered list item
            if not business_match:
                pattern = rf'{txn_num}\.?\s+.*?Business Name:\s*(.+?)(?:\n|Category:)'
                business_match = re.search(pattern, response_text, re.IGNORECASE | re.DOTALL)
            
            business_name = business_match.group(1).strip() if business_match else None
            
            # Extract category and reasoning
            if business_match:
                # Find the section for this transaction
                start_pos = business_match.start()
                # Look for next transaction or end of response
                next_txn_match = re.search(rf'{txn_num + 1}\.?\s+', response_text[start_pos:], re.IGNORECASE)
                if next_txn_match:
                    section = response_text[start_pos:start_pos + next_txn_match.start()]
                else:
                    section = response_text[start_pos:]
                
                category_match = re.search(r'Category:\s*(.+?)(?:\n|Reasoning:)', section, re.IGNORECASE)
                category = category_match.group(1).strip() if category_match else None
                
                if category_match:
                    reasoning_match = re.search(r'Reasoning:\s*(.+?)(?:\n\n|\n\d+\.|\Z)', section[category_match.end():], re.IGNORECASE | re.DOTALL)
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
                # If parsing failed, show a snippet of the response for debugging
                if not business_name and not category:
                    # Try to find any mention of this merchant in the response
                    merchant_snippet = txn['merchant'][:30]
                    if merchant_snippet.lower() in response_text.lower():
                        # Find the section mentioning this merchant
                        idx = response_text.lower().find(merchant_snippet.lower())
                        snippet = response_text[max(0, idx-50):idx+200]
                        print(f"      [LLM] Debug - Response snippet for '{txn['merchant'][:40]}': ...{snippet}...")
        
        return transfer_results + results
        
    except Exception as e:
        if verbose:
            print(f"      [LLM] ✗ Error: {e}")
        # Return empty results on error
        return transfer_results + [{'transaction_id': t['transaction_id'], 'identified_business': None, 'category': None, 'category_description': None} for t in valid_transactions]

def identify_and_categorize_transaction(merchant: str, amount: float, date: str, account_type: str, project_root: Path, verbose: bool = True) -> Dict[str, Optional[str]]:
    """
    Identify business name and categorize transaction using LLM.
    
    Args:
        merchant: Merchant name from transaction
        amount: Transaction amount
        date: Transaction date
        account_type: 'Business' or 'Personal'
        project_root: Project root directory
        verbose: Whether to print debug information
    
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
    full_prompt = build_llm_prompt(merchant, amount, date, account_type, prompt_template, categories)
    
    if verbose:
        print(f"      [LLM] Processing: {merchant[:50]} (${amount:.2f}) - {account_type} account")
    
    try:
        # Call OpenAI API
        if verbose:
            print(f"      [LLM] Calling OpenAI API...")
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
        
        if verbose:
            print(f"      [LLM] Response received")
        
        # Parse the response
        result = parse_llm_response(response_text)
        
        # Validate category is in the allowed list
        if result['category'] and result['category'] not in categories:
            if verbose:
                print(f"      [LLM] Warning: Invalid category '{result['category']}', using 'Uncategorized'")
            result['category'] = 'Uncategorized'
        
        if verbose:
            if result['identified_business']:
                print(f"      [LLM] ✓ Identified: {result['identified_business']}")
            if result['category']:
                print(f"      [LLM] ✓ Category: {result['category']}")
            if not result['identified_business'] and not result['category']:
                print(f"      [LLM] ⚠ No results extracted from response")
        
        return result
        
    except Exception as e:
        print(f"      [LLM] ✗ Error: {e}")
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

def parse_ofx_date(date_str: str) -> str:
    """Convert OFX date format (YYYYMMDD) to YYYY-MM-DD."""
    if len(date_str) >= 8:
        return f"{date_str[0:4]}-{date_str[4:6]}-{date_str[6:8]}"
    return date_str

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
    # Allow optional trailing characters (like "Df", "If" suffixes)
    pattern = r'^\d{4}\s+\*{4}\s+\*{4}\s+\d{4}'
    return bool(re.match(pattern, name.strip()))

def extract_card_number(name: str) -> Optional[str]:
    """Extract card number from NAME field (convert spaces to hyphens)."""
    if is_masked_card(name):
        # Extract just the card number part (4 digits, stars, 4 digits)
        # Handle cases like "4037 **** **** 6505 Df" -> "4037-****-****-6505"
        match = re.match(r'^(\d{4}\s+\*{4}\s+\*{4}\s+\d{4})', name.strip())
        if match:
            return match.group(1).replace(' ', '-')
    return None

def is_transfer(memo: str, name: str, account_id: str) -> bool:
    """Detect if a transaction is a transfer based on patterns."""
    if not memo:
        memo = ""
    memo = memo.strip()
    name = name.strip()
    
    # Check for account number pattern in MEMO
    account_pattern = r'\b\d{2}\s+\d{4}\s+\d{7}\s+\d{2}\b'
    if re.search(account_pattern, memo):
        return True
    
    # Check for masked card pattern in MEMO
    card_pattern = r'\d{4}\s*\*{4}\s*\*{4}\s*\d{4}'
    if re.search(card_pattern, memo):
        return True
    
    # Check for transfer keywords
    transfer_keywords = [
        'Transfer',
        'Transfer Debit Transfer',
        'Payment To',
        'Credit To',
        'Account Transfer'
    ]
    memo_lower = memo.lower()
    if any(keyword.lower() in memo_lower for keyword in transfer_keywords):
        return True
    
    # Check if MEMO is very short
    if len(memo) < 5:
        return True
    
    # Check if MEMO is mostly numeric
    if re.match(r'^[\d\s-]+$', memo):
        return True
    
    # Check if NAME matches account number pattern
    account_name_pattern = r'^\d{2}\s+\d{4}\s+\d{7}\s+\d{2}$'
    if re.match(account_name_pattern, name):
        return True
    
    return False

def normalize_merchant_name(merchant: str) -> str:
    """Normalize merchant name for matching."""
    # Remove extra whitespace, lowercase, and normalize
    normalized = merchant.strip().lower()
    # Replace multiple spaces with single space
    normalized = re.sub(r'\s+', ' ', normalized)
    # Remove common location suffixes that might differ between CSV and OFX
    # Keep the core merchant name for matching
    return normalized

def get_ofx_tag_value(content: str, tag_name: str) -> Optional[str]:
    """Extract value from OFX SGML tag. Tags are like <TAG>value on next line."""
    pattern = f'<{tag_name}>([^<\\n]+)'
    match = re.search(pattern, content)
    if match:
        return match.group(1).strip()
    return None

def parse_ofx_file(ofx_path: Path) -> Tuple[Optional[str], Optional[str], List[Dict[str, Any]]]:
    """
    Parse an OFX file and extract account info and transactions.
    OFX files use SGML format where tags don't have closing tags.
    
    Returns:
        (account_id, account_type, transactions)
        account_type: 'CHECKING' or 'CREDITCARD'
    """
    try:
        # Read OFX file
        with open(ofx_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Remove OFX header if present (before <OFX> tag)
        ofx_start = content.find('<OFX>')
        if ofx_start > 0:
            content = content[ofx_start:]
        
        account_id = None
        account_type = None
        transactions = []
        
        # Check for credit card account first (more specific - uses CREDITCARDMSGSRSV1 and CCACCTFROM)
        # Credit cards use CREDITCARDMSGSRSV1 section with CCACCTFROM
        if '<CREDITCARDMSGSRSV1>' in content or '<CCACCTFROM>' in content:
            account_type = 'CREDITCARD'
            # Extract ACCTID from within CCACCTFROM section to avoid conflicts with checking accounts
            ccacctfrom_match = re.search(r'<CCACCTFROM>(.*?)</CCACCTFROM>', content, re.DOTALL)
            if ccacctfrom_match:
                ccacctfrom_content = ccacctfrom_match.group(1)
                acct_id = get_ofx_tag_value(ccacctfrom_content, 'ACCTID')
            else:
                # Fallback: search entire content (but only if we're sure it's a credit card)
                if '<CREDITCARDMSGSRSV1>' in content:
                    acct_id = get_ofx_tag_value(content, 'ACCTID')
            if acct_id:
                account_id = acct_id
        
        # Check for checking/debit account (BANKACCTFROM) - uses BANKMSGSRSV1
        # Only check if we haven't already identified it as a credit card
        if account_type is None and ('<BANKACCTFROM>' in content or '<BANKMSGSRSV1>' in content):
            account_type = 'CHECKING'
            bank_id = get_ofx_tag_value(content, 'BANKID')
            branch_id = get_ofx_tag_value(content, 'BRANCHID')
            acct_id = get_ofx_tag_value(content, 'ACCTID')
            
            if bank_id and branch_id and acct_id:
                account_id = bank_id + branch_id + acct_id
        
        # Extract all STMTTRN transactions
        # Pattern: <STMTTRN>...content...</STMTTRN>
        stmttrn_pattern = r'<STMTTRN>(.*?)</STMTTRN>'
        stmttrn_matches = re.findall(stmttrn_pattern, content, re.DOTALL)
        
        for stmttrn_content in stmttrn_matches:
            fitid = get_ofx_tag_value(stmttrn_content, 'FITID') or ''
            dtposted = get_ofx_tag_value(stmttrn_content, 'DTPOSTED') or ''
            trnamt_str = get_ofx_tag_value(stmttrn_content, 'TRNAMT') or '0'
            trntype = get_ofx_tag_value(stmttrn_content, 'TRNTYPE') or ''
            name = get_ofx_tag_value(stmttrn_content, 'NAME') or ''
            memo = get_ofx_tag_value(stmttrn_content, 'MEMO') or ''
            
            try:
                trnamt = float(trnamt_str)
            except:
                trnamt = 0.0
            
            # Determine if transaction is a credit (income) or debit (expense)
            # Credits: TRNTYPE=CREDIT or DEP, or positive TRNAMT for checking accounts
            # Debits: TRNTYPE=DEBIT, PAYMENT, etc., or negative TRNAMT for checking accounts
            trntype_upper = trntype.upper()
            if account_type == 'CHECKING':
                # For checking accounts:
                # - Credits: TRNTYPE=CREDIT or DEP, or positive TRNAMT
                # - Debits: TRNTYPE=DEBIT, PAYMENT, etc., or negative TRNAMT
                is_credit = (trntype_upper in ['CREDIT', 'DEP'] or trnamt > 0)
            else:
                # For credit cards, all transactions are typically debits (expenses)
                # But we'll check TRNTYPE to be safe
                is_credit = (trntype_upper == 'CREDIT')
            
            # Note: We now track both credits and debits (previously skipped credits)
            # Credits will be filtered from display in the UI but remain in the data
            
            transaction_date = parse_ofx_date(dtposted)
            
            transaction = {
                'fitid': fitid,
                'dtposted': dtposted,
                'transaction_date': transaction_date,
                'amount': abs(trnamt),  # Store as positive (absolute value)
                'trnamt': trnamt,  # Keep original signed value
                'trntype': trntype,
                'is_credit': is_credit,  # Track if this is a credit (income) or debit (expense)
                'name': name.strip(),
                'memo': memo.strip(),
                'account_type': account_type,
            }
            
            transactions.append(transaction)
        
        return account_id, account_type, transactions
    
    except Exception as e:
        print(f"  Error parsing OFX file {ofx_path.name}: {e}")
        return None, None, []

def parse_csv_file(csv_path: Path) -> List[Dict[str, Any]]:
    """Parse a CSV file and extract transactions."""
    transactions = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                transaction_type = row.get('Type', '').strip().upper()
                card = row.get('Card', '').strip()
                amount = row.get('Amount', '').strip()
                details = row.get('Details', '').strip()
                transaction_date = row.get('TransactionDate', '').strip()
                processed_date = row.get('ProcessedDate', '').strip()
                
                # Skip credit/payment transactions (Type "C") - these are payments TO the card, not expenses
                # Only process debit transactions (Type "D") which are actual expenses
                if transaction_type == 'C':
                    continue
                
                try:
                    amount_float = float(amount) if amount else 0.0
                except:
                    amount_float = 0.0
                
                transaction = {
                    'card': card,
                    'amount': amount_float,
                    'merchant': details,
                    'transaction_date': parse_csv_date(transaction_date),
                    'processed_date': parse_csv_date(processed_date),
                }
                
                transactions.append(transaction)
    
    except Exception as e:
        print(f"  Error parsing CSV file {csv_path.name}: {e}")
    
    return transactions

def match_csv_to_ofx(ofx_transaction: Dict, csv_transactions: List[Dict]) -> Optional[str]:
    """Match an OFX transaction to a CSV transaction and return the card number."""
    ofx_merchant = normalize_merchant_name(ofx_transaction.get('name', ''))
    ofx_amount = ofx_transaction.get('amount', 0.0)
    ofx_date = ofx_transaction.get('transaction_date', '')
    
    # Extract core merchant name (first few words, before location)
    # OFX format: "Sushi Bi Limited Wellington Nz" -> "sushi bi limited"
    # CSV format: "Sushi Bi               Wellington    Nz" -> "sushi bi"
    # Try to match on first 2-3 words which are usually the merchant name
    ofx_words = ofx_merchant.split()
    ofx_core = ' '.join(ofx_words[:3]) if len(ofx_words) >= 3 else ofx_merchant
    
    for csv_txn in csv_transactions:
        csv_merchant = normalize_merchant_name(csv_txn.get('merchant', ''))
        csv_amount = csv_txn.get('amount', 0.0)
        csv_date = csv_txn.get('transaction_date', '')
        
        # Extract core merchant name from CSV
        csv_words = csv_merchant.split()
        csv_core = ' '.join(csv_words[:3]) if len(csv_words) >= 3 else csv_merchant
        
        # Match by:
        # 1. Exact normalized merchant match, OR
        # 2. Core merchant name match (first 2-3 words)
        # AND amount must match (within 0.01)
        # AND date must match
        merchant_matches = (
            ofx_merchant == csv_merchant or  # Exact match
            ofx_core == csv_core or  # Core name match
            ofx_merchant.startswith(csv_core) or  # OFX contains CSV core
            csv_merchant.startswith(ofx_core)  # CSV contains OFX core
        )
        
        if (merchant_matches and 
            abs(ofx_amount - csv_amount) < 0.01 and 
            ofx_date == csv_date):
            return csv_txn.get('card')
    
    return None

def process_account(account_folder: Path, project_root: Path) -> None:
    """Process all OFX and CSV files for a single account."""
    account_name = account_folder.name
    print(f"\n{'='*60}")
    print(f"Processing account: {account_name}")
    print(f"{'='*60}")
    
    # Get account type from configuration
    is_business = is_business_account(account_name, project_root)
    account_type_label = "Business" if is_business else "Personal"
    print(f"  Account type: {account_type_label}")
    
    # Show OpenAI status
    if OPENAI_AVAILABLE and openai_client:
        print(f"  OpenAI: ✓ Available (will categorize transactions)")
    else:
        print(f"  OpenAI: ✗ Not available (transactions will not be categorized)")
    
    ofx_dir = account_folder / 'ofx'
    csv_dir = account_folder / 'csv'
    
    if not ofx_dir.exists():
        print(f"  Warning: OFX directory not found: {ofx_dir}")
        return
    
    # Load existing transactions
    output_file = project_root / 'storage' / 'transactions' / f"{account_name}.json"
    existing_transactions = []
    existing_ids = set()
    
    if output_file.exists():
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                existing_transactions = json.load(f)
                existing_ids = {t.get('id') for t in existing_transactions if t.get('id')}
        except:
            pass
    
    # Process all OFX files
    ofx_files = sorted(ofx_dir.glob('*.ofx'))
    print(f"  Found {len(ofx_files)} OFX file(s)")
    
    all_transactions = []
    account_id = None
    detected_account_type = None
    
    for ofx_file in ofx_files:
        print(f"    Processing {ofx_file.name}...")
        file_account_id, file_account_type, file_transactions = parse_ofx_file(ofx_file)
        
        if file_account_id:
            account_id = file_account_id
        if file_account_type:
            detected_account_type = file_account_type
        
        for txn in file_transactions:
            txn['source_file'] = ofx_file.name
            all_transactions.append(txn)
    
    if not account_id:
        print(f"  Error: Could not determine account ID from OFX files")
        return
    
    print(f"  Account ID: {account_id}")
    print(f"  Account type (from OFX): {detected_account_type}")
    if not detected_account_type:
        print(f"  WARNING: Could not detect account type from OFX structure!")
        print(f"    - Checked for BANKACCTFROM/BANKMSGSRSV1 (checking/debit)")
        print(f"    - Checked for CCACCTFROM/CREDITCARDMSGSRSV1 (credit card)")
    
    # Load CSV files if this is a credit card account
    csv_transactions = []
    if detected_account_type == 'CREDITCARD' and csv_dir.exists():
        csv_files = sorted(csv_dir.glob('*.csv'))
        print(f"  Found {len(csv_files)} CSV file(s)")
        for csv_file in csv_files:
            csv_txns = parse_csv_file(csv_file)
            csv_transactions.extend(csv_txns)
    
    # Process transactions
    processed_transactions = []
    sanitized_account_id = sanitize_account_id(account_id)
    
    skipped_count = 0
    total_to_process = len(all_transactions)
    
    # Collect new transactions to process
    new_transactions_to_process = []
    
    print(f"  Processing {total_to_process} transaction(s)...")
    
    for idx, txn in enumerate(all_transactions, 1):
        fitid = txn.get('fitid', '')
        transaction_id = f"{fitid}_{sanitized_account_id}"
        
        # Skip if already exists
        if transaction_id in existing_ids:
            skipped_count += 1
            continue
        
        new_transactions_to_process.append((idx, txn, transaction_id))
    
    if skipped_count > 0:
        print(f"  Skipped {skipped_count} existing transaction(s)")
    
    if not new_transactions_to_process:
        print(f"  No new transactions to process")
        print(f"  Total transactions: {len(existing_transactions)}")
        return
    
    print(f"  Processing {len(new_transactions_to_process)} new transaction(s)...")
    print()
    
    # First, prepare all transaction data (merchant names, etc.)
    prepared_transactions = []
    for idx, txn, transaction_id in new_transactions_to_process:
        # Process based on account type
        if detected_account_type == 'CHECKING':
            # Debit account processing
            name = txn.get('name', '')
            memo = txn.get('memo', '')
            
            # Check if NAME is a masked card
            card_number = extract_card_number(name)
            
            # Determine merchant name
            if card_number:
                # NAME is a card, merchant comes from MEMO
                merchant = memo
                if merchant.startswith('Visa Purchase'):
                    merchant = merchant.replace('Visa Purchase', '', 1).strip()
                if 'FXAmnt=' in merchant:
                    merchant = merchant.split('FXAmnt=')[0].strip()
                merchant = re.sub(r'^\d+\s+\d+\.?\d*\s+', '', merchant).strip()
                merchant = re.sub(r'\s+\d+\.?\d+\s*$', '', merchant).strip()
                merchant = re.sub(r'\s+\d+\s*$', '', merchant).strip()
                merchant = re.sub(r'\s+\*[A-Z0-9]+$', '', merchant).strip()
                merchant = re.sub(r'\s+', ' ', merchant).strip()
            else:
                merchant = name
            
            # Detect transfers
            is_transfer_txn = is_transfer(memo, name, account_id)
            if is_transfer_txn:
                merchant = "Account Transfer"
            
            prepared_transactions.append({
                'transaction_id': transaction_id,
                'txn': txn,  # txn already contains is_credit from parse_ofx_file
                'merchant': merchant.strip(),
                'card_number': card_number,
                'is_transfer': is_transfer_txn,
                'foreign_currency': memo if card_number else '',
            })
        
        else:  # CREDITCARD
            # Credit card processing
            name = txn.get('name', '')
            card_number = match_csv_to_ofx(txn, csv_transactions)
            
            # For credit cards, all transactions are typically debits (expenses)
            # But check if is_credit was set in the OFX parsing
            prepared_transactions.append({
                'transaction_id': transaction_id,
                'txn': txn,  # txn already contains is_credit from parse_ofx_file
                'merchant': name.strip(),
                'card_number': card_number,
                'is_transfer': False,
                'foreign_currency': '',
            })
    
    # Process transactions in batches
    BATCH_SIZE = 5  # Process 5 transactions per API call
    BATCH_DELAY = 1.2  # 1.2 second delay between batches (stays well under 500 RPM limit)
    
    # Group into batches
    for batch_idx in range(0, len(prepared_transactions), BATCH_SIZE):
        batch = prepared_transactions[batch_idx:batch_idx + BATCH_SIZE]
        batch_num = (batch_idx // BATCH_SIZE) + 1
        total_batches = (len(prepared_transactions) + BATCH_SIZE - 1) // BATCH_SIZE
        
        print(f"  Batch {batch_num}/{total_batches}: Processing {len(batch)} transaction(s)...")
        
        # Prepare batch data for LLM
        batch_data = [{
            'transaction_id': pt['transaction_id'],
            'merchant': pt['merchant'],
            'amount': pt['txn'].get('amount', 0.0),
            'date': pt['txn'].get('transaction_date', ''),
        } for pt in batch]
        
        # Process batch with LLM
        llm_results = identify_and_categorize_transaction_batch(
            batch_data,
            account_type_label,
            project_root,
            verbose=True
        )
        
        # Create a mapping of transaction_id to LLM results
        llm_results_map = {r['transaction_id']: r for r in llm_results}
        
        # Create final transaction objects
        for pt in batch:
            transaction_id = pt['transaction_id']
            llm_result = llm_results_map.get(transaction_id, {})
            
            # is_credit is determined from OFX TRNTYPE/TRNAMT during parsing, NOT from LLM results
            # This ensures credits are ALWAYS marked correctly, even if LLM fails to identify merchant
            # The LLM only affects identified_business and category, never is_credit
            is_credit = pt['txn'].get('is_credit', False)
            
            if detected_account_type == 'CHECKING':
                processed_txn = {
                    'id': transaction_id,
                    'account': account_id,
                    'card': pt['card_number'],
                    'amount': pt['txn'].get('amount', 0.0),
                    'merchant': pt['merchant'],
                    'identified_business': llm_result.get('identified_business'),  # LLM may return None/N/A
                    'transaction_date': pt['txn'].get('transaction_date', ''),
                    'processed_date': pt['txn'].get('transaction_date', ''),
                    'foreign_currency': pt['foreign_currency'],
                    'source_file': pt['txn'].get('source_file', ''),
                    'account_type': account_type_label,
                    'categorized': bool(llm_result.get('category')),
                    'category': llm_result.get('category'),  # LLM may return None/N/A
                    'category_description': llm_result.get('category_description'),
                    'categorized_at': datetime.now().isoformat() if llm_result.get('category') else None,
                    'is_transfer': pt['is_transfer'],
                    'is_credit': is_credit,  # Always set from OFX data, independent of LLM success
                }
            else:  # CREDITCARD
                processed_txn = {
                    'id': transaction_id,
                    'account': account_id,
                    'card': pt['card_number'],
                    'amount': pt['txn'].get('amount', 0.0),
                    'merchant': pt['merchant'],
                    'identified_business': llm_result.get('identified_business'),  # LLM may return None/N/A
                    'transaction_date': pt['txn'].get('transaction_date', ''),
                    'processed_date': pt['txn'].get('transaction_date', ''),
                    'foreign_currency': pt['foreign_currency'],
                    'source_file': pt['txn'].get('source_file', ''),
                    'account_type': account_type_label,
                    'categorized': bool(llm_result.get('category')),
                    'category': llm_result.get('category'),  # LLM may return None/N/A
                    'category_description': llm_result.get('category_description'),
                    'categorized_at': datetime.now().isoformat() if llm_result.get('category') else None,
                    'is_transfer': False,
                    'is_credit': is_credit,  # Always set from OFX data, independent of LLM success
                }
            
            processed_transactions.append(processed_txn)
        
        # Add delay between batches to respect rate limits (except for last batch)
        if batch_idx + BATCH_SIZE < len(prepared_transactions):
            time.sleep(BATCH_DELAY)
    
    # Merge with existing transactions
    all_processed = existing_transactions + processed_transactions
    
    # Backfill account_type for existing transactions that don't have it
    for txn in all_processed:
        if 'account_type' not in txn:
            txn['account_type'] = account_type_label
    
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
    
    # Save transactions
    print()
    if skipped_count > 0:
        print(f"  Skipped {skipped_count} existing transaction(s)")
    
    if processed_transactions:
        print(f"  Saving {len(processed_transactions)} new transaction(s)...")
        save_json_safely(output_file, unique_transactions)
        print(f"  ✓ Added {len(processed_transactions)} new transaction(s)")
        print(f"  ✓ Total transactions: {len(unique_transactions)}")
        
        # Count categorized transactions
        categorized_count = sum(1 for t in processed_transactions if t.get('categorized'))
        transfer_count = sum(1 for t in processed_transactions if t.get('is_transfer'))
        non_transfer_count = len(processed_transactions) - transfer_count
        
        if categorized_count > 0:
            print(f"  ✓ Categorized: {categorized_count}/{non_transfer_count} transactions (excluding {transfer_count} transfers)")
    else:
        print(f"  No new transactions to add")
        print(f"  Total transactions: {len(unique_transactions)}")

def main():
    """Main processing function."""
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
    print("=" * 60)
    print(f"Found {len(account_folders)} account folder(s)")
    
    for account_folder in sorted(account_folders):
        process_account(account_folder, project_root)
    
    print("\n" + "=" * 60)
    print("Processing complete!")
    print("=" * 60)

if __name__ == '__main__':
    main()

