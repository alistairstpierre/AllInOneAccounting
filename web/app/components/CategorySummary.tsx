/**
 * CategorySummary Component
 * 
 * Displays a summary of expenses by category with total amounts and date range.
 */

'use client';

import { useState, useRef, useEffect } from 'react';

interface Entity {
  id: string;
  name: string;
  type: 'Personal' | 'Business';
  transactions: string[];
  cards?: string[]; // Assigned credit cards (array)
}

interface Transaction {
  account?: string;  // Bank account ID from OFX ACCTID
  card?: string;  // Credit card number from CSV (for entity assignment)
  merchant: string;
  amount: number;
  transaction_date: string;
}

interface CategorySummaryProps {
  categoryTotals: Record<string, number>;
  totalExpenses: number;
  transactionCount?: number;
  entities?: Entity[];
  entityTotals?: Record<string, number>;
  entityTransactionCounts?: Record<string, number>;
  selectedEntityId?: string | null;
  onEntitySelect?: (entityId: string | null) => void;
  onSelectTransactions?: (entityId: string) => void;
  onEntityDelete?: (entityId: string) => void;
  transactions?: Transaction[];
  onCardAssign?: (entityId: string, card: string, action?: 'add' | 'remove') => void;
  selectedCategory?: string;
  onCategoryChange?: (category: string) => void;
  onEntityCreate?: (name: string, type: 'Personal' | 'Business') => void;
  selectedEntityFilterIds?: string[];
  onEntityFilterChange?: (entityIds: string[]) => void;
  selectedAccountIds?: string[];
  onAccountFilterChange?: (accountIds: string[]) => void;
}

