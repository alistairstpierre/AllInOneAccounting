/**
 * Main Transactions Page
 * 
 * Displays categorized bank transactions with filtering and sorting capabilities.
 * Shows transactions with their categories and amounts.
 */

'use client';

import { useEffect, useState, useMemo, useRef } from 'react';
import { getCategoriesForMode, type CategoryMode } from './lib/categories';
import TransactionCard from './components/TransactionCard';
import CategorySummary from './components/CategorySummary';
import FilterBar from './components/FilterBar';
import TransactionHeader from './components/TransactionHeader';
import SmartCategoryUpdateModal from './components/SmartCategoryUpdateModal';
import SmartEntityUpdateModal from './components/SmartEntityUpdateModal';
import SmartTransferUpdateModal from './components/SmartTransferUpdateModal';
import SmartCreditUpdateModal from './components/SmartCreditUpdateModal';
import UndoButton from './components/UndoButton';
import { useUndo, UndoAction } from './hooks/useUndo';

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
  transaction_file?: string;  // Transaction file name (JSON file name without extension)
  categorized: boolean;
  category: string | null;
  category_description: string | null;
  categorized_at: string | null;
  updated_at?: string | null;  // Timestamp when transaction was last updated
  is_transfer?: boolean;  // Whether this is a transfer between accounts
  is_credit?: boolean;  // Whether this is a credit (income) or debit (expense)
}

interface Entity {
  id: string;
  name: string;
  type: 'Personal' | 'Business';
  transactions: string[];
  cards?: string[]; // Assigned credit cards (array)
}

function getTransactionId(transaction: Transaction | { id?: string; merchant: string; amount: number; transaction_date: string }): string {
  // Use the id field if available, otherwise fall back to old format for compatibility
  return transaction.id || `${transaction.merchant}_${transaction.amount}_${transaction.transaction_date}`;
}


// localStorage keys
const STORAGE_KEYS = {
  dateRange: 'budgetOptimizer_dateRange',
  selectedAccountIds: 'budgetOptimizer_selectedAccountIds',
  selectedEntityFilterIds: 'budgetOptimizer_selectedEntityFilterIds',
  searchText: 'budgetOptimizer_searchText',
  showTransfers: 'budgetOptimizer_showTransfers',
  showOnlyCredits: 'budgetOptimizer_showOnlyCredits',
  selectedCategory: 'budgetOptimizer_selectedCategory',
  categoryMode: 'budgetOptimizer_categoryMode',
  showIncomeSummary: 'budgetOptimizer_showIncomeSummary',
};

// Helper functions to load/save from localStorage
const loadFromStorage = <T,>(key: string, defaultValue: T): T => {
  if (typeof window === 'undefined') return defaultValue;
  try {
    const item = localStorage.getItem(key);
    if (item === null) return defaultValue;
    return JSON.parse(item);
  } catch {
    return defaultValue;
  }
};

const saveToStorage = <T,>(key: string, value: T): void => {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (error) {
    console.error(`Error saving to localStorage (${key}):`, error);
  }
};

