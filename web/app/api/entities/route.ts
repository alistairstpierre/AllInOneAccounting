/**
 * API Route for Entities
 * 
 * Manages entities (people/organizations) and their transaction assignments
 */

import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

const ENTITIES_FILE = path.resolve(process.cwd(), '..', 'storage', 'entities.json');

export type EntityType = 'Personal' | 'Business';

interface Entity {
  id: string;
  name: string;
  type: EntityType; // Type of entity: Personal or Business
  transactions: string[]; // Array of transaction IDs (merchant_amount_date)
  cards?: string[]; // Assigned credit cards (array)
  accounts?: string[]; // Assigned bank account numbers (array)
}

function getTransactionId(transaction: any): string {
  // Use the id field if available, otherwise fall back to old format for compatibility
  return transaction.id || `${transaction.merchant}_${transaction.amount}_${transaction.transaction_date}`;
}

function loadEntities(): Entity[] {
  if (fs.existsSync(ENTITIES_FILE)) {
    const fileContents = fs.readFileSync(ENTITIES_FILE, 'utf-8');
    const entities = JSON.parse(fileContents);
    
    // Migrate old card field to cards array for backward compatibility
    // Also add default type for entities without a type field
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
      if (!entity.accounts) {
        entity.accounts = [];
        needsMigration = true;
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

export async function GET() {
  try {
    const entities = loadEntities();
    return NextResponse.json(entities);
  } catch (error) {
    console.error('Error loading entities:', error);
    return NextResponse.json(
      { error: 'Failed to load entities' },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  try {
    const { action, entityName, entityId, transactionIds, entityType } = await request.json();

    let entities = loadEntities();

    if (action === 'create') {
      // Create new entity
      const newEntity: Entity = {
        id: Date.now().toString(),
        name: entityName,
        type: entityType || 'Personal', // Default to Personal if not specified
        transactions: [],
      };
      entities.push(newEntity);
      saveEntities(entities);
      return NextResponse.json({ success: true, entity: newEntity });
    } else if (action === 'assign') {
      // Assign transactions to entity
      const entity = entities.find(e => e.id === entityId);
      if (!entity) {
        return NextResponse.json(
          { error: 'Entity not found' },
          { status: 404 }
        );
      }

      // Remove transactions from other entities first
      entities.forEach(e => {
        if (e.id !== entityId) {
          e.transactions = e.transactions.filter(tid => !transactionIds.includes(tid));
        }
      });

      // Add transactions to this entity (avoid duplicates)
      const existingIds = new Set(entity.transactions);
      transactionIds.forEach((tid: string) => {
        if (!existingIds.has(tid)) {
          entity.transactions.push(tid);
        }
      });

      saveEntities(entities);
      return NextResponse.json({ success: true, entity });
    } else if (action === 'unassign') {
      // Unassign transactions from entity
      const entity = entities.find(e => e.id === entityId);
      if (!entity) {
        return NextResponse.json(
          { error: 'Entity not found' },
          { status: 404 }
        );
      }

      entity.transactions = entity.transactions.filter(tid => !transactionIds.includes(tid));
      saveEntities(entities);
      return NextResponse.json({ success: true, entity });
    } else if (action === 'delete') {
      // Delete entity
      const index = entities.findIndex(e => e.id === entityId);
      if (index === -1) {
        return NextResponse.json(
          { error: 'Entity not found' },
          { status: 404 }
        );
      }

      entities.splice(index, 1);
      saveEntities(entities);
      return NextResponse.json({ success: true });
    }

    return NextResponse.json(
      { error: 'Invalid action' },
      { status: 400 }
    );
  } catch (error) {
    console.error('Error managing entities:', error);
    return NextResponse.json(
      { error: 'Failed to manage entities' },
      { status: 500 }
    );
  }
}

