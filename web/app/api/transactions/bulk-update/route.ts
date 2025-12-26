/**
 * API Route for Bulk Updating Transaction Categories
 * 
 * Updates multiple transactions' categories at once
 */

import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

const TRANSACTIONS_FILE = path.resolve(process.cwd(), '..', 'storage', 'transactions.json');

function getTransactionId(transaction: any): string {
  // Use the id field if available, otherwise fall back to old format for compatibility
  return transaction.id || `${transaction.merchant}_${transaction.amount}_${transaction.transaction_date}`;
}

export async function POST(request: Request) {
  try {
    const { transactionIds, category } = await request.json();

    if (!transactionIds || !Array.isArray(transactionIds) || transactionIds.length === 0) {
      return NextResponse.json(
        { error: 'Transaction IDs array is required' },
        { status: 400 }
      );
    }

    // Path to transactions directory
    const projectRoot = path.resolve(process.cwd(), '..');
    const transactionsDir = path.join(projectRoot, 'storage', 'transactions');

    // Check if directory exists
    if (!fs.existsSync(transactionsDir)) {
      return NextResponse.json(
        { error: 'Transactions directory not found' },
        { status: 404 }
      );
    }

    // Create a set for fast lookup
    const idsSet = new Set(transactionIds);
    let updatedCount = 0;

    // Search through all account files
    const files = fs.readdirSync(transactionsDir).filter(file => file.endsWith('.json'));
    
    for (const file of files) {
      const filePath = path.join(transactionsDir, file);
      try {
        const fileContents = fs.readFileSync(filePath, 'utf-8');
        const transactions = JSON.parse(fileContents);
        let fileUpdated = false;

        // Update matching transactions in this file
        transactions.forEach((t: any) => {
          const tId = getTransactionId(t);
          if (idsSet.has(tId)) {
            t.category = category || null;
            t.categorized = category !== '';
            t.category_description = category ? 'Manually updated by user' : null;
            t.categorized_at = category ? new Date().toISOString() : null;
            updatedCount++;
            fileUpdated = true;
          }
        });

        // Write back to file if any transactions were updated
        if (fileUpdated) {
          fs.writeFileSync(filePath, JSON.stringify(transactions, null, 2), 'utf-8');
        }
      } catch (error) {
        console.error(`Error updating ${file}:`, error);
        continue;
      }
    }

    return NextResponse.json({ 
      success: true, 
      updatedCount 
    });
  } catch (error) {
    console.error('Error bulk updating transactions:', error);
    return NextResponse.json(
      { error: 'Failed to bulk update transactions' },
      { status: 500 }
    );
  }
}

