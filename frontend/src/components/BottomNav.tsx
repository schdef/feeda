import { AlignLeft, Bookmark, LayoutDashboard, LayoutGrid, Rss, Search, Sparkles } from 'lucide-react';
import { useAppStore } from '../stores/appStore';
import clsx from 'clsx';

export function BottomNav() {
  const {
    toggleSidebar,
    filterView,
    setFilterView,
    viewMode,
    setViewMode,
    discoverViewOpen,
    setDiscoverViewOpen,
    searchQuery,
    setSearchQuery,
    stats,
    selectedFeedId,
    selectedFolderId,
    selectedBoardId
  } = useAppStore();

  const handleSearchClick = () => {
    if (searchQuery) {
      setSearchQuery('');
    } else {
      const query = window.prompt('Search articles:');
      if (query !== null) {
        setSearchQuery(query);
      }
    }
  };

  const isForYouActive = filterView === 'for-you' && !discoverViewOpen && !selectedFeedId && !selectedFolderId && !selectedBoardId;
  const isInterestsActive = filterView === 'interests' && !discoverViewOpen && !selectedFeedId && !selectedFolderId && !selectedBoardId;

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-30 md:hidden bg-gray-950/95 backdrop-blur-md border-t border-gray-800/80 px-4 py-2 flex items-center justify-around h-14">
      {/* 1. Drawer / Feeds List */}
      <button
        onClick={toggleSidebar}
        className="p-2 text-gray-400 hover:text-gray-100 active:scale-95 transition-all"
        title="Feeds"
      >
        <AlignLeft size={22} />
      </button>

      {/* 2. For You */}
      <button
        onClick={() => {
          setDiscoverViewOpen(false);
          setFilterView('for-you');
        }}
        className={clsx(
          "p-2 relative active:scale-95 transition-all flex items-center justify-center",
          isForYouActive ? "text-amber-400" : "text-gray-400 hover:text-gray-100"
        )}
        title="For You"
      >
        <Sparkles size={22} className={isForYouActive ? "fill-amber-400/20" : ""} />
        {Boolean(stats?.for_you_unread_count && stats.for_you_unread_count > 0) && (
          <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-amber-400 ring-2 ring-gray-950" />
        )}
      </button>

      {/* 3. Interests */}
      <button
        onClick={() => {
          setDiscoverViewOpen(false);
          setFilterView('interests');
        }}
        className={clsx(
          "p-2 relative active:scale-95 transition-all flex items-center justify-center",
          isInterestsActive ? "text-indigo-400" : "text-gray-400 hover:text-gray-100"
        )}
        title="Interests"
      >
        <LayoutDashboard size={22} className={isInterestsActive ? "fill-indigo-400/20" : ""} />
      </button>

      {/* 3. Read Later (Bookmark) */}
      <button
        onClick={() => {
          setDiscoverViewOpen(false);
          setFilterView(filterView === 'starred' ? 'all' : 'starred');
        }}
        className={clsx(
          "p-2 active:scale-95 transition-all",
          filterView === 'starred' ? "text-emerald-500" : "text-gray-400 hover:text-gray-100"
        )}
        title="Read Later"
      >
        <Bookmark size={22} className={filterView === 'starred' ? "fill-emerald-500" : ""} />
      </button>

      {/* 4. View Mode Toggle (Feedly-style green accent) */}
      <button
        onClick={() => setViewMode(viewMode === 'magazine' ? 'compact' : 'magazine')}
        className="p-2 text-gray-400 hover:text-emerald-400 active:scale-95 transition-all flex items-center justify-center"
        title={`View: ${viewMode === 'magazine' ? 'Magazine' : 'Compact'}`}
      >
        <LayoutGrid size={22} />
      </button>

      {/* 5. Discover / Add Feed */}
      <button
        onClick={() => setDiscoverViewOpen(!discoverViewOpen)}
        className={clsx(
          "p-2 active:scale-95 transition-all",
          discoverViewOpen ? "text-emerald-500" : "text-gray-400 hover:text-gray-100"
        )}
        title="Discover"
      >
        <Rss size={22} />
      </button>

      {/* 6. Search */}
      <button
        onClick={handleSearchClick}
        className={clsx(
          "p-2 active:scale-95 transition-all",
          searchQuery ? "text-blue-400" : "text-gray-400 hover:text-gray-100"
        )}
        title="Search"
      >
        <Search size={22} />
      </button>
    </nav>
  );
}
