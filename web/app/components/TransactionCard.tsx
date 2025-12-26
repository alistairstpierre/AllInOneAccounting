/**
 * TransactionCard Component
 * 
 * Displays a single transaction with all its details including category,
 * amount, merchant, and date.
 * Includes an expandable section for full details.
 */

'use client';

import { useState, useEffect, useRef } from 'react';
import { getCategoriesForEntityType, getCategoriesForMode, type CategoryMode } from '../lib/categories';

interface Transaction {
  id: string;
  account?: string;  // Bank account ID from OFX ACCTID
  card?: string;  // Credit card number from CSV (for entity assignment)
  amount: number;
  merchant: string;
  identified_business?: string;
  transaction_date: string;
  processed_date: string;
  foreign_currency: string;
  source_file: string;
  categorized: boolean;
  category: string | null;
  category_description: string | null;
  categorized_at: string | null;
  is_transfer?: boolean;  // Whether this is a transfer between accounts
}

interface Entity {
  id: string;
  name: string;
  type: 'Personal' | 'Business';
  transactions: string[];
  cards?: string[]; // Assigned credit cards (array)
}

interface TransactionCardProps {
  transaction: Transaction;
  onCategoryUpdate?: (transactionId: string, newCategory: string) => void;
  onEntityUpdate?: (transactionId: string, entityId: string | null) => void;
  onTransactionUpdate?: (updatedTransaction: Transaction) => void;
  onTransferUpdate?: (transactionId: string, isTransfer: boolean) => void;
  isSelectMode?: boolean;
  isSelected?: boolean;
  onSelectChange?: (selected: boolean) => void;
  getTransactionId: (transaction: Transaction) => string;
  entities?: Entity[];
  entityId?: string | null;
  categoryMode?: 'Personal' | 'Business' | 'Personal + Business';
}

const formatDate = (dateString: string): string => {
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return dateString;
  }
};

