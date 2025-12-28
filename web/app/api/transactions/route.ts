/**
 * API Route for Transactions
 * 
 * Serves categorized transactions from account-specific JSON files in storage/transactions/
 * This endpoint provides transaction data to the frontend React components.
 */

import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET() {
  try {
    // Path to transactions directory (go up from web directory to root, then to storage/transactions)
    // process.cwd() in Next.js API routes gives us the web directory
    // We need to go up one level to get to the project root
    const projectRoot = path.resolve(process.cwd(), '..');
    const transactionsDir = path.join(projectRoot, 'storage', 'transactions');
    
    // Check if directory exists
    if (!fs.existsSync(transactionsDir)) {
      return NextResponse.json([]);
    }

    // Read all JSON files in the transactions directory
    const files = fs.readdirSync(transactionsDir).filter(file => file.endsWith('.json'));
    const allTransactions: any[] = [];

    for (const file of files) {
      const filePath = path.join(transactionsDir, file);
      try {
        const fileContents = fs.readFileSync(filePath, 'utf-8');
        const transactions = JSON.parse(fileContents);
        if (Array.isArray(transactions)) {
          // Extract the file name without .json extension
          const transactionFileName = file.replace(/\.json$/, '');
          // Add the transaction file name to each transaction
          const transactionsWithFileName = transactions.map((t: any) => ({
            ...t,
            transaction_file: transactionFileName
          }));
          allTransactions.push(...transactionsWithFileName);
        }
      } catch (error) {
        console.error(`Error reading ${file}:`, error);
        // Continue with other files even if one fails
      }
    }

    return NextResponse.json(allTransactions);
  } catch (error) {
    console.error('Error reading transactions:', error);
    return NextResponse.json(
      { error: 'Failed to load transactions' },
      { status: 500 }
    );
  }
}

