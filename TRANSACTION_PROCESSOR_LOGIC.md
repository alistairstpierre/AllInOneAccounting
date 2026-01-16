# Transaction Processor Logic

This document describes how transactions are processed from CSV files into the JSON format stored in `storage/transactions/`.

## File Structure

### Input Files Location
- `data/{AccountName}/csv/` - CSV files for the account

### Output Files Location
- `storage/transactions/{AccountName}.json` - Processed transactions

---

## CSV File Processing

### Account Types
- **Checking Accounts**: Debit/checking account transactions
- **Credit Card Accounts**: Credit card transactions

### CSV Format Detection

The processor automatically detects the CSV format by checking for the `Card` column:

**Simple Detection:**
- Has `Card` column → Credit Card CSV
- No `Card` column → Checking Account CSV

**Credit Card CSV Format:**
- Required columns: `Card`, `Type`, `Amount`, `Details`, `TransactionDate`, `ProcessedDate`, `ForeignCurrencyAmount`, `ConversionCharge`
- All columns are required (none are optional)

**Checking Account CSV Format:**
- Required columns: `Type`, `Details`, `Particulars`, `Code`, `Reference`, `Amount`, `Date`, `ForeignCurrencyAmount`, `ConversionCharge`
- All columns are required (none are optional)

### Transaction Extraction

**Credit Card CSV Fields:**
- **Card**: Card number (format: `####-****-****-####`)
- **Type**: "C" = transfer (payment to card), "D" = expense
- **Amount**: Transaction amount
- **Details**: Merchant name
- **TransactionDate**: Date in format `DD/MM/YYYY` → converted to `YYYY-MM-DD`
- **ProcessedDate**: Date in format `DD/MM/YYYY` → converted to `YYYY-MM-DD`
- **ForeignCurrencyAmount**: Foreign currency information
- **ConversionCharge**: Currency conversion charge

**Checking Account CSV Fields:**
- **Type**: Transaction type (e.g., "Transfer", "Visa Purchase", "Direct Credit", "Direct Debit", "Payment", "Automatic Payment")
- **Details**: Transaction details (may contain card number for Visa Purchases)
- **Particulars**: Additional transaction information (may contain conversion rate for foreign transactions)
- **Code**: Transaction code (often contains actual merchant name for Visa Purchases)
- **Reference**: Transaction reference number
- **Amount**: Transaction amount (positive = debit/expense, negative = credit/revenue)
- **Date**: Date in format `DD/MM/YYYY` → converted to `YYYY-MM-DD`
- **ForeignCurrencyAmount**: Foreign currency information
- **ConversionCharge**: Currency conversion charge

**Merchant Name Extraction (Checking Accounts - Visa Purchase):**
- For "Visa Purchase" transactions, merchant name is extracted from the `Code` field
- If `Code` is empty, falls back to `Particulars` (if not a number/conversion rate)
- If both are empty, uses `Details` (after removing card number)

### Revenue/Credit Detection

**Checking Accounts:**
- **Positive amount** = debit (expense/outgoing money)
- **Negative amount** = credit (revenue/incoming money)
- Transactions with negative amounts are marked with `is_credit = True`

**Credit Card Accounts:**
- All transactions are expenses (debits)
- Type "C" transactions are transfers (payments to the card) and are filtered out
- Type "D" transactions are expenses

### Transfer Detection

**Checking Accounts:**
- Transaction type is "Transfer" → `is_transfer = True`

**Credit Card Accounts:**
- Transaction type is "C" → `is_transfer = True` (these are filtered out during parsing)

### Transaction ID Generation

Transaction IDs are generated using a hash-based approach from a composite key:

```
Composite Key = {
    account_id,
    transaction_date,
    amount,
    merchant (normalized),
    card (or empty),
    reference (or empty),
    code (or empty)
}

Transaction ID = SHA256(composite_key)[:16] (hex digest, first 16 chars)
```

**Within-File Duplicates:**
- If the same composite key appears multiple times in the same CSV file, subsequent occurrences get sequence numbers:
  - First occurrence: `{base_id}`
  - Second occurrence: `{base_id}_dup2`
  - Third occurrence: `{base_id}_dup3`
  - etc.