export default function TransactionCard({ 
  transaction, 
  onCategoryUpdate,
  onEntityUpdate,
  onTransactionUpdate,
  onTransferUpdate,
  isSelectMode = false,
  isSelected = false,
  onSelectChange,
  getTransactionId,
  entities = [],
  entityId = null,
  categoryMode = 'Personal + Business',
}: TransactionCardProps) {
  // Get the entity type for this transaction to determine which categories to show
  const entity = entityId ? entities.find(e => e.id === entityId) : null;
  const entityType = entity?.type || null;
  
  // Use category mode to filter available categories, but include the current category if it exists
  const modeCategories = getCategoriesForMode(categoryMode);
  const currentCategory = transaction.category;
  
  // Always include the current category in the list even if it's not in the current mode
  const categories = currentCategory && !modeCategories.includes(currentCategory)
    ? [...modeCategories, currentCategory].sort()
    : modeCategories;
  
  // Helper function to extract business name from various sources
  const getDisplayBusinessName = () => {
    if (transaction.identified_business) {
      return transaction.identified_business;
    }
    // Try to extract from category_description if it follows the format "Business: [name]"
    if (transaction.category_description) {
      const match = transaction.category_description.match(/Business: ([^\.]+)/);
      if (match && match[1]) {
        return match[1].trim();
      }
    }
    return transaction.merchant;
  };

  const displayBusinessName = getDisplayBusinessName();

  const [isExpanded, setIsExpanded] = useState(false);
  const [isCategoryDropdownOpen, setIsCategoryDropdownOpen] = useState(false);
  const [isEntityDropdownOpen, setIsEntityDropdownOpen] = useState(false);
  const [isEditingMerchant, setIsEditingMerchant] = useState(false);
  const [editedMerchantName, setEditedMerchantName] = useState(displayBusinessName);
  const [selectedCategory, setSelectedCategory] = useState(transaction.category || '');
  const [selectedEntity, setSelectedEntity] = useState<string | null>(entityId || null);
  const categoryDropdownRef = useRef<HTMLDivElement>(null);
  const entityDropdownRef = useRef<HTMLDivElement>(null);
  const merchantInputRef = useRef<HTMLInputElement>(null);
  const category = transaction.category || 'Uncategorized';
  const entityName = entityId ? entities.find(e => e.id === entityId)?.name || 'Unknown' : 'Unassigned';

  // Sync selectedEntity with entityId prop changes
  useEffect(() => {
    setSelectedEntity(entityId || null);
  }, [entityId]);

  // Sync editedMerchantName when transaction changes
  useEffect(() => {
    setEditedMerchantName(displayBusinessName);
  }, [displayBusinessName]);

  // Focus input when editing starts
  useEffect(() => {
    if (isEditingMerchant && merchantInputRef.current) {
      merchantInputRef.current.focus();
      merchantInputRef.current.select();
    }
  }, [isEditingMerchant]);

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (categoryDropdownRef.current && !categoryDropdownRef.current.contains(event.target as Node)) {
        setIsCategoryDropdownOpen(false);
      }
      if (entityDropdownRef.current && !entityDropdownRef.current.contains(event.target as Node)) {
        setIsEntityDropdownOpen(false);
      }
    };

    if (isCategoryDropdownOpen || isEntityDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
      };
    }
  }, [isCategoryDropdownOpen, isEntityDropdownOpen]);

  const isMatched = transaction.category_description?.includes('Matched with similar transaction') ?? false;
  const matchedMerchant = isMatched && transaction.category_description
    ? transaction.category_description.match(/Matched with similar transaction: (.+)/)?.[1]
    : null;
  const isManuallyUpdated = transaction.category_description?.includes('Manually updated by user') ?? false;

  const handleCategorySelect = async (newCategory: string) => {
    setSelectedCategory(newCategory);
    setIsCategoryDropdownOpen(false);
    
    if (onCategoryUpdate && newCategory !== transaction.category) {
      const transactionId = getTransactionId(transaction);
      onCategoryUpdate(transactionId, newCategory);
    }
  };

  const handleEntitySelect = async (newEntityId: string | null) => {
    setSelectedEntity(newEntityId);
    setIsEntityDropdownOpen(false);
    
    if (onEntityUpdate && newEntityId !== entityId) {
      const transactionId = getTransactionId(transaction);
      onEntityUpdate(transactionId, newEntityId);
    }
  };

  return (
    <div className={`bg-white rounded-lg shadow-sm border ${isSelected ? 'border-blue-500' : 'border-gray-200'} hover:shadow-md transition-shadow flex`}>
      {isManuallyUpdated && (
        <div className="w-1 bg-blue-500 rounded-l-lg flex-shrink-0" />
      )}
      <div className="flex-1 flex flex-col">
        <div 
          className="flex items-center gap-3 p-2"
          onClick={() => !isSelectMode && setIsExpanded(!isExpanded)}
        >
        {isSelectMode && (
          <input
            type="checkbox"
            checked={isSelected}
            onChange={(e) => {
              e.stopPropagation();
              onSelectChange?.(e.target.checked);
            }}
            onClick={(e) => e.stopPropagation()}
            className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
          />
        )}
        <div className={`text-xs text-gray-600 font-medium ${isSelectMode ? 'w-20' : 'w-24'} flex-shrink-0 ${!isSelectMode ? 'cursor-pointer' : ''}`}>
          {formatDate(transaction.transaction_date)}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            {isEditingMerchant ? (
              <input
                ref={merchantInputRef}
                type="text"
                value={editedMerchantName}
                onChange={(e) => setEditedMerchantName(e.target.value)}
                onBlur={async () => {
                  if (editedMerchantName.trim() !== displayBusinessName) {
                    try {
                      const response = await fetch('/api/transactions/update', {
                        method: 'POST',
                        headers: {
                          'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                          transactionId: getTransactionId(transaction),
                          identified_business: editedMerchantName.trim() || null,
                        }),
                      });
                      if (response.ok) {
                        const result = await response.json();
                        if (result.transaction && onTransactionUpdate) {
                          // Update the transaction in parent state
                          onTransactionUpdate(result.transaction);
                        } else {
                          // Fallback: refresh all transactions if callback not available
                          window.location.reload();
                        }
                      }
                    } catch (error) {
                      console.error('Error updating merchant name:', error);
                    }
                  }
                  setIsEditingMerchant(false);
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.currentTarget.blur();
                  } else if (e.key === 'Escape') {
                    setEditedMerchantName(displayBusinessName);
                    setIsEditingMerchant(false);
                  }
                }}
                className="text-sm font-semibold text-gray-900 border border-blue-500 rounded px-1 focus:outline-none focus:ring-2 focus:ring-blue-500 min-w-[150px]"
                autoFocus
              />
            ) : (
              <h3 
                className="text-sm font-semibold text-gray-900 truncate cursor-pointer hover:text-blue-600 transition-colors" 
                title={`Click to edit. Original: ${transaction.merchant}`}
                onClick={() => setIsEditingMerchant(true)}
              >
                {displayBusinessName}
              </h3>
            )}
            <div className="relative inline-block" ref={categoryDropdownRef}>
              <span
                className={`px-2 py-0.5 text-xs font-medium rounded-full whitespace-nowrap cursor-pointer transition-colors ${
                  transaction.category
                    ? 'bg-blue-100 text-blue-800 hover:bg-blue-200'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
                onClick={(e) => {
                  e.stopPropagation();
                  setIsCategoryDropdownOpen(!isCategoryDropdownOpen);
                }}
                title="Click to change category"
              >
                {category}
              </span>
              {isCategoryDropdownOpen && (
                <div 
                  className="absolute z-20 mt-1 bg-white border border-gray-300 rounded-md shadow-lg min-w-[150px] max-h-60 overflow-auto"
                  onClick={(e) => e.stopPropagation()}
                >
                  <div
                    className="px-3 py-2 text-xs cursor-pointer hover:bg-gray-50 text-black"
                    onClick={() => handleCategorySelect('')}
                  >
                    Uncategorized
                  </div>
                  {categories.map((cat) => (
                    <div
                      key={cat}
                      className="px-3 py-2 text-xs cursor-pointer hover:bg-gray-50 text-black"
                      onClick={() => handleCategorySelect(cat)}
                    >
                      {cat}
                    </div>
                  ))}
                </div>
              )}
            </div>
            {isMatched && matchedMerchant && (
              <span className="px-2 py-0.5 text-xs font-medium bg-purple-100 text-purple-700 rounded-full whitespace-nowrap" title={`Matched with: ${matchedMerchant}`}>
                Matched
              </span>
            )}
            <div className="relative inline-block" ref={entityDropdownRef}>
              <span
                className={`px-2 py-0.5 text-xs font-medium rounded-full whitespace-nowrap cursor-pointer transition-colors ${
                  entityId
                    ? 'bg-green-100 text-green-800 hover:bg-green-200'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
                onClick={(e) => {
                  e.stopPropagation();
                  setIsEntityDropdownOpen(!isEntityDropdownOpen);
                }}
                title="Click to change entity"
              >
                {entityName}
              </span>
              {isEntityDropdownOpen && (
                <div 
                  className="absolute z-20 mt-1 bg-white border border-gray-300 rounded-md shadow-lg min-w-[120px] max-h-60 overflow-auto"
                  onClick={(e) => e.stopPropagation()}
                >
                  <div
                    className="px-3 py-2 text-xs cursor-pointer hover:bg-gray-50 text-black"
                    onClick={() => handleEntitySelect(null)}
                  >
                    Unassigned
                  </div>
                  {entities.map((entity) => (
                    <div
                      key={entity.id}
                      className="px-3 py-2 text-xs cursor-pointer hover:bg-gray-50 text-black"
                      onClick={() => handleEntitySelect(entity.id)}
                    >
                      {entity.name}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
        <div className="text-right flex-shrink-0">
          <div className="text-base font-bold text-gray-900">
            ${transaction.amount.toFixed(2)}
          </div>
        </div>
        <div className="flex-shrink-0 w-6 text-center">
          <svg
            className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
        </div>
        
        {isExpanded && (
          <div className="px-2 pb-3 pt-1 border-t border-gray-100">
          <div className="grid grid-cols-2 gap-3 text-xs text-gray-600">
            <div>
              <span className="font-medium text-gray-700">Processed Date:</span>{' '}
              {formatDate(transaction.processed_date)}
            </div>
            <div>
              <span className="font-medium text-gray-700">Card:</span>{' '}
              {transaction.card}
            </div>
            {transaction.foreign_currency && (
              <div>
                <span className="font-medium text-gray-700">Foreign Currency:</span>{' '}
                {transaction.foreign_currency}
              </div>
            )}
            <div>
              <span className="font-medium text-gray-700">Source File:</span>{' '}
              {transaction.source_file}
            </div>
            {transaction.category_description && !isMatched && (
              <div className="col-span-2">
                <span className="font-medium text-gray-700">Description:</span>{' '}
                {transaction.category_description}
                {transaction.identified_business && transaction.merchant !== transaction.identified_business && (
                  <span className="text-gray-500 text-xs ml-2">
                    (Original: {transaction.merchant})
                  </span>
                )}
              </div>
            )}
            {!transaction.category_description && transaction.identified_business && transaction.merchant !== transaction.identified_business && (
              <div className="col-span-2">
                <span className="font-medium text-gray-700">Original Name:</span>{' '}
                <span className="text-gray-500">{transaction.merchant}</span>
              </div>
            )}
            {isMatched && matchedMerchant && (
              <div className="col-span-2">
                <span className="font-medium text-gray-700">Matched with:</span>{' '}
                {matchedMerchant}
              </div>
            )}
            {transaction.categorized_at && (
              <div>
                <span className="font-medium text-gray-700">Categorized At:</span>{' '}
                {new Date(transaction.categorized_at).toLocaleString()}
              </div>
            )}
            {onTransferUpdate && (
              <div className="col-span-2 flex items-center gap-2">
                <input
                  type="checkbox"
                  id={`transfer-${getTransactionId(transaction)}`}
                  checked={transaction.is_transfer || false}
                  onChange={async (e) => {
                    if (onTransferUpdate) {
                      onTransferUpdate(getTransactionId(transaction), e.target.checked);
                    }
                  }}
                  className="w-3.5 h-3.5 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <label htmlFor={`transfer-${getTransactionId(transaction)}`} className="text-xs font-medium text-gray-700 cursor-pointer">
                  Mark as Transfer (exclude from expenses)
                </label>
              </div>
            )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

