/**
 * API Route for Assigning Transactions by Credit Card
 * 
 * Assigns all transactions from a specific credit card to an entity
 */

import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

const ENTITIES_FILE = path.resolve(process.cwd(), '..', 'storage', 'entities.json');

interface Entity {
  id: string;
  name: string;
  type: 'Personal' | 'Business';
  transactions: string[]; // Array of transaction IDs
  cards?: string[]; // Assigned credit cards (array)
}

function getTransactionId(transaction: any): string {
  // Use the id field if available, otherwise fall back to old format for compatibility
  return transaction.id || `${transaction.merchant}_${transaction.amount}_${transaction.transaction_date}`;
}

function loadTransactions(): any[] {
  const projectRoot = path.resolve(process.cwd(), '..');
  const transactionsDir = path.join(projectRoot, 'storage', 'transactions');
  
  if (!fs.existsSync(transactionsDir)) {
    return [];
  }

  const files = fs.readdirSync(transactionsDir).filter(file => file.endsWith('.json'));
  const allTransactions: any[] = [];

  for (const file of files) {
    const filePath = path.join(transactionsDir, file);
    try {
      const fileContents = fs.readFileSync(filePath, 'utf-8');
      const transactions = JSON.parse(fileContents);
      if (Array.isArray(transactions)) {
        allTransactions.push(...transactions);
      }
    } catch (error) {
      console.error(`Error reading ${file}:`, error);
      continue;
    }
  }

  return allTransactions;
}

function loadEntities(): Entity[] {
  if (fs.existsSync(ENTITIES_FILE)) {
    const fileContents = fs.readFileSync(ENTITIES_FILE, 'utf-8');
    const entities = JSON.parse(fileContents);
    
    // Migrate old card field to cards array and add default type for backward compatibility
    let needsMigration = false;
    entities.forEach((entity: any) => {
      if (entity.card && !entity.cards) {
        // Convert single card to cards array
        entity.cards = [entity.card];
        delete entity.card;
        needsMigration = true;
      } else if (!entity.cards) {
        // Initialize empty cards array if neither exists
        entity.cards = [];
      }
      // Add default type for backward compatibility
      if (!entity.type) {
        entity.type = 'Personal';
        needsMigration = true;
      }
    });
    
    // Save migrated entities back to file
    if (needsMigration) {
      saveEntities(entities);
    }
    
    return entities;
  }
  return [];
}


function saveEntities(entities: Entity[]): void {
  fs.writeFileSync(ENTITIES_FILE, JSON.stringify(entities, null, 2), 'utf-8');
}

export async function POST(request: Request) {
  try {
    const { entityId, card, action } = await request.json();

    if (!entityId) {
      return NextResponse.json(
        { error: 'Entity ID is required' },
        { status: 400 }
      );
    }

    let entities = loadEntities();
    const entity = entities.find(e => e.id === entityId);
    if (!entity) {
      return NextResponse.json(
        { error: 'Entity not found' },
        { status: 404 }
      );
    }

    // Initialize cards array if it doesn't exist
    if (!entity.cards) {
      entity.cards = [];
    }

    // Handle remove action
    if (action === 'remove' && card) {
      // Remove the card from the entity's cards array
      entity.cards = entity.cards.filter(c => c !== card);
      
      // Optionally remove transactions from this card (or keep them assigned)
      // For now, we'll keep the transactions assigned even if the card is removed
      
      saveEntities(entities);
      return NextResponse.json({ success: true, entity });
    }

    // Handle add action (default)
    if (!card || card === '') {
      return NextResponse.json(
        { error: 'Card is required' },
        { status: 400 }
      );
    }

    // Check if card is already assigned
    if (entity.cards.includes(card)) {
      return NextResponse.json(
        { error: 'Card is already assigned to this entity' },
        { status: 400 }
      );
    }

    const transactions = loadTransactions();

    // Find all transaction IDs for the specified card
    const cardTransactionIds: string[] = transactions
      .filter((t: any) => t.card === card)
      .map((t: any) => getTransactionId(t));

    if (cardTransactionIds.length === 0) {
      return NextResponse.json(
        { error: 'No transactions found for this card' },
        { status: 404 }
      );
    }

    // Remove transactions from other entities first
    entities.forEach(e => {
      if (e.id !== entityId) {
        e.transactions = e.transactions.filter(tid => !cardTransactionIds.includes(tid));
      }
    });

    // Add transactions to this entity (avoid duplicates)
    const existingIds = new Set(entity.transactions);
    cardTransactionIds.forEach((tid: string) => {
      if (!existingIds.has(tid)) {
        entity.transactions.push(tid);
      }
    });

    // Add the card to the entity's cards array
    entity.cards.push(card);

    saveEntities(entities);
    return NextResponse.json({ 
      success: true, 
      entity,
      assignedCount: cardTransactionIds.length 
    });
  } catch (error) {
    console.error('Error assigning by card:', error);
    return NextResponse.json(
      { error: 'Failed to assign transactions by card' },
      { status: 500 }
    );
  }
}

