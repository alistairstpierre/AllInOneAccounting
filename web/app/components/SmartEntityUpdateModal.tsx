/**
 * SmartEntityUpdateModal Component
 * 
 * Modal that shows similar transactions when an entity is changed,
 * allowing the user to select which ones should also be updated.
 */

'use client';

import { useState, useEffect } from 'react';

// Simplified Transaction interface for the modal (matches API response)
interface Transaction {
  id?: string;  // Optional for backward compatibility
  merchant: string;
  amount: number;
  transaction_date: string;
}

interface SmartEntityUpdateModalProps {
  isOpen: boolean;
  onClose: () => void;
  matchingTransactions: Transaction[];
  newEntityId: string | null;
  newEntityName: string;
  originalTransaction: Transaction;
  onConfirm: (selectedTransactionIds: string[]) => void;
  getTransactionId: (transaction: { id?: string; merchant: string; amount: number; transaction_date: string }) => string;
  dateRange?: { start: string; end: string } | null;
  onExpandDateRange?: () => void;
}

export default function SmartEntityUpdateModal({
  isOpen,
  onClose,
  matchingTransactions,
  newEntityId,
  newEntityName,
  originalTransaction,
  onConfirm,
  getTransactionId,
  dateRange,
  onExpandDateRange,
}: SmartEntityUpdateModalProps) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (isOpen) {
      setSelectedIds(new Set());
    }
  }, [isOpen]);

  const handleToggle = (transactionId: string) => {
    setSelectedIds(prev => {
      const newSet = new Set(prev);
      if (newSet.has(transactionId)) {
        newSet.delete(transactionId);
      } else {
        newSet.add(transactionId);
      }
      return newSet;
    });
  };

  const handleSelectAll = () => {
    if (selectedIds.size === matchingTransactions.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(matchingTransactions.map(t => getTransactionId(t))));
    }
  };

  const handleConfirm = () => {
    onConfirm(Array.from(selectedIds));
    onClose();
  };

  if (!isOpen || matchingTransactions.length === 0) return null;

  // Close on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      // Prevent body scroll when modal is open
      document.body.style.overflow = 'hidden';
      return () => {
        document.removeEventListener('keydown', handleEscape);
        document.body.style.overflow = 'unset';
      };
    }
  }, [isOpen, onClose]);

  return (
    <div 
      className="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center z-50 p-4 backdrop-blur-sm"
      onClick={(e) => {
        // Close when clicking the backdrop
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
    >
      <div className="bg-white rounded-lg shadow-2xl max-w-2xl w-full max-h-[85vh] flex flex-col animate-in fade-in zoom-in duration-200">
        <div className="p-6 border-b border-gray-200 bg-gradient-to-r from-green-50 to-emerald-50">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">
              Similar Transactions Found
            </h2>
            <p className="text-sm text-gray-600 mt-2">
              We found {matchingTransactions.length} transaction{matchingTransactions.length !== 1 ? 's' : ''} with similar merchant names.
              Select which ones should also be assigned to <span className="font-semibold text-green-700">&quot;{newEntityName || 'Unassigned'}&quot;</span>
              {dateRange && (
                <span className="block mt-1 text-xs text-gray-500">
                  Showing transactions from {new Date(dateRange.start).toLocaleDateString()} to {new Date(dateRange.end).toLocaleDateString()}
                </span>
              )}
            </p>
            {onExpandDateRange && (
              <button
                onClick={onExpandDateRange}
                className="mt-2 px-3 py-1.5 text-xs font-medium bg-green-100 text-green-700 rounded-md hover:bg-green-200 transition-colors"
              >
                Expand Date Range
              </button>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6 bg-gray-50">
          <div className="mb-4 flex items-center justify-between">
            <button
              onClick={handleSelectAll}
              className="px-4 py-2 text-sm font-medium bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 transition-colors"
            >
              {selectedIds.size === matchingTransactions.length ? 'Deselect All' : 'Select All'}
            </button>
            <span className="text-sm text-gray-600">
              {selectedIds.size} selected
            </span>
          </div>

          <div className="space-y-2">
            {matchingTransactions.map((transaction) => {
              const transactionId = getTransactionId(transaction);
              const isSelected = selectedIds.has(transactionId);
              return (
                <div
                  key={transactionId}
                  className={`border rounded-lg p-3 cursor-pointer transition-colors ${
                    isSelected ? 'border-green-500 bg-green-50' : 'border-gray-200 hover:bg-gray-50'
                  }`}
                  onClick={() => handleToggle(transactionId)}
                >
                  <div className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => handleToggle(transactionId)}
                      onClick={(e) => e.stopPropagation()}
                      className="w-4 h-4 text-green-600 border-gray-300 rounded focus:ring-green-500"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-gray-900 truncate">
                          {transaction.merchant}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 mt-1 text-xs text-gray-600">
                        <span>${transaction.amount.toFixed(2)}</span>
                        <span>{new Date(transaction.transaction_date).toLocaleDateString()}</span>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="p-6 border-t border-gray-200 flex items-center justify-end gap-3">
          {selectedIds.size > 1 && (
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 transition-colors"
            >
              Cancel
            </button>
          )}
          <button
            onClick={handleConfirm}
            className="px-4 py-2 text-sm font-medium bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
          >
            {selectedIds.size === 0 ? 'No Changes' : `Update ${selectedIds.size} transaction${selectedIds.size !== 1 ? 's' : ''}`}
          </button>
        </div>
      </div>
    </div>
  );
}

