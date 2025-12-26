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
            
            # Skip deposits/revenue - only process expenses
            # This only applies to checking/debit accounts, not credit cards
            # Credit cards don't have deposits (all transactions are expenses/debits)
            if account_type == 'CHECKING':
                # Deposits have TRNTYPE=DEP or positive TRNAMT
                # Expenses have TRNTYPE=DEBIT/PAYMENT/etc or negative TRNAMT
                is_deposit = (trntype.upper() == 'DEP' or trnamt > 0)
                if is_deposit:
                    continue  # Skip deposits/revenue, only track expenses
            # For credit cards, all transactions are expenses (negative amounts are normal)
            
            transaction_date = parse_ofx_date(dtposted)
            
            transaction = {
                'fitid': fitid,
                'dtposted': dtposted,
                'transaction_date': transaction_date,
                'amount': abs(trnamt),  # Store as positive for expenses
                'trnamt': trnamt,  # Keep original signed value
                'trntype': trntype,
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
    print(f"\nProcessing account: {account_name}")
    
    # Get account type from configuration
    is_business = is_business_account(account_name, project_root)
    account_type_label = "Business" if is_business else "Personal"
    print(f"  Account type: {account_type_label}")
    
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
    
    for txn in all_transactions:
        fitid = txn.get('fitid', '')
        transaction_id = f"{fitid}_{sanitized_account_id}"
        
        # Skip if already exists
        if transaction_id in existing_ids:
            continue
        
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
                # Extract merchant from MEMO (remove "Visa Purchase" prefix if present)
                merchant = memo
                # Clean up common prefixes
                if merchant.startswith('Visa Purchase'):
                    # Remove "Visa Purchase" and any leading/trailing whitespace
                    merchant = merchant.replace('Visa Purchase', '', 1).strip()
                # Remove FX amount info if present (e.g., "0 55 Twilio Inc         0 28 FXAmnt=...")
                # Keep only the merchant name part before FX info
                if 'FXAmnt=' in merchant:
                    merchant = merchant.split('FXAmnt=')[0].strip()
                # Clean up leading numbers and spaces (e.g., "0 55 Twilio Inc" -> "Twilio Inc")
                # Remove patterns like "0 55 " or "0.55 " at the start (FX rate info)
                merchant = re.sub(r'^\d+\s+\d+\.?\d*\s+', '', merchant).strip()
                # Remove trailing FX amount numbers (e.g., "Twilio Inc         0 28" -> "Twilio Inc")
                # Pattern: spaces followed by decimal number at the end
                merchant = re.sub(r'\s+\d+\.?\d+\s*$', '', merchant).strip()
                # Remove trailing single numbers (e.g., "Whatconverts         0 46" -> "Whatconverts")
                # This handles cases where FX amount is just a number
                merchant = re.sub(r'\s+\d+\s*$', '', merchant).strip()
                # Remove trailing merchant codes (e.g., "*V85D", "*R50V")
                merchant = re.sub(r'\s+\*[A-Z0-9]+$', '', merchant).strip()
                # Clean up multiple spaces
                merchant = re.sub(r'\s+', ' ', merchant).strip()
            else:
                # NAME is merchant
                merchant = name
            
            # Detect transfers
            is_transfer_txn = is_transfer(memo, name, account_id)
            if is_transfer_txn:
                merchant = "Account Transfer"
            
            processed_txn = {
                'id': transaction_id,
                'account': account_id,
                'card': card_number,
                'amount': txn.get('amount', 0.0),
                'merchant': merchant.strip(),
                'identified_business': None,  # Will be processed later
                'transaction_date': txn.get('transaction_date', ''),
                'processed_date': txn.get('transaction_date', ''),
                'foreign_currency': memo if card_number else '',
                'source_file': txn.get('source_file', ''),
                'account_type': account_type_label,  # Personal or Business from accounts.json
                'categorized': False,
                'category': None,
                'category_description': None,
                'categorized_at': None,
                'is_transfer': is_transfer_txn,
            }
        
        else:  # CREDITCARD
            # Credit card processing
            name = txn.get('name', '')
            
            # Try to match with CSV to get card number
            card_number = match_csv_to_ofx(txn, csv_transactions)
            
            processed_txn = {
                'id': transaction_id,
                'account': account_id,
                'card': card_number,
                'amount': txn.get('amount', 0.0),
                'merchant': name.strip(),
                'identified_business': None,  # Will be processed later
                'transaction_date': txn.get('transaction_date', ''),
                'processed_date': txn.get('transaction_date', ''),
                'foreign_currency': '',
                'source_file': txn.get('source_file', ''),
                'account_type': account_type_label,  # Personal or Business from accounts.json
                'categorized': False,
                'category': None,
                'category_description': None,
                'categorized_at': None,
                'is_transfer': False,  # Credit cards don't have transfers
            }
        
        processed_transactions.append(processed_txn)
    
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
    if processed_transactions:
        save_json_safely(output_file, unique_transactions)
        print(f"  Added {len(processed_transactions)} new transaction(s)")
        print(f"  Total transactions: {len(unique_transactions)}")
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