### Duplicate Detection

**Within-File Duplicates:**
- Duplicates within the same CSV file are preserved as separate transactions
- Each gets a unique ID with `_dup2`, `_dup3`, etc. suffix

**Cross-File Duplicates:**
- Uses one-to-one matching across files
- If File 1 has 2 duplicates and File 2 has 3 duplicates of the same transaction:
  - File 1: Both saved (2 total)
  - File 2: First 2 match File 1 → skipped, remaining 1 kept (3-2=1)

**Matching Logic:**
- Transactions are matched using fuzzy matching on composite key:
  - Date must match exactly
  - Amount must match exactly (rounded to 2 decimals)
  - Merchant name normalized (lowercase, trimmed, extra spaces removed)
  - Card, reference, and code must match if both present
  - Code field is optional - missing code doesn't prevent matching

### Category Preservation

When processing CSV files, all manual category changes are automatically preserved:

1. **Matches transactions by composite key** (date, amount, merchant, card, reference, code)
2. **Preserves all categorization fields** when updating existing transactions:
   - `category`
   - `identified_business`
   - `category_description`
   - `categorized`
   - `categorized_at`
3. **Only updates metadata** like `source_file` when matching duplicates

### Output Format

```json
{
  "id": "a1b2c3d4e5f6g7h8",
  "account": "01-0142-0771521-00",
  "card": "9554-****-****-6788" or null,
  "amount": 29.93,
  "merchant": "Freemans Lotto         Pipitea       Nz",
  "identified_business": "Freemans Lotto",
  "transaction_date": "2025-12-05",
  "processed_date": "2025-12-05",
  "foreign_currency": "",
  "source_file": "01-0142-0771521-00_Transactions_2025-12.csv",
  "source_files": ["file1.csv", "file2.csv"],  // Multiple files if updated
  "categorized": true,
  "category": "Entertainment",
  "category_description": "Lottery ticket purchase",
  "categorized_at": "2025-12-06T10:30:00",
  "is_transfer": false,
  "is_credit": false,
  "account_type": "Personal",
  "reference": "123456",
  "code": "ABC123"
}
```

---

## Processing Flow

1. **Identify Account Type**
   - Check account configuration in `storage/accounts.json`
   - Defaults to "Personal" if not specified

2. **Extract Account ID**
   - Checking: Extract from filename pattern `\d{2}-\d{4}-\d{7}-\d{2}`
   - Credit Card: Extract from filename pattern `\d{4}-xxxx-xxxx-\d{4}` (convert to `****`)

3. **Parse CSV Files**
   - Detect CSV format from column headers
   - Extract all transactions from CSV files
   - Group transactions by source file

4. **Process Files in Sorted Order**
   - Process each CSV file separately
   - Track within-file duplicates with sequence numbers
   - Match cross-file duplicates using one-to-one matching
   - **Check for existing transactions:**
     - Load existing transactions from `storage/transactions/{AccountName}.json`
     - Match by transaction ID (composite key hash)
     - **Skip transactions that already exist with valid categories** (not "Uncategorized" or empty)
     - Preserve categories from existing transactions
     - Only process new transactions or existing transactions that need re-categorization

5. **Categorize Transactions**
   - For transactions needing categories:
     - First try merchant-based matching (reuse categories from similar merchants)
     - If no match, use AI to generate category and identify business name
     - Process transactions one at a time sequentially

6. **Save Transactions**
   - Merge with existing transactions
   - Deduplicate by ID (final check)
   - Sort by transaction date (newest first)
   - Save to `storage/transactions/{AccountName}.json`

---

## Date Format Conversion

### CSV Date Format
- Input: `DD/MM/YYYY` (e.g., `05/12/2025`)
- Output: `YYYY-MM-DD` (e.g., `2025-12-05`)

---

## Amount Handling

- Amounts are stored as positive values in the JSON output
- For checking accounts:
  - **Positive amount in CSV** = debit (expense/outgoing money)
  - **Negative amount in CSV** = credit (revenue/incoming money)
  - Negative amounts are marked with `is_credit = True`
