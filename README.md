# AllInOneAccounting

A web application for categorizing bank transaction details from CSV files.

## Overview

AllInOneAccounting helps you categorize bank transactions by importing CSV files containing bank details and providing tools to organize and categorize them.

## Project Structure

- `data/{AccountName}/` - Input data folders for each account (OFX and CSV files)
- `storage/transactions/` - Processed transaction JSON files
- `storage/accounts.json` - Account configuration (defines Personal vs Business accounts)
- `storage/entities.json` - Entity definitions (Personal/Business entities)
- `storage/categorization_rules.json` - Learned categorization rules
- `business_categorization_prompt.md` - Prompt template for LLM-based business expense categorization
- `web/` - Next.js web application

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

