/**
 * API Route for Assigning Transactions by Bank Account
 *
 * Links a bank account number (e.g. 01-0142-0771521-00) to an entity and
 * assigns all matching transactions — including Direct Credits with no card.
 * Mirrors assign-by-card for account-based entity membership.
 */

import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

const ENTITIES_FILE = path.resolve(process.cwd(), '..', 'storage', 'entities.json');

interface Entity {
  id: string;
  name: string;
  type: 'Personal' | 'Business';
  transactions: string[];
  cards?: string[];
  accounts?: string[];
}

function getTransactionId(transaction: any): string {
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

    let needsMigration = false;
    entities.forEach((entity: any) => {
      if (!entity.cards) {
        entity.cards = [];
      }
      if (!entity.accounts) {
        entity.accounts = [];
        needsMigration = true;
      }
      if (!entity.type) {
        entity.type = 'Personal';
        needsMigration = true;
      }
    });

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
    const { entityId, account, action } = await request.json();

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

    if (!entity.accounts) {
      entity.accounts = [];
    }

    if (action === 'remove' && account) {
      entity.accounts = entity.accounts.filter(a => a !== account);
      saveEntities(entities);
      return NextResponse.json({ success: true, entity });
    }

    if (!account || account === '') {
      return NextResponse.json(
        { error: 'Account is required' },
        { status: 400 }
      );
    }

    if (entity.accounts.includes(account)) {
      return NextResponse.json(
        { error: 'Account is already assigned to this entity' },
        { status: 400 }
      );
    }

    const transactions = loadTransactions();

    const accountTransactionIds: string[] = transactions
      .filter((t: any) => t.account === account)
      .map((t: any) => getTransactionId(t));

    if (accountTransactionIds.length === 0) {
      return NextResponse.json(
        { error: 'No transactions found for this account' },
        { status: 404 }
      );
    }

    // Remove these transactions from other entities first
    entities.forEach(e => {
      if (e.id !== entityId) {
        e.transactions = e.transactions.filter(tid => !accountTransactionIds.includes(tid));
      }
    });

    const existingIds = new Set(entity.transactions);
    accountTransactionIds.forEach((tid: string) => {
      if (!existingIds.has(tid)) {
        entity.transactions.push(tid);
      }
    });

    entity.accounts.push(account);

    saveEntities(entities);
    return NextResponse.json({
      success: true,
      entity,
      assignedCount: accountTransactionIds.length,
    });
  } catch (error) {
    console.error('Error assigning by account:', error);
    return NextResponse.json(
      { error: 'Failed to assign transactions by account' },
      { status: 500 }
    );
  }
}
