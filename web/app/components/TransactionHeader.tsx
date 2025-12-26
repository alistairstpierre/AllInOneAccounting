/**
 * TransactionHeader Component
 * 
 * Sortable column headers for transactions with visual sort indicators
 * Layout matches TransactionCard component structure
 */

interface TransactionHeaderProps {
  sortBy: 'date' | 'amount';
  sortOrder: 'asc' | 'desc';
  onSortChange: (sortBy: 'date' | 'amount') => void;
}

export default function TransactionHeader({
  sortBy,
  sortOrder,
  onSortChange,
}: TransactionHeaderProps) {
  const SortArrow = ({ column }: { column: 'date' | 'amount' }) => {
    const isActive = sortBy === column;
    const isAsc = sortOrder === 'asc';
    
    return (
      <span className="inline-flex flex-col ml-1">
        <span className={`text-xs leading-none ${isActive && isAsc ? 'text-gray-900' : 'text-gray-300'}`}>▲</span>
        <span className={`text-xs leading-none -mt-0.5 ${isActive && !isAsc ? 'text-gray-900' : 'text-gray-300'}`}>▼</span>
      </span>
    );
  };

  return (
    <div className="bg-gray-100 border border-gray-200 rounded-lg p-2 mb-2">
      <div className="flex items-center gap-3">
        {/* Spacer for potential checkbox column - matches TransactionCard layout */}
        <div className="w-4 flex-shrink-0"></div>
        <button
          onClick={() => onSortChange('date')}
          className="flex items-center text-xs font-semibold text-gray-700 hover:text-gray-900 transition-colors w-24 flex-shrink-0"
        >
          Date
          <SortArrow column="date" />
        </button>
        <div className="flex-1 min-w-0">
          <span className="text-xs font-semibold text-gray-500">Merchant / Category</span>
        </div>
        <button
          onClick={() => onSortChange('amount')}
          className="flex items-center justify-end text-xs font-semibold text-gray-700 hover:text-gray-900 transition-colors flex-shrink-0"
        >
          Amount
          <SortArrow column="amount" />
        </button>
      </div>
    </div>
  );
}

