# categorize_transactions.py - Complete Analysis

## File Statistics
- **Total Lines**: ~2,332 lines
- **Total Functions**: 25 functions
- **Main Entry Point**: `main()` function

---

## SECTION 1: Imports and Configuration (Lines 1-92)
**Purpose**: Setup, imports, constants

### Components:
1. **Imports** (lines 17-27): Standard libraries + OpenAI
2. **OpenAI Setup** (lines 36-53): Handles OpenAI client initialization with error handling
3. **Category Lists** (lines 55-91): PERSONAL_CATEGORIES and BUSINESS_CATEGORIES arrays

**Keep?** ✅ **YES** - Essential foundation
- Imports are necessary
- OpenAI setup is needed for AI categorization
- Category lists must match web app categories

---

## SECTION 2: LLM/Prompt Functions (Lines 93-599)
**Purpose**: Functions for AI categorization

### Functions:
1. **`load_prompt_template()`** (93-101): Loads prompt file
2. **`looks_like_person_name()`** (104-148): Detects if merchant is a person's name
3. **`build_llm_prompt()`** (150-226): Builds the prompt sent to OpenAI
4. **`parse_llm_response()`** (228-251): Parses AI response
5. **`identify_and_categorize_transaction_batch()`** (253-483): Batch processing (UNUSED?)
6. **`identify_and_categorize_transaction()`** (485-597): Single transaction AI processing

**Keep?** 
- ✅ `load_prompt_template()` - YES, needed
- ✅ `looks_like_person_name()` - YES, helps with transfer detection
- ✅ `build_llm_prompt()` - YES, core AI functionality
- ✅ `parse_llm_response()` - YES, needed to parse AI output
- ❓ `identify_and_categorize_transaction_batch()` - **CHECK IF USED** - May be dead code
- ✅ `identify_and_categorize_transaction()` - YES, core AI function

---

## SECTION 3: Entity Assignment Functions (Lines 617-761)
**Purpose**: Assign transactions to entities based on credit cards

### Functions:
1. **`get_transaction_id()`** (617-619): Gets transaction ID
2. **`load_entities()`** (621-641): Loads entities.json
3. **`save_entities()`** (643-649): Saves entities.json
4. **`normalize_card_number()`** (651-657): Normalizes card number formats
5. **`assign_transactions_to_entities_by_card()`** (659-761): Main entity assignment logic

**Keep?** ✅ **YES** - All needed for entity assignment feature
- These functions work together to assign transactions to entities
- User requested this feature earlier

---

## SECTION 4: Utility Functions (Lines 599-966)
**Purpose**: Helper functions for various tasks

### Functions:
1. **`save_json_safely()`** (599-615): Atomic JSON file saving
2. **`parse_csv_date()`** (800-808): Converts CSV date formats
3. **`sanitize_account_id()`** (810-812): Cleans account IDs
4. **`is_masked_card()`** (814-819): Checks if string is masked card
5. **`extract_card_number()`** (821-829): Extracts card number from string
6. **`is_transfer()`** (831-894): Detects if transaction is a transfer
7. **`normalize_merchant_name()`** (896-903): Normalizes merchant names
8. **`generate_transaction_id_from_csv()`** (905-965): Generates unique transaction IDs
9. **`is_duplicate_transaction()`** (967-1032): Checks for duplicate transactions

**Keep?**
- ✅ `save_json_safely()` - YES, prevents data corruption
- ✅ `parse_csv_date()` - YES, needed for date parsing
- ✅ `sanitize_account_id()` - YES, safety function
- ✅ `is_masked_card()` - YES, used in transfer detection
- ✅ `extract_card_number()` - YES, used for card extraction
- ✅ `is_transfer()` - YES, critical for transfer detection
- ✅ `normalize_merchant_name()` - YES, used for merchant matching
- ✅ `generate_transaction_id_from_csv()` - YES, needed for unique IDs
- ✅ `is_duplicate_transaction()` - YES, prevents duplicates

---

## SECTION 5: CSV Parsing (Lines 1035-1217)
**Purpose**: Parse CSV files into transaction dictionaries