- For credit cards:
  - All transactions are expenses (debits)
  - Amounts are always positive in the output

---

## AI Categorization

The processor uses OpenAI's GPT-4o-mini model to automatically categorize transactions and identify business names.

### Prompt Building

The system builds prompts dynamically by combining:
1. **Base prompt template** (from `business_categorization_prompt.md` or `personal_categorization_prompt.md`)
2. **Transaction data**: Merchant name, amount, date
3. **Transaction context** (for checking accounts):
   - `Details`: Full transaction details
   - `Particulars`: Additional transaction information
   - `Code`: Transaction code (often contains actual merchant name for Visa Purchases)
   - `Reference`: Transaction reference number
4. **Special notes**:
   - If merchant looks like a person's name, adds note about payment direction

### Business Categorization Prompt

```markdown
# Business Expense Categorization Prompt

This prompt is designed to help categorize business expenses, covering both online services/digital subscriptions and traditional local businesses that are common in modern business operations.

## Context

You are categorizing business expenses for a company. Transactions may be for:
- **Online services**: Software subscriptions, digital tools, cloud-based platforms, SaaS services
- **Local businesses**: Physical stores, restaurants, service providers, contractors, suppliers in your area
- **Hybrid businesses**: Companies that operate both online and have physical locations

All of these are legitimate business expenses and should be categorized appropriately. Your task is to identify the business name (cleaning up merchant names) and assign the correct business category.

## Business Expense Categories

Available categories:
- **Office Supplies**: Physical office materials, stationery, equipment
- **Software/Subscriptions**: Software licenses, SaaS subscriptions, cloud services, online tools
- **Marketing/Advertising**: Advertising campaigns, marketing tools, social media ads, SEO services
- **Professional Services**: Consulting, freelancers, contractors, professional advice
- **Travel**: Business trips, flights, hotels, transportation for business purposes
- **Meals/Entertainment**: Business meals, client entertainment, team events
- **Equipment**: Hardware, machinery, computers, office equipment
- **Rent/Utilities**: Office rent, utilities, internet, phone services
- **Insurance**: Business insurance policies
- **Education/Training**: Courses, training programs, certifications for business
- **Transportation**: Business vehicle expenses, fuel, parking, business travel
- **Legal/Accounting**: Legal services, accounting services, tax preparation
- **Telecommunications**: Phone services, internet, communication tools
- **Bank Fees**: Banking fees, transaction fees, account maintenance
- **Uncategorized**: Expenses that don't fit other categories

## Categorization Guidelines

### Software/Subscriptions
Include:
- SaaS platforms (CRM, project management, collaboration tools)
- Cloud services (hosting, storage, infrastructure)
- Software licenses and subscriptions
- Online tools and platforms
- API services and integrations
- Development tools and services
- Analytics and tracking tools
- Email marketing platforms
- Payment processing services
- Domain and hosting services

Examples:
- "Twilio" → Software/Subscriptions (cloud communications)
- "GoDaddy" → Software/Subscriptions (domain/hosting) or Rent/Utilities
- "OpenAI" → Software/Subscriptions (AI services)
- "Calendly" → Software/Subscriptions (scheduling tool)
- "ClickUp" → Software/Subscriptions (project management)
- "Cloudflare" → Software/Subscriptions (CDN/hosting services)

### Marketing/Advertising
Include:
- Social media advertising (Facebook Ads, Google Ads, etc.)
- Marketing automation platforms
- SEO tools and services
- Content creation tools
- Email marketing services
- Analytics and conversion tracking tools
- Influencer marketing platforms

Examples:
- "Facebook Ads" → Marketing/Advertising
- "Google Ads" → Marketing/Advertising
- "Mailchimp" → Marketing/Advertising (email marketing)
- "Ahrefs" → Marketing/Advertising (SEO tool)

### Professional Services
Include:
- Freelance platforms (Upwork, Fiverr)
- Consulting services
- Design services
- Development services
- Writing and content services
- Virtual assistants

Examples:
- "Upwork" → Professional Services
- Consulting fees → Professional Services

### Rent/Utilities
Include:
- Office rent
- Internet and phone services
- Cloud infrastructure (if primary business infrastructure)
- Co-working spaces
- Utilities (electricity, water, etc.)

Examples:
- "Google Workspace" → Rent/Utilities (business email/infrastructure)
- "Microsoft 365" → Rent/Utilities (business productivity suite)
- Office rent → Rent/Utilities

### Telecommunications
Include:
- Phone services
- Internet services
- Communication tools (if not covered under Software/Subscriptions)
- Video conferencing (if primary communication tool)

### Education/Training
Include:
- Online courses for business skills
- Training programs
- Certifications
- Educational platforms for business development

Examples:
- "Coursera" (business courses) → Education/Training
- "Udemy" (business courses) → Education/Training

## Identifying Business Names

When identifying the business name from merchant transaction data:

**Important**: Check over all the information on the transaction to infer a name, as it could be stored within any of the values within the transaction. Sometimes the transaction details don't provide much context, so examine all available fields (merchant name, code, reference, details, particulars) to identify the actual business.

1. **Online Services**: Look for company names, service names, or platform names
   - "Openai *Chat" → "OpenAI"
   - "Google Workspace_Elect" → "Google Workspace"
   - "Twilio" → "Twilio"
   - Clean up transaction codes, locations, and formatting

2. **Local Businesses**: Identify the actual business name, removing location details if they're just for identification
   - "Freemans Lotto Pipitea Nz" → "Freemans Lotto" (local business)
   - "Zambrero Courtney Wellington Nz" → "Zambrero" (local restaurant chain)
   - "Badminton Wellington C Wellington Nz" → "Badminton Wellington" (local facility)
   - Keep location if it's part of the business name (e.g., "Wellington Airport")

3. **Hybrid Businesses**: Companies with both online and physical presence
   - Identify the company name regardless of whether transaction was online or in-store
   - "Amazon" could be online or physical (Amazon Go stores)
   - "Starbucks" could be in-store or mobile app

## Important Notes

1. **Both Online and Local are Business Expenses**: Modern businesses use both online services (SaaS, cloud tools) and local businesses (suppliers, contractors, restaurants for meetings). Both are legitimate business expenses.

2. **Context Matters**: Consider the business context. For example:
   - "Twilio" → Software/Subscriptions (communication infrastructure)
   - "OpenAI" → Software/Subscriptions (AI services)
   - "Local Restaurant" → Meals/Entertainment (business meal)
   - "Office Supply Store" → Office Supplies
   - "Contractor Name" → Professional Services

3. **Subscription Services**: Most recurring online services should go to Software/Subscriptions unless they're clearly in another category (e.g., marketing tools → Marketing/Advertising).

4. **Local Business Services**: 
   - Physical stores for office supplies → Office Supplies
   - Local contractors/freelancers → Professional Services
   - Local restaurants (business meals) → Meals/Entertainment
   - Local service providers → Appropriate category based on service type

5. **When in Doubt**: If an expense could fit multiple categories, choose the most specific one. If truly unclear, use "Uncategorized" and note why.

## Output Format

When categorizing a transaction, provide:
1. **Category**: The selected category name
2. **Reasoning**: Brief explanation of why this category was chosen, including what field/value provided the core information used to make the decision (e.g., "Identified from Code field: 'Openai *Chat' - OpenAI is a cloud-based AI service provider")
3. **Business Context**: Note if it's an online service, subscription, or traditional business expense

Example:
```
Category: Software/Subscriptions
Reasoning: Identified from Code field: 'Twilio' - Twilio provides cloud-based communication APIs and services, which are essential infrastructure for modern businesses. This is a recurring subscription service for business operations.
Business Context: Online service subscription
```
```

