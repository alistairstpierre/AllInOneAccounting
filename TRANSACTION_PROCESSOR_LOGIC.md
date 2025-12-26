# Transaction Processor Logic - Reverse Engineered

This document describes how transactions are processed from OFX and CSV files into the JSON format stored in `storage/transactions/`.

## File Structure

### Input Files Location
- `data/{AccountName}/ofx/` - OFX files for the account
- `data/{AccountName}/csv/` - CSV files for the account (credit cards only)

### Output Files Location
- `storage/transactions/{AccountName}.json` - Processed transactions

---

## Type 1: Debit Account (Checking Account) OFX Files

### OFX Structure
- Uses `<BANKACCTFROM>` section
- Contains: `<BANKID>`, `<BRANCHID>`, `<ACCTID>`
- Account type: `CHECKING`

### Account ID Extraction
```
Account ID = BANKID + BRANCHID + ACCTID
Example: "06" + "0441" + "0179990-00" = "0604410179990-00"
```

### Transaction Extraction (from `<STMTTRN>`)
- **FITID**: Unique transaction ID (format: `YYYYMMDDN` where N is sequence number)
- **DTPOSTED**: Transaction date (format: `YYYYMMDD`)
- **TRNAMT**: Transaction amount (negative for debits, positive for deposits)
- **NAME**: Merchant name OR masked card number (format: `#### **** **** ####`)
- **MEMO**: Additional transaction details (may contain merchant name, FX info, etc.)
- **TRNTYPE**: Transaction type (`DEBIT`, `DEP`, etc.)

### Card Number Extraction (Debit Accounts)
- If NAME field matches pattern `#### **** **** ####` (masked card):
  - Extract card number: Convert spaces to hyphens → `4835-****-****-0506`
  - Merchant name comes from MEMO field instead

### Merchant Name Extraction (Debit Accounts)
1. **If NAME is a masked card** (`#### **** **** ####`):
   - Check MEMO for transfer patterns (see Transfer Detection)
   - If transfer: merchant = "Account Transfer"
   - Else: Extract merchant from MEMO field

2. **If NAME is NOT a masked card**:
   - Check if NAME looks like account number (transfer indicator)
   - If transfer: merchant = "Account Transfer"
   - Else: merchant = NAME field (trimmed)

### Transfer Detection (Debit Accounts)
A transaction is marked as a transfer if:
- MEMO contains account number pattern: `\b\d{2}\s+\d{4}\s+\d{7}\s+\d{2}\b`
- MEMO contains masked card pattern: `\d{4}\s*\*{4}\s*\*{4}\s*\d{4}`
- MEMO contains transfer keywords: "Transfer", "Transfer Debit Transfer", "Payment To", "Credit To", "Account Transfer"
- MEMO is very short (< 5 characters)
- MEMO is mostly numeric: `^[\d\s-]+$`
- NAME field matches account number pattern: `^\d{2}\s+\d{4}\s+\d{7}\s+\d{2}$`

### Transaction ID Generation (Debit Accounts)
```
Transaction ID = FITID + "_" + sanitized_account_id
Sanitized Account ID = account_id.replace('*', 'X')
Example: "202512221_0604410179990-00"
```

### Output Format (Debit Accounts)
```json
{
  "id": "202512221_0604410179990-00",
  "account": "0604410179990-00",
  "card": "4835-****-****-0506" or null,
  "amount": 29.93,  // abs(TRNAMT)
  "merchant": "0 57 Audible*R50V 0",  // From MEMO if NAME is card, else NAME
  "identified_business": "Audible",  // Processed later
  "transaction_date": "2025-12-22",  // DTPOSTED converted to YYYY-MM-DD
  "processed_date": "2025-12-22",
  "foreign_currency": "Visa Purchase 0 57 Audible*R50V...",  // MEMO field
  "source_file": "06-0441-0179990-00_Transactions_2025-12.ofx",
  "categorized": false,
  "category": null,
  "category_description": null,
  "categorized_at": null,
  "is_transfer": true/false  // Based on transfer detection
}
```

---

## Type 2: Credit Card OFX Files

### OFX Structure
- Uses `<CCACCTFROM>` section (CREDITCARDMSGSRSV1)
- Contains: `<ACCTID>` (masked card number)
- Account type: CREDITCARD

### Account ID Extraction
```
Account ID = ACCTID (directly from OFX)
Example: "9554********6788"
```

### Transaction Extraction (from `<STMTTRN>`)
- **FITID**: Unique transaction ID (format: `YYYYMMDDYYYYMMDDN`)
- **DTPOSTED**: Transaction date (format: `YYYYMMDD`)
- **TRNAMT**: Transaction amount (negative for debits)
- **NAME**: Merchant name (location included, e.g., "Freemans Lotto Pipitea Nz")
- **MEMO**: Usually empty or not present

### Card Number Assignment (Credit Cards)
- Card number comes from CSV file matching (see CSV Processing)
- CSV files contain Card column that matches to transactions
- Card format: `4055-****-****-0170`

### Merchant Name Extraction (Credit Cards)
- Merchant = NAME field (trimmed)
- Usually includes location: "Merchant Name Location Nz"

### Transaction ID Generation (Credit Cards)
```
Transaction ID = FITID + "_" + sanitized_account_id
Sanitized Account ID = account_id.replace('*', 'X')
Example: "20251205202512051_9554XXXXXXXX6788"
```