// Add Entity Section Component
function AddEntitySection({ onEntityCreate }: { onEntityCreate: (name: string, type: 'Personal' | 'Business') => void }) {
  const [newEntityName, setNewEntityName] = useState('');
  const [entityType, setEntityType] = useState<'Personal' | 'Business'>('Personal');
  const [showAddForm, setShowAddForm] = useState(false);

  const handleCreateEntity = async () => {
    if (newEntityName.trim()) {
      onEntityCreate(newEntityName.trim(), entityType);
      setNewEntityName('');
      setEntityType('Personal');
      setShowAddForm(false);
    }
  };

  return (
    <div className="mb-4 pb-4 border-b border-gray-200">
      {showAddForm ? (
        <div className="space-y-2">
          <input
            type="text"
            value={newEntityName}
            onChange={(e) => setNewEntityName(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleCreateEntity()}
            placeholder="Enter name..."
            className="w-full px-3 py-1 text-sm border border-gray-300 rounded-md text-black bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            autoFocus
          />
          <select
            value={entityType}
            onChange={(e) => setEntityType(e.target.value as 'Personal' | 'Business')}
            className="w-full px-3 py-1 text-sm border border-gray-300 rounded-md text-black bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="Personal">Personal</option>
            <option value="Business">Business</option>
          </select>
          <div className="flex items-center gap-2">
            <button
              onClick={handleCreateEntity}
              className="flex-1 px-3 py-1 text-sm font-medium bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
            >
              Add
            </button>
            <button
              onClick={() => {
                setShowAddForm(false);
                setNewEntityName('');
                setEntityType('Personal');
              }}
              className="px-3 py-1 text-sm font-medium bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setShowAddForm(true)}
          className="w-full px-3 py-2 text-sm font-medium bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 transition-colors"
        >
          + Add Person/Entity
        </button>
      )}
    </div>
  );
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

export default function CategorySummary({
  categoryTotals,
  totalExpenses,
  transactionCount,
  entities = [],
  entityTotals = {},
  entityTransactionCounts = {},
  selectedEntityId,
  onEntitySelect,
  onSelectTransactions,
  onEntityDelete,
  transactions = [],
  onCardAssign,
  selectedCategory,
  onCategoryChange,
  onEntityCreate,
  selectedEntityFilterIds = [],
  onEntityFilterChange,
  selectedAccountIds = [],
  onAccountFilterChange,
}: CategorySummaryProps) {
  const [isAccountDropdownOpen, setIsAccountDropdownOpen] = useState(false);
  const accountDropdownRef = useRef<HTMLDivElement>(null);
  
  // Get unique accounts from transactions (bank accounts from OFX, not credit cards)
  const uniqueAccounts = Array.from(new Set(transactions.map(t => t.account).filter((account): account is string => Boolean(account)))).sort();
  // Get unique cards for entity assignment (credit cards from CSV)
  const uniqueCards = Array.from(new Set(transactions.map(t => t.card).filter((card): card is string => Boolean(card)))).sort();
  const sortedCategories = Object.entries(categoryTotals)
    .sort(([, a], [, b]) => b - a); // Show all categories, sorted by amount

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (accountDropdownRef.current && !accountDropdownRef.current.contains(event.target as Node)) {
        setIsAccountDropdownOpen(false);
      }
    };

    if (isAccountDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
      };
    }
  }, [isAccountDropdownOpen]);

  const handleAccountToggle = (account: string) => {
    if (!onAccountFilterChange) return;
    
    if (selectedAccountIds.includes(account)) {
      onAccountFilterChange(selectedAccountIds.filter(id => id !== account));
    } else {
      onAccountFilterChange([...selectedAccountIds, account]);
    }
  };

  const handleClearAccounts = () => {
    onAccountFilterChange?.([]);
    setIsAccountDropdownOpen(false);
  };

  const getAccountButtonText = () => {
    if (selectedAccountIds.length === 0) {
      return 'All Accounts';
    }
    if (selectedAccountIds.length === 1) {
      return selectedAccountIds[0];
    }
    return `${selectedAccountIds.length} selected`;
  };

  const getCategoryColor = (index: number): string => {
    const colors = [
      'bg-blue-500',
      'bg-green-500',
      'bg-yellow-500',
      'bg-purple-500',
      'bg-pink-500',
    ];
    return colors[index % colors.length];
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold text-gray-900">
            Expense Summary
          </h2>
          
          {/* Account Filter Dropdown */}
          {onAccountFilterChange && (
            <div className="relative" ref={accountDropdownRef}>
              <button
                type="button"
                onClick={() => setIsAccountDropdownOpen(!isAccountDropdownOpen)}
                className="px-3 py-1.5 text-sm border border-gray-300 rounded-md text-black bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent min-w-[150px] text-left flex items-center justify-between"
              >
                <span>{getAccountButtonText()}</span>
                <svg
                  className={`w-4 h-4 ml-2 transition-transform ${isAccountDropdownOpen ? 'rotate-180' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {isAccountDropdownOpen && (
                <div className="absolute z-10 mt-1 right-0 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-auto min-w-[200px]">
                  {uniqueAccounts.length > 0 ? (
                    <>
                      {uniqueAccounts.map((account) => {
                        const accountTransactionCount = transactions.filter(t => t.account && t.account === account).length;
                        const isSelected = selectedAccountIds.includes(account);
                        return (
                          <label
                            key={account}
                            className="flex items-center px-4 py-2 hover:bg-gray-50 cursor-pointer"
                          >
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => handleAccountToggle(account)}
                              className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                              onClick={(e) => e.stopPropagation()}
                            />
                            <span className="ml-3 text-sm text-black">
                              {account} ({accountTransactionCount})
                            </span>
                          </label>
                        );
                      })}
                      {selectedAccountIds.length > 0 && (
                        <div className="border-t border-gray-200">
                          <button
                            type="button"
                            onClick={handleClearAccounts}
                            className="w-full px-4 py-2 text-sm text-left text-gray-700 hover:bg-gray-50"
                          >
                            Clear All
                          </button>
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="px-4 py-2 text-sm text-gray-500">
                      No accounts found. Re-process transactions to populate account data.
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
        <div className="text-3xl font-bold text-blue-600">
          ${totalExpenses.toFixed(2)}
        </div>
        {transactionCount !== undefined && (
          <div className="text-sm text-gray-600 mt-2">
            {transactionCount} transaction{transactionCount !== 1 ? 's' : ''}
          </div>
        )}
      </div>

      <div className="mb-6">
        <h3 className="text-lg font-semibold text-gray-700 mb-4">
          By Person/Entity
        </h3>
        
        {/* Add Person/Entity section */}
        {onEntityCreate && (
          <AddEntitySection onEntityCreate={onEntityCreate} />
        )}
        
        {entities.length > 0 && (
          <div className="space-y-2 mt-4">
            {entities.map((entity) => {
              const isSelected = selectedEntityId === entity.id;
              const isFiltered = selectedEntityFilterIds.includes(entity.id);
              const entityTotal = entityTotals[entity.id] || 0;
              return (
                <div key={entity.id}>
                  <div className={`border rounded-md p-3 ${
                    isFiltered ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
                  }`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={isFiltered}
                            onChange={() => {
                              if (onEntityFilterChange) {
                                // Toggle filter: if already filtered, remove it; otherwise add it
                                if (isFiltered) {
                                  onEntityFilterChange(selectedEntityFilterIds.filter(id => id !== entity.id));
                                } else {
                                  onEntityFilterChange([...selectedEntityFilterIds, entity.id]);
                                }
                              }
                            }}
                            className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                            onClick={(e) => e.stopPropagation()}
                          />
                          <span className={`text-base font-semibold ${
                            isFiltered 
                              ? 'text-blue-700' 
                              : isSelected 
                                ? 'text-blue-600' 
                                : 'text-gray-900 hover:text-blue-600'
                          }`}>
                            {entity.name}
                          </span>
                        </label>
                        {entity.cards && entity.cards.length > 0 && (
                          <div className="flex items-center gap-1 flex-wrap">
                            {entity.cards.map((card) => (
                              <span key={card} className="text-xs px-2 py-0.5 bg-gray-200 text-gray-700 rounded-full">
                                {card}
                              </span>
                            ))}
                          </div>
                        )}
                        <span className="text-sm text-gray-500">
                          ${entityTotal.toFixed(2)} ({entityTransactionCounts[entity.id] || 0} transactions)
                        </span>
                      </div>
                      {/* Manage button */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onEntitySelect?.(entity.id === selectedEntityId ? null : entity.id);
                        }}
                        className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
                          isSelected
                            ? 'bg-blue-600 text-white hover:bg-blue-700'
                            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                        }`}
                      >
                        Manage
                      </button>
                    </div>
                  </div>
                  {isSelected && (
                    <div className="border-x border-b border-gray-200 rounded-b-md p-3 bg-gray-50 flex items-center gap-2 flex-wrap">
                      {onSelectTransactions && (
                        <button
                          onClick={() => onSelectTransactions(entity.id)}
                          className="px-3 py-1 text-sm font-medium bg-blue-100 text-blue-700 rounded-md hover:bg-blue-200 transition-colors"
                        >
                          Select transactions
                        </button>
                      )}
                      {uniqueCards.length > 0 && onCardAssign && (
                        <div className="flex items-center gap-2 flex-wrap">
                          <label className="text-sm text-gray-600">Assign card:</label>
                          <select
                            value=""
                            onChange={(e) => {
                              const selectedCard = e.target.value;
                              if (selectedCard && selectedCard !== '') {
                                // Check if card is already assigned
                                const isAlreadyAssigned = entity.cards?.includes(selectedCard);
                                if (isAlreadyAssigned) {
                                  alert(`Card "${selectedCard}" is already assigned to "${entity.name}"`);
                                  e.target.value = '';
                                  return;
                                }
                                // Assign card
                                if (confirm(`Assign all transactions from card "${selectedCard}" to "${entity.name}"?`)) {
                                  onCardAssign(entity.id, selectedCard);
                                  e.target.value = '';
                                }
                              }
                            }}
                            className="px-3 py-1 text-sm border border-gray-300 rounded-md text-black bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                          >
                            <option value="">Select a card to assign...</option>
                            {uniqueCards.map((card) => {
                              const isAssigned = entity.cards?.includes(card);
                              const cardTransactionCount = transactions.filter(t => t.card === card).length;
                              return (
                                <option key={card} value={card} disabled={isAssigned}>
                                  {card} ({cardTransactionCount} transactions){isAssigned ? ' - Already assigned' : ''}
                                </option>
                              );
                            })}
                          </select>
                          {entity.cards && entity.cards.length > 0 && (
                            <div className="flex items-center gap-1 flex-wrap">
                              {entity.cards.map((card) => (
                                <span key={card} className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded-md flex items-center gap-1">
                                  {card}
                                  <button
                                    onClick={() => {
                                      if (confirm(`Remove card "${card}" from "${entity.name}"? This will not unassign transactions, only remove the card association.`)) {
                                        onCardAssign(entity.id, card, 'remove');
                                      }
                                    }}
                                    className="text-blue-700 hover:text-blue-900 font-bold"
                                    title="Remove card"
                                  >
                                    ×
                                  </button>
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                      {onEntityDelete && (
                        <button
                          onClick={() => {
                            if (confirm(`Are you sure you want to delete "${entity.name}"? This will unassign all transactions from this entity.`)) {
                              onEntityDelete(entity.id);
                            }
                          }}
                          className="px-3 py-1 text-sm font-medium bg-red-100 text-red-700 rounded-md hover:bg-red-200 transition-colors"
                          title="Delete entity"
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div>
        <h3 className="text-lg font-semibold text-gray-700 mb-4">
          Categories
        </h3>
        <div className="space-y-3">
          {sortedCategories.map(([category, amount], index) => {
            const percentage = totalExpenses > 0 ? (amount / totalExpenses) * 100 : 0;
            const isSelected = selectedCategory === category;
            return (
              <div 
                key={category}
                className={`cursor-pointer rounded-lg p-2 transition-colors ${
                  isSelected ? 'bg-blue-50 border-2 border-blue-500' : 'hover:bg-gray-50'
                }`}
                onClick={() => onCategoryChange?.(isSelected ? 'all' : category)}
              >
                <div className="flex justify-between items-center mb-1">
                  <span className={`text-sm font-medium ${isSelected ? 'text-blue-700' : 'text-gray-700'}`}>
                    {category}
                  </span>
                  <span className={`text-sm font-semibold ${isSelected ? 'text-blue-900' : 'text-gray-900'}`}>
                    ${amount.toFixed(2)} ({percentage.toFixed(1)}%)
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className={`${getCategoryColor(index)} h-2 rounded-full transition-all`}
                    style={{ width: `${percentage}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

