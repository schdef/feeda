import React, { useState, useEffect } from 'react';
import { 
  Rss, 
  Bookmark, 
  Sparkles, 
  Flame, 
  Plus, 
  ChevronRight, 
  ChevronDown, 
  AlignLeft,
  RefreshCw,
  X,
  FolderKanban,
  MoreVertical,
  Pencil,
  Trash2,
  AlertTriangle,
  FolderInput
} from 'lucide-react';
import { useAppStore } from '../stores/appStore';
import clsx from 'clsx';

export function formatUnreadCount(count: number): string {
  if (count <= 0) return '';
  if (count >= 1000) return `${Math.floor(count / 1000)}K+`;
  return `${count}`;
}

export function Sidebar() {
  const { 
    feeds, 
    folders, 
    boards,
    selectedBoardId,
    selectBoard,
    setCreateBoardModalOpen,
    deleteBoard,
    filterView, 
    setFilterView,
    selectedFeedId,
    selectFeed,
    selectedFolderId,
    selectFolder,
    setAddFeedModalOpen,
    setSelectFolderModalOpen,
    setSidebarOpen,
    stats,
    refreshAllFeeds,
    refreshFeed,
    isRefreshing
  } = useAppStore();

  const [expandedFolders, setExpandedFolders] = useState<Record<number, boolean>>({
    1: true // Keep default folder expanded if any
  });
  const [menuBoardId, setMenuBoardId] = useState<number | null>(null);

  useEffect(() => {
    const handleOutsideClick = () => setMenuBoardId(null);
    window.addEventListener('click', handleOutsideClick);
    return () => window.removeEventListener('click', handleOutsideClick);
  }, []);

  const toggleFolder = (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedFolders(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const uncategorizedFeeds = feeds.filter(f => !f.folder_id);

  // Compute total unread count
  const totalUnread = stats?.unread_count ?? feeds.reduce((acc, f) => acc + (f.unread_count || 0), 0);

  const topItemClass = (isActive: boolean) => clsx(
    'flex items-center gap-4 px-4 py-2.5 rounded-lg cursor-pointer transition-colors duration-150 text-sm font-medium',
    isActive 
      ? 'bg-gray-800/80 text-blue-400' 
      : 'text-gray-300 hover:bg-gray-800/50 hover:text-gray-100'
  );

  return (
    <div className="flex flex-col h-full bg-gray-950 text-gray-200 select-none border-r border-gray-800/60">
      {/* Header bar with Edit & Close on mobile */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800/60">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-blue-500" />
          <span className="font-bold tracking-tight text-gray-100 text-base">Feeda</span>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setAddFeedModalOpen(true)}
            className="text-xs font-semibold text-gray-400 hover:text-gray-200 transition-colors"
          >
            Manage Feeds
          </button>
          <button
            onClick={() => setSidebarOpen(false)}
            className="md:hidden p-1 text-gray-400 hover:text-gray-200"
          >
            <X size={18} />
          </button>
        </div>
      </div>

      {/* Navigation Links (Feedly-style Today, Read Later, For You) */}
      <div className="px-3 pt-3 pb-2 space-y-1">
        <div 
          className={topItemClass(filterView === 'today')} 
          onClick={() => setFilterView('today')}
        >
          <Flame size={19} className="text-gray-400" />
          <span className="flex-1">Today</span>
          {stats?.today_unread_count ? (
            <span className="text-xs text-gray-500 font-medium">{formatUnreadCount(stats.today_unread_count)}</span>
          ) : null}
        </div>

        <div 
          className={topItemClass(filterView === 'starred')} 
          onClick={() => setFilterView('starred')}
        >
          <Bookmark size={19} className="text-gray-400" />
          <span className="flex-1">Read Later</span>
          {stats?.starred_count ? (
            <span className="text-xs text-gray-500 font-medium">{stats.starred_count}</span>
          ) : null}
        </div>

        <div 
          className={topItemClass(filterView === 'for-you')} 
          onClick={() => setFilterView('for-you')}
        >
          <Sparkles size={19} className="text-gray-400" />
          <span className="flex-1">For You</span>
          {stats?.for_you_unread_count ? (
            <span className="text-xs text-gray-500 font-medium">{formatUnreadCount(stats.for_you_unread_count)}</span>
          ) : null}
        </div>
      </div>

      <div className="h-px bg-gray-800/50 mx-4 my-2" />

      {/* Content Section (Boards & Feeds) */}
      <div className="flex-1 overflow-y-auto px-3 pb-4">
        {/* BOARDS Section */}
        <div className="mb-2">
          <div className="px-3 py-1.5 flex items-center justify-between">
            <h2 className="text-[11px] font-bold text-gray-500 uppercase tracking-wider flex items-center gap-1.5">
              <FolderKanban size={13} className="text-gray-500" />
              <span>Boards</span>
            </h2>
            <button 
              onClick={() => setCreateBoardModalOpen(true)}
              className="p-1 text-gray-500 hover:text-gray-300 rounded transition-colors" 
              title="Create new board"
            >
              <Plus size={14} />
            </button>
          </div>

          <div className="space-y-0.5 mt-0.5">
            {boards.map(board => {
              const isSelected = selectedBoardId === board.id;
              return (
                <div key={board.id} className="relative group">
                  <div 
                    className={clsx(
                      "flex items-center gap-2.5 px-3 py-2 rounded-lg cursor-pointer transition-colors text-sm",
                      isSelected 
                        ? "bg-gray-800/80 text-blue-400 font-medium" 
                        : "text-gray-300 hover:bg-gray-800/50 hover:text-gray-100"
                    )}
                    onClick={() => selectBoard(board.id)}
                  >
                    <FolderKanban size={15} className={isSelected ? "text-blue-400 shrink-0" : "text-gray-400 shrink-0"} />
                    <span className="flex-1 truncate">{board.name}</span>
                    {board.article_count > 0 && (
                      <span className="text-xs text-gray-500 font-medium shrink-0">
                        {board.article_count}
                      </span>
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setMenuBoardId(menuBoardId === board.id ? null : board.id);
                      }}
                      className="opacity-0 group-hover:opacity-100 p-0.5 text-gray-500 hover:text-gray-300 rounded transition-opacity shrink-0"
                      title="Board options"
                    >
                      <MoreVertical size={14} />
                    </button>
                  </div>

                  {menuBoardId === board.id && (
                    <div 
                      className="absolute right-2 top-8 z-30 w-36 bg-gray-900 border border-gray-800 rounded-lg shadow-xl py-1 text-xs text-gray-200"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        onClick={() => {
                          setMenuBoardId(null);
                          setCreateBoardModalOpen(true, board);
                        }}
                        className="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-gray-800 text-left text-gray-300 hover:text-gray-100"
                      >
                        <Pencil size={13} />
                        <span>Edit / Rename</span>
                      </button>
                      <button
                        onClick={async () => {
                          setMenuBoardId(null);
                          if (confirm(`Delete board "${board.name}"? Articles will not be removed from your feeds.`)) {
                            await deleteBoard(board.id);
                          }
                        }}
                        className="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-red-500/20 text-left text-red-400 hover:text-red-300"
                      >
                        <Trash2 size={13} />
                        <span>Delete Board</span>
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
            {boards.length === 0 && (
              <div 
                onClick={() => setCreateBoardModalOpen(true)}
                className="px-3 py-1.5 text-xs text-gray-500 hover:text-gray-400 cursor-pointer italic"
              >
                + Create your first board...
              </div>
            )}
          </div>
        </div>

        <div className="h-px bg-gray-800/50 mx-2 mb-2" />

        {/* FEEDS Section */}
        <div>
          <div className="px-3 py-1.5 flex items-center justify-between">
            <h2 className="text-[11px] font-bold text-gray-500 uppercase tracking-wider">Feeds</h2>
            <button 
              onClick={refreshAllFeeds} 
              disabled={isRefreshing}
              className="p-1 text-gray-500 hover:text-gray-300 rounded transition-colors" 
              title="Refresh all feeds"
            >
              <RefreshCw size={13} className={isRefreshing ? "animate-spin text-blue-400" : ""} />
            </button>
          </div>

        {/* "All" item */}
        <div 
          className={clsx(
            "flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer transition-colors text-sm font-medium mb-1",
            filterView === 'all' && !selectedFeedId && !selectedFolderId
              ? "bg-gray-800/80 text-gray-100"
              : "text-gray-300 hover:bg-gray-800/50 hover:text-gray-100"
          )}
          onClick={() => setFilterView('all')}
        >
          <AlignLeft size={18} className="text-gray-400" />
          <span className="flex-1">All</span>
          {totalUnread > 0 && (
            <span className="text-xs text-gray-500 font-medium">
              {formatUnreadCount(totalUnread)}
            </span>
          )}
        </div>

        {/* Folders List */}
        <div className="space-y-0.5 mt-1">
          {folders.map(folder => {
            const isExpanded = !!expandedFolders[folder.id];
            const folderFeeds = feeds.filter(f => f.folder_id === folder.id);
            const isSelected = selectedFolderId === folder.id;

            return (
              <div key={folder.id} className="group">
                <div 
                  className={clsx(
                    "flex items-center gap-2.5 px-3 py-2 rounded-lg cursor-pointer transition-colors text-sm",
                    isSelected 
                      ? "bg-gray-800/80 text-gray-100 font-medium" 
                      : "text-gray-300 hover:bg-gray-800/50 hover:text-gray-100"
                  )}
                  onClick={() => selectFolder(folder.id)}
                >
                  <button 
                    onClick={(e) => toggleFolder(folder.id, e)} 
                    className="p-0.5 text-gray-500 hover:text-gray-300"
                  >
                    {isExpanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                  </button>
                  <span className="flex-1 truncate">{folder.name}</span>
                  {folder.unread_count > 0 && (
                    <span className="text-xs text-gray-500 font-medium">
                      {formatUnreadCount(folder.unread_count)}
                    </span>
                  )}
                </div>

                {/* Indented feeds list under folder */}
                {isExpanded && (
                  <div className="ml-5 space-y-0.5 pl-2 border-l border-gray-800/60 my-0.5">
                    {folderFeeds.map(feed => (
                      <div 
                        key={feed.id}
                        className={clsx(
                          "group/feed flex items-center gap-2.5 px-2.5 py-1.5 rounded-md cursor-pointer transition-colors text-xs",
                          selectedFeedId === feed.id 
                            ? "bg-gray-800 text-gray-100 font-medium" 
                            : "text-gray-400 hover:bg-gray-800/40 hover:text-gray-200"
                        )}
                        onClick={() => selectFeed(feed.id)}
                      >
                        {feed.favicon_url ? (
                          <img 
                            src={feed.favicon_url} 
                            alt="" 
                            className="w-4 h-4 rounded-sm object-contain shrink-0"
                            onError={(e) => {
                              // Fallback on broken favicon
                              (e.target as HTMLElement).style.display = 'none';
                            }}
                          />
                        ) : (
                          <Rss size={13} className="text-gray-500 shrink-0" />
                        )}
                        <span className="flex-1 truncate">{feed.title}</span>
                        {feed.error_count >= 3 && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              refreshFeed(feed.id);
                            }}
                            className="p-0.5 text-amber-400 hover:text-amber-300 hover:bg-amber-500/10 rounded transition-colors shrink-0"
                            title={feed.last_error ? `Connection issue: ${feed.last_error} - click to retry` : "Feed connection issue - click to retry"}
                          >
                            <AlertTriangle size={12} />
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectFolderModalOpen(true, feed);
                          }}
                          className="opacity-70 sm:opacity-0 group-hover/feed:opacity-100 p-0.5 text-gray-400 hover:text-gray-100 hover:bg-gray-700/60 rounded transition-opacity shrink-0"
                          title="Change folder / group"
                        >
                          <FolderInput size={12} />
                        </button>
                        {feed.unread_count > 0 && (
                          <span className="text-[11px] text-gray-500 font-medium">
                            {formatUnreadCount(feed.unread_count)}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Uncategorized Feeds */}
        {uncategorizedFeeds.length > 0 && (
          <div className="mt-3 pt-2 border-t border-gray-800/50 space-y-0.5">
            {uncategorizedFeeds.map(feed => (
              <div 
                key={feed.id}
                className={clsx(
                  "group/feed flex items-center gap-2.5 px-3 py-1.5 rounded-md cursor-pointer transition-colors text-xs",
                  selectedFeedId === feed.id 
                    ? "bg-gray-800 text-gray-100 font-medium" 
                    : "text-gray-400 hover:bg-gray-800/40 hover:text-gray-200"
                )}
                onClick={() => selectFeed(feed.id)}
              >
                {feed.favicon_url ? (
                  <img 
                    src={feed.favicon_url} 
                    alt="" 
                    className="w-4 h-4 rounded-sm object-contain shrink-0"
                    onError={(e) => {
                      (e.target as HTMLElement).style.display = 'none';
                    }}
                  />
                ) : (
                  <Rss size={13} className="text-gray-500 shrink-0" />
                )}
                <span className="flex-1 truncate">{feed.title}</span>
                {feed.error_count >= 3 && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      refreshFeed(feed.id);
                    }}
                    className="p-0.5 text-amber-400 hover:text-amber-300 hover:bg-amber-500/10 rounded transition-colors shrink-0"
                    title={feed.last_error ? `Connection issue: ${feed.last_error} - click to retry` : "Feed connection issue - click to retry"}
                  >
                    <AlertTriangle size={12} />
                  </button>
                )}
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectFolderModalOpen(true, feed);
                  }}
                  className="opacity-70 sm:opacity-0 group-hover/feed:opacity-100 p-0.5 text-gray-400 hover:text-gray-100 hover:bg-gray-700/60 rounded transition-opacity shrink-0"
                  title="Change folder / group"
                >
                  <FolderInput size={12} />
                </button>
                {feed.unread_count > 0 && (
                  <span className="text-[11px] text-gray-500 font-medium">
                    {formatUnreadCount(feed.unread_count)}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
        </div>
      </div>

      {/* Add Feed button at bottom of sidebar */}
      <div className="p-3 border-t border-gray-800/60">
        <button 
          onClick={() => setAddFeedModalOpen(true)}
          className="w-full flex items-center justify-center gap-2 bg-gray-900 hover:bg-gray-800 text-gray-300 py-2 px-3 rounded-lg border border-gray-800 transition-colors text-sm font-medium"
        >
          <Plus size={16} />
          <span>Add Content / Import</span>
        </button>
      </div>
    </div>
  );
}