### Output Format (Credit Cards)
```json
{
  "id": "20251205202512051_9554XXXXXXXX6788",
  "account": "9554********6788",
  "card": "4055-****-****-0170",  // From CSV matching
  "amount": 6.19,  // abs(TRNAMT)
  "merchant": "Freemans Lotto Pipitea Nz",  // NAME field
  "identified_business": "Freemans Lotto",  // Processed later
  "transaction_date": "2025-12-05",  // DTPOSTED converted to YYYY-MM-DD
  "processed_date": "2025-12-05",
  "foreign_currency": "",  // Usually empty for credit cards
  "source_file": "9554-xxxx-xxxx-6788_Statement_2025-12-05.ofx",
  "categorized": false,
  "category": null,
  "category_description": null,
  "categorized_at": null,
  "is_transfer": false  // Credit cards don't have transfers in same way
}
```

---

## Type 3: Credit Card CSV Files

### CSV Structure
Columns: `Card,Type,Amount,Details,TransactionDate,ProcessedDate,ForeignCurrencyAmount,ConversionCharge`

### Card Number
- Format: `4055-****-****-0170` (from Card column)

### Transaction Matching with OFX
CSV files are used to:
1. Extract card numbers for credit card transactions
2. Match transactions between CSV and OFX files
3. Matching is done by:
   - Merchant name (Details in CSV vs NAME in OFX)
   - Amount (must match exactly)
   - Transaction date (must match)

### CSV Row Extraction
- **Card**: Card number (format: `####-****-****-####`)
- **Type**: Transaction type (usually "D" for debit)
- **Amount**: Transaction amount (positive)
- **Details**: Merchant name with location
- **TransactionDate**: Date in format `DD/MM/YYYY`
- **ProcessedDate**: Date in format `DD/MM/YYYY`

### Card Assignment Logic
1. Process OFX file to extract transactions
2. For each OFX transaction, look for matching CSV row:
   - Match by merchant name (normalized)
   - Match by amount
   - Match by date
3. If match found, assign card number from CSV to transaction

---

## Date Format Conversion

### OFX Date Format
- Input: `YYYYMMDD` (e.g., `20251222`)
- Output: `YYYY-MM-DD` (e.g., `2025-12-22`)

### CSV Date Format
- Input: `DD/MM/YYYY` (e.g., `05/12/2025`)
- Output: `YYYY-MM-DD` (e.g., `2025-12-05`)

---

## Processing Flow

1. **Identify Account Type**
   - Check OFX file: `<BANKACCTFROM>` = Checking Account
   - Check OFX file: `<CCACCTFROM>` = Credit Card

2. **Extract Account ID**
   - Checking: Combine BANKID + BRANCHID + ACCTID
   - Credit Card: Use ACCTID directly

3. **Parse OFX Transactions**
   - Extract all `<STMTTRN>` entries
   - For each transaction:
     - Extract FITID, DTPOSTED, TRNAMT, NAME, MEMO
     - Convert dates to YYYY-MM-DD format
     - Extract amount as abs(TRNAMT)

4. **Process Debit Account Transactions**
   - Check if NAME is masked card number
   - Extract card number if present
   - Extract merchant name (from MEMO if card, else NAME)
   - Detect transfers based on patterns
   - Generate transaction ID: `{FITID}_{sanitized_account}`

5. **Process Credit Card Transactions**
   - Merchant = NAME field
   - Match with CSV to get card number
   - Generate transaction ID: `{FITID}_{sanitized_account}`

6. **Save Transactions**
   - Group by account name (folder name)
   - Save to `storage/transactions/{AccountName}.json`
   - Merge with existing transactions (deduplicate by ID)

7. **Account Type Configuration**
   - Read account type from `storage/accounts.json`
   - This determines which category set to use (Personal vs Business)
   - If account not found in config, default to "Personal"

---

## Account Configuration

### Configuration File: `storage/accounts.json`

This file maps account folder names to account types (`Personal` or `Business`). The account type determines which category set should be used during categorization.

**Format:**
```json
{
  "accounts": {
    "Account Folder Name": {
      "type": "Personal" | "Business"
    }
  }
}
```

**Example:**
```json
{
  "accounts": {
    "Alistair Personal Account": {
      "type": "Personal"
    },
    "Century Digital Main Account": {
      "type": "Business"
    }
  }
}
```

**Usage in Processing:**
1. Read `storage/accounts.json` at the start of processing
2. For each account folder, look up the account type
3. If account type is "Business", use `BUSINESS_CATEGORIES` from `web/app/lib/categories.ts`
4. If account type is "Personal" or not found, use `PERSONAL_CATEGORIES`

---

## Important Notes

1. **Account ID Sanitization**: Replace `*` with `X` in account IDs for transaction ID generation
2. **Transaction Deduplication**: Use transaction ID (FITID + account) to prevent duplicates
3. **File Naming**: Use folder name for JSON file, but store actual account ID in transactions
4. **Amount Handling**: Always use absolute value of TRNAMT (debits are negative in OFX)
5. **Transfer Detection**: Only applies to debit/checking accounts
6. **Card Assignment**: Credit cards require CSV matching to get card numbers

