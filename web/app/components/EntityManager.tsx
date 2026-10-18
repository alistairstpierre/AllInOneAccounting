/**
 * EntityManager Component
 * 
 * Manages entities (people/organizations) and allows adding new ones
 */

'use client';

import { useState, useEffect } from 'react';

interface Entity {
  id: string;
  name: string;
  transactions: string[];
  cards?: string[]; // Assigned credit cards (array)
  accounts?: string[]; // Assigned bank account numbers (array)
}

interface EntityManagerProps {
  entities: Entity[];
  onEntitySelect: (entityId: string | null) => void;
  selectedEntityId: string | null;
  onEntityCreate: (name: string) => void;
}

export default function EntityManager({
  entities,
  onEntitySelect,
  selectedEntityId,
  onEntityCreate,
}: EntityManagerProps) {
  const [newEntityName, setNewEntityName] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);

  const handleCreateEntity = async () => {
    if (newEntityName.trim()) {
      onEntityCreate(newEntityName.trim());
      setNewEntityName('');
      setShowAddForm(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-6">
      <div className="flex items-center gap-4 flex-wrap">
        <label className="text-sm font-medium text-black">Assign to:</label>
        {entities.map((entity) => (
          <button
            key={entity.id}
            onClick={() => onEntitySelect(entity.id === selectedEntityId ? null : entity.id)}
            className={`px-3 py-1 text-sm font-medium rounded-md transition-colors ${
              selectedEntityId === entity.id
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            {entity.name}
          </button>
        ))}
        {showAddForm ? (
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={newEntityName}
              onChange={(e) => setNewEntityName(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleCreateEntity()}
              placeholder="Enter name..."
              className="px-3 py-1 text-sm border border-gray-300 rounded-md text-black bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              autoFocus
            />
            <button
              onClick={handleCreateEntity}
              className="px-3 py-1 text-sm font-medium bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
            >
              Add
            </button>
            <button
              onClick={() => {
                setShowAddForm(false);
                setNewEntityName('');
              }}
              className="px-3 py-1 text-sm font-medium bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            onClick={() => setShowAddForm(true)}
            className="px-3 py-1 text-sm font-medium bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 transition-colors"
          >
            + Add Person/Entity
          </button>
        )}
      </div>
    </div>
  );
}

