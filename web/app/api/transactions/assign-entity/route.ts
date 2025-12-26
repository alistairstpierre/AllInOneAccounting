/**
 * API Route for Assigning/Unassigning Transaction to Entity
 * 
 * Updates entity assignments in storage/entities.json
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
    const { transactionId, entityId } = await request.json(); // entityId can be null for unassign

    if (!transactionId) {
      return NextResponse.json(
        { error: 'Transaction ID is required' },
        { status: 400 }
      );
    }

    let entities = loadEntities();

    // Remove transaction from all entities first
    entities.forEach(entity => {
      entity.transactions = entity.transactions.filter(tid => tid !== transactionId);
    });

    // If entityId is provided and not null, assign to that entity
    if (entityId !== null && entityId !== undefined && entityId !== '') {
      const targetEntity = entities.find(e => e.id === entityId);
      if (!targetEntity) {
        return NextResponse.json(
          { error: 'Entity not found' },
          { status: 404 }
        );
      }

      // Add transaction to target entity (avoid duplicates)
      if (!targetEntity.transactions.includes(transactionId)) {
        targetEntity.transactions.push(transactionId);
      }
    }

    saveEntities(entities);
    return NextResponse.json({ success: true, entities });
  } catch (error) {
    console.error('Error assigning entity:', error);
    return NextResponse.json(
      { error: 'Failed to assign entity' },
      { status: 500 }
    );
  }
}

