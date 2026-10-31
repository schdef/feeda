import React, { useState, useEffect } from 'react';
import { X, FolderKanban, Loader2 } from 'lucide-react';
import { useAppStore } from '../stores/appStore';

export function CreateBoardModal() {
  const {
    createBoardModalOpen,
    editingBoard,
    setCreateBoardModalOpen,
    createBoard,
    updateBoard
  } = useAppStore();

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (editingBoard) {
      setName(editingBoard.name);
      setDescription(editingBoard.description || '');
    } else {
      setName('');
      setDescription('');
    }
    setError(null);
  }, [editingBoard, createBoardModalOpen]);

  if (!createBoardModalOpen) return null;

  const handleClose = () => {
    setCreateBoardModalOpen(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) {
      setError('Board name is required');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      if (editingBoard) {
        await updateBoard(
          editingBoard.id, 
          trimmedName, 
          description.trim() ? description.trim() : undefined
        );
      } else {
        await createBoard(
          trimmedName, 
          description.trim() ? description.trim() : undefined
        );
      }
      handleClose();
    } catch (err: any) {
      setError(err?.message || 'Failed to save board');
    } finally {
      setIsSubmitting(false);
    }
  };

  const isEditing = !!editingBoard;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-end sm:items-center justify-center sm:p-4">
      <div className="bg-gray-900 border border-gray-800 w-full sm:max-w-md rounded-t-2xl sm:rounded-2xl overflow-hidden shadow-2xl animate-in slide-in-from-bottom-4 sm:slide-in-from-bottom-0 sm:zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800">
          <div className="flex items-center gap-2.5">
            <FolderKanban size={18} className="text-blue-400" />
            <h2 className="font-semibold text-gray-100 text-base">
              {isEditing ? 'Edit Board' : 'Create New Board'}
            </h2>
          </div>
          <button 
            type="button"
            onClick={handleClose}
            className="p-1 text-gray-400 hover:text-gray-200 rounded-lg hover:bg-gray-800 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {error && (
            <div className="p-2.5 bg-red-500/10 border border-red-500/30 text-red-400 text-xs rounded-lg">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="board-name" className="block text-xs font-semibold text-gray-300 mb-1.5">
              Board Name *
            </label>
            <input
              id="board-name"
              type="text"
              autoFocus
              placeholder="e.g. AI Research, Design Inspiration, Tech News"
              value={name}
              onChange={e => setName(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3.5 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>

          <div>
            <label htmlFor="board-desc" className="block text-xs font-semibold text-gray-300 mb-1.5">
              Description <span className="text-gray-500 font-normal">(optional)</span>
            </label>
            <textarea
              id="board-desc"
              rows={3}
              placeholder="What kind of articles will be saved here?"
              value={description}
              onChange={e => setDescription(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3.5 py-2 text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500 resize-none leading-relaxed transition-colors"
            />
          </div>

          <div className="pt-2 flex items-center justify-end gap-2.5">
            <button
              type="button"
              onClick={handleClose}
              className="px-4 py-2 rounded-lg text-xs font-medium text-gray-400 hover:text-gray-200 hover:bg-gray-800 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !name.trim()}
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-xs font-semibold transition-colors disabled:opacity-50"
            >
              {isSubmitting && <Loader2 size={13} className="animate-spin" />}
              <span>{isEditing ? 'Save Changes' : 'Create Board'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
