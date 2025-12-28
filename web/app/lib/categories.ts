/**
 * Categories Library
 * 
 * Defines expense categories for Personal and Business transactions.
 * Provides functions to filter categories based on entity type and mode.
 */

export type CategoryMode = 'Personal' | 'Business' | 'Personal + Business';

// Personal expense categories
export const PERSONAL_CATEGORIES = [
  'Housing',
  'Transportation',
  'Food & Dining',
  'Healthcare',
  'Personal Care',
  'Entertainment',
  'Shopping',
  'Insurance',
  'Savings/Investing',
  'Debt Payment',
  'Education',
  'Travel',
  'Gifts & Donations',
  'Uncategorized',
] as const;

// Business expense categories
export const BUSINESS_CATEGORIES = [
  'Office Supplies',
  'Software/Subscriptions',
  'Marketing/Advertising',
  'Professional Services',
  'Salaries/Wages',
  'Commissions',
  'Travel',
  'Meals/Entertainment',
  'Equipment',
  'Rent/Utilities',
  'Insurance',
  'Education/Training',
  'Transportation',
  'Legal/Accounting',
  'Telecommunications',
  'Bank Fees',
  'Drawings',
  'Uncategorized',
] as const;

// All categories (combined, deduplicated)
export const ALL_CATEGORIES = [
  ...new Set([...PERSONAL_CATEGORIES, ...BUSINESS_CATEGORIES]),
] as string[];

/**
 * Get all categories as a flat array
 */
export function getAllCategories(): string[] {
  return [...ALL_CATEGORIES];
}

/**
 * Get categories for a specific entity type
 */
export function getCategoriesForEntityType(entityType: 'Personal' | 'Business' | null): string[] {
  if (entityType === 'Personal') {
    return [...PERSONAL_CATEGORIES];
  }
  if (entityType === 'Business') {
    return [...BUSINESS_CATEGORIES];
  }
  return getAllCategories();
}

/**
 * Get categories for a specific mode
 */
export function getCategoriesForMode(mode: CategoryMode): string[] {
  if (mode === 'Personal') {
    return [...PERSONAL_CATEGORIES];
  }
  if (mode === 'Business') {
    return [...BUSINESS_CATEGORIES];
  }
  return getAllCategories();
}

