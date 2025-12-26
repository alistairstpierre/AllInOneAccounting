/**
 * SmartTransferUpdateModal Component
 * 
 * Modal that shows similar transactions when a transfer status is changed,
 * allowing the user to select which ones should also be marked as transfers.
 */

'use client';

import { useState, useEffect } from 'react';

// Simplified Transaction interface for the modal (matches API response)
interface Transaction {
  id?: string;  // Optional for backward compatibility
  merchant: string;
  amount: number;
  transaction_date: string;
  is_transfer?: boolean;
}

interface SmartTransferUpdateModalProps {
  isOpen: boolean;
  onClose: () => void;
  matchingTransactions: Transaction[];
  isTransfer: boolean;
  originalTransaction: Transaction;
  onConfirm: (selectedTransactionIds: string[]) => void;
  getTransactionId: (transaction: { id?: string; merchant: string; amount: number; transaction_date: string }) => string;
  dateRange?: { start: string; end: string } | null;
  onExpandDateRange?: () => void;
}

export default function SmartTransferUpdateModal({
  isOpen,
  onClose,
  matchingTransactions,
  isTransfer,
  originalTransaction,
  onConfirm,
  getTransactionId,
  dateRange,
  onExpandDateRange,
}: SmartTransferUpdateModalProps) {
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
        <div className="p-6 border-b border-gray-200 bg-gradient-to-r from-blue-50 to-indigo-50">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">
              Similar Transactions Found
            </h2>
            <p className="text-sm text-gray-600 mt-2">
              We found {matchingTransactions.length} transaction{matchingTransactions.length !== 1 ? 's' : ''} with the same merchant name.
              Select which ones should also be marked as <span className="font-semibold text-blue-700">{isTransfer ? 'transfer' : 'non-transfer'}</span>.
              {dateRange && (
                <span className="block mt-1 text-xs text-gray-500">
                  Showing transactions from {new Date(dateRange.start).toLocaleDateString()} to {new Date(dateRange.end).toLocaleDateString()}
                </span>
              )}
            </p>
            {onExpandDateRange && (
              <button
                onClick={onExpandDateRange}
                className="mt-2 px-3 py-1.5 text-xs font-medium bg-blue-100 text-blue-700 rounded-md hover:bg-blue-200 transition-colors"
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
              {selectedIds.size} of {matchingTransactions.length} selected
            </span>
          </div>

          <div className="space-y-2">
            {matchingTransactions.map((transaction) => {
              const transactionId = getTransactionId(transaction);
              const isSelected = selectedIds.has(transactionId);
              return (
                <div
                  key={transactionId}
                  className={`bg-white rounded-lg border-2 p-4 cursor-pointer transition-all ${
                    isSelected
                      ? 'border-blue-500 bg-blue-50 shadow-md'
                      : 'border-gray-200 hover:border-gray-300 hover:shadow-sm'
                  }`}
                  onClick={() => handleToggle(transactionId)}
                >
                  <div className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => handleToggle(transactionId)}
                      onClick={(e) => e.stopPropagation()}
                      className="w-5 h-5 text-blue-600 border-gray-300 rounded focus:ring-blue-500 cursor-pointer"
                    />
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <h3 className="font-semibold text-gray-900">
                          {transaction.merchant}
                        </h3>
                        <span className="text-lg font-bold text-gray-900">
                          ${transaction.amount.toFixed(2)}
                        </span>
                      </div>
                      <p className="text-sm text-gray-500 mt-1">
                        {new Date(transaction.transaction_date).toLocaleDateString('en-US', {
                          year: 'numeric',
                          month: 'long',
                          day: 'numeric',
                        })}
                      </p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="p-6 border-t border-gray-200 bg-white flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={selectedIds.size === 0}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Update {selectedIds.size > 0 ? `${selectedIds.size} ` : ''}Transaction{selectedIds.size !== 1 ? 's' : ''}
          </button>
        </div>
      </div>
    </div>
  );
}

