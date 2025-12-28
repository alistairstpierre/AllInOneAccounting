/**
 * API Route for Finding Similar Transactions
 * 
 * Finds transactions with exactly matching merchant names (uses identified_business if available)
 */

import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

const TRANSACTIONS_FILE = path.resolve(process.cwd(), '..', 'storage', 'transactions.json');

export async function POST(request: Request) {
  try {
    const { merchant, excludeTransactionId, targetCategory, targetEntityId, dateRange } = await request.json();

    if (!merchant) {
      return NextResponse.json(
        { error: 'Merchant name is required' },
        { status: 400 }
      );
    }

    // Path to transactions directory and entities.json
    const projectRoot = path.resolve(process.cwd(), '..');
    const transactionsDir = path.join(projectRoot, 'storage', 'transactions');
    const entitiesPath = path.join(projectRoot, 'storage', 'entities.json');

    // Check if directory exists
    if (!fs.existsSync(transactionsDir)) {
      return NextResponse.json([]);
    }

    // Read all transaction files
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

    const transactions = allTransactions;

    // Load entities if we need to filter by entity
    let entities: any[] = [];
    if (targetEntityId !== undefined && targetEntityId !== null) {
      if (fs.existsSync(entitiesPath)) {
        const entitiesContents = fs.readFileSync(entitiesPath, 'utf-8');
        entities = JSON.parse(entitiesContents);
      }
    }

    // Get transaction IDs already assigned to target entity
    const targetEntityTransactionIds = new Set<string>();
    if (targetEntityId !== undefined && targetEntityId !== null && targetEntityId !== '') {
      const targetEntity = entities.find((e: any) => e.id === targetEntityId);
      if (targetEntity && targetEntity.transactions) {
        targetEntity.transactions.forEach((tid: string) => targetEntityTransactionIds.add(tid));
      }
    }

    // Find similar transactions (excluding the original one and those already in the target category/entity)
    const similarTransactions = transactions
      .filter((t: any) => {
        // Exclude the original transaction (use id field if available, fall back to old format)
        const tId = t.id || `${t.merchant}_${t.amount}_${t.transaction_date}`;
        if (tId === excludeTransactionId) return false;
        
        // Filter by date range if provided
        if (dateRange && dateRange.start && dateRange.end) {
          const transactionDate = t.transaction_date || '';
          if (transactionDate < dateRange.start || transactionDate > dateRange.end) {
            return false;
          }
        }
        
        // Exclude transactions that already have the target category
        if (targetCategory !== undefined && targetCategory !== null && targetCategory !== '') {
          const currentCategory = t.category || null;
          if (currentCategory === targetCategory) return false;
        }

        // Check if merchant name matches (check both identified_business first, then raw merchant)
        const targetIdentifiedBusiness = (t.identified_business || '').trim().toLowerCase();
        const targetMerchant = (t.merchant || '').trim().toLowerCase();
        const sourceMerchant = merchant.trim().toLowerCase();
        
        // Match if either identified_business or merchant matches the source
        const merchantMatches = 
          (targetIdentifiedBusiness && sourceMerchant === targetIdentifiedBusiness) ||
          (targetMerchant && sourceMerchant === targetMerchant);
        
        if (!merchantMatches) return false;
        
        // Return true to include this transaction
        // All matching transactions are shown regardless of current entity assignment
        return true;
      })
      .map((t: any) => ({
        id: t.id || null,  // Include id if available
        merchant: t.identified_business || t.merchant,  // Use identified_business if available
        amount: t.amount,
        transaction_date: t.transaction_date,
        category: t.category || null,
      }))
      .sort((a: any, b: any) => {
        // Sort by date (most recent first)
        const aDate = new Date(a.transaction_date).getTime();
        const bDate = new Date(b.transaction_date).getTime();
        return bDate - aDate;
      });

    return NextResponse.json(similarTransactions);
  } catch (error) {
    console.error('Error finding similar transactions:', error);
    return NextResponse.json(
      { error: 'Failed to find similar transactions' },
      { status: 500 }
    );
  }
}

