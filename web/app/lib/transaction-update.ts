/**
 * Transaction Update Utility
 * 
 * Provides a function to update transaction fields and mark transactions as updated
 * only when values actually change.
 */

/**
 * Updates a transaction object with new values, only marking as updated if values changed.
 * 
 * @param transaction - The transaction object to update
 * @param updates - Object containing the fields to update
 * @returns Object with the updated transaction and a boolean indicating if any changes were made
 */
export function updateTransaction(
  transaction: any,
  updates: {
    category?: string | null;
    identified_business?: string | null;
    is_transfer?: boolean;
    is_credit?: boolean;
    [key: string]: any;
  }
): { transaction: any; wasUpdated: boolean } {
  let wasUpdated = false;
  const updatedTransaction = { ...transaction };

  // Check each field and only update if the value actually changed
  if (updates.category !== undefined) {
    const oldCategory = updatedTransaction.category || null;
    const newCategory = updates.category || null;
    if (oldCategory !== newCategory) {
      updatedTransaction.category = newCategory;
      updatedTransaction.categorized = newCategory !== null && newCategory !== '';
      updatedTransaction.categorized_at = newCategory ? new Date().toISOString() : null;
      wasUpdated = true;
    }
  }

  if (updates.identified_business !== undefined) {
    const oldBusiness = updatedTransaction.identified_business || null;
    const newBusiness = updates.identified_business || null;
    if (oldBusiness !== newBusiness) {
      updatedTransaction.identified_business = newBusiness;
      wasUpdated = true;
    }
  }

  if (updates.is_transfer !== undefined) {
    const oldTransfer = updatedTransaction.is_transfer || false;
    const newTransfer = updates.is_transfer || false;
    if (oldTransfer !== newTransfer) {
      updatedTransaction.is_transfer = newTransfer;
      wasUpdated = true;
    }
  }

  if (updates.is_credit !== undefined) {
    const oldCredit = updatedTransaction.is_credit || false;
    const newCredit = updates.is_credit || false;
    if (oldCredit !== newCredit) {
      updatedTransaction.is_credit = newCredit;
      wasUpdated = true;
    }
  }

  if (updates.is_credit !== undefined) {
    const oldCredit = updatedTransaction.is_credit || false;
    const newCredit = updates.is_credit || false;
    if (oldCredit !== newCredit) {
      updatedTransaction.is_credit = newCredit;
      wasUpdated = true;
    }
  }

  // Check for any other fields
  for (const key in updates) {
    if (key !== 'category' && key !== 'identified_business' && key !== 'is_transfer' && key !== 'is_credit') {
      const oldValue = updatedTransaction[key];
      const newValue = updates[key];
      if (oldValue !== newValue) {
        updatedTransaction[key] = newValue;
        wasUpdated = true;
      }
    }
  }

  // Only set updated_at if something actually changed
  if (wasUpdated) {
    updatedTransaction.updated_at = new Date().toISOString();
  }

  return { transaction: updatedTransaction, wasUpdated };
}

