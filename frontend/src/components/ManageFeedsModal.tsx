import React, { useState, useMemo } from 'react';
import { 
  Folder as FolderIcon, 
  FolderMinus, 
  Rss, 
  Mic, 
  Plus, 
  X, 
  Pencil, 
  Trash2, 
  Check, 
  Search, 
  ChevronDown, 
  ChevronRight,
  SlidersHorizontal,
  FolderInput
} from 'lucide-react';
import { useAppStore } from '../stores/appStore';
import type { Feed, Folder } from '../types';

export function ManageFeedsModal() {
  const {
    folders,
    feeds,
    manageFeedsModalOpen,
    setManageFeedsModalOpen,
    createFolder,
    updateFolder,
    deleteFolder,
    updateFeedTitle,
    updateFeedFolder,
    deleteFeed,
  } = useAppStore();

  const [searchQuery, setSearchQuery] = useState('');
  const [isCreatingFolder, setIsCreatingFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [editingFolderId, setEditingFolderId] = useState<number | null>(null);
  const [editingFolderName, setEditingFolderName] = useState('');
  const [editingFeedId, setEditingFeedId] = useState<number | null>(null);
  const [editingFeedTitle, setEditingFeedTitle] = useState('');
  const [collapsedFolders, setCollapsedFolders] = useState<Record<number, boolean>>({});
  const [isBusy, setIsBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  if (!manageFeedsModalOpen) return null;

  const handleClose = () => {
    setManageFeedsModalOpen(false);
    setSearchQuery('');
    setIsCreatingFolder(false);
    setEditingFolderId(null);
    setEditingFeedId(null);
    setActionError(null);
  };

  const toggleFolderCollapse = (folderId: number) => {
    setCollapsedFolders(prev => ({
      ...prev,
      [folderId]: !prev[folderId]
    }));
  };

  const isPodcastFeed = (feed: Feed, folderName?: string) => {
    const fName = (folderName || '').toLowerCase();
    const fTitle = (feed.title || '').toLowerCase();
    const fUrl = (feed.url || '').toLowerCase();
    return fName.includes('podcast') || fTitle.includes('podcast') || fUrl.includes('podcast') || fUrl.includes('/podcasts');
  };

  // Filtered categories and feeds
  const query = searchQuery.trim().toLowerCase();

  const filteredFoldersWithFeeds = useMemo(() => {
    return folders.map(folder => {
      const folderFeeds = feeds.filter(f => f.folder_id === folder.id);
      if (!query) {
        return { folder, feeds: folderFeeds, matches: true };
      }
      const folderMatches = folder.name.toLowerCase().includes(query);
      const matchingFeeds = folderFeeds.filter(feed => 
        (feed.title || '').toLowerCase().includes(query) ||
        (feed.url || '').toLowerCase().includes(query) ||
        (feed.site_url || '').toLowerCase().includes(query)
      );
      if (folderMatches) {
        return { folder, feeds: folderFeeds, matches: true };
      }
      return { folder, feeds: matchingFeeds, matches: matchingFeeds.length > 0 };
    }).filter(item => item.matches);
  }, [folders, feeds, query]);

  const uncategorizedFeeds = useMemo(() => {
    const list = feeds.filter(f => !f.folder_id);
    if (!query) return list;
    return list.filter(feed =>
      (feed.title || '').toLowerCase().includes(query) ||
      (feed.url || '').toLowerCase().includes(query) ||
      (feed.site_url || '').toLowerCase().includes(query)
    );
  }, [feeds, query]);

  // Actions
  const handleCreateFolder = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanName = newFolderName.trim();
    if (!cleanName || isBusy) return;

    setIsBusy(true);
    setActionError(null);
    try {
      await createFolder(cleanName);
      setNewFolderName('');
      setIsCreatingFolder(false);
    } catch (err: any) {
      setActionError(err?.message || 'Failed to create category');
    } finally {
      setIsBusy(false);
    }
  };

  const startEditFolder = (folder: Folder) => {
    setEditingFolderId(folder.id);
    setEditingFolderName(folder.name);
  };

  const handleSaveFolder = async (folderId: number) => {
    const cleanName = editingFolderName.trim();
    if (!cleanName || isBusy) return;

    setIsBusy(true);
    setActionError(null);
    try {
      await updateFolder(folderId, cleanName);
      setEditingFolderId(null);
    } catch (err: any) {
      setActionError(err?.message || 'Failed to update category name');
    } finally {
      setIsBusy(false);
    }
  };

  const handleDeleteFolder = async (folder: Folder) => {
    if (!confirm(`Delete category "${folder.name}"?\n\nFeeds currently inside this category will become Uncategorized. No articles or feeds will be deleted.`)) {
      return;
    }
    setIsBusy(true);
    setActionError(null);
    try {
      await deleteFolder(folder.id);
    } catch (err: any) {
      setActionError(err?.message || 'Failed to delete category');
    } finally {
      setIsBusy(false);
    }
  };

  const startEditFeed = (feed: Feed) => {
    setEditingFeedId(feed.id);
    setEditingFeedTitle(feed.title || '');
  };

  const handleSaveFeedTitle = async (feedId: number) => {
    const cleanTitle = editingFeedTitle.trim();
    if (!cleanTitle || isBusy) return;

    setIsBusy(true);
    setActionError(null);
    try {
      await updateFeedTitle(feedId, cleanTitle);
      setEditingFeedId(null);
    } catch (err: any) {
      setActionError(err?.message || 'Failed to rename feed');
    } finally {
      setIsBusy(false);
    }
  };

  const handleChangeFeedFolder = async (feedId: number, targetFolderIdStr: string) => {
    setIsBusy(true);
    setActionError(null);
    try {
      const folderId = targetFolderIdStr === '' ? null : Number(targetFolderIdStr);
      await updateFeedFolder(feedId, folderId);
    } catch (err: any) {
      setActionError(err?.message || 'Failed to move feed');
    } finally {
      setIsBusy(false);
    }
  };

  const handleDeleteFeed = async (feed: Feed) => {
    const isPodcast = isPodcastFeed(feed);
    const label = isPodcast ? 'podcast' : 'feed';
    if (!confirm(`Are you sure you want to delete the ${label} "${feed.title}" and all its downloaded articles?\n\nThis action cannot be undone.`)) {
      return;
    }
    setIsBusy(true);
    setActionError(null);
    try {
      await deleteFeed(feed.id);
    } catch (err: any) {
      setActionError(err?.message || 'Failed to delete feed');
    } finally {
      setIsBusy(false);
    }
  };

  const totalFeedsCount = feeds.length;
  const totalFoldersCount = folders.length;

  return (
    <div 
      className="fixed inset-0 bg-black/75 backdrop-blur-xs z-50 flex items-center justify-center p-2 sm:p-4"
      onClick={handleClose}
    >
      <div 
        className="bg-gray-900 border border-gray-800 w-full max-w-3xl max-h-[90vh] rounded-2xl flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800 bg-gray-900/90">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
              <SlidersHorizontal size={18} />
            </div>
            <div>
              <h2 className="font-bold text-gray-100 text-base sm:text-lg">Manage Feeds & Categories</h2>
              <p className="text-xs text-gray-400">
                Organize, rename, recategorize, or delete RSS feeds and podcasts ({totalFeedsCount} feeds, {totalFoldersCount} categories)
              </p>
            </div>
          </div>
          <button 
            type="button"
            onClick={handleClose}
            className="text-gray-400 hover:text-gray-200 p-1.5 rounded-lg hover:bg-gray-800 transition-colors"
            title="Close"
          >
            <X size={20} />
          </button>
        </div>

        {/* Toolbar: Search and Create Category */}
        <div className="px-5 py-3 border-b border-gray-800 bg-gray-950/50 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5">
          {/* Search bar */}
          <div className="relative flex-1">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search feeds, podcasts or categories..."
              className="w-full pl-9 pr-8 py-1.5 bg-gray-900 border border-gray-800 rounded-lg text-sm text-gray-200 placeholder-gray-500 focus:outline-hidden focus:border-blue-500/70 transition-colors"
            />
            {searchQuery && (
              <button 
                onClick={() => setSearchQuery('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 p-0.5"
                title="Clear search"
              >
                <X size={14} />
              </button>
            )}
          </div>

          {/* Add Category Button / Form */}
          {!isCreatingFolder ? (
            <button
              type="button"
              onClick={() => setIsCreatingFolder(true)}
              className="inline-flex items-center justify-center gap-1.5 px-3 py-1.5 bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 border border-blue-500/30 rounded-lg text-xs font-semibold transition-colors shrink-0"
            >
              <Plus size={14} />
              <span>New Category</span>
            </button>
          ) : (
            <form onSubmit={handleCreateFolder} className="flex items-center gap-1.5 shrink-0">
              <input
                type="text"
                autoFocus
                value={newFolderName}
                onChange={(e) => setNewFolderName(e.target.value)}
                placeholder="Category name..."
                className="px-2.5 py-1.5 bg-gray-900 border border-blue-500/50 rounded-lg text-xs text-gray-200 placeholder-gray-500 focus:outline-hidden"
              />
              <button
                type="submit"
                disabled={!newFolderName.trim() || isBusy}
                className="p-1.5 bg-blue-600 hover:bg-blue-500 text-gray-100 rounded-lg text-xs font-medium disabled:opacity-50 transition-colors"
                title="Save category"
              >
                <Check size={14} />
              </button>
              <button
                type="button"
                onClick={() => {
                  setIsCreatingFolder(false);
                  setNewFolderName('');
                }}
                className="p-1.5 text-gray-400 hover:text-gray-200 rounded-lg transition-colors"
                title="Cancel"
              >
                <X size={14} />
              </button>
            </form>
          )}
        </div>

        {/* Error banner */}
        {actionError && (
          <div className="px-5 py-2 bg-red-950/40 border-b border-red-900/50 text-red-400 text-xs flex items-center justify-between">
            <span>{actionError}</span>
            <button onClick={() => setActionError(null)} className="text-red-400 hover:text-red-300">
              <X size={14} />
            </button>
          </div>
        )}

        {/* Content list */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4">
          {filteredFoldersWithFeeds.length === 0 && uncategorizedFeeds.length === 0 && (
            <div className="text-center py-12 text-gray-500">
              {query ? (
                <div>
                  <p className="text-sm font-medium text-gray-400">No results found for "{query}"</p>
                  <p className="text-xs text-gray-500 mt-1">Try a different search term or clear the filter.</p>
                </div>
              ) : (
                <div>
                  <p className="text-sm font-medium text-gray-400">No feeds or categories yet</p>
                  <p className="text-xs text-gray-500 mt-1">Add feeds using the "Add Content / Import" button in the sidebar.</p>
                </div>
              )}
            </div>
          )}

          {/* Categories List */}
          {filteredFoldersWithFeeds.map(({ folder, feeds: folderFeeds }) => {
            const isCollapsed = !!collapsedFolders[folder.id];
            const isEditing = editingFolderId === folder.id;
            const isPodcastCategory = folder.name.toLowerCase().includes('podcast');

            return (
              <div 
                key={folder.id} 
                className="bg-gray-950/70 border border-gray-800/80 rounded-xl overflow-hidden shadow-xs transition-colors"
              >
                {/* Category Header Row */}
                <div className="flex items-center justify-between px-3.5 py-2.5 bg-gray-900/60 border-b border-gray-800/50 gap-2">
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <button
                      type="button"
                      onClick={() => toggleFolderCollapse(folder.id)}
                      className="p-1 text-gray-400 hover:text-gray-200 rounded transition-colors"
                      title={isCollapsed ? "Expand category" : "Collapse category"}
                    >
                      {isCollapsed ? <ChevronRight size={15} /> : <ChevronDown size={15} />}
                    </button>

                    {isPodcastCategory ? (
                      <Mic size={16} className="text-purple-400 shrink-0" />
                    ) : (
                      <FolderIcon size={16} className="text-blue-400 shrink-0" />
                    )}

                    {isEditing ? (
                      <div className="flex items-center gap-1.5 flex-1 max-w-sm">
                        <input
                          type="text"
                          autoFocus
                          value={editingFolderName}
                          onChange={(e) => setEditingFolderName(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') handleSaveFolder(folder.id);
                            if (e.key === 'Escape') setEditingFolderId(null);
                          }}
                          className="px-2 py-0.5 bg-gray-900 border border-blue-500 rounded text-xs text-gray-100 w-full focus:outline-hidden"
                        />
                        <button
                          type="button"
                          onClick={() => handleSaveFolder(folder.id)}
                          className="p-1 text-emerald-400 hover:text-emerald-300 rounded"
                          title="Save"
                        >
                          <Check size={14} />
                        </button>
                        <button
                          type="button"
                          onClick={() => setEditingFolderId(null)}
                          className="p-1 text-gray-400 hover:text-gray-200 rounded"
                          title="Cancel"
                        >
                          <X size={14} />
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="font-semibold text-gray-200 text-sm truncate">
                          {folder.name}
                        </span>
                        <span className="text-[11px] font-medium text-gray-400 bg-gray-800/70 border border-gray-700/40 px-2 py-0.5 rounded-full shrink-0">
                          {folderFeeds.length} {folderFeeds.length === 1 ? 'feed' : 'feeds'}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Category Actions */}
                  {!isEditing && (
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        type="button"
                        onClick={() => startEditFolder(folder)}
                        className="p-1.5 text-gray-400 hover:text-gray-200 hover:bg-gray-800 rounded transition-colors"
                        title="Rename category"
                      >
                        <Pencil size={13} />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDeleteFolder(folder)}
                        className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors"
                        title="Delete category (feeds will become uncategorized)"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  )}
                </div>

                {/* Feeds inside this Category */}
                {!isCollapsed && (
                  <div className="divide-y divide-gray-800/40">
                    {folderFeeds.length === 0 ? (
                      <div className="px-4 py-3 text-xs text-gray-500 italic">
                        No feeds in this category yet. Move feeds here using the dropdown below.
                      </div>
                    ) : (
                      folderFeeds.map(feed => {
                        const isEditingThisFeed = editingFeedId === feed.id;
                        const isPodcast = isPodcastFeed(feed, folder.name);

                        return (
                          <div 
                            key={feed.id} 
                            className="px-3.5 py-2.5 flex flex-col sm:flex-row sm:items-center justify-between gap-2 hover:bg-gray-900/40 transition-colors"
                          >
                            {/* Feed Icon & Title */}
                            <div className="flex items-center gap-2.5 min-w-0 flex-1">
                              {feed.favicon_url ? (
                                <img
                                  src={feed.favicon_url}
                                  alt=""
                                  className="w-4 h-4 rounded-xs object-contain shrink-0"
                                  onError={(e) => {
                                    (e.target as HTMLElement).style.display = 'none';
                                  }}
                                />
                              ) : isPodcast ? (
                                <Mic size={15} className="text-purple-400 shrink-0" />
                              ) : (
                                <Rss size={15} className="text-gray-500 shrink-0" />
                              )}

                              {isEditingThisFeed ? (
                                <div className="flex items-center gap-1.5 flex-1 max-w-sm">
                                  <input
                                    type="text"
                                    autoFocus
                                    value={editingFeedTitle}
                                    onChange={(e) => setEditingFeedTitle(e.target.value)}
                                    onKeyDown={(e) => {
                                      if (e.key === 'Enter') handleSaveFeedTitle(feed.id);
                                      if (e.key === 'Escape') setEditingFeedId(null);
                                    }}
                                    className="px-2 py-0.5 bg-gray-900 border border-blue-500 rounded text-xs text-gray-100 w-full focus:outline-hidden"
                                  />
                                  <button
                                    type="button"
                                    onClick={() => handleSaveFeedTitle(feed.id)}
                                    className="p-1 text-emerald-400 hover:text-emerald-300 rounded"
                                    title="Save"
                                  >
                                    <Check size={14} />
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => setEditingFeedId(null)}
                                    className="p-1 text-gray-400 hover:text-gray-200 rounded"
                                    title="Cancel"
                                  >
                                    <X size={14} />
                                  </button>
                                </div>
                              ) : (
                                <div className="min-w-0 flex-1">
                                  <div className="flex items-center gap-2">
                                    <span className="text-xs font-medium text-gray-200 truncate">
                                      {feed.title || 'Untitled Feed'}
                                    </span>
                                    {isPodcast && (
                                      <span className="text-[10px] bg-purple-500/10 text-purple-400 border border-purple-500/20 px-1.5 py-0.2 rounded font-medium shrink-0">
                                        Podcast
                                      </span>
                                    )}
                                  </div>
                                  {feed.site_url && (
                                    <div className="text-[11px] text-gray-500 truncate max-w-xs">
                                      {feed.site_url.replace(/^https?:\/\//, '')}
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>

                            {/* Feed Controls: Category Dropdown & Actions */}
                            <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
                              {/* Category selector */}
                              <div className="flex items-center gap-1 bg-gray-900 border border-gray-800 rounded-lg px-2 py-1 text-xs text-gray-300 hover:border-gray-700 transition-colors">
                                <FolderInput size={12} className="text-gray-400 shrink-0" />
                                <select
                                  value={feed.folder_id ?? ''}
                                  onChange={(e) => handleChangeFeedFolder(feed.id, e.target.value)}
                                  className="bg-transparent text-gray-300 text-xs focus:outline-hidden cursor-pointer"
                                  title="Change Category"
                                >
                                  <option value="" className="bg-gray-900 text-gray-300">Uncategorized</option>
                                  {folders.map(f => (
                                    <option key={f.id} value={f.id} className="bg-gray-900 text-gray-300">
                                      {f.name}
                                    </option>
                                  ))}
                                </select>
                              </div>

                              {/* Unread badge */}
                              {feed.unread_count > 0 && (
                                <span className="text-[10px] text-gray-400 bg-gray-800/80 px-1.5 py-0.5 rounded font-medium shrink-0">
                                  {feed.unread_count}
                                </span>
                              )}

                              {/* Rename Feed */}
                              {!isEditingThisFeed && (
                                <button
                                  type="button"
                                  onClick={() => startEditFeed(feed)}
                                  className="p-1.5 text-gray-400 hover:text-gray-200 hover:bg-gray-800 rounded transition-colors"
                                  title="Rename feed / podcast"
                                >
                                  <Pencil size={13} />
                                </button>
                              )}

                              {/* Delete Feed */}
                              <button
                                type="button"
                                onClick={() => handleDeleteFeed(feed)}
                                className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors"
                                title="Delete / Unsubscribe"
                              >
                                <Trash2 size={13} />
                              </button>
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                )}
              </div>
            );
          })}

          {/* Uncategorized Feeds Section */}
          {uncategorizedFeeds.length > 0 && (
            <div className="bg-gray-950/70 border border-gray-800/80 rounded-xl overflow-hidden shadow-xs transition-colors">
              <div className="flex items-center justify-between px-3.5 py-2.5 bg-gray-900/60 border-b border-gray-800/50">
                <div className="flex items-center gap-2">
                  <FolderMinus size={16} className="text-gray-400" />
                  <span className="font-semibold text-gray-300 text-sm">Uncategorized</span>
                  <span className="text-[11px] font-medium text-gray-400 bg-gray-800/70 border border-gray-700/40 px-2 py-0.5 rounded-full">
                    {uncategorizedFeeds.length} {uncategorizedFeeds.length === 1 ? 'feed' : 'feeds'}
                  </span>
                </div>
              </div>

              <div className="divide-y divide-gray-800/40">
                {uncategorizedFeeds.map(feed => {
                  const isEditingThisFeed = editingFeedId === feed.id;
                  const isPodcast = isPodcastFeed(feed);

                  return (
                    <div 
                      key={feed.id} 
                      className="px-3.5 py-2.5 flex flex-col sm:flex-row sm:items-center justify-between gap-2 hover:bg-gray-900/40 transition-colors"
                    >
                      <div className="flex items-center gap-2.5 min-w-0 flex-1">
                        {feed.favicon_url ? (
                          <img
                            src={feed.favicon_url}
                            alt=""
                            className="w-4 h-4 rounded-xs object-contain shrink-0"
                            onError={(e) => {
                              (e.target as HTMLElement).style.display = 'none';
                            }}
                          />
                        ) : isPodcast ? (
                          <Mic size={15} className="text-purple-400 shrink-0" />
                        ) : (
                          <Rss size={15} className="text-gray-500 shrink-0" />
                        )}

                        {isEditingThisFeed ? (
                          <div className="flex items-center gap-1.5 flex-1 max-w-sm">
                            <input
                              type="text"
                              autoFocus
                              value={editingFeedTitle}
                              onChange={(e) => setEditingFeedTitle(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') handleSaveFeedTitle(feed.id);
                                if (e.key === 'Escape') setEditingFeedId(null);
                              }}
                              className="px-2 py-0.5 bg-gray-900 border border-blue-500 rounded text-xs text-gray-100 w-full focus:outline-hidden"
                            />
                            <button
                              type="button"
                              onClick={() => handleSaveFeedTitle(feed.id)}
                              className="p-1 text-emerald-400 hover:text-emerald-300 rounded"
                              title="Save"
                            >
                              <Check size={14} />
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditingFeedId(null)}
                              className="p-1 text-gray-400 hover:text-gray-200 rounded"
                              title="Cancel"
                            >
                              <X size={14} />
                            </button>
                          </div>
                        ) : (
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-medium text-gray-200 truncate">
                                {feed.title || 'Untitled Feed'}
                              </span>
                              {isPodcast && (
                                <span className="text-[10px] bg-purple-500/10 text-purple-400 border border-purple-500/20 px-1.5 py-0.2 rounded font-medium shrink-0">
                                  Podcast
                                </span>
                              )}
                            </div>
                            {feed.site_url && (
                              <div className="text-[11px] text-gray-500 truncate max-w-xs">
                                {feed.site_url.replace(/^https?:\/\//, '')}
                              </div>
                            )}
                          </div>
                        )}
                      </div>

                      <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
                        <div className="flex items-center gap-1 bg-gray-900 border border-gray-800 rounded-lg px-2 py-1 text-xs text-gray-300 hover:border-gray-700 transition-colors">
                          <FolderInput size={12} className="text-gray-400 shrink-0" />
                          <select
                            value={feed.folder_id ?? ''}
                            onChange={(e) => handleChangeFeedFolder(feed.id, e.target.value)}
                            className="bg-transparent text-gray-300 text-xs focus:outline-hidden cursor-pointer"
                            title="Assign to Category"
                          >
                            <option value="" className="bg-gray-900 text-gray-300">Uncategorized</option>
                            {folders.map(f => (
                              <option key={f.id} value={f.id} className="bg-gray-900 text-gray-300">
                                {f.name}
                              </option>
                            ))}
                          </select>
                        </div>

                        {feed.unread_count > 0 && (
                          <span className="text-[10px] text-gray-400 bg-gray-800/80 px-1.5 py-0.5 rounded font-medium shrink-0">
                            {feed.unread_count}
                          </span>
                        )}

                        {!isEditingThisFeed && (
                          <button
                            type="button"
                            onClick={() => startEditFeed(feed)}
                            className="p-1.5 text-gray-400 hover:text-gray-200 hover:bg-gray-800 rounded transition-colors"
                            title="Rename feed / podcast"
                          >
                            <Pencil size={13} />
                          </button>
                        )}

                        <button
                          type="button"
                          onClick={() => handleDeleteFeed(feed)}
                          className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors"
                          title="Delete / Unsubscribe"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-gray-800 bg-gray-900/90 flex items-center justify-between">
          <span className="text-xs text-gray-500">
            Changes to categories and feeds are saved immediately.
          </span>
          <button
            type="button"
            onClick={handleClose}
            className="px-4 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-200 text-xs font-semibold rounded-lg border border-gray-700 transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
