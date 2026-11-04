import { useState, useRef, useMemo, useEffect } from 'react';
import { Check, RefreshCw, MoreVertical, Sparkles, Moon, Eye, EyeOff, FolderKanban, CheckCircle2, CheckCheck, FolderInput, ArrowUpDown } from 'lucide-react';
import { isToday, isYesterday, format } from 'date-fns';
import { useAppStore } from '../stores/appStore';
import { ArticleCard } from './ArticleCard';
import { formatUnreadCount } from './Sidebar';
import { useInfiniteScroll } from '../hooks/useInfiniteScroll';
import { useScrollMarkAsRead } from '../hooks/useScrollMarkAsRead';
import type { Article } from '../types';
import clsx from 'clsx';

export function ArticleList() {
  const { 
    articles, 
    isLoading, 
    hasMore, 
    loadMoreArticles,
    viewMode,
    sortMode,
    setSortMode,
    markAllAsRead,
    filterView,
    likelihoodFilter,
    setLikelihoodFilter,
    selectedFeedId,
    selectedFolderId,
    boards,
    selectedBoardId,
    feeds,
    folders,
    stats,
    setSelectFolderModalOpen,
    toggleSidebar,
    refreshFeed,
    refreshAllFeeds,
    isRefreshing,
    markArticleRead,
    selectedArticle,
    selectArticle,
    isOffline,
    showRead,
    toggleShowRead
  } = useAppStore();

  const [menuOpen, setMenuOpen] = useState(false);
  const [markReadMenuOpen, setMarkReadMenuOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const lastScrollTopRef = useRef<number>(0);
  const openedAtRef = useRef<number>(0);
  const loadMoreRef = useInfiniteScroll(loadMoreArticles, hasMore, isLoading);

  useScrollMarkAsRead({
    containerRef,
    onMarkRead: markArticleRead,
    enabled: true
  });

  // Track initial scroll position and timestamp when an article is opened
  useEffect(() => {
    if (selectedArticle) {
      openedAtRef.current = Date.now();
      if (containerRef.current) {
        lastScrollTopRef.current = containerRef.current.scrollTop;
      }
    }
  }, [selectedArticle?.id]);

  // Auto-close detail page when continuing to scroll in article list stream
  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const currentScrollTop = e.currentTarget.scrollTop;
    if (selectedArticle) {
      if (Date.now() - openedAtRef.current < 600) {
        lastScrollTopRef.current = currentScrollTop;
        return;
      }

      const diff = Math.abs(currentScrollTop - lastScrollTopRef.current);
      if (diff > 80) {
        selectArticle(null);
      }
    } else {
      lastScrollTopRef.current = currentScrollTop;
    }
  };

  let title = 'All';
  if (filterView === 'today') title = 'Today';
  if (filterView === 'unread') title = 'Unread';
  if (filterView === 'starred') title = 'Read Later';
  if (filterView === 'for-you') title = 'For You';
  const selectedFeed = selectedFeedId ? feeds.find(f => f.id === selectedFeedId) : null;
  const feedFolder = selectedFeed?.folder_id ? folders.find(fol => fol.id === selectedFeed.folder_id) : null;
  if (selectedFeed) {
    title = selectedFeed.title || 'Feed';
  }
  if (selectedFolderId) {
    title = folders.find(f => f.id === selectedFolderId)?.name || 'Folder';
  }
  const currentBoard = selectedBoardId ? boards.find(b => b.id === selectedBoardId) : null;
  if (currentBoard) {
    title = currentBoard.name;
  }

  // Calculate unread badge count
  let currentUnread = stats?.unread_count;
  if (filterView === 'today') {
    currentUnread = (stats?.today_unread_count && stats.today_unread_count > 0) ? stats.today_unread_count : articles.filter(a => !a.is_read).length;
  } else if (filterView === 'for-you') {
    currentUnread = (stats?.for_you_unread_count && stats.for_you_unread_count > 0) ? stats.for_you_unread_count : articles.filter(a => !a.is_read).length;
  }
  const unreadCount = currentUnread ?? articles.filter(a => !a.is_read).length;
  const badgeText = selectedBoardId ? `${articles.length}` : formatUnreadCount(unreadCount);

  const visibleArticles = useMemo(() => {
    const raw = (!showRead && (filterView === 'for-you' || filterView === 'unread' || filterView === 'today')) 
      ? articles.filter(a => !a.is_read || a.id === selectedArticle?.id) 
      : articles;

    const seenIds = new Set<number>();
    const seenUrls = new Set<string>();
    const seenTitles = new Set<string>();
    const deduped: Article[] = [];

    const normalizeTitle = (t: string) => 
      t.toLowerCase().replace(/<[^>]+>/g, '').replace(/\s+[-–—|»/•]\s+.*$/, '').replace(/[^a-z0-9]/g, '').trim();

    const normalizeUrl = (url?: string) => {
      if (!url) return '';
      try {
        const u = new URL(url);
        return `${u.hostname}${u.pathname}`.toLowerCase().replace(/\/+$/, '');
      } catch {
        return url.toLowerCase().trim();
      }
    };

    for (const a of raw) {
      if (a.id && seenIds.has(a.id)) continue;
      const nUrl = normalizeUrl(a.url);
      if (nUrl && seenUrls.has(nUrl)) continue;
      const nTitle = normalizeTitle(a.title || '');
      if (nTitle && nTitle.length > 10 && seenTitles.has(nTitle)) continue;

      if (a.id) seenIds.add(a.id);
      if (nUrl) seenUrls.add(nUrl);
      if (nTitle && nTitle.length > 10) seenTitles.add(nTitle);
      deduped.push(a);
    }
    return deduped;
  }, [articles, showRead, filterView, selectedArticle]);

  const groupedArticles = useMemo(() => {
    if (visibleArticles.length === 0) return [];

    if (sortMode === 'date') {
      const sortedByDate = [...visibleArticles].sort((a, b) => {
        const dateA = a.published_at ? new Date(a.published_at).getTime() : 0;
        const dateB = b.published_at ? new Date(b.published_at).getTime() : 0;
        return dateB - dateA;
      });

      const groups: { dateHeader: string; items: typeof articles }[] = [];
      let currentHeader = '';

      for (const article of sortedByDate) {
        let header = 'Older';
        if (article.published_at) {
          const date = new Date(article.published_at);
          if (isToday(date)) {
            header = 'Today';
          } else if (isYesterday(date)) {
            header = 'Yesterday';
          } else {
            header = format(date, 'MMM d, yyyy');
          }
        }

        if (header !== currentHeader) {
          groups.push({ dateHeader: header, items: [article] });
          currentHeader = header;
        } else {
          groups[groups.length - 1].items.push(article);
        }
      }
      return groups;
    }

    if (likelihoodFilter === 'likely') {
      const getArticleTier = (article: Article): 'high' | 'medium' | 'low' => {
        if (article.likelihood_tier === 'high') return 'high';
        if (article.likelihood_tier === 'medium') return 'medium';
        if (article.likelihood_tier === 'low') return 'low';
        return 'low';
      };

      const sortedArticles = [...visibleArticles].sort((a, b) => {
        const tierWeight = { high: 3, medium: 2, low: 1 };
        const tierA = tierWeight[getArticleTier(a)];
        const tierB = tierWeight[getArticleTier(b)];
        if (tierA !== tierB) return tierB - tierA;
        if ((b.interest_score || 0) !== (a.interest_score || 0)) {
          return (b.interest_score || 0) - (a.interest_score || 0);
        }
        const dateA = a.published_at ? new Date(a.published_at).getTime() : 0;
        const dateB = b.published_at ? new Date(b.published_at).getTime() : 0;
        return dateB - dateA;
      });

      const highItems = sortedArticles.filter(a => getArticleTier(a) === 'high');
      const mediumItems = sortedArticles.filter(a => getArticleTier(a) === 'medium');
      const lowItems = sortedArticles.filter(a => getArticleTier(a) === 'low');

      if (highItems.length === 0 && mediumItems.length === 0) {
        return [{ dateHeader: '✨ Likely Interesting', items: sortedArticles }];
      }

      const groups: { dateHeader: string; items: typeof articles }[] = [];
      if (highItems.length > 0) {
        groups.push({ dateHeader: '🌟 Top Recommendations', items: highItems });
      }
      if (mediumItems.length > 0) {
        groups.push({ dateHeader: '✨ Likely Interesting', items: mediumItems });
      }
      if (lowItems.length > 0) {
        groups.push({ dateHeader: '💡 Suggested Stories', items: lowItems });
      }
      return groups;
    }

    if (likelihoodFilter === 'not_likely') {
      return [{ dateHeader: '💤 Lower Priority Stories', items: visibleArticles }];
    }

    // Default 'all': group by date
    const groups: { dateHeader: string; items: typeof articles }[] = [];
    let currentHeader = '';

    for (const article of visibleArticles) {
      let header = 'Older';
      if (article.published_at) {
        const date = new Date(article.published_at);
        if (isToday(date)) {
          header = 'Today';
        } else if (isYesterday(date)) {
          header = 'Yesterday';
        } else {
          header = format(date, 'MMM d, yyyy');
        }
      }

      if (header !== currentHeader) {
        groups.push({ dateHeader: header, items: [article] });
        currentHeader = header;
      } else {
        groups[groups.length - 1].items.push(article);
      }
    }
    return groups;
  }, [visibleArticles, likelihoodFilter, sortMode]);

  return (
    <div className="flex flex-col h-full bg-gray-950 text-gray-200">
      {/* Top App Bar matching Feedly Screenshot 2 */}
      <header className="px-4 py-3 border-b border-gray-900 bg-gray-950/90 backdrop-blur-md sticky top-0 z-20 shrink-0">
        <div className={clsx("w-full flex items-center justify-between", !selectedArticle && "max-w-4xl lg:max-w-5xl mx-auto")}>
          {/* Left: Unread badge pill button that opens drawer on mobile */}
          <div className="flex items-center gap-2">
            <button 
              onClick={toggleSidebar}
              className="flex items-center justify-center min-w-[32px] h-7 px-2 rounded-full border border-gray-800 text-xs font-semibold text-gray-400 hover:text-gray-200 hover:border-gray-700 active:scale-95 transition-all"
              title="Open Feeds Drawer"
            >
              {badgeText || 'Feeds'}
            </button>
          </div>

          {/* Center: Title & Offline Indicator */}
          <div className="flex flex-col items-center justify-center max-w-[50%] min-w-0">
            <div className="flex items-center justify-center gap-1.5 max-w-full">
              <h1 className="font-bold text-gray-100 text-base truncate text-center">
                {title}
              </h1>
              {isOffline && (
                <span className="text-[10px] bg-amber-500/10 text-amber-400 border border-amber-500/30 px-1.5 py-0.5 rounded font-medium shrink-0">
                  Offline
                </span>
              )}
            </div>
            {selectedFeed && (
              <button
                type="button"
                onClick={() => setSelectFolderModalOpen(true, selectedFeed)}
                className="inline-flex items-center gap-1 mt-0.5 px-2 py-0.5 rounded text-[11px] font-medium bg-gray-800/80 hover:bg-gray-800 text-gray-300 hover:text-gray-100 border border-gray-700/60 transition-colors cursor-pointer group"
                title="Change feed grouping / folder"
              >
                <FolderInput size={11} className="text-gray-400 group-hover:text-emerald-400 transition-colors shrink-0" />
                <span className="truncate max-w-[140px]">{feedFolder ? feedFolder.name : 'No Folder (Uncategorized)'}</span>
              </button>
            )}
          </div>

          {/* Right: Refresh, Checkmark (mark read options) and Three dots (options) */}
          <div className="flex items-center gap-1 text-gray-400 relative">
            <button
              onClick={() => setSortMode(sortMode === 'date' ? 'score' : 'date')}
              className={clsx(
                "p-1.5 rounded-md transition-colors flex items-center gap-1 text-xs",
                sortMode === 'date' ? "text-blue-400 hover:bg-gray-800/60" : "text-gray-400 hover:text-gray-100 hover:bg-gray-800/60"
              )}
              title={`Sorted by: ${sortMode === 'date' ? 'Date (Newest first)' : 'Relevance (Score)'}. Click to switch.`}
            >
              <ArrowUpDown size={17} />
              <span className="hidden sm:inline text-[11px] font-medium capitalize">{sortMode}</span>
            </button>

            <button 
              onClick={() => refreshAllFeeds()}
              disabled={isRefreshing}
              className="p-1.5 hover:text-gray-100 hover:bg-gray-800/60 rounded-md transition-colors"
              title="Refresh feeds"
            >
              <RefreshCw size={19} className={isRefreshing ? "animate-spin text-blue-400" : ""} />
            </button>

            <div className="relative">
              <button 
                onClick={() => {
                  setMarkReadMenuOpen(!markReadMenuOpen);
                  setMenuOpen(false);
                }}
                className="p-1.5 hover:text-gray-100 hover:bg-gray-800/60 rounded-md transition-colors"
                title="Mark read options"
              >
                <Check size={20} />
              </button>

              {/* Mark Read Dropdown */}
              {markReadMenuOpen && (
                <div 
                  className="absolute right-0 mt-1 w-52 bg-gray-900 border border-gray-800 rounded-lg shadow-xl py-1 z-30 text-xs"
                  onClick={() => setMarkReadMenuOpen(false)}
                >
                  <button
                    onClick={() => markAllAsRead('all')}
                    className="w-full text-left px-3 py-2 hover:bg-gray-800 text-gray-300 transition-colors"
                  >
                    Mark all as read
                  </button>
                  <button
                    onClick={() => markAllAsRead('1d')}
                    className="w-full text-left px-3 py-2 hover:bg-gray-800 text-gray-300 transition-colors"
                  >
                    Mark read older than 1 day
                  </button>
                  <button
                    onClick={() => markAllAsRead('1w')}
                    className="w-full text-left px-3 py-2 hover:bg-gray-800 text-gray-300 transition-colors"
                  >
                    Mark read older than 1 week
                  </button>
                </div>
              )}
            </div>

            <div className="relative">
              <button 
                onClick={() => {
                  setMenuOpen(!menuOpen);
                  setMarkReadMenuOpen(false);
                }}
                className="p-1.5 hover:text-gray-100 hover:bg-gray-800/60 rounded-md transition-colors"
                title="Options"
              >
                <MoreVertical size={20} />
              </button>

              {/* Dropdown menu */}
              {menuOpen && (
                <div 
                  className="absolute right-0 mt-1 w-52 bg-gray-900 border border-gray-800 rounded-lg shadow-xl py-1 z-30 text-xs"
                  onClick={() => setMenuOpen(false)}
                >
                  <button
                    onClick={() => setSortMode(sortMode === 'date' ? 'score' : 'date')}
                    className="w-full text-left px-3 py-2 hover:bg-gray-800 text-gray-300"
                  >
                    Sort by: <span className="font-semibold text-blue-400 capitalize">{sortMode}</span>
                  </button>
                  <button
                    onClick={toggleShowRead}
                    className="w-full text-left px-3 py-2 hover:bg-gray-800 text-gray-300 flex items-center justify-between"
                  >
                    <span>Show read articles</span>
                    <span className={showRead ? "text-blue-400 font-bold" : "text-gray-500"}>
                      {showRead ? "ON" : "OFF"}
                    </span>
                  </button>
                  {selectedFeedId && (
                    <button
                      onClick={() => refreshFeed(selectedFeedId)}
                      className="w-full text-left px-3 py-2 hover:bg-gray-800 text-gray-300"
                    >
                      Refresh this feed
                    </button>
                  )}
                  {selectedFeed && (
                    <button
                      onClick={() => {
                        setMenuOpen(false);
                        setSelectFolderModalOpen(true, selectedFeed);
                      }}
                      className="w-full text-left px-3 py-2 hover:bg-gray-800 text-gray-300 flex items-center gap-2"
                    >
                      <FolderInput size={13} className="text-gray-400" />
                      <span>Change Folder / Grouping...</span>
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Likelihood Filter Segmented Bar - only for general streams and feeds */}
      {!selectedBoardId && filterView !== 'for-you' && filterView !== 'starred' && (
        <div className="px-4 py-2 border-b border-gray-900/80 bg-gray-950/70 shrink-0">
          <div className={clsx("w-full flex items-center justify-start gap-1.5 overflow-x-auto", !selectedArticle && "max-w-4xl lg:max-w-5xl mx-auto")}>
            <button
              onClick={() => setLikelihoodFilter('likely')}
              className={clsx(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold transition-all border",
                likelihoodFilter === 'likely'
                  ? "bg-blue-600/30 text-blue-400 border-blue-500/40 shadow-sm"
                  : "text-gray-400 border-transparent hover:text-gray-200 hover:bg-gray-900/60"
              )}
              title="Articles most likely to match your interests"
            >
              <Sparkles size={14} className={likelihoodFilter === 'likely' ? "text-blue-400" : "text-gray-400"} />
              <span>Likely</span>
            </button>

            <button
              onClick={() => setLikelihoodFilter('all')}
              className={clsx(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold transition-all border",
                likelihoodFilter === 'all'
                  ? "bg-blue-600/30 text-blue-400 border-blue-500/40 shadow-sm"
                  : "text-gray-400 border-transparent hover:text-gray-200 hover:bg-gray-900/60"
              )}
              title="All articles regardless of likelihood"
            >
              <span>All</span>
            </button>

            <button
              onClick={() => setLikelihoodFilter('not_likely')}
              className={clsx(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold transition-all border",
                likelihoodFilter === 'not_likely'
                  ? "bg-blue-600/30 text-blue-400 border-blue-500/40 shadow-sm"
                  : "text-gray-400 border-transparent hover:text-gray-200 hover:bg-gray-900/60"
              )}
              title="Lower priority or less likely articles"
            >
              <Moon size={14} className={likelihoodFilter === 'not_likely' ? "text-blue-400" : "text-gray-400"} />
              <span>Less Likely</span>
            </button>

            <div className="ml-auto flex items-center shrink-0 pl-2">
              <button
                onClick={toggleShowRead}
                className={clsx(
                  "flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-xs font-medium transition-all border",
                  showRead
                    ? "bg-blue-600/30 text-blue-400 border-blue-500/40 shadow-sm"
                    : "text-gray-400 border-gray-800/80 hover:text-gray-300 hover:border-gray-700 bg-gray-900/40"
                )}
                title={showRead ? "Showing read articles (click to hide)" : "Hiding read articles (click to show)"}
              >
                {showRead ? <Eye size={13} /> : <EyeOff size={13} />}
                <span>{showRead ? "Read visible" : "Unread only"}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* For You Sub-header with showRead toggle */}
      {!selectedBoardId && filterView === 'for-you' && (
        <div className="px-4 py-2 border-b border-gray-900/80 bg-gray-950/70 shrink-0">
          <div className={clsx("w-full flex items-center justify-between", !selectedArticle && "max-w-4xl lg:max-w-5xl mx-auto")}>
            <div className="flex items-center gap-1.5 text-xs text-purple-400 font-semibold">
              <Sparkles size={14} className="text-purple-400" />
              <span>Personalized Top Recommendations</span>
            </div>
            <div className="flex items-center shrink-0">
              <button
                onClick={toggleShowRead}
                className={clsx(
                  "flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-xs font-medium transition-all border",
                  showRead
                    ? "bg-blue-600/30 text-blue-400 border-blue-500/40 shadow-sm"
                    : "text-gray-400 border-gray-800/80 hover:text-gray-300 hover:border-gray-700 bg-gray-900/40"
                )}
                title={showRead ? "Showing read articles (click to hide)" : "Hiding read articles (click to show)"}
              >
                {showRead ? <Eye size={13} /> : <EyeOff size={13} />}
                <span>{showRead ? "Read visible" : "Unread only"}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Article List Stream */}
      <div 
        ref={containerRef} 
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto pb-32"
      >
        <div className={clsx("w-full mx-auto", !selectedArticle && "max-w-4xl lg:max-w-5xl px-2 sm:px-6 py-2")}>
          {currentBoard && (
            <div className="px-4 py-3 mb-2 rounded-xl bg-gray-900/60 border border-gray-800/60">
              <div className="flex items-center gap-2 text-xs text-blue-400 font-semibold">
                <FolderKanban size={15} />
                <span>Personal Board</span>
                <span className="text-gray-600">&middot;</span>
                <span className="text-gray-400 font-normal">
                  {articles.length} {articles.length === 1 ? 'article' : 'articles'}
                </span>
              </div>
              {currentBoard.description && (
                <p className="text-xs text-gray-400 mt-1.5 leading-relaxed">
                  {currentBoard.description}
                </p>
              )}
            </div>
          )}

          {visibleArticles.length === 0 && !isLoading && (
            <div className="p-12 text-center text-gray-500 text-sm">
              {selectedBoardId 
                ? "No articles saved to this board yet. Click the 'Save to Board' icon on any article to add it here!" 
                : "No articles found."}
            </div>
          )}
          
          <div>
            {groupedArticles.map(({ dateHeader, items }) => (
              <div key={dateHeader}>
                <div className="text-blue-500 font-semibold text-sm px-4 sm:px-6 my-2">
                  {dateHeader}
                </div>
                {items.map((article) => (
                  <ArticleCard key={article.id} article={article} viewMode={viewMode} />
                ))}
              </div>
            ))}
          </div>

          {hasMore && (
            <div ref={loadMoreRef} className="p-4 flex justify-center text-gray-500">
              {isLoading ? <RefreshCw className="animate-spin text-gray-400" size={18} /> : null}
            </div>
          )}

          {!hasMore && articles.length > 0 && (
            <div className="py-12 flex flex-col items-center justify-center text-center">
              <div className="w-12 h-12 rounded-full bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400 mb-3">
                <CheckCircle2 size={24} />
              </div>
              <h3 className="text-base font-semibold text-gray-200">You're all caught up! 🎉</h3>
              <p className="text-xs text-gray-400 mt-1 max-w-xs">
                No more unread articles in this stream.
              </p>
              <button 
                onClick={() => markAllAsRead('all')} 
                className="mt-3 px-4 py-2 rounded-full bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 border border-blue-500/30 text-xs font-semibold flex items-center gap-1.5 transition-colors"
              >
                <CheckCheck size={14} /> Mark all as read
              </button>
              {/* Spacer below the card so the last articles can easily be scrolled up */}
              <div className="h-48" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