### Functions:
1. **`parse_csv_file()`** (1035-1217): Main CSV parser - handles both credit card and checking account formats

**Keep?** ✅ **YES** - Core functionality
- This is the heart of the script
- Handles two different CSV formats
- Extracts code/reference fields
- Builds transaction_context

**Complexity**: This function is ~180 lines. Could potentially be split into:
- `parse_credit_card_csv()`
- `parse_checking_account_csv()`
- But it's manageable as-is

---

## SECTION 6: Account/Transaction Utilities (Lines 1219-1227)
**Purpose**: Account-related utilities

### Functions:
1. **`normalize_account_for_signature()`** (1219-1227): Normalizes account IDs for duplicate detection

**Keep?** ✅ **YES** - Needed for duplicate detection

---

## SECTION 7: Progress Saving (Lines 762-798)
**Purpose**: Incremental saving during processing

### Functions:
1. **`_save_progress_incremental()`** (762-798): Saves progress incrementally to prevent data loss

**Keep?** ✅ **YES** - Important for long-running processes
- Prevents data loss if script crashes
- Saves after each batch of AI calls

---

## SECTION 8: Main Processing Function (Lines 1229-2281)
**Purpose**: The main `process_account()` function - orchestrates everything

**Size**: ~1,052 lines - **THIS IS THE PROBLEM**

### Sub-sections within process_account():

#### 8.1: Setup and Loading (lines ~1229-1400)
- Loads account configuration
- Loads existing transactions
- Finds CSV files
- Builds merchant category lookup

**Keep?** ✅ **YES** - Essential setup

#### 8.2: CSV Processing Loop (lines ~1400-1900)
- Loops through CSV files
- Parses each CSV
- Processes each transaction
- Handles duplicates
- Builds transaction_context
- Creates processed_txn objects

**Keep?** ✅ **YES** - Core processing logic
**Complexity**: This section is very long (~500 lines). Could be extracted into:
- `process_csv_transactions()` function
- `build_transaction_context()` function
- `create_processed_transaction()` function

#### 8.3: AI Categorization (lines ~1900-2225)
- Filters transactions needing categories
- Processes with AI (with threading/rate limiting)
- Handles errors and retries
- Updates merchant names for "If"/"Df" transactions

**Keep?** ✅ **YES** - Core AI functionality
**Complexity**: Could be extracted into:
- `categorize_transactions_with_ai()` function

#### 8.4: Final Processing (lines ~2225-2281)
- Merges transactions
- Assigns to entities
- Saves final JSON

**Keep?** ✅ **YES** - Finalization steps

---

## SECTION 9: Main Entry Point (Lines 2284-2331)
**Purpose**: CLI entry point

### Functions:
1. **`main()`** (2284-2327): Parses arguments, finds accounts, calls process_account()

**Keep?** ✅ **YES** - Entry point

---

## RECOMMENDATIONS FOR SIMPLIFICATION

### High Priority Refactoring:
1. **Extract `process_account()` sub-functions**:
   - `load_account_data()` - Setup and loading
   - `process_csv_files()` - CSV processing loop
   - `categorize_with_ai()` - AI categorization
   - `finalize_transactions()` - Final merge and save

2. **Check for dead code**:
   - `identify_and_categorize_transaction_batch()` - Verify if used

3. **Simplify transaction_context building**:
   - Extract into `build_transaction_context()` function
   - Currently duplicated logic in multiple places

### Medium Priority:
1. **Split CSV parsing**:
   - Could split `parse_csv_file()` into credit card and checking account parsers
   - But current structure is fine if well-documented

2. **Consolidate utility functions**:
   - Some utility functions are only used once - could inline them
   - But keeping them separate improves readability

---

## SUMMARY

**Total Functions**: 25
**Functions to Keep**: ~23-24 (need to verify batch function)
**Functions to Consider Removing**: 1 (batch function if unused)

**Main Issue**: The `process_account()` function is 1,052 lines - this should be broken into smaller functions.

**Estimated Reduction**: Breaking `process_account()` into 4-5 functions could reduce it from 1,052 lines to ~200-300 lines per function, making it much more maintainable.


