/**
 * DateRangePicker Component
 * 
 * A calendar-based date range picker with two months displayed side-by-side,
 * quick selection options, and Clear/Apply buttons.
 */

'use client';

import { useState, useRef, useEffect } from 'react';

interface DateRangePickerProps {
  dateRange: { start: string; end: string };
  onDateRangeChange: (dateRange: { start: string; end: string }) => void;
}

type QuickRangeOption = 
  | 'today'
  | 'last7days'
  | 'last4weeks'
  | 'last6months'
  | 'last12months'
  | 'monthToDate'
  | 'quarterToDate'
  | 'yearToDate'
  | 'allTime';

export default function DateRangePicker({
  dateRange,
  onDateRangeChange,
}: DateRangePickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [tempStart, setTempStart] = useState<string | null>(null);
  const [tempEnd, setTempEnd] = useState<string | null>(null);
  const [selectingStart, setSelectingStart] = useState(true);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        resetTempDates();
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
      };
    }
  }, [isOpen]);

  // Initialize current month to show the start date or current month
  useEffect(() => {
    if (dateRange.start) {
      const startDate = new Date(dateRange.start);
      setCurrentMonth(new Date(startDate.getFullYear(), startDate.getMonth(), 1));
    }
  }, [dateRange.start]);

  const resetTempDates = () => {
    setTempStart(null);
    setTempEnd(null);
    setSelectingStart(true);
  };

  const formatDateRange = (start: string, end: string): string => {
    if (!start || !end) return 'Select date range';
    
    const startDate = new Date(start);
    const endDate = new Date(end);
    
    const startMonth = startDate.toLocaleDateString('en-US', { month: 'short' });
    const endMonth = endDate.toLocaleDateString('en-US', { month: 'short' });
    const startDay = startDate.getDate();
    const endDay = endDate.getDate();
    const year = startDate.getFullYear();
    
    if (startMonth === endMonth && startDate.getFullYear() === endDate.getFullYear()) {
      return `${startMonth} ${startDay} - ${endDay}, ${year}`;
    } else if (startDate.getFullYear() === endDate.getFullYear()) {
      return `${startMonth} ${startDay} - ${endMonth} ${endDay}, ${year}`;
    } else {
      return `${startMonth} ${startDay}, ${startDate.getFullYear()} - ${endMonth} ${endDay}, ${endDate.getFullYear()}`;
    }
  };

  const formatDateRangeHeader = (start: string, end: string): string => {
    if (!start || !end) return 'Select date range';
    
    const startDate = new Date(start);
    const endDate = new Date(end);
    
    const startMonth = startDate.toLocaleDateString('en-US', { month: 'short' });
    const endMonth = endDate.toLocaleDateString('en-US', { month: 'short' });
    const startDay = startDate.getDate();
    const endDay = endDate.getDate();
    const startYear = startDate.getFullYear();
    const endYear = endDate.getFullYear();
    
    return `${startMonth} ${startDay}, ${startYear} → ${endMonth} ${endDay}, ${endYear}`;
  };

  const formatDateInput = (dateStr: string): string => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const year = date.getFullYear();
    return `${month} / ${day} / ${year}`;
  };

  const parseDateInput = (input: string): string | null => {
    // Parse format: MM / DD / YYYY
    const parts = input.split('/').map(p => p.trim());
    if (parts.length !== 3) return null;
    const [month, day, year] = parts;
    const date = new Date(parseInt(year), parseInt(month) - 1, parseInt(day));
    if (isNaN(date.getTime())) return null;
    return formatDateString(date);
  };

  const formatDateString = (date: Date): string => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  };

  const getDaysInMonth = (date: Date): number => {
    return new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate();
  };

  const getFirstDayOfMonth = (date: Date): number => {
    return new Date(date.getFullYear(), date.getMonth(), 1).getDay();
  };

  const isDateInRange = (date: Date, start: string | null, end: string | null): boolean => {
    if (!start || !end) return false;
    const dateStr = formatDateString(date);
    return dateStr >= start && dateStr <= end;
  };

  const isDateStart = (date: Date, start: string | null): boolean => {
    if (!start) return false;
    return formatDateString(date) === start;
  };

  const isDateEnd = (date: Date, end: string | null): boolean => {
    if (!end) return false;
    return formatDateString(date) === end;
  };

  const handleDateClick = (day: number, month: Date) => {
    const date = new Date(month.getFullYear(), month.getMonth(), day);
    const dateStr = formatDateString(date);
    
    if (selectingStart || !tempStart) {
      setTempStart(dateStr);
      setTempEnd(null);
      setSelectingStart(false);
    } else {
      if (dateStr < tempStart) {
        setTempEnd(tempStart);
        setTempStart(dateStr);
      } else {
        setTempEnd(dateStr);
      }
    }
  };

  const handleQuickRange = (option: QuickRangeOption) => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    let start: Date;
    let end: Date = new Date(today);

    switch (option) {
      case 'today':
        start = new Date(today);
        break;
      case 'last7days':
        start = new Date(today);
        start.setDate(today.getDate() - 6);
        break;
      case 'last4weeks':
        start = new Date(today);
        start.setDate(today.getDate() - 27);
        break;
      case 'last6months':
        start = new Date(today);
        start.setMonth(today.getMonth() - 6);
        break;
      case 'last12months':
        start = new Date(today);
        start.setMonth(today.getMonth() - 12);
        break;
      case 'monthToDate':
        start = new Date(today.getFullYear(), today.getMonth(), 1);
        break;
      case 'quarterToDate':
        const quarter = Math.floor(today.getMonth() / 3);
        start = new Date(today.getFullYear(), quarter * 3, 1);
        break;
      case 'yearToDate':
        start = new Date(today.getFullYear(), 0, 1);
        break;
      case 'allTime':
        // Set to a very early date - you might want to get the earliest transaction date
        start = new Date(2000, 0, 1);
        end = new Date(today);
        end.setDate(today.getDate() + 365); // Future date for "all time"
        break;
      default:
        return;
    }

    const startStr = formatDateString(start);
    const endStr = formatDateString(end);
    
    setTempStart(startStr);
    setTempEnd(endStr);
    setSelectingStart(true);
  };

  const handleApply = () => {
    if (tempStart && tempEnd) {
      onDateRangeChange({
        start: tempStart,
        end: tempEnd,
      });
      setIsOpen(false);
      resetTempDates();
    }
  };

  const handleClear = () => {
    setTempStart(null);
    setTempEnd(null);
    onDateRangeChange({ start: '', end: '' });
    setIsOpen(false);
    resetTempDates();
  };

  const handlePrevMonth = () => {
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1));
  };

  const handleNextMonth = () => {
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1));
  };

  const renderCalendar = (month: Date) => {
    const daysInMonth = getDaysInMonth(month);
    const firstDay = getFirstDayOfMonth(month);
    const days: (number | null)[] = [];
    
    for (let i = 0; i < firstDay; i++) {
      days.push(null);
    }
    
    for (let day = 1; day <= daysInMonth; day++) {
      days.push(day);
    }

    const monthName = month.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
    const displayStart = tempStart || dateRange.start;
    const displayEnd = tempEnd || dateRange.end;

    return (
      <div className="flex-1">
        <div className="flex items-center justify-between mb-3">
          <button
            type="button"
            onClick={handlePrevMonth}
            className="p-1 hover:bg-gray-100 rounded transition-colors"
          >
            <svg className="w-4 h-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <h3 className="text-sm font-semibold text-gray-900">{monthName}</h3>
          <button
            type="button"
            onClick={handleNextMonth}
            className="p-1 hover:bg-gray-100 rounded transition-colors"
          >
            <svg className="w-4 h-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>

        <div className="grid grid-cols-7 gap-0.5 mb-1">
          {['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map((day, index) => (
            <div key={index} className="text-center text-xs font-medium text-gray-500 py-2">
              {day}
            </div>
          ))}
        </div>

        <div className="grid grid-cols-7 gap-0.5">
          {days.map((day, index) => {
            if (day === null) {
              return <div key={index} className="aspect-square" />;
            }

            const date = new Date(month.getFullYear(), month.getMonth(), day);
            const dateStr = formatDateString(date);
            const isInRange = isDateInRange(date, displayStart, displayEnd);
            const isStart = isDateStart(date, displayStart);
            const isEnd = isDateEnd(date, displayEnd);

            return (
              <button
                key={index}
                type="button"
                onClick={() => handleDateClick(day, month)}
                className={`
                  aspect-square text-xs font-medium rounded transition-colors flex items-center justify-center
                  ${isStart || isEnd
                    ? 'bg-purple-600 text-white font-semibold'
                    : isInRange
                    ? 'bg-purple-100 text-purple-900'
                    : 'text-gray-700 hover:bg-gray-50'
                  }
                `}
              >
                {day}
              </button>
            );
          })}
        </div>
      </div>
    );
  };

  const displayStart = tempStart || dateRange.start;
  const displayEnd = tempEnd || dateRange.end;
  const nextMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1);

  const [startInput, setStartInput] = useState(formatDateInput(displayStart));
  const [endInput, setEndInput] = useState(formatDateInput(displayEnd));

  useEffect(() => {
    setStartInput(formatDateInput(displayStart));
    setEndInput(formatDateInput(displayEnd));
  }, [displayStart, displayEnd]);

  const handleStartInputChange = (value: string) => {
    setStartInput(value);
    const parsed = parseDateInput(value);
    if (parsed) {
      setTempStart(parsed);
      setSelectingStart(false);
    }
  };

  const handleEndInputChange = (value: string) => {
    setEndInput(value);
    const parsed = parseDateInput(value);
    if (parsed) {
      setTempEnd(parsed);
    }
  };

  const quickRangeOptions = [
    { key: 'today' as QuickRangeOption, label: 'Today' },
    { key: 'last7days' as QuickRangeOption, label: 'Last 7 days' },
    { key: 'last4weeks' as QuickRangeOption, label: 'Last 4 weeks' },
    { key: 'last6months' as QuickRangeOption, label: 'Last 6 months' },
    { key: 'last12months' as QuickRangeOption, label: 'Last 12 months' },
    { key: 'monthToDate' as QuickRangeOption, label: 'Month to date' },
    { key: 'quarterToDate' as QuickRangeOption, label: 'Quarter to date' },
    { key: 'yearToDate' as QuickRangeOption, label: 'Year to date' },
    { key: 'allTime' as QuickRangeOption, label: 'All time' },
  ];

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="px-3 py-1.5 border border-gray-300 rounded-md text-xs text-black bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent flex items-center gap-2 min-w-[180px] justify-between"
      >
        <span className="flex items-center gap-1.5">
          <svg
            className="w-3.5 h-3.5 text-gray-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          <span>{formatDateRange(displayStart, displayEnd)}</span>
        </span>
        <svg
          className={`w-3 h-3 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute z-50 mt-1 bg-white border border-gray-300 rounded-lg shadow-xl w-[700px]">
          {/* Header */}
          <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
            <div className="text-sm font-medium text-gray-900">
              Date range {formatDateRangeHeader(displayStart, displayEnd)}
            </div>
          </div>

          <div className="flex">
            {/* Left Sidebar - Quick Options */}
            <div className="w-48 border-r border-gray-200 p-3">
              <div className="space-y-1">
                {quickRangeOptions.map((option) => (
                  <button
                    key={option.key}
                    type="button"
                    onClick={() => handleQuickRange(option.key)}
                    className="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded transition-colors"
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Main Calendar Area */}
            <div className="flex-1 p-4">
              {/* Date Input Fields */}
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Start</label>
                  <input
                    type="text"
                    value={startInput}
                    onChange={(e) => handleStartInputChange(e.target.value)}
                    placeholder="MM / DD / YYYY"
                    className="w-full px-3 py-2 border border-blue-500 rounded-md text-sm text-black bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">End</label>
                  <input
                    type="text"
                    value={endInput}
                    onChange={(e) => handleEndInputChange(e.target.value)}
                    placeholder="MM / DD / YYYY"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-black bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              {/* Two Calendars Side by Side */}
              <div className="flex gap-4">
                {renderCalendar(currentMonth)}
                {renderCalendar(nextMonth)}
              </div>
            </div>
          </div>

          {/* Footer with Clear and Apply buttons */}
          <div className="px-4 py-3 border-t border-gray-200 flex justify-end gap-2">
            <button
              type="button"
              onClick={handleClear}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
            >
              Clear
            </button>
            <button
              type="button"
              onClick={handleApply}
              disabled={!tempStart || !tempEnd}
              className="px-4 py-2 text-sm font-medium text-white bg-purple-600 rounded-md hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Apply
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
