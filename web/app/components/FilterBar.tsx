/**
 * FilterBar Component
 * 
 * Provides filtering by category and sorting options for transactions.
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

interface FilterBarProps {
  categories: string[];
  selectedCategory: string;
  onCategoryChange: (category: string) => void;
  dateRange: { start: string; end: string };
  onDateRangeChange: (dateRange: { start: string; end: string }) => void;
  entities?: Entity[];
  selectedEntityIds?: string[];
  onEntityFilterChange?: (entityIds: string[]) => void;
  searchText?: string;
  onSearchChange?: (searchText: string) => void;
  showTransfers?: boolean;
  onShowTransfersChange?: (show: boolean) => void;
}

export default function FilterBar({
  categories,
  selectedCategory,
  onCategoryChange,
  dateRange,
  onDateRangeChange,
  entities = [],
  selectedEntityIds = [],
  onEntityFilterChange,
  searchText = '',
  onSearchChange,
  showTransfers = true,
  onShowTransfersChange,
}: FilterBarProps) {
  const [isEntityDropdownOpen, setIsEntityDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsEntityDropdownOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const handleEntityToggle = (entityId: string) => {
    if (selectedEntityIds.includes(entityId)) {
      onEntityFilterChange?.(selectedEntityIds.filter(id => id !== entityId));
    } else {
      onEntityFilterChange?.([...selectedEntityIds, entityId]);
    }
  };

  const handleClearEntities = () => {
    onEntityFilterChange?.([]);
    setIsEntityDropdownOpen(false);
  };

  const getEntityButtonText = () => {
    if (selectedEntityIds.length === 0) {
      return 'All Entities';
    }
    if (selectedEntityIds.length === 1) {
      const entity = entities.find(e => e.id === selectedEntityIds[0]);
      return entity?.name || '1 selected';
    }
    return `${selectedEntityIds.length} selected`;
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-3 mb-6">
      <div className="flex items-center flex-wrap gap-x-3 gap-y-2">
        <h3 className="text-xs font-bold text-gray-900 uppercase mr-2">FILTERS</h3>
        <div className="flex items-center gap-1.5">
          <label className="text-xs font-medium text-black">Date:</label>
          <input
            type="date"
            value={dateRange.start}
            onChange={(e) => onDateRangeChange({ ...dateRange, start: e.target.value })}
            className="px-2 py-1 border border-gray-300 rounded-md text-xs text-black bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent w-32"
          />
          <span className="text-xs text-gray-600">to</span>
          <input
            type="date"
            value={dateRange.end}
            onChange={(e) => onDateRangeChange({ ...dateRange, end: e.target.value })}
            className="px-2 py-1 border border-gray-300 rounded-md text-xs text-black bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent w-32"
          />
        </div>
        {entities.length > 0 && onEntityFilterChange && (
          <div className="flex items-center gap-1.5">
            <label className="text-xs font-medium text-black">Entity:</label>
            <div className="relative" ref={dropdownRef}>
              <button
                type="button"
                onClick={() => setIsEntityDropdownOpen(!isEntityDropdownOpen)}
                className="px-2 py-1 border border-gray-300 rounded-md text-xs text-black bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent min-w-[120px] text-left flex items-center justify-between"
              >
                <span>{getEntityButtonText()}</span>
                <svg
                  className={`w-3 h-3 ml-1 transition-transform ${isEntityDropdownOpen ? 'rotate-180' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {isEntityDropdownOpen && (
                <div className="absolute z-10 mt-1 w-full bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-auto">
                  {entities.map((entity) => (
                    <label
                      key={entity.id}
                      className="flex items-center px-3 py-1.5 hover:bg-gray-50 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={selectedEntityIds.includes(entity.id)}
                        onChange={() => handleEntityToggle(entity.id)}
                        className="w-3.5 h-3.5 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                        onClick={(e) => e.stopPropagation()}
                      />
                      <span className="ml-2 text-xs text-black">{entity.name}</span>
                    </label>
                  ))}
                  {selectedEntityIds.length > 0 && (
                    <div className="border-t border-gray-200">
                      <button
                        type="button"
                        onClick={handleClearEntities}
                        className="w-full px-3 py-1.5 text-xs text-left text-gray-700 hover:bg-gray-50"
                      >
                        Clear All
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
        <div className="flex items-center gap-1.5">
          <label className="text-xs font-medium text-black">Category:</label>
          <select
            value={selectedCategory}
            onChange={(e) => onCategoryChange(e.target.value)}
            className="px-2 py-1 border border-gray-300 rounded-md text-xs text-black bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="all">All</option>
            {categories.map((category) => (
              <option key={category} value={category}>
                {category}
              </option>
            ))}
          </select>
        </div>
        {onSearchChange && (
          <div className="flex items-center gap-1.5">
            <label className="text-xs font-medium text-black">Search:</label>
            <input
              type="text"
              value={searchText}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="Search..."
              className="w-32 px-2 py-1 border border-gray-300 rounded-md text-xs text-black bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
        )}
        {onShowTransfersChange && (
          <div className="flex items-center gap-1.5">
            <input
              type="checkbox"
              id="show-transfers"
              checked={showTransfers}
              onChange={(e) => onShowTransfersChange(e.target.checked)}
              className="w-3.5 h-3.5 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
            />
            <label htmlFor="show-transfers" className="text-xs font-medium text-black cursor-pointer">
              Show Transfers
            </label>
          </div>
        )}
      </div>
    </div>
  );
}

