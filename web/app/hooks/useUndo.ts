/**
 * Undo System Hook
 * 
 * Manages undo/redo stack with actions
 */

import { useState, useCallback, useRef } from 'react';

export interface UndoAction {
  type: 'category' | 'merchant' | 'entity' | 'bulk_category' | 'bulk_entity';
  transactionIds: string[];
  beforeState: any; // State before the change
  afterState: any; // State after the change
  description?: string;
}

const UNDO_COOLDOWN_MS = 300;

export function useUndo() {
  const [undoStack, setUndoStack] = useState<UndoAction[]>([]);
  const [isUndoing, setIsUndoing] = useState(false);
  const lastUndoTime = useRef<number>(0);

  const addAction = useCallback((action: UndoAction) => {
    setUndoStack(prev => [...prev, action]);
  }, []);

  const undo = useCallback((): UndoAction | null => {
    const now = Date.now();
    if (now - lastUndoTime.current < UNDO_COOLDOWN_MS) {
      return null; // Cooldown active
    }
    lastUndoTime.current = now;

    setUndoStack(prev => {
      if (prev.length === 0) return prev;
      return prev.slice(0, -1);
    });

    const action = undoStack[undoStack.length - 1];
    if (action) {
      setIsUndoing(true);
      setTimeout(() => setIsUndoing(false), 200); // Animation duration
      return action;
    }
    return null;
  }, [undoStack]);

  const canUndo = undoStack.length > 0;

  const clear = useCallback(() => {
    setUndoStack([]);
  }, []);

  return {
    addAction,
    undo,
    canUndo,
    clear,
    isUndoing,
    undoStackLength: undoStack.length,
  };
}