### Personal Categorization Prompt

```markdown
# Personal Expense Categorization Prompt

This prompt is designed to help categorize personal expenses, covering both online services and local businesses.

## Context

You are categorizing personal expenses. Transactions may be for:
- **Online services**: Software subscriptions, digital tools, streaming services, online shopping
- **Local businesses**: Physical stores, restaurants, service providers, local shops
- **Hybrid businesses**: Companies that operate both online and have physical locations

Your task is to identify the business name (cleaning up merchant names) and assign the correct personal category.

## Personal Expense Categories

Available categories:
- **Housing**: Rent, mortgage, utilities, home improvement, maintenance
- **Transportation**: Gas, car payments, public transit, parking, vehicle maintenance
- **Food & Dining**: Groceries, restaurants, cafes, food delivery
- **Healthcare**: Medical expenses, prescriptions, doctor visits, health insurance
- **Personal Care**: Grooming, hygiene products, spa services, fitness memberships
- **Entertainment**: Movies, streaming services, games, hobbies, recreation
- **Shopping**: Clothing, electronics, household items, general retail
- **Insurance**: Health, auto, life, renters insurance
- **Savings/Investing**: Investments, savings accounts, retirement contributions
- **Debt Payment**: Credit card payments, loan payments
- **Education**: Tuition, courses, books, educational materials
- **Travel**: Vacations, flights, hotels, travel expenses
- **Gifts & Donations**: Gifts, charitable donations
- **Uncategorized**: Expenses that don't fit other categories

## Identifying Business Names

When identifying the business name from merchant transaction data:

**Important**: Check over all the information on the transaction to infer a name, as it could be stored within any of the values within the transaction. Sometimes the transaction details don't provide much context, so examine all available fields (merchant name, code, reference, details, particulars) to identify the actual business.

1. **Online Services**: Look for company names, service names, or platform names
   - "Netflix" → "Netflix"
   - "Spotify" → "Spotify"
   - "Amazon" → "Amazon"
   - Clean up transaction codes, locations, and formatting

2. **Local Businesses**: Identify the actual business name, removing location details if they're just for identification
   - "Zambrero Courtney Wellington Nz" → "Zambrero" (local restaurant)
   - "Freemans Lotto Pipitea Nz" → "Freemans Lotto" (local shop)
   - "Badminton Wellington C Wellington Nz" → "Badminton Wellington" (local facility)
   - Keep location if it's part of the business name

3. **Hybrid Businesses**: Companies with both online and physical presence
   - Identify the company name regardless of whether transaction was online or in-store

## Categorization Guidelines

### Food & Dining
- Groceries → Food & Dining
- Restaurants, cafes → Food & Dining
- Food delivery services → Food & Dining

### Entertainment
- Streaming services (Netflix, Spotify, etc.) → Entertainment
- Movie theaters → Entertainment
- Recreation facilities → Entertainment
- Hobbies and games → Entertainment

### Shopping
- Retail stores → Shopping
- Online shopping → Shopping
- Clothing stores → Shopping

### Personal Care
- Gyms, fitness centers → Personal Care
- Salons, spas → Personal Care
- Personal hygiene products → Personal Care

### Transportation
- Gas stations → Transportation
- Public transit → Transportation
- Parking → Transportation
- Car maintenance → Transportation

## Important Notes

1. **Both Online and Local**: Personal expenses include both online services (streaming, subscriptions) and local businesses (restaurants, shops). Both are legitimate personal expenses.

2. **Context Matters**: Consider the personal context. For example:
   - "Netflix" → Entertainment (streaming service)
   - "Local Restaurant" → Food & Dining
   - "Gym" → Personal Care (fitness)

3. **When in Doubt**: If an expense could fit multiple categories, choose the most specific one. If truly unclear, use "Uncategorized" and note why.

## Output Format

When categorizing a transaction, provide:
1. **Business Name**: The cleaned business name
2. **Category**: The selected category name
3. **Reasoning**: Brief explanation of why this category was chosen, including what field/value provided the core information used to make the decision (e.g., "Identified from Code field: 'Netflix' - Netflix is a streaming service for movies and TV shows")

Example:
```
Business Name: Netflix
Category: Entertainment
Reasoning: Identified from Merchant field: 'Netflix' - Netflix is a streaming service for movies and TV shows, which is a personal entertainment expense.
```
```
