/**
 * API Route for Updating Transaction Category
 * 
 * Updates a transaction's category in storage/transactions.json
 */

import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

import { getAllCategories } from '../../../lib/categories';

const CATEGORIES = getAllCategories();

export async function POST(request: Request) {
  try {
    const { transactionId, category, identified_business, is_transfer } = await request.json();

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

    // Update the transaction
    if (category !== undefined) {
      transactions[foundIndex].category = category || null;
      transactions[foundIndex].categorized = category !== '';
      transactions[foundIndex].category_description = category ? 'Manually updated by user' : null;
      transactions[foundIndex].categorized_at = category ? new Date().toISOString() : null;
    }
    if (identified_business !== undefined) {
      const oldIdentifiedBusiness = transactions[foundIndex].identified_business || null;
      const newIdentifiedBusiness = identified_business || null;
      
      // Only update if the value actually changed
      if (oldIdentifiedBusiness !== newIdentifiedBusiness) {
        transactions[foundIndex].identified_business = newIdentifiedBusiness;
        // Mark as manually updated if merchant name was changed
        // If category wasn't also updated, preserve existing description or set new one
        if (category === undefined) {
          const existingDesc = transactions[foundIndex].category_description;
          // If there's an existing LLM-generated description, append note
          if (existingDesc && !existingDesc.includes('Manually updated by user')) {
            transactions[foundIndex].category_description = existingDesc + ' (Merchant name manually updated)';
          } else {
            // Otherwise mark as manually updated
            transactions[foundIndex].category_description = 'Manually updated by user';
          }
          // Update categorized_at if not already set
          if (!transactions[foundIndex].categorized_at) {
            transactions[foundIndex].categorized_at = new Date().toISOString();
          }
        }
        // If category was also updated, category_description is already set to 'Manually updated by user'
      }
    }
    if (is_transfer !== undefined) {
      transactions[foundIndex].is_transfer = is_transfer;
    }

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

