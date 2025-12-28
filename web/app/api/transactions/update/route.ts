/**
 * API Route for Updating Transaction Category
 * 
 * Updates a transaction's category in storage/transactions.json
 */

import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

import { getAllCategories } from '../../../lib/categories';
import { updateTransaction } from '../../../lib/transaction-update';

const CATEGORIES = getAllCategories();

export async function POST(request: Request) {
  try {
    const { transactionId, category, identified_business, is_transfer, is_credit } = await request.json();

    // Validate category (allow empty string for uncategorized)
    if (category !== undefined && category !== '' && !CATEGORIES.includes(category)) {
      return NextResponse.json(
        { error: 'Invalid category' },
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

    // Search through all account files to find the transaction
    const files = fs.readdirSync(transactionsDir).filter(file => file.endsWith('.json'));
    let foundTransaction: any = null;
    let foundFile: string | null = null;
    let foundIndex: number = -1;

    for (const file of files) {
      const filePath = path.join(transactionsDir, file);
      try {
        const fileContents = fs.readFileSync(filePath, 'utf-8');
        const transactions = JSON.parse(fileContents);
        
        const index = transactions.findIndex((t: any) => {
          if (typeof transactionId === 'string') {
            // New format: transactionId is a string (ID)
            const tId = t.id || `${t.merchant}_${t.amount}_${t.transaction_date}`;
            return tId === transactionId;
          } else {
            // Old format: transactionId is an object (for backward compatibility)
            return t.merchant === transactionId.merchant &&
                   t.amount === transactionId.amount &&
                   t.transaction_date === transactionId.transaction_date;
          }
        });

        if (index !== -1) {
          foundTransaction = transactions[index];
          foundFile = file;
          foundIndex = index;
          break;
        }
      } catch (error) {
        console.error(`Error reading ${file}:`, error);
        continue;
      }
    }

    if (!foundTransaction || !foundFile || foundIndex === -1) {
      return NextResponse.json(
        { error: 'Transaction not found' },
        { status: 404 }
      );
    }

    // Read the file again to get all transactions
    const filePath = path.join(transactionsDir, foundFile);
    const fileContents = fs.readFileSync(filePath, 'utf-8');
    const transactions = JSON.parse(fileContents);

    // Prepare updates object
    const updates: any = {};
    if (category !== undefined) {
      updates.category = category;
    }
    if (identified_business !== undefined) {
      updates.identified_business = identified_business;
    }
    if (is_transfer !== undefined) {
      updates.is_transfer = is_transfer;
    }
    if (is_credit !== undefined) {
      updates.is_credit = is_credit;
    }

    // Use utility function to update transaction (only marks as updated if values changed)
    const { transaction: updatedTransaction, wasUpdated } = updateTransaction(
      transactions[foundIndex],
      updates
    );

    // Set category_description if category was updated and value changed
    if (category !== undefined && wasUpdated) {
      updatedTransaction.category_description = category ? 'Manually updated by user' : null;
    } else if (identified_business !== undefined && wasUpdated && category === undefined) {
      // If only merchant name was updated (and value changed), preserve or update description
      const existingDesc = updatedTransaction.category_description;
      if (existingDesc && !existingDesc.includes('Manually updated by user')) {
        updatedTransaction.category_description = existingDesc + ' (Merchant name manually updated)';
      } else if (!existingDesc) {
        updatedTransaction.category_description = 'Manually updated by user';
      }
    }

    transactions[foundIndex] = updatedTransaction;

    // Write back to file
    fs.writeFileSync(filePath, JSON.stringify(transactions, null, 2), 'utf-8');

    // Return the updated transaction
    return NextResponse.json({ success: true, transaction: transactions[foundIndex] });
  } catch (error) {
    console.error('Error updating transaction:', error);
    return NextResponse.json(
      { error: 'Failed to update transaction' },
      { status: 500 }
    );
  }
}

