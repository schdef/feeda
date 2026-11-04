import React, { useState } from 'react';
import { Folder as FolderIcon, FolderMinus, Check, Plus, X, Loader2 } from 'lucide-react';
import { useAppStore } from '../stores/appStore';
import clsx from 'clsx';

export function SelectFolderModal() {
  const {
    folders,
    targetFeedForFolder,
    setSelectFolderModalOpen,
    updateFeedFolder,
    createFolder
  } = useAppStore();

  const [isCreating, setIsCreating] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!targetFeedForFolder) return null;

  const handleClose = () => {
    setSelectFolderModalOpen(false, null);
  };

  const handleSelectFolder = async (folderId: number | null) => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      await updateFeedFolder(targetFeedForFolder.id, folderId);
      handleClose();
    } catch (err) {
      console.error('Failed to update feed folder:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCreateFolder = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanName = newFolderName.trim();
    if (!cleanName || isSubmitting) return;
    
    setIsSubmitting(true);
    try {
      const newFolder = await createFolder(cleanName);
      if (newFolder && newFolder.id) {
        await updateFeedFolder(targetFeedForFolder.id, newFolder.id);
      }
      setIsCreating(false);
      setNewFolderName('');
      handleClose();
    } catch (err) {
      console.error('Failed to create and assign folder:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div 
      className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-end sm:items-center justify-center sm:p-4"
      onClick={handleClose}
    >
      <div 
        className="bg-gray-900 border border-gray-800 w-full sm:max-w-md rounded-t-2xl sm:rounded-2xl overflow-hidden shadow-2xl animate-in slide-in-from-bottom-4 sm:slide-in-from-bottom-0 sm:zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top Navigation Bar */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800 bg-gray-900/90">
          <button 
            type="button"
            onClick={() => setIsCreating(true)}
            className="inline-flex items-center gap-1 text-emerald-400 font-medium text-sm hover:text-emerald-300 transition-colors"
          >
            <Plus size={15} />
            <span>New Folder</span>
          </button>
          <h2 className="font-semibold text-gray-100 text-sm sm:text-base">Change Grouping</h2>
          <button 
            type="button"
            onClick={handleClose}
            className="text-gray-400 hover:text-gray-200 p-1 rounded-md transition-colors"
            title="Close"
          >
            <X size={18} />
          </button>
        </div>

        {/* Target Feed Banner */}
        <div className="px-4 py-2.5 bg-gray-800/40 border-b border-gray-800 flex items-center gap-2">
          <span className="text-xs text-gray-400 shrink-0">Feed:</span>
          <span className="text-xs font-semibold text-gray-200 truncate" title={targetFeedForFolder.title}>
            Folder / Group for "{targetFeedForFolder.title}"
          </span>
        </div>

        {/* Create Folder Form */}
        {isCreating && (
          <div className="p-3 border-b border-gray-800 bg-gray-800/20">
            <form onSubmit={handleCreateFolder} className="flex gap-2">
              <input
                type="text"
                autoFocus
                placeholder="New folder name (e.g. Podcast)"
                value={newFolderName}
                onChange={e => setNewFolderName(e.target.value)}
                disabled={isSubmitting}
                className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-emerald-500"
              />
              <button 
                type="submit" 
                disabled={!newFolderName.trim() || isSubmitting}
                className="bg-emerald-600 hover:bg-emerald-500 text-white px-3 py-1.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 flex items-center gap-1"
              >
                {isSubmitting ? <Loader2 size={14} className="animate-spin" /> : 'Create & Move'}
              </button>
              <button 
                type="button" 
                onClick={() => {
                  setIsCreating(false);
                  setNewFolderName('');
                }}
                disabled={isSubmitting}
                className="text-gray-400 hover:text-gray-200 px-2 py-1.5 text-sm transition-colors"
              >
                Cancel
              </button>
            </form>
          </div>
        )}

        {/* Folder List */}
        <div className="max-h-[60vh] overflow-y-auto p-2 space-y-1">
          {/* No Folder (Uncategorized) Option */}
          <button
            type="button"
            disabled={isSubmitting}
            onClick={() => handleSelectFolder(null)}
            className={clsx(
              "flex items-center justify-between px-3 py-2.5 rounded-lg transition-colors w-full text-left group",
              targetFeedForFolder.folder_id === null
                ? "bg-gray-800 text-gray-100 border border-emerald-500/40"
                : "text-gray-300 hover:bg-gray-800/50 hover:text-gray-100"
            )}
          >
            <div className="flex items-center gap-3 min-w-0">
              <FolderMinus size={18} className="text-gray-400 group-hover:text-gray-300 shrink-0" />
              <span className="font-normal text-sm truncate">No Folder (Uncategorized)</span>
            </div>
            {targetFeedForFolder.folder_id === null && (
              <span className="bg-emerald-600 text-white text-[11px] font-bold px-2 py-0.5 rounded flex items-center gap-1 shrink-0">
                <Check size={12} strokeWidth={3} /> CURRENT
              </span>
            )}
          </button>

          {/* Existing Folders */}
          {folders.map(folder => {
            const isCurrent = targetFeedForFolder.folder_id === folder.id;
            return (
              <button
                key={folder.id}
                type="button"
                disabled={isSubmitting}
                onClick={() => handleSelectFolder(folder.id)}
                className={clsx(
                  "flex items-center justify-between px-3 py-2.5 rounded-lg transition-colors w-full text-left group",
                  isCurrent
                    ? "bg-gray-800 text-gray-100 border border-emerald-500/40"
                    : "text-gray-300 hover:bg-gray-800/50 hover:text-gray-100"
                )}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <FolderIcon size={18} className={isCurrent ? "text-emerald-400 shrink-0" : "text-gray-400 group-hover:text-gray-300 shrink-0"} />
                  <span className="font-normal text-sm truncate">{folder.name}</span>
                </div>
                {isCurrent && (
                  <span className="bg-emerald-600 text-white text-[11px] font-bold px-2 py-0.5 rounded flex items-center gap-1 shrink-0">
                    <Check size={12} strokeWidth={3} /> CURRENT
                  </span>
                )}
              </button>
            );
          })}

          {folders.length === 0 && !isCreating && (
            <div className="text-center py-6 text-gray-500 text-sm">
              No custom folders yet. Click "New Folder" above to create one.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
