#!/usr/bin/env python3
"""
Assign Existing Transactions to Entities by Credit Card or Bank Account

Fills in entity membership for transactions that are not yet linked to any entity:
- if a transaction's `card` matches an entity's `cards` entry, or
- if a transaction's `account` matches an entity's `accounts` entry,
it is appended to that entity's `transactions` list.

Account matching covers bank-account credits/debits that have no card number
(e.g. Stripe Direct Credits on Century Digital Main Account).

Transactions already listed on any entity are skipped so re-running
categorize_transactions / process_new_transactions does not undo manual
assignments from the web app.

Usage:
    python assign_transactions_by_card.py
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Set

def normalize_card_number(card: str) -> str:
    """Normalize card number by removing spaces and hyphens, keeping only digits and stars."""
    if not card:
        return ''
    # Remove all spaces and hyphens, keep only alphanumeric and stars
    normalized = ''.join(c for c in card.strip() if c.isalnum() or c == '*')
    return normalized

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
            if 'accounts' not in entity:
                entity['accounts'] = []
        
        return entities
    except Exception as e:
        print(f"Error: Failed to load entities: {e}")
        return []

def save_entities(project_root: Path, entities: List[Dict[str, Any]]) -> None:
    """Save entities to storage/entities.json."""
    entities_file = project_root / 'storage' / 'entities.json'
    try:
        # Save entities
        with open(entities_file, 'w', encoding='utf-8') as f:
            json.dump(entities, f, indent=2, ensure_ascii=False)
        print(f"  Saved entities to {entities_file}")
    except Exception as e:
        print(f"Error: Failed to save entities: {e}")
        raise

def load_all_transactions(project_root: Path) -> List[Dict[str, Any]]:
    """Load all transactions from storage/transactions/ directory."""
    transactions_dir = project_root / 'storage' / 'transactions'
    if not transactions_dir.exists():
        return []
    
    all_transactions = []
    for json_file in transactions_dir.glob('*.json'):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                transactions = json.load(f)
                if isinstance(transactions, list):
                    all_transactions.extend(transactions)
                else:
                    print(f"Warning: {json_file.name} does not contain a list of transactions")
        except Exception as e:
            print(f"Error loading {json_file.name}: {e}")
    
    return all_transactions

def _transaction_linked_to_any_entity(transaction_id: str, entities: List[Dict[str, Any]]) -> bool:
    """True if this transaction id appears on any entity (user or prior run linked it)."""
    for entity in entities:
        if transaction_id in entity.get('transactions', []):
            return True
    return False


def assign_transactions_to_entities_by_card(transactions: List[Dict[str, Any]], project_root: Path) -> Dict[str, int]:
    """
    Assign transactions to entities based on credit card numbers.

    Only assigns transactions that are not yet linked to any entity. If a transaction
    already appears in any entity's `transactions` list (e.g. set in the web app),
    it is left alone so re-running the CSV processor does not override manual choices.

    Returns:
        Dictionary with statistics: {'assigned': count, 'already_assigned': count, 'no_card': count, 'no_match': count}
    """
    entities = load_entities(project_root)
    if not entities:
        print("No entities found. Please create entities first.")
        return {'assigned': 0, 'already_assigned': 0, 'no_card': 0, 'no_match': 0}
    
    # Build a map of normalized card -> entity for quick lookup
    # Also store original card formats for each entity
    card_to_entity = {}
    entity_cards_map = {}  # entity_id -> set of normalized cards
    
    for entity in entities:
        entity_id = entity.get('id', '')
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
        entity_cards_map[entity_id] = entity_normalized_cards
    
    if not card_to_entity:
        print("No credit cards assigned to entities. Please assign cards to entities first.")
        return {'assigned': 0, 'already_assigned': 0, 'no_card': 0, 'no_match': 0}
    
    stats = {
        'assigned': 0,
        'already_assigned': 0,
        'no_card': 0,
        'no_match': 0
    }
    entities_modified = False

    for transaction in transactions:
        transaction_card = transaction.get('card')
        if not transaction_card:
            stats['no_card'] += 1
            continue

        transaction_id = get_transaction_id(transaction)

        if _transaction_linked_to_any_entity(transaction_id, entities):
            stats['already_assigned'] += 1
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

        if not matching_entity:
            stats['no_match'] += 1
            continue

        # Sanity check: the entity we matched must actually have this card in its list
        matching_entity_cards = entity_cards_map.get(matching_entity.get('id'), set())
        if normalized_transaction_card not in matching_entity_cards:
            # Should not happen if card_to_entity is built correctly; skip to avoid wrong assignment
            stats['no_match'] += 1
            continue

        # Add to matching entity (transaction was not linked to any entity)
        if 'transactions' not in matching_entity:
            matching_entity['transactions'] = []
        if transaction_id not in matching_entity['transactions']:
            matching_entity['transactions'].append(transaction_id)
            entities_modified = True
            stats['assigned'] += 1
    
    # Save entities if any changes were made
    if entities_modified:
        save_entities(project_root, entities)
    
    return stats


def assign_transactions_to_entities_by_account(transactions: List[Dict[str, Any]], project_root: Path) -> Dict[str, int]:
    """
    Assign transactions to entities based on bank account numbers.

    Matches transaction `account` (e.g. 01-0142-0771521-00) to an entity's
    `accounts` list. Only assigns transactions not yet linked to any entity.

    Returns:
        Dictionary with statistics: {'assigned': count, 'already_assigned': count,
        'no_account': count, 'no_match': count}
    """
    entities = load_entities(project_root)
    if not entities:
        print("No entities found. Please create entities first.")
        return {'assigned': 0, 'already_assigned': 0, 'no_account': 0, 'no_match': 0}

    account_to_entity: Dict[str, Dict[str, Any]] = {}
    for entity in entities:
        for account in entity.get('accounts', []):
            if account and str(account).strip():
                account_to_entity[str(account).strip()] = entity

    if not account_to_entity:
        print("No bank accounts assigned to entities. Skipping account-based assignment.")
        return {'assigned': 0, 'already_assigned': 0, 'no_account': 0, 'no_match': 0}

    stats = {
        'assigned': 0,
        'already_assigned': 0,
        'no_account': 0,
        'no_match': 0,
    }
    entities_modified = False

    for transaction in transactions:
        transaction_account = transaction.get('account')
        if not transaction_account:
            stats['no_account'] += 1
            continue

        transaction_id = get_transaction_id(transaction)

        if _transaction_linked_to_any_entity(transaction_id, entities):
            stats['already_assigned'] += 1
            continue

        matching_entity = account_to_entity.get(str(transaction_account).strip())
        if not matching_entity:
            stats['no_match'] += 1
            continue

        if 'transactions' not in matching_entity:
            matching_entity['transactions'] = []
        if transaction_id not in matching_entity['transactions']:
            matching_entity['transactions'].append(transaction_id)
            entities_modified = True
            stats['assigned'] += 1

    if entities_modified:
        save_entities(project_root, entities)

    return stats


def main():
    """Main function."""
    project_root = Path(__file__).parent
    
    print("=" * 60)
    print("Assign Transactions to Entities by Card / Account")
    print("=" * 60)
    print()
    
    # Load all transactions
    print("Loading transactions...")
    transactions = load_all_transactions(project_root)
    print(f"  Found {len(transactions)} transaction(s)")
    
    if not transactions:
        print("No transactions found. Nothing to assign.")
        return
    
    # Load entities
    print("\nLoading entities...")
    entities = load_entities(project_root)
    print(f"  Found {len(entities)} entity/entities")
    
    if not entities:
        print("No entities found. Please create entities first.")
        return
    
    # Count entities with cards / accounts
    entities_with_cards = sum(1 for e in entities if e.get('cards'))
    entities_with_accounts = sum(1 for e in entities if e.get('accounts'))
    print(f"  {entities_with_cards} entity/entities have credit cards assigned")
    print(f"  {entities_with_accounts} entity/entities have bank accounts assigned")
    
    if entities_with_cards == 0 and entities_with_accounts == 0:
        print("\nNo entities have cards or accounts assigned. Assign them first.")
        return
    
    # Assign by card, then by account (account covers Stripe Direct Credits etc.)
    card_stats = {'assigned': 0, 'already_assigned': 0, 'no_card': 0, 'no_match': 0}
    account_stats = {'assigned': 0, 'already_assigned': 0, 'no_account': 0, 'no_match': 0}

    if entities_with_cards > 0:
        print("\nAssigning transactions to entities based on credit cards...")
        card_stats = assign_transactions_to_entities_by_card(transactions, project_root)

    if entities_with_accounts > 0:
        print("\nAssigning transactions to entities based on bank accounts...")
        # Reload after card assignment so we don't double-assign
        transactions = load_all_transactions(project_root)
        account_stats = assign_transactions_to_entities_by_account(transactions, project_root)
    
    # Print results
    print("\n" + "=" * 60)
    print("Results:")
    print("=" * 60)
    print("By card:")
    print(f"  [OK] Assigned: {card_stats['assigned']} transaction(s)")
    print(f"  - Already assigned: {card_stats['already_assigned']} transaction(s)")
    print(f"  - No card number: {card_stats['no_card']} transaction(s)")
    print(f"  - No matching entity: {card_stats['no_match']} transaction(s)")
    print("By account:")
    print(f"  [OK] Assigned: {account_stats['assigned']} transaction(s)")
    print(f"  - Already assigned: {account_stats['already_assigned']} transaction(s)")
    print(f"  - No account number: {account_stats['no_account']} transaction(s)")
    print(f"  - No matching entity: {account_stats['no_match']} transaction(s)")
    print()
    
    total_assigned = card_stats['assigned'] + account_stats['assigned']
    if total_assigned > 0:
        print(f"[OK] Successfully assigned {total_assigned} transaction(s) to entities!")
    else:
        print("No new assignments made.")
    print()

if __name__ == '__main__':
    main()

