/**
 * Undo Button Component
 * 
 * Fixed button in bottom left with animation and cooldown
 */

'use client';

import { useEffect } from 'react';

interface UndoButtonProps {
  canUndo: boolean;
  onUndo: () => void;
  isUndoing: boolean;
  undoStackLength: number;
}

export default function UndoButton({ canUndo, onUndo, isUndoing, undoStackLength }: UndoButtonProps) {
  useEffect(() => {
    // Keyboard shortcut: Ctrl+Z or Cmd+Z
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
        e.preventDefault();
        if (canUndo) {
          onUndo();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [canUndo, onUndo]);

  if (!canUndo) return null;

  return (
    <button
      onClick={onUndo}
      disabled={isUndoing}
      className={`
        fixed bottom-6 left-6 z-50
        px-4 py-3
        bg-blue-600 text-white
        rounded-lg shadow-lg
        font-medium text-sm
        transition-all duration-200
        hover:bg-blue-700
        active:scale-95
        disabled:opacity-50 disabled:cursor-not-allowed
        ${isUndoing ? 'animate-pulse' : ''}
      `}
      style={{
        boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1), 0 2px 4px rgba(0, 0, 0, 0.06)',
      }}
      title={`Undo (${undoStackLength} action${undoStackLength !== 1 ? 's' : ''} available)`}
    >
      <div className="flex items-center gap-2">
        <svg
          className="w-5 h-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"
          />
        </svg>
        <span>Undo</span>
        {undoStackLength > 1 && (
          <span className="ml-1 text-xs opacity-75">({undoStackLength})</span>
        )}
      </div>
    </button>
  );
}




