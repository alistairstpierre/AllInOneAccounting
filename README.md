# AllInOneAccounting

A web application for categorizing bank transaction details from CSV files.

## Overview

AllInOneAccounting helps you categorize bank transactions by importing CSV files containing bank details and providing tools to organize and categorize them.

## Project Structure

- `data/{AccountName}/` - Input data folders for each account (CSV files)
- `storage/transactions/` - Processed transaction JSON files
- `storage/processing_logs/` - Timestamped logs from each `process_new_transactions.py` run
- `storage/accounts.json` - Account configuration (defines Personal vs Business accounts)
- `storage/entities.json` - Entity definitions (Personal/Business entities)
- `storage/categorization_rules.json` - Learned categorization rules
- `business_categorization_prompt.md` - Prompt template for LLM-based business expense categorization
- `personal_categorization_prompt.md` - Prompt template for LLM-based personal expense categorization
- `process_new_transactions.py` - **Single entry point**: import CSVs into storage, then categorize by entity type (run this after adding new CSV files)
- `categorize_transactions.py` - Imports CSV files into storage/transactions (used by process_new_transactions.py)
- `identify_and_categorize.py` - Identifies and categorizes transactions in storage by entity type (used by process_new_transactions.py)
- `update_transactions_with_credit_debit.py` - Script to update existing transactions with credit/debit information
- `assign_transactions_by_card.py` - Links unassigned transactions to entities by card (runs after CSV import; skips transactions already on any entity so manual assignments persist)
- `export_century_6788_expenses.py` - Exports Century-assigned transactions on credit card *6788 to dated CSVs under `storage/`
- `web/` - Next.js web application
  - `web/app/lib/transaction-update.ts` - Utility function for updating transactions (marks as updated only when values change)

## Account Configuration

Accounts can be marked as "Personal" or "Business" in `storage/accounts.json`. This determines which category set is used during processing:

- **Personal accounts**: Use personal finance categories (Housing, Food & Dining, etc.)
- **Business accounts**: Use business categories (Office Supplies, Marketing/Advertising, etc.)

### Setting Account Types

Edit `storage/accounts.json` to configure account types:

```json
{
  "accounts": {
    "Account Folder Name": {
      "type": "Personal"  // or "Business"
    }
  }
}
```

**Default**: If an account is not specified in the config, it defaults to "Personal".

### Account Type Storage

When transactions are processed, the account type (Personal or Business) is stored in each transaction's `account_type` field. This allows the system to:
- Track which transactions belong to business vs personal accounts
- Use appropriate category sets for categorization
- Provide context for LLM-based categorization (see `business_categorization_prompt.md`)

See `TRANSACTION_PROCESSOR_LOGIC.md` for more details on how account types are used during processing.

## Entity-Based Categorization

Transactions can be assigned to entities (people or organizations) in the web interface. The `identify_and_categorize.py` script processes transactions based on their assigned entity type:

- **Business entities**: Uses `business_categorization_prompt.md` and business categories
- **Personal entities**: Uses `personal_categorization_prompt.md` and personal categories
- **Unassigned transactions**: Uses account type to determine prompt and categories

### Processing new transactions (one command)

After adding new CSV files under `data/<AccountName>/csv/`, run:

```powershell
# Import new CSVs and categorize everything (recommended)
python3 process_new_transactions.py

# See what would be categorized without writing (import still runs)
python3 process_new_transactions.py --dry-run
```

This runs: (1) import CSVs into storage, (2) entity-based identify & categorize. To run only the categorization step on existing storage (e.g. after assigning entities), use `python3 identify_and_categorize.py --no-dry-run`.

Every run writes a timestamped log file to `storage/processing_logs/` so you can audit past processing output.

## Category Preservation

**Important**: When processing CSV files, all manual category changes are automatically preserved. The processor:

1. **Matches transactions by composite key** (date, amount, merchant, card, reference, code)
2. **Identical lines in CSV** (same composite key) each get their own row in storage: first row keeps the base `id`, further rows use `{id}_dup2`, `{id}_dup3`, … so true duplicates (e.g. four identical charges) all appear.
3. **Preserves all categorization fields** when updating existing transactions:
   - `category`
   - `identified_business`
   - `category_description`
   - `categorized`
   - `categorized_at`
4. **Only updates metadata** like `source_file` when matching duplicates

### Backup and Restore

Before processing CSV files, you can create a backup of all categorized transactions:

```powershell
# Create a backup of all categories
python backup_categories.py
```

This creates a timestamped backup in `storage/category_backups/` containing all categorized transactions.

To restore categories from a backup:

```powershell
# Restore from most recent backup
python restore_categories.py

# Or specify a specific backup
python restore_categories.py 20260107_184714
```

### Verify Categories

Check how many transactions have categories:

```powershell
python verify_category_preservation.py
```