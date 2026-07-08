/**
 * API Route for Bulk Updating Transaction reconciled_at
 *
 * Sets reconciled_at for multiple transactions at once (e.g. "reconcile up to here").
 */

import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { updateTransaction } from '../../../lib/transaction-update';

function getTransactionId(transaction: any): string {
  return transaction.id || `${transaction.merchant}_${transaction.amount}_${transaction.transaction_date}`;
}

export async function POST(request: Request) {
  try {
    const { transactionIds, reconciled_at } = await request.json();

    if (!transactionIds || !Array.isArray(transactionIds) || transactionIds.length === 0) {
      return NextResponse.json(
        { error: 'Transaction IDs array is required' },
        { status: 400 }
      );
    }

    const projectRoot = path.resolve(process.cwd(), '..');
    const transactionsDir = path.join(projectRoot, 'storage', 'transactions');

    if (!fs.existsSync(transactionsDir)) {
      return NextResponse.json(
        { error: 'Transactions directory not found' },
        { status: 404 }
      );
    }

    const idsSet = new Set(transactionIds);
    let updatedCount = 0;

    const files = fs.readdirSync(transactionsDir).filter((file: string) => file.endsWith('.json'));

    for (const file of files) {
      const filePath = path.join(transactionsDir, file);
      try {
        const fileContents = fs.readFileSync(filePath, 'utf-8');
        const transactions = JSON.parse(fileContents);
        let fileUpdated = false;

        transactions.forEach((t: any, index: number) => {
          const tId = getTransactionId(t);
          if (idsSet.has(tId)) {
            const { transaction: updatedTransaction, wasUpdated } = updateTransaction(t, {
              reconciled_at: reconciled_at ?? null,
            });
            if (wasUpdated) {
              transactions[index] = updatedTransaction;
              updatedCount++;
              fileUpdated = true;
            }
          }
        });

        if (fileUpdated) {
          fs.writeFileSync(filePath, JSON.stringify(transactions, null, 2), 'utf-8');
        }
      } catch (error) {
        console.error(`Error processing ${file}:`, error);
        continue;
      }
    }

    return NextResponse.json({
      success: true,
      updatedCount,
    });
  } catch (error) {
    console.error('Error bulk reconciling transactions:', error);
    return NextResponse.json(
      { error: 'Failed to bulk update reconciliation' },
      { status: 500 }
    );
  }
}