export default function Home() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [entities, setEntities] = useState<Entity[]>([]);
  const [loading, setLoading] = useState(true);
  const { addAction, undo, canUndo, isUndoing, undoStackLength } = useUndo();
  
  // Initialize state with default values (same on server and client)
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [categoryMode, setCategoryMode] = useState<'Personal' | 'Business' | 'Personal + Business'>('Personal + Business');
  const [sortBy, setSortBy] = useState<'date' | 'amount'>('date');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [dateRange, setDateRange] = useState<{ start: string; end: string }>({ start: '', end: '' });
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [isSelectionMode, setIsSelectionMode] = useState(false);
  const [selectedTransactionIds, setSelectedTransactionIds] = useState<Set<string>>(new Set());
  const [selectedEntityFilterIds, setSelectedEntityFilterIds] = useState<string[]>([]);
  const [selectedAccountIds, setSelectedAccountIds] = useState<string[]>([]);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [searchText, setSearchText] = useState<string>('');
  const [showTransfers, setShowTransfers] = useState<boolean>(true);
  const [showIncomeSummary, setShowIncomeSummary] = useState<boolean>(true);
  const [showOnlyCredits, setShowOnlyCredits] = useState<boolean>(false);
  const [isHydrated, setIsHydrated] = useState(false);
  
  // Store original date range before expanding (for modal restoration)
  const originalDateRangeRef = useRef<{ start: string; end: string } | null>(null);
  const [smartTransferUpdateModal, setSmartTransferUpdateModal] = useState<{
    isOpen: boolean;
    matchingTransactions: Transaction[];
    isTransfer: boolean;
    originalTransaction: Transaction | null;
  }>({
    isOpen: false,
    matchingTransactions: [],
    isTransfer: false,
    originalTransaction: null,
  });
  const [smartCreditUpdateModal, setSmartCreditUpdateModal] = useState<{
    isOpen: boolean;
    matchingTransactions: Transaction[];
    isCredit: boolean;
    originalTransaction: Transaction | null;
  }>({
    isOpen: false,
    matchingTransactions: [],
    isCredit: false,
    originalTransaction: null,
  });
  const [smartUpdateModal, setSmartUpdateModal] = useState<{
    isOpen: boolean;
    matchingTransactions: Transaction[];
    newCategory: string;
    originalTransaction: Transaction | null;
  }>({
    isOpen: false,
    matchingTransactions: [],
    newCategory: '',
    originalTransaction: null,
  });
  const [smartEntityUpdateModal, setSmartEntityUpdateModal] = useState<{
    isOpen: boolean;
    matchingTransactions: Transaction[];
    newEntityId: string | null;
    newEntityName: string;
    originalTransaction: Transaction | null;
  }>({
    isOpen: false,
    matchingTransactions: [],
    newEntityId: null,
    newEntityName: '',
    originalTransaction: null,
  });

  // Load from localStorage after component mounts (client-side only)
  useEffect(() => {
    setIsHydrated(true);
    setSelectedCategory(loadFromStorage(STORAGE_KEYS.selectedCategory, 'all'));
    setCategoryMode(loadFromStorage(STORAGE_KEYS.categoryMode, 'Personal + Business'));
    setDateRange(loadFromStorage(STORAGE_KEYS.dateRange, { start: '', end: '' }));
    setSelectedEntityFilterIds(loadFromStorage(STORAGE_KEYS.selectedEntityFilterIds, []));
    setSelectedAccountIds(loadFromStorage(STORAGE_KEYS.selectedAccountIds, []));
    setSearchText(loadFromStorage(STORAGE_KEYS.searchText, ''));
    setShowTransfers(loadFromStorage(STORAGE_KEYS.showTransfers, true));
    setShowIncomeSummary(loadFromStorage(STORAGE_KEYS.showIncomeSummary, true));
    setShowOnlyCredits(loadFromStorage(STORAGE_KEYS.showOnlyCredits, false));
  }, []);

  useEffect(() => {
    if (isHydrated) {
      fetchTransactions();
      fetchEntities();
    }
  }, [isHydrated]);

  const fetchEntities = async () => {
    try {
      const response = await fetch('/api/entities');
      if (response.ok) {
        const data = await response.json();
        setEntities(data);
      } else {
        console.error('Failed to fetch entities');
      }
    } catch (error) {
      console.error('Error fetching entities:', error);
    }
  };

  // Set initial date range to last month (1 month ago to today) if not loaded from storage
  useEffect(() => {
    if (isHydrated && transactions.length > 0 && !dateRange.start && !dateRange.end) {
      const today = new Date();
      const oneMonthAgo = new Date(today);
      oneMonthAgo.setMonth(today.getMonth() - 1);
      
      // Format dates as YYYY-MM-DD
      const formatDate = (date: Date) => {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
      };
      
      const newDateRange = {
        start: formatDate(oneMonthAgo),
        end: formatDate(today),
      };
      setDateRange(newDateRange);
      saveToStorage(STORAGE_KEYS.dateRange, newDateRange);
    }
  }, [isHydrated, transactions, dateRange.start, dateRange.end]);

  // Save to localStorage whenever filters change
  useEffect(() => {
    saveToStorage(STORAGE_KEYS.dateRange, dateRange);
  }, [dateRange]);

  useEffect(() => {
    saveToStorage(STORAGE_KEYS.selectedAccountIds, selectedAccountIds);
  }, [selectedAccountIds]);

  useEffect(() => {
    saveToStorage(STORAGE_KEYS.selectedEntityFilterIds, selectedEntityFilterIds);
  }, [selectedEntityFilterIds]);

  useEffect(() => {
    saveToStorage(STORAGE_KEYS.searchText, searchText);
  }, [searchText]);

  useEffect(() => {
    saveToStorage(STORAGE_KEYS.showTransfers, showTransfers);
  }, [showTransfers]);

  useEffect(() => {
    saveToStorage(STORAGE_KEYS.showOnlyCredits, showOnlyCredits);
  }, [showOnlyCredits]);

  useEffect(() => {
    saveToStorage(STORAGE_KEYS.selectedCategory, selectedCategory);
  }, [selectedCategory]);

  useEffect(() => {
    saveToStorage(STORAGE_KEYS.categoryMode, categoryMode);
  }, [categoryMode]);

  useEffect(() => {
    saveToStorage(STORAGE_KEYS.showIncomeSummary, showIncomeSummary);
  }, [showIncomeSummary]);

  const fetchTransactions = async () => {
    try {
      const response = await fetch('/api/transactions');
      if (response.ok) {
        const data = await response.json();
        setTransactions(data);
      } else {
        console.error('Failed to fetch transactions');
      }
    } catch (error) {
      console.error('Error fetching transactions:', error);
    } finally {
      setLoading(false);
    }
  };

  const getEntityIdForTransaction = (transactionId: string): string | null => {
    const entity = entities.find(e => e.transactions.includes(transactionId));
    return entity ? entity.id : null;
  };

  // Handler for undo operations
  const handleUndo = async () => {
    const action = undo();
    if (!action) return;

    try {
      if (action.type === 'category' || action.type === 'bulk_category') {
        // Revert category changes
        const promises = action.transactionIds.map(async (transactionId) => {
          const beforeState = action.beforeState[transactionId];
          return fetch('/api/transactions/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              transactionId,
              category: beforeState.category,
            }),
          });
        });
        await Promise.all(promises);
        await fetchTransactions();
      } else if (action.type === 'entity' || action.type === 'bulk_entity') {
        // Revert entity assignments
        const promises = action.transactionIds.map(async (transactionId) => {
          const beforeState = action.beforeState[transactionId];
          return fetch('/api/transactions/assign-entity', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              transactionId,
              entityId: beforeState.entityId,
            }),
          });
        });
        await Promise.all(promises);
        await fetchEntities();
        await fetchTransactions();
      } else if (action.type === 'merchant') {
        // Revert merchant name changes
        const beforeState = action.beforeState[action.transactionIds[0]];
        await fetch('/api/transactions/update', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            transactionId: action.transactionIds[0],
            identified_business: beforeState.identified_business,
          }),
        });
        await fetchTransactions();
      }
    } catch (error) {
      console.error('Error undoing action:', error);
      alert('Failed to undo');
    }
  };

  const handleTransactionUpdate = (updatedTransaction: Transaction) => {
    const transactionId = getTransactionId(updatedTransaction);
    const oldTransaction = transactions.find(t => getTransactionId(t) === transactionId);
    
    if (oldTransaction) {
      // Check if merchant name changed
      const oldMerchant = oldTransaction.identified_business;
      const newMerchant = updatedTransaction.identified_business;
      
      if (oldMerchant !== newMerchant) {
        // Track undo action before making the change
        addAction({
          type: 'merchant',
          transactionIds: [transactionId],
          beforeState: { [transactionId]: { identified_business: oldMerchant } },
          afterState: { [transactionId]: { identified_business: newMerchant } },
        });
      }
    }

    setTransactions((prevTransactions) =>
      prevTransactions.map((t) =>
        getTransactionId(t) === transactionId
          ? { ...updatedTransaction }
          : t
      )
    );
  };

  const handleEntityUpdate = async (transactionId: string, entityId: string | null) => {
    // Track undo action before making the change
    const oldEntityId = getEntityIdForTransaction(transactionId);
    addAction({
      type: 'entity',
      transactionIds: [transactionId],
      beforeState: { [transactionId]: { entityId: oldEntityId } },
      afterState: { [transactionId]: { entityId } },
    });

    // First, update the transaction
    try {
      const response = await fetch('/api/transactions/assign-entity', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          transactionId,
          entityId,
        }),
      });

      if (response.ok) {
        // Refresh entities to get updated state
        await fetchEntities();
        
        // Find the original transaction to get merchant name from current state
        const originalTransaction = transactions.find(t => getTransactionId(t) === transactionId);
        if (originalTransaction && (originalTransaction.identified_business || originalTransaction.merchant)) {
          const merchantName = originalTransaction.identified_business || originalTransaction.merchant;
          
          // Check for similar transactions (exclude those already assigned to the target entity)
          const requestBody = {
            merchant: merchantName,
            excludeTransactionId: transactionId,
            targetEntityId: entityId,
            dateRange: dateRange.start && dateRange.end ? dateRange : null,
          };
          
          const similarResponse = await fetch('/api/transactions/find-similar', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody),
          });

          if (similarResponse.ok) {
            const matchingTransactions = await similarResponse.json();
            
            // Show modal if there are matching transactions
            if (matchingTransactions.length > 0) {
              // Convert API response to full Transaction objects
              const fullMatchingTransactions = matchingTransactions
                .map((match: any) => transactions.find(t => getTransactionId(t) === match.id))
                .filter((t: Transaction | undefined): t is Transaction => t !== undefined);
              
              // Get the entity name - fetch fresh entities list to ensure we have the latest
              let newEntityName = 'Unassigned';
              if (entityId) {
                const entitiesResponse = await fetch('/api/entities');
                if (entitiesResponse.ok) {
                  const updatedEntities = await entitiesResponse.json();
                  newEntityName = updatedEntities.find((e: Entity) => e.id === entityId)?.name || 'Unknown';
                } else {
                  // Fallback to current entities state
                  newEntityName = entities.find((e: Entity) => e.id === entityId)?.name || 'Unknown';
                }
              }
              
              setSmartEntityUpdateModal({
                isOpen: true,
                matchingTransactions: fullMatchingTransactions,
                newEntityId: entityId,
                newEntityName,
                originalTransaction,
              });
            }
          }
        }
      } else {
        console.error('Failed to update entity assignment');
      }
    } catch (error) {
      console.error('Error updating entity assignment:', error);
    }
  };

  const handleBulkEntityUpdate = async (selectedTransactionIds: string[]) => {
    if (selectedTransactionIds.length === 0 || !smartEntityUpdateModal.originalTransaction) return;

    // Track undo action before making the change
    const beforeState: Record<string, any> = {};
    const afterState: Record<string, any> = {};
    selectedTransactionIds.forEach(id => {
      const oldEntityId = getEntityIdForTransaction(id);
      beforeState[id] = { entityId: oldEntityId };
      afterState[id] = { entityId: smartEntityUpdateModal.newEntityId };
    });
    
    addAction({
      type: 'bulk_entity',
      transactionIds: selectedTransactionIds,
      beforeState,
      afterState,
    });

    try {
      // Use the existing assign endpoint in a loop, or create a bulk endpoint
      // For now, we'll use the existing endpoint in a loop since we already have it
      const promises = selectedTransactionIds.map(transactionId =>
        fetch('/api/transactions/assign-entity', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            transactionId,
            entityId: smartEntityUpdateModal.newEntityId,
          }),
        })
      );

      const responses = await Promise.all(promises);
      const allOk = responses.every(r => r.ok);

      if (allOk) {
        // Reload entities and transactions to get updated data
        await fetchEntities();
        await fetchTransactions();
        restoreDateRange();
        setSmartEntityUpdateModal({
          isOpen: false,
          matchingTransactions: [],
          newEntityId: null,
          newEntityName: '',
          originalTransaction: null,
        });
      } else {
        console.error('Failed to bulk update entity assignments');
        alert('Failed to update some transactions');
      }
    } catch (error) {
      console.error('Error bulk updating entity assignments:', error);
      alert('Error updating transactions');
    }
  };

  const handleCategoryUpdate = async (transactionId: string, newCategory: string) => {
    // First, update the original transaction
    const originalTransaction = transactions.find(t => getTransactionId(t) === transactionId);

    if (!originalTransaction) return;

    // Track undo action before making the change
    const oldCategory = originalTransaction.category;
    addAction({
      type: 'category',
      transactionIds: [transactionId],
      beforeState: { [transactionId]: { category: oldCategory } },
      afterState: { [transactionId]: { category: newCategory } },
    });

    // Update the original transaction immediately
    try {
      const response = await fetch('/api/transactions/update', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          transactionId,
          category: newCategory,
        }),
      });

      if (response.ok) {
        // Update the transaction in the local state
        setTransactions((prevTransactions) =>
          prevTransactions.map((t) =>
            getTransactionId(t) === transactionId
              ? {
                  ...t,
                  category: newCategory || null,
                  categorized: newCategory !== '',
                  category_description: newCategory ? 'Manually updated by user' : null,
                  categorized_at: newCategory ? new Date().toISOString() : null,
                }
              : t
          )
        );

        // Find similar transactions
        const excludeTransactionId = transactionId;
        const similarResponse = await fetch('/api/transactions/find-similar', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
            body: JSON.stringify({
              merchant: originalTransaction.identified_business || originalTransaction.merchant,
              excludeTransactionId,
              targetCategory: newCategory,
              dateRange: dateRange.start && dateRange.end ? dateRange : null,
            }),
        });

          if (similarResponse.ok) {
            const matchingTransactions = await similarResponse.json();
            if (matchingTransactions.length > 0) {
              // Convert API response to full Transaction objects
              const fullMatchingTransactions = matchingTransactions
                .map((match: any) => transactions.find(t => getTransactionId(t) === match.id))
                .filter((t: Transaction | undefined): t is Transaction => t !== undefined);
              // Show modal with similar transactions
              setSmartUpdateModal({
                isOpen: true,
                matchingTransactions: fullMatchingTransactions,
                newCategory,
                originalTransaction,
              });
            }
          }
      } else {
        console.error('Failed to update transaction category');
        fetchTransactions();
      }
    } catch (error) {
      console.error('Error updating transaction category:', error);
      fetchTransactions();
    }
  };

  const handleBulkCategoryUpdate = async (selectedTransactionIds: string[]) => {
    if (selectedTransactionIds.length === 0 || !smartUpdateModal.originalTransaction) return;

    try {
      const response = await fetch('/api/transactions/bulk-update', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          transactionIds: selectedTransactionIds,
          category: smartUpdateModal.newCategory,
        }),
      });

      if (response.ok) {
        // Reload transactions to get updated data
        await fetchTransactions();
        restoreDateRange();
        setSmartUpdateModal({
          isOpen: false,
          matchingTransactions: [],
          newCategory: '',
          originalTransaction: null,
        });
      } else {
        console.error('Failed to bulk update transactions');
        alert('Failed to update transactions');
      }
    } catch (error) {
      console.error('Error bulk updating transactions:', error);
      alert('Error updating transactions');
    }
  };

  const handleTransferUpdate = async (transactionId: string, isTransfer: boolean) => {
    const originalTransaction = transactions.find(t => getTransactionId(t) === transactionId);
    if (!originalTransaction) return;

    // Update the transaction immediately
    try {
      const response = await fetch('/api/transactions/update', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          transactionId,
          is_transfer: isTransfer,
        }),
      });

      if (response.ok) {
        // Update local state
        setTransactions((prevTransactions) =>
          prevTransactions.map((t) =>
            getTransactionId(t) === transactionId
              ? { ...t, is_transfer: isTransfer }
              : t
          )
        );

        // Find similar transactions (same merchant name)
        const merchantName = originalTransaction.identified_business || originalTransaction.merchant;
        const similarResponse = await fetch('/api/transactions/find-similar', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            merchant: merchantName,
            excludeTransactionId: transactionId,
            dateRange: dateRange.start && dateRange.end ? dateRange : null,
          }),
        });

      if (similarResponse.ok) {
        const matchingTransactions = await similarResponse.json();
        if (matchingTransactions.length > 0) {
          // Convert API response to full Transaction objects
          const fullMatchingTransactions = matchingTransactions
            .map((match: any) => transactions.find(t => getTransactionId(t) === match.id))
            .filter((t: Transaction | undefined): t is Transaction => t !== undefined);

            setSmartTransferUpdateModal({
              isOpen: true,
              matchingTransactions: fullMatchingTransactions,
              isTransfer,
              originalTransaction,
            });
          }
        } else {
          // No similar transactions found, just update the single transaction
          await fetch('/api/transactions/update', {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              transactionId,
              is_transfer: isTransfer,
            }),
          });
        }
      } else {
        console.error('Failed to update transaction transfer status');
        fetchTransactions();
      }
    } catch (error) {
      console.error('Error updating transaction transfer status:', error);
      fetchTransactions();
    }
  };

  const handleCreditUpdate = async (transactionId: string, isCredit: boolean) => {
    const originalTransaction = transactions.find(t => getTransactionId(t) === transactionId);
    if (!originalTransaction) return;

    // Update the transaction immediately
    try {
      const response = await fetch('/api/transactions/update', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          transactionId,
          is_credit: isCredit,
        }),
      });

      if (response.ok) {
        // Update local state
        setTransactions((prevTransactions) =>
          prevTransactions.map((t) =>
            getTransactionId(t) === transactionId
              ? { ...t, is_credit: isCredit }
              : t
          )
        );

        // Find similar transactions (same merchant name)
        const merchantName = originalTransaction.identified_business || originalTransaction.merchant;
        if (!merchantName) {
          console.log('No merchant name found for transaction, skipping similar transaction search');
        } else {
          const similarResponse = await fetch('/api/transactions/find-similar', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              merchant: merchantName,
              excludeTransactionId: transactionId,
              dateRange: dateRange.start && dateRange.end ? dateRange : null,
            }),
          });

          if (similarResponse.ok) {
            const matchingTransactions = await similarResponse.json();
            console.log(`Found ${matchingTransactions.length} similar transactions for merchant: ${merchantName}`);
            if (matchingTransactions.length > 0) {
              // Convert API response to full Transaction objects
              const fullMatchingTransactions = matchingTransactions
                .map((match: any) => transactions.find(t => getTransactionId(t) === match.id))
                .filter((t: Transaction | undefined): t is Transaction => t !== undefined);

              console.log(`Converted to ${fullMatchingTransactions.length} full transaction objects`);
              setSmartCreditUpdateModal({
                isOpen: true,
                matchingTransactions: fullMatchingTransactions,
                isCredit,
                originalTransaction,
              });
            }
          } else {
            console.error('Failed to find similar transactions:', await similarResponse.text());
          }
        }
      } else {
        console.error('Failed to update transaction credit status');
        fetchTransactions();
      }
    } catch (error) {
      console.error('Error updating transaction credit status:', error);
      fetchTransactions();
    }
  };

  const handleBulkCreditUpdate = async (selectedTransactionIds: string[]) => {
    if (selectedTransactionIds.length === 0 || !smartCreditUpdateModal.originalTransaction) return;

    try {
      // Update each transaction one by one
      const updatePromises = selectedTransactionIds.map(id =>
        fetch('/api/transactions/update', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            transactionId: id,
            is_credit: smartCreditUpdateModal.isCredit,
          }),
        })
      );

      await Promise.all(updatePromises);

      // Reload transactions to get updated data
      await fetchTransactions();
      restoreDateRange();
      setSmartCreditUpdateModal({
        isOpen: false,
        matchingTransactions: [],
        isCredit: false,
        originalTransaction: null,
      });
    } catch (error) {
      console.error('Error bulk updating credits:', error);
      alert('Error updating transactions');
    }
  };

  const handleBulkTransferUpdate = async (selectedTransactionIds: string[]) => {
    if (selectedTransactionIds.length === 0 || !smartTransferUpdateModal.originalTransaction) return;

    try {
      // Update each transaction one by one (since bulk-update doesn't support is_transfer yet)
      const updatePromises = selectedTransactionIds.map(id =>
        fetch('/api/transactions/update', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            transactionId: id,
            is_transfer: smartTransferUpdateModal.isTransfer,
          }),
        })
      );

      await Promise.all(updatePromises);

      // Reload transactions to get updated data
      await fetchTransactions();
      restoreDateRange();
      setSmartTransferUpdateModal({
        isOpen: false,
        matchingTransactions: [],
        isTransfer: false,
        originalTransaction: null,
      });
    } catch (error) {
      console.error('Error bulk updating transfers:', error);
      alert('Error updating transactions');
    }
  };

  const filteredAndSortedTransactions = useMemo(() => {
    let filtered = transactions;

    // Filter by selected accounts (bank accounts from OFX, not credit cards)
    if (selectedAccountIds.length > 0) {
      filtered = filtered.filter(t => t.account && selectedAccountIds.includes(t.account));
    }

    // Filter by selected entities
    if (selectedEntityFilterIds.length > 0) {
      const entityTransactionIds = new Set<string>();
      selectedEntityFilterIds.forEach(entityId => {
        const entity = entities.find(e => e.id === entityId);
        if (entity) {
          entity.transactions.forEach(tid => entityTransactionIds.add(tid));
        }
      });
      filtered = filtered.filter(t => entityTransactionIds.has(getTransactionId(t)));
    }

    // Filter by date range
    if (dateRange.start) {
      filtered = filtered.filter(
        (t) => t.transaction_date >= dateRange.start
      );
    }
    if (dateRange.end) {
      filtered = filtered.filter(
        (t) => t.transaction_date <= dateRange.end
      );
    }

    // Filter by category (only if not showing only credits)
    if (!showOnlyCredits && selectedCategory !== 'all') {
      filtered = filtered.filter(
        (t) => t.category === selectedCategory
      );
    }

    // Filter by search text
    if (searchText.trim()) {
      const searchLower = searchText.toLowerCase().trim();
      filtered = filtered.filter((t) => {
        const merchant = (t.identified_business || t.merchant || '').toLowerCase();
        const category = (t.category || '').toLowerCase();
        const description = (t.category_description || '').toLowerCase();
        return merchant.includes(searchLower) || 
               category.includes(searchLower) || 
               description.includes(searchLower);
      });
    }

    // Filter out transfers if showTransfers is false
    if (!showTransfers) {
      filtered = filtered.filter(t => !t.is_transfer);
    }

    // Filter by credit/debit based on showOnlyCredits setting
    if (showOnlyCredits) {
      // Show only credits (income)
      filtered = filtered.filter(t => {
        if (t.is_credit !== undefined) {
          return t.is_credit;
        }
        // Fallback for transactions without is_credit field
        const merchant = (t.identified_business || t.merchant || '').toLowerCase();
        const description = (t.category_description || '').toLowerCase();
        const creditKeywords = [
          'deposit',
          'credit to',
          'payment received',
          'salary deposit',
          'wage deposit',
          'income deposit',
          'transfer credit',
          'payment from'
        ];
        return creditKeywords.some(keyword => 
          merchant.includes(keyword) || description.includes(keyword)
        );
      });
    } else {
      // Filter out credits (income) - only show debits (expenses)
      // Credits are income/deposits and shouldn't be displayed as expenses
      // Credits remain in the data for tracking purposes but are hidden from display
      filtered = filtered.filter(t => {
        // Use is_credit field if available (from processor)
        if (t.is_credit !== undefined) {
          return !t.is_credit; // Exclude credits, include debits
        }
        
        // Fallback: Check if transaction appears to be a credit/income
        // (for transactions that haven't been updated yet)
        const merchant = (t.identified_business || t.merchant || '').toLowerCase();
        const description = (t.category_description || '').toLowerCase();
        
        // Common credit/income indicators (be conservative to avoid false positives)
        const creditKeywords = [
          'deposit',
          'credit to',
          'payment received',
          'salary deposit',
          'wage deposit',
          'income deposit',
          'transfer credit',
          'payment from'
        ];
        
        // Check if merchant or description contains credit keywords
        // Only filter if it's clearly a credit/income transaction
        const isCredit = creditKeywords.some(keyword => 
          merchant.includes(keyword) || description.includes(keyword)
        );
        
        if (isCredit) {
          return false; // Exclude credits
        }
        
        return true; // Include all other transactions (debits/expenses)
      });
    }

    // Sort transactions
    const sorted = [...filtered].sort((a, b) => {
      let comparison = 0;

      if (sortBy === 'date') {
        comparison = a.transaction_date.localeCompare(b.transaction_date);
      } else if (sortBy === 'amount') {
        comparison = a.amount - b.amount;
      }

      return sortOrder === 'asc' ? comparison : -comparison;
    });

    return sorted;
  }, [transactions, selectedCategory, sortBy, sortOrder, dateRange, selectedEntityFilterIds, selectedAccountIds, entities, searchText, showTransfers, showOnlyCredits]);

  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [selectedCategory, dateRange, selectedEntityFilterIds, selectedAccountIds, sortBy, sortOrder, searchText, showTransfers]);

  const TRANSACTIONS_PER_PAGE = 100;
  const totalPages = Math.ceil(filteredAndSortedTransactions.length / TRANSACTIONS_PER_PAGE);
  const paginatedTransactions = useMemo(() => {
    const startIndex = (currentPage - 1) * TRANSACTIONS_PER_PAGE;
    const endIndex = startIndex + TRANSACTIONS_PER_PAGE;
    return filteredAndSortedTransactions.slice(startIndex, endIndex);
  }, [filteredAndSortedTransactions, currentPage]);

  // Get categories based on mode for filtering
  const availableCategories = useMemo(() => {
    return getCategoriesForMode(categoryMode);
  }, [categoryMode]);

  // For filtering dropdown, use available categories based on mode
  const categories = availableCategories;


  const categoryTotals = useMemo(() => {
    const totals: Record<string, number> = {};
    filteredAndSortedTransactions.forEach((t) => {
      if (t.category) {
        totals[t.category] = (totals[t.category] || 0) + t.amount;
      }
    });
    return totals;
  }, [filteredAndSortedTransactions]);

  // Calculate entity totals (from filtered transactions, respecting date range and filters)
  const entityTotals = useMemo(() => {
    const totals: Record<string, number> = {};
    entities.forEach(entity => {
      const entityTransactionIds = new Set(entity.transactions);
      const entityTransactions = filteredAndSortedTransactions.filter(t => 
        entityTransactionIds.has(getTransactionId(t))
      );
      totals[entity.id] = entityTransactions.reduce((sum, t) => sum + t.amount, 0);
    });
    return totals;
  }, [entities, filteredAndSortedTransactions]);

  // Calculate entity transaction counts (from filtered transactions, respecting date range and filters)
  const entityTransactionCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    entities.forEach(entity => {
      const entityTransactionIds = new Set(entity.transactions);
      const entityTransactions = filteredAndSortedTransactions.filter(t => 
        entityTransactionIds.has(getTransactionId(t))
      );
      counts[entity.id] = entityTransactions.length;
    });
    return counts;
  }, [entities, filteredAndSortedTransactions]);

  const handleEntityCreate = async (name: string, type: 'Personal' | 'Business') => {
    try {
      const response = await fetch('/api/entities', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          action: 'create',
          entityName: name,
          entityType: type,
        }),
      });

      if (response.ok) {
        fetchEntities();
      } else {
        console.error('Failed to create entity');
      }
    } catch (error) {
      console.error('Error creating entity:', error);
    }
  };

  const handleSelectTransactions = (entityId: string) => {
    setSelectedEntityId(entityId);
    setIsSelectionMode(true);
    setSelectedTransactionIds(new Set());
  };

  const handleSelectAll = () => {
    setSelectedTransactionIds(new Set(
      filteredAndSortedTransactions.map(t => getTransactionId(t))
    ));
  };

  const handleUnselectAll = () => {
    setSelectedTransactionIds(new Set());
  };

  const handleHeaderCheckboxChange = () => {
    if (!isSelectionMode) {
      // Enter selection mode and select all
      setIsSelectionMode(true);
      setSelectedEntityId(null);
      handleSelectAll();
    } else {
      // Toggle between select all and unselect all
      const allSelected = selectedTransactionIds.size === filteredAndSortedTransactions.length;
      if (allSelected) {
        handleUnselectAll();
      } else {
        handleSelectAll();
      }
    }
  };

  const handleTransactionSelect = (transactionId: string, selected: boolean) => {
    setSelectedTransactionIds(prev => {
      const newSet = new Set(prev);
      if (selected) {
        newSet.add(transactionId);
      } else {
        newSet.delete(transactionId);
      }
      return newSet;
    });
  };

  const handleDone = async () => {
    if (!selectedEntityId) return;

    try {
      const response = await fetch('/api/entities', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          action: 'assign',
          entityId: selectedEntityId,
          transactionIds: Array.from(selectedTransactionIds),
        }),
      });

      if (response.ok) {
        await fetchEntities();
        await fetchTransactions();
        setIsSelectionMode(false);
        setSelectedTransactionIds(new Set());
        setSelectedEntityId(null);
      } else {
        console.error('Failed to assign transactions');
      }
    } catch (error) {
      console.error('Error assigning transactions:', error);
    }
  };

  const handleBulkAssignEntity = async (entityId: string) => {
    if (selectedTransactionIds.size === 0 || !entityId) return;

    try {
      const response = await fetch('/api/entities', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          action: 'assign',
          entityId: entityId,
          transactionIds: Array.from(selectedTransactionIds),
        }),
      });

      if (response.ok) {
        await fetchEntities();
        await fetchTransactions();
        setIsSelectionMode(false);
        setSelectedTransactionIds(new Set());
        setSelectedEntityId(null);
      } else {
        console.error('Failed to assign transactions');
      }
    } catch (error) {
      console.error('Error assigning transactions:', error);
    }
  };

  const handleEnterBulkSelectionMode = () => {
    setIsSelectionMode(true);
    setSelectedEntityId(null); // Don't pre-select an entity
    setSelectedTransactionIds(new Set());
  };

  const handleCancelSelection = () => {
    setIsSelectionMode(false);
    setSelectedTransactionIds(new Set());
    setSelectedEntityId(null);
  };

  const handleEntityDelete = async (entityId: string) => {
    try {
      const response = await fetch('/api/entities', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          action: 'delete',
          entityId: entityId,
        }),
      });

      if (response.ok) {
        fetchEntities();
        // If the deleted entity was selected, clear selection
        if (selectedEntityId === entityId) {
          setSelectedEntityId(null);
          setIsSelectionMode(false);
        }
      } else {
        console.error('Failed to delete entity');
      }
    } catch (error) {
      console.error('Error deleting entity:', error);
    }
  };

  const handleCardAssign = async (entityId: string, card: string, action: 'add' | 'remove' = 'add') => {
    try {
      const response = await fetch('/api/entities/assign-by-card', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          entityId,
          card,
          action,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        await fetchEntities();
        if (action === 'add' && card) {
          alert(`Successfully assigned ${data.assignedCount || 0} transactions from card "${card}" to the entity.`);
        } else if (action === 'remove') {
          alert(`Card "${card}" removed from entity.`);
        }
      } else {
        const errorData = await response.json();
        alert(`Failed to ${action === 'add' ? 'assign' : 'remove'} card: ${errorData.error || 'Unknown error'}`);
        console.error(`Failed to ${action} card`);
      }
    } catch (error) {
      console.error('Error assigning transactions by card:', error);
      alert('Error assigning transactions by card');
    }
  };

  const totalExpensesFiltered = useMemo(() => {
    // Only count debits (expenses), exclude credits
    return filteredAndSortedTransactions.reduce((sum, t) => sum + t.amount, 0);
  }, [filteredAndSortedTransactions]);

  // Calculate total income (credits) from all transactions (before filtering out credits)
  const totalIncomeFiltered = useMemo(() => {
    // Get all transactions that match current filters (before credit filtering)
    let incomeTransactions = transactions;

    // Apply same filters as filteredAndSortedTransactions (except credit filter)
    if (selectedAccountIds.length > 0) {
      incomeTransactions = incomeTransactions.filter(t => t.account && selectedAccountIds.includes(t.account));
    }

    if (selectedEntityFilterIds.length > 0) {
      const entityTransactionIds = new Set<string>();
      selectedEntityFilterIds.forEach(entityId => {
        const entity = entities.find(e => e.id === entityId);
        if (entity) {
          entity.transactions.forEach(tid => entityTransactionIds.add(tid));
        }
      });
      incomeTransactions = incomeTransactions.filter(t => entityTransactionIds.has(getTransactionId(t)));
    }

    if (dateRange.start) {
      incomeTransactions = incomeTransactions.filter((t) => t.transaction_date >= dateRange.start);
    }
    if (dateRange.end) {
      incomeTransactions = incomeTransactions.filter((t) => t.transaction_date <= dateRange.end);
    }

    if (searchText.trim()) {
      const searchLower = searchText.toLowerCase().trim();
      incomeTransactions = incomeTransactions.filter((t) => {
        const merchant = (t.identified_business || t.merchant || '').toLowerCase();
        const category = (t.category || '').toLowerCase();
        const description = (t.category_description || '').toLowerCase();
        return merchant.includes(searchLower) || 
               category.includes(searchLower) || 
               description.includes(searchLower);
      });
    }

    // Only count credits (income)
    return incomeTransactions
      .filter(t => {
        if (t.is_credit !== undefined) {
          return t.is_credit;
        }
        // Fallback for transactions without is_credit field
        const merchant = (t.identified_business || t.merchant || '').toLowerCase();
        const description = (t.category_description || '').toLowerCase();
        const creditKeywords = [
          'deposit',
          'credit to',
          'payment received',
          'salary deposit',
          'wage deposit',
          'income deposit',
          'transfer credit',
          'payment from'
        ];
        return creditKeywords.some(keyword => 
          merchant.includes(keyword) || description.includes(keyword)
        );
      })
      .reduce((sum, t) => sum + t.amount, 0);
  }, [transactions, selectedAccountIds, selectedEntityFilterIds, dateRange, searchText, entities]);

  const dateRangeForSummary = useMemo(() => {
    if (filteredAndSortedTransactions.length === 0) return null;
    const dates = filteredAndSortedTransactions.map(t => t.transaction_date).sort();
    return {
      start: dates[0],
      end: dates[dates.length - 1],
    };
  }, [filteredAndSortedTransactions]);

  // Helper function to restore original date range when modal closes
  const restoreDateRange = () => {
    if (originalDateRangeRef.current) {
      setDateRange(originalDateRangeRef.current);
      originalDateRangeRef.current = null;
    }
  };

  // Handler to expand date range to include all transactions and refresh modal
  const handleExpandDateRange = async () => {
    if (transactions.length === 0) return;
    
    // Store the original date range before expanding (only if not already stored)
    if (!originalDateRangeRef.current) {
      originalDateRangeRef.current = { ...dateRange };
    }
    
    const allDates = transactions.map(t => t.transaction_date).sort();
    const newDateRange = {
      start: allDates[0],
      end: allDates[allDates.length - 1],
    };
    setDateRange(newDateRange);
    
    // Re-fetch similar transactions with expanded date range
    // Check if we're in category, entity, or transfer modal and refresh accordingly
    if (smartUpdateModal.isOpen && smartUpdateModal.originalTransaction) {
      const similarResponse = await fetch('/api/transactions/find-similar', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          merchant: smartUpdateModal.originalTransaction.identified_business || smartUpdateModal.originalTransaction.merchant,
          excludeTransactionId: getTransactionId(smartUpdateModal.originalTransaction),
          targetCategory: smartUpdateModal.newCategory,
          dateRange: null, // null means no date filtering
        }),
      });
      
      if (similarResponse.ok) {
        const matchingTransactions = await similarResponse.json();
        // Convert API response to full Transaction objects
        const fullMatchingTransactions = matchingTransactions
          .map((match: any) => transactions.find(t => getTransactionId(t) === match.id))
          .filter((t: Transaction | undefined): t is Transaction => t !== undefined);
        setSmartUpdateModal({
          ...smartUpdateModal,
          matchingTransactions: fullMatchingTransactions,
        });
      }
    } else if (smartEntityUpdateModal.isOpen && smartEntityUpdateModal.originalTransaction) {
      const similarResponse = await fetch('/api/transactions/find-similar', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          merchant: smartEntityUpdateModal.originalTransaction.identified_business || smartEntityUpdateModal.originalTransaction.merchant,
          excludeTransactionId: getTransactionId(smartEntityUpdateModal.originalTransaction),
          targetEntityId: smartEntityUpdateModal.newEntityId,
          dateRange: null, // null means no date filtering
        }),
      });
      
      if (similarResponse.ok) {
        const matchingTransactions = await similarResponse.json();
        // Convert API response to full Transaction objects
        const fullMatchingTransactions = matchingTransactions
          .map((match: any) => transactions.find(t => getTransactionId(t) === match.id))
          .filter((t: Transaction | undefined): t is Transaction => t !== undefined);
        setSmartEntityUpdateModal({
          ...smartEntityUpdateModal,
          matchingTransactions: fullMatchingTransactions,
        });
      }
    } else if (smartTransferUpdateModal.isOpen && smartTransferUpdateModal.originalTransaction) {
      const similarResponse = await fetch('/api/transactions/find-similar', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          merchant: smartTransferUpdateModal.originalTransaction.identified_business || smartTransferUpdateModal.originalTransaction.merchant,
          excludeTransactionId: getTransactionId(smartTransferUpdateModal.originalTransaction),
          dateRange: null, // null means no date filtering
        }),
      });
      
      if (similarResponse.ok) {
        const matchingTransactions = await similarResponse.json();
        // Convert API response to full Transaction objects
        const fullMatchingTransactions = matchingTransactions
          .map((match: any) => transactions.find(t => getTransactionId(t) === match.id))
          .filter((t: Transaction | undefined): t is Transaction => t !== undefined);
        setSmartTransferUpdateModal({
          ...smartTransferUpdateModal,
          matchingTransactions: fullMatchingTransactions,
        });
      }
    } else if (smartCreditUpdateModal.isOpen && smartCreditUpdateModal.originalTransaction) {
      const similarResponse = await fetch('/api/transactions/find-similar', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          merchant: smartCreditUpdateModal.originalTransaction.identified_business || smartCreditUpdateModal.originalTransaction.merchant,
          excludeTransactionId: getTransactionId(smartCreditUpdateModal.originalTransaction),
          dateRange: null, // null means no date filtering
        }),
      });
      
      if (similarResponse.ok) {
        const matchingTransactions = await similarResponse.json();
        // Convert API response to full Transaction objects
        const fullMatchingTransactions = matchingTransactions
          .map((match: any) => transactions.find(t => getTransactionId(t) === match.id))
          .filter((t: Transaction | undefined): t is Transaction => t !== undefined);
        setSmartCreditUpdateModal({
          ...smartCreditUpdateModal,
          matchingTransactions: fullMatchingTransactions,
        });
      }
    }
  };

  // Prevent hydration mismatch - only render main content after mount
  const shouldShowLoading = typeof window === 'undefined' || loading || !isHydrated;

  if (shouldShowLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-xl text-gray-600">Loading transactions...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div className="bg-white border-b border-gray-200 mb-6 py-2 px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <h1 className="text-lg font-semibold text-gray-900">
                Budget Optimizer
              </h1>
              <span className="text-sm text-gray-500">•</span>
              <p className="text-sm text-gray-600">
                Categorized Transaction Overview
              </p>
            </div>
            <div className="flex items-center gap-2">
              <label htmlFor="category-mode" className="text-sm font-medium text-gray-700">Mode:</label>
              <select
                id="category-mode"
                value={categoryMode}
                onChange={(e) => setCategoryMode(e.target.value as CategoryMode)}
                className="px-3 py-1.5 text-sm border border-gray-300 rounded-md text-black bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="Personal">Personal</option>
                <option value="Business">Business</option>
                <option value="Personal + Business">Personal + Business</option>
              </select>
            </div>
          </div>
        </div>

        <div className="flex gap-6">
          {/* Left Sidebar - Dashboard */}
          <div className="w-1/3 flex-shrink-0 space-y-6">
        <CategorySummary
          categoryTotals={categoryTotals}
          totalExpenses={totalExpensesFiltered}
          totalIncome={totalIncomeFiltered}
          transactionCount={filteredAndSortedTransactions.length}
          entities={entities}
          entityTotals={entityTotals}
          entityTransactionCounts={entityTransactionCounts}
          selectedEntityId={selectedEntityId}
          onEntitySelect={(id) => {
            setSelectedEntityId(id);
            setIsSelectionMode(false);
          }}
          onSelectTransactions={handleSelectTransactions}
          onEntityDelete={handleEntityDelete}
          transactions={transactions}
          onCardAssign={handleCardAssign}
          selectedCategory={selectedCategory}
          onCategoryChange={setSelectedCategory}
          onEntityCreate={handleEntityCreate}
          selectedEntityFilterIds={selectedEntityFilterIds}
          onEntityFilterChange={setSelectedEntityFilterIds}
          selectedAccountIds={selectedAccountIds}
          onAccountFilterChange={setSelectedAccountIds}
          showIncomeSummary={showIncomeSummary}
          onShowIncomeSummaryChange={setShowIncomeSummary}
          showOnlyCredits={showOnlyCredits}
          onShowOnlyCreditsChange={setShowOnlyCredits}
        />
          </div>

          {/* Right Side - Transactions */}
          <div className="flex-1 min-w-0 space-y-6">
            <FilterBar
              categories={categories}
              selectedCategory={selectedCategory}
              onCategoryChange={setSelectedCategory}
              dateRange={dateRange}
              onDateRangeChange={setDateRange}
              entities={entities}
              selectedEntityIds={selectedEntityFilterIds}
              onEntityFilterChange={setSelectedEntityFilterIds}
              searchText={searchText}
              onSearchChange={setSearchText}
              showTransfers={showTransfers}
              onShowTransfersChange={setShowTransfers}
            />

            <div className="space-y-2">
          {filteredAndSortedTransactions.length > 0 && (
            <>
              <TransactionHeader
                sortBy={sortBy}
                sortOrder={sortOrder}
                onSortChange={(newSortBy) => {
                  if (sortBy === newSortBy) {
                    // Toggle order if clicking the same column
                    setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
                  } else {
                    // Set new column and default to desc
                    setSortBy(newSortBy);
                    setSortOrder('desc');
                  }
                }}
                isSelectionMode={isSelectionMode}
                isAllSelected={isSelectionMode && selectedTransactionIds.size === filteredAndSortedTransactions.length && filteredAndSortedTransactions.length > 0}
                onCheckboxChange={handleHeaderCheckboxChange}
              />
              {isSelectionMode && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4 flex items-center justify-between gap-4">
                  <span className="text-sm text-gray-600">
                    {selectedTransactionIds.size} selected
                  </span>
                  {selectedEntityId ? (
                    // Pre-selected entity mode (from CategorySummary)
                    <div className="flex items-center gap-3">
                      <button
                        onClick={handleCancelSelection}
                        className="px-3 py-1.5 text-sm font-medium bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleDone}
                        className="px-4 py-2 text-sm font-medium bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
                      >
                        Assign to {entities.find(e => e.id === selectedEntityId)?.name || 'Entity'}
                      </button>
                    </div>
                  ) : (
                    // Bulk selection mode - choose entity
                    <div className="flex items-center gap-3">
                      <select
                        value=""
                        onChange={(e) => {
                          if (e.target.value) {
                            handleBulkAssignEntity(e.target.value);
                          }
                        }}
                        className="px-3 py-1.5 text-sm border border-gray-300 rounded-md text-black bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="">Select entity to assign...</option>
                        {entities.map((entity) => (
                          <option key={entity.id} value={entity.id}>
                            {entity.name} ({entity.type})
                          </option>
                        ))}
                      </select>
                      <button
                        onClick={handleCancelSelection}
                        className="px-3 py-1.5 text-sm font-medium bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
          {filteredAndSortedTransactions.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              No transactions found
            </div>
          ) : (
            <>
              {paginatedTransactions.map((transaction, index) => {
                const transactionId = getTransactionId(transaction);
                const entityId = getEntityIdForTransaction(transactionId);
                return (
                  <TransactionCard 
                    key={transactionId} 
                    transaction={transaction}
                    onCategoryUpdate={handleCategoryUpdate}
                    onEntityUpdate={handleEntityUpdate}
                    onTransactionUpdate={handleTransactionUpdate}
                    onTransferUpdate={handleTransferUpdate}
                    onCreditUpdate={handleCreditUpdate}
                    isSelectMode={isSelectionMode}
                    isSelected={selectedTransactionIds.has(transactionId)}
                    onSelectChange={(selected) => handleTransactionSelect(transactionId, selected)}
                    getTransactionId={getTransactionId}
                    entities={entities}
                    entityId={entityId}
                    categoryMode={categoryMode}
                  />
                );
              })}
              
              {/* Pagination Controls */}
              {totalPages > 1 && (
                <div className="mt-6 flex items-center justify-between border-t border-gray-200 pt-4">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                      disabled={currentPage === 1}
                      className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Previous
                    </button>
                    <span className="text-sm text-gray-700 px-4">
                      Page {currentPage} of {totalPages}
                    </span>
                    <button
                      onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                      disabled={currentPage === totalPages}
                      className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Next
                    </button>
                  </div>
                  <div className="text-sm text-gray-600">
                    Showing {((currentPage - 1) * TRANSACTIONS_PER_PAGE) + 1} to {Math.min(currentPage * TRANSACTIONS_PER_PAGE, filteredAndSortedTransactions.length)} of {filteredAndSortedTransactions.length} transactions
                  </div>
                </div>
              )}
            </>
          )}
            </div>
          </div>
        </div>
      </div>

      {smartUpdateModal.originalTransaction && (
        <SmartCategoryUpdateModal
          isOpen={smartUpdateModal.isOpen}
          onClose={() => {
            restoreDateRange();
            setSmartUpdateModal({
              isOpen: false,
              matchingTransactions: [],
              newCategory: '',
              originalTransaction: null,
            });
          }}
          matchingTransactions={smartUpdateModal.matchingTransactions}
          newCategory={smartUpdateModal.newCategory}
          originalTransaction={smartUpdateModal.originalTransaction}
          onConfirm={handleBulkCategoryUpdate}
          getTransactionId={getTransactionId}
          dateRange={dateRange.start && dateRange.end ? dateRange : null}
          onExpandDateRange={handleExpandDateRange}
        />
      )}

      {smartEntityUpdateModal.originalTransaction && (
        <SmartEntityUpdateModal
          isOpen={smartEntityUpdateModal.isOpen}
          onClose={() => {
            restoreDateRange();
            setSmartEntityUpdateModal({
              isOpen: false,
              matchingTransactions: [],
              newEntityId: null,
              newEntityName: '',
              originalTransaction: null,
            });
          }}
          matchingTransactions={smartEntityUpdateModal.matchingTransactions}
          newEntityId={smartEntityUpdateModal.newEntityId}
          newEntityName={smartEntityUpdateModal.newEntityName}
          originalTransaction={smartEntityUpdateModal.originalTransaction}
          onConfirm={handleBulkEntityUpdate}
          getTransactionId={getTransactionId}
          dateRange={dateRange.start && dateRange.end ? dateRange : null}
          onExpandDateRange={handleExpandDateRange}
        />
      )}

      {smartTransferUpdateModal.originalTransaction && (
        <SmartTransferUpdateModal
          isOpen={smartTransferUpdateModal.isOpen}
          onClose={() => {
            restoreDateRange();
            setSmartTransferUpdateModal({
              isOpen: false,
              matchingTransactions: [],
              isTransfer: false,
              originalTransaction: null,
            });
          }}
          matchingTransactions={smartTransferUpdateModal.matchingTransactions}
          isTransfer={smartTransferUpdateModal.isTransfer}
          originalTransaction={smartTransferUpdateModal.originalTransaction}
          onConfirm={handleBulkTransferUpdate}
          getTransactionId={getTransactionId}
          dateRange={dateRange.start && dateRange.end ? dateRange : null}
          onExpandDateRange={handleExpandDateRange}
        />
      )}

      {smartCreditUpdateModal.originalTransaction && (
        <SmartCreditUpdateModal
          isOpen={smartCreditUpdateModal.isOpen}
          onClose={() => {
            restoreDateRange();
            setSmartCreditUpdateModal({
              isOpen: false,
              matchingTransactions: [],
              isCredit: false,
              originalTransaction: null,
            });
          }}
          matchingTransactions={smartCreditUpdateModal.matchingTransactions}
          isCredit={smartCreditUpdateModal.isCredit}
          originalTransaction={smartCreditUpdateModal.originalTransaction}
          onConfirm={handleBulkCreditUpdate}
          getTransactionId={getTransactionId}
          dateRange={dateRange.start && dateRange.end ? dateRange : null}
          onExpandDateRange={handleExpandDateRange}
        />
      )}

      <UndoButton
        canUndo={canUndo}
        onUndo={handleUndo}
        isUndoing={isUndoing}
        undoStackLength={undoStackLength}
      />
    </div>
  );
}
