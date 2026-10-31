import React, { useState } from 'react';
import { Folder as FolderIcon, Check } from 'lucide-react';
import { useAppStore } from '../stores/appStore';

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

  if (!targetFeedForFolder) return null;

  const handleClose = () => {
    setSelectFolderModalOpen(false);
  };

  const handleToggleFolder = async (folderId: number) => {
    // If it's already in this folder, we might want to remove it or keep it?
    // The prompt says "Clicking a folder toggles/moves the feed into that folder"
    // Usually, Feedly allows assigning a feed to a folder. Toggling it if it's the current one means setting it to null.
    const newFolderId = targetFeedForFolder.folder_id === folderId ? null : folderId;
    await updateFeedFolder(targetFeedForFolder.id, newFolderId);
  };

  const handleCreateFolder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFolderName.trim()) return;
    
    try {
      await createFolder(newFolderName.trim());
      setIsCreating(false);
      setNewFolderName('');
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-end sm:items-center justify-center sm:p-4">
      <div className="bg-gray-900 w-full sm:max-w-sm rounded-t-2xl sm:rounded-2xl overflow-hidden shadow-2xl animate-in slide-in-from-bottom-4 sm:slide-in-from-bottom-0 sm:zoom-in-95 duration-200">
        
        {/* Top Navigation Bar */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
          <button 
            onClick={() => setIsCreating(true)}
            className="text-emerald-500 font-medium text-sm hover:text-emerald-400 min-w-[3rem] text-left"
          >
            New
          </button>
          <h2 className="font-bold text-gray-100 text-base">Select Folder</h2>
          <button 
            onClick={handleClose}
            className="text-gray-400 hover:text-gray-200 text-sm font-medium min-w-[3rem] text-right"
          >
            Done
          </button>
        </div>

        {/* Folder List / Content */}
        <div className="max-h-[60vh] overflow-y-auto p-2">
          {isCreating && (
            <div className="p-2 mb-2">
              <form onSubmit={handleCreateFolder} className="flex gap-2">
                <input
                  type="text"
                  autoFocus
                  placeholder="Folder name"
                  value={newFolderName}
                  onChange={e => setNewFolderName(e.target.value)}
                  className="flex-1 bg-gray-800 border border-gray-700 rounded-md px-3 py-1.5 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-emerald-500"
                />
                <button 
                  type="submit" 
                  disabled={!newFolderName.trim()}
                  className="bg-emerald-600 text-white px-3 py-1.5 rounded-md text-sm font-medium disabled:opacity-50"
                >
                  Add
                </button>
                <button 
                  type="button" 
                  onClick={() => setIsCreating(false)}
                  className="text-gray-400 px-2 py-1.5 text-sm"
                >
                  Cancel
                </button>
              </form>
            </div>
          )}

          <div className="flex flex-col gap-1">
            {folders.map(folder => {
              const isAdded = targetFeedForFolder.folder_id === folder.id;
              
              return (
                <button
                  key={folder.id}
                  onClick={() => handleToggleFolder(folder.id)}
                  className="flex items-center justify-between px-3 py-3 rounded-lg hover:bg-gray-800/50 transition-colors w-full text-left group"
                >
                  <div className="flex items-center gap-3">
                    <FolderIcon size={20} className="text-gray-400" />
                    <span className="font-normal text-gray-200 text-sm">{folder.name}</span>
                  </div>
                  
                  {isAdded && (
                    <span className="bg-emerald-600 text-white text-[11px] font-bold px-2.5 py-1 rounded-sm flex items-center gap-1">
                      <Check size={12} strokeWidth={3} /> ADDED
                    </span>
                  )}
                </button>
              );
            })}
            
            {folders.length === 0 && !isCreating && (
              <div className="text-center py-6 text-gray-500 text-sm">
                No folders yet. Click "New" to create one.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
