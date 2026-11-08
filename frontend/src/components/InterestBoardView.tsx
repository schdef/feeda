import { useState, useRef, useMemo } from 'react';
import { 
  LayoutDashboard, 
  Sparkles, 
  Moon,
  RefreshCw, 
  CheckCheck, 
  LayoutGrid, 
  List, 
  ArrowUp,
  Inbox,
  Eye,
  EyeOff,
  ArrowDownWideNarrow,
  Clock
} from 'lucide-react';
import { useAppStore } from '../stores/appStore';
import { ArticleCard } from './ArticleCard';
import { formatUnreadCount } from './Sidebar';
import clsx from 'clsx';

type LikelihoodSelection = 'likely' | 'not_likely';

export function InterestBoardView() {
  const { 
    interestGroups, 
    interestBoardLoading, 
    fetchInterestBoard, 
    markAllAsRead, 
    markArticleRead, 
    viewMode, 
    setViewMode, 
    stats,
    toggleSidebar,
    isOffline,
    showRead,
    toggleShowRead
  } = useAppStore();

  const [sortMode, setSortMode] = useState<'score' | 'date'>('score');
  const [selectedLikelihoods, setSelectedLikelihoods] = useState<Set<LikelihoodSelection>>(new Set());

  const columnRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const scrollToColumnTop = (slug: string) => {
    const el = columnRefs.current[slug];
    if (el) {
      el.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const markGroupAsRead = (articles: { id: number; is_read: boolean }[]) => {
    articles.forEach(a => {
      if (!a.is_read) {
        markArticleRead(a.id);
      }
    });
  };

  // Likelihood multi-selection state calculations
  const isAllExplicit = selectedLikelihoods.size === 0;
  const hasLikely = selectedLikelihoods.has('likely');
  const hasNotLikely = selectedLikelihoods.has('not_likely');
  const hasBoth = hasLikely && hasNotLikely;

  const isAllActive = isAllExplicit;
  const isLikelyActive = hasLikely;
  const isNotLikelyActive = hasNotLikely;

  const handleSelectAll = () => {
    setSelectedLikelihoods(new Set());
  };

  const handleToggleLikelihood = (key: LikelihoodSelection) => {
    if (isAllExplicit) {
      // If "All" was active, set selection to only the clicked one
      setSelectedLikelihoods(new Set([key]));
      return;
    }

    const next = new Set(selectedLikelihoods);
    if (next.has(key)) {
      next.delete(key);
    } else {
      next.add(key);
    }

    // If the user deselects the only active filter, revert automatically to showing "All"
    if (next.size === 0) {
      setSelectedLikelihoods(new Set());
    } else {
      setSelectedLikelihoods(next);
    }
  };

  const parseScore = (score: number | string | undefined | null): number => {
    if (score === undefined || score === null) return 0;
    const num = typeof score === 'number' ? score : parseFloat(score);
    return isNaN(num) ? 0 : num;
  };

  const filteredGroups = useMemo(() => {
    return interestGroups.map(group => {
      const matching = (group.articles || []).filter(article => {
        // Combine with unread filter: !showRead ? (!a.is_read || a.is_starred) : true
        if (!showRead && article.is_read && !article.is_starred) {
          return false;
        }

        // When 'all' is selected: true
        if (isAllExplicit || hasBoth) {
          return true;
        }

        const tier = article.likelihood_tier || 'low';
        // 'likely' in selection AND (likelihood_tier === 'high' || likelihood_tier === 'medium')
        if (hasLikely && (tier === 'high' || tier === 'medium')) {
          return true;
        }
        // 'not_likely' in selection AND likelihood_tier === 'low'
        if (hasNotLikely && tier === 'low') {
          return true;
        }

        return false;
      });

      const sorted = [...matching].sort((a, b) => {
        if (sortMode === 'score') {
          const scoreDiff = parseScore(b.interest_score) - parseScore(a.interest_score);
          if (scoreDiff !== 0) {
            return scoreDiff;
          }
          const dateA = a.published_at ? new Date(a.published_at).getTime() : 0;
          const dateB = b.published_at ? new Date(b.published_at).getTime() : 0;
          return dateB - dateA;
        } else {
          const dateA = a.published_at ? new Date(a.published_at).getTime() : 0;
          const dateB = b.published_at ? new Date(b.published_at).getTime() : 0;
          return dateB - dateA;
        }
      });

      return {
        ...group,
        articles: sorted
      };
    });
  }, [interestGroups, showRead, isAllExplicit, hasBoth, hasLikely, hasNotLikely, sortMode]);

  const totalBoardArticles = useMemo(() => {
    return filteredGroups.reduce((acc, g) => acc + g.articles.length, 0);
  }, [filteredGroups]);

  const badgeText = formatUnreadCount(stats?.unread_count || 0);

  return (
    <div className="flex flex-col h-full bg-gray-950 text-gray-200 overflow-hidden">
      {/* 1. Header matching Feeda's header standard */}
      <header className="px-4 py-3 border-b border-gray-900 bg-gray-950/90 backdrop-blur-md sticky top-0 z-20 shrink-0">
        <div className="w-full flex items-center justify-between">
          {/* Left: Mobile drawer button + Title & Badge */}
          <div className="flex items-center gap-3 min-w-0">
            <button 
              onClick={toggleSidebar}
              className="flex items-center justify-center min-w-[32px] h-7 px-2 rounded-full border border-gray-800 text-xs font-semibold text-gray-400 hover:text-gray-200 hover:border-gray-700 active:scale-95 transition-all md:hidden shrink-0 cursor-pointer"
              title="Open Feeds Drawer"
            >
              {badgeText || 'Feeds'}
            </button>

            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-7 h-7 rounded-lg bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0">
                <LayoutDashboard size={16} />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h1 className="font-bold text-gray-100 text-base truncate">
                    Interests
                  </h1>
                  <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 shrink-0">
                    <Sparkles size={10} />
                    {showRead ? 'AI Grouped • All' : 'AI Grouped • Unread & Read Later'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Right: Actions (Sort, View Mode, Show Read, Refresh, Mark all read) */}
          <div className="flex items-center gap-1.5 text-gray-400 shrink-0">
            {isOffline && (
              <span className="text-[10px] bg-amber-500/10 text-amber-400 border border-amber-500/30 px-1.5 py-0.5 rounded font-medium mr-1 shrink-0">
                Offline
              </span>
            )}

            {/* Header Sort Toggle */}
            <button
              onClick={() => setSortMode(sortMode === 'score' ? 'date' : 'score')}
              className={clsx(
                "p-1.5 rounded-md transition-colors flex items-center gap-1 text-xs cursor-pointer",
                sortMode === 'score' ? "text-blue-400 hover:bg-gray-800/60" : "text-gray-400 hover:text-gray-100 hover:bg-gray-800/60"
              )}
              title={`Sorted by: ${sortMode === 'score' ? 'Relevance (Score)' : 'Date (Newest first)'}. Click to switch.`}
            >
              <ArrowDownWideNarrow size={17} />
              <span className="hidden sm:inline text-[11px] font-medium capitalize">{sortMode === 'score' ? 'Relevance' : 'Date'}</span>
            </button>

            {/* View Mode Toggle */}
            <button
              onClick={() => setViewMode(viewMode === 'magazine' ? 'compact' : 'magazine')}
              className="p-1.5 rounded-md transition-colors flex items-center gap-1 text-xs text-gray-400 hover:text-gray-100 hover:bg-gray-800/60 cursor-pointer"
              title={viewMode === 'magazine' ? "Switch to List view" : "Switch to Magazine view"}
            >
              {viewMode === 'magazine' ? (
                <LayoutGrid size={17} className="text-indigo-400" />
              ) : (
                <List size={17} className="text-indigo-400" />
              )}
              <span className="hidden lg:inline text-[11px] font-medium capitalize">
                {viewMode === 'magazine' ? 'Magazine' : 'List'}
              </span>
            </button>

            {/* Show Read Toggle */}
            <button
              onClick={toggleShowRead}
              className={clsx(
                "p-1.5 rounded-md transition-colors flex items-center gap-1 text-xs cursor-pointer",
                showRead ? "text-indigo-400 bg-gray-800/60" : "text-gray-400 hover:text-gray-100 hover:bg-gray-800/60"
              )}
              title={showRead ? "Showing read articles (click to hide)" : "Hiding read articles (click to show)"}
            >
              {showRead ? <Eye size={17} /> : <EyeOff size={17} />}
              <span className="hidden lg:inline text-[11px] font-medium">
                {showRead ? "Read visible" : "Unread only"}
              </span>
            </button>

            {/* Refresh Board */}
            <button 
              onClick={() => fetchInterestBoard()}
              disabled={interestBoardLoading}
              className="p-1.5 hover:text-gray-100 hover:bg-gray-800/60 rounded-md transition-colors cursor-pointer"
              title="Refresh Interest Board"
            >
              <RefreshCw size={17} className={clsx(interestBoardLoading && "animate-spin text-indigo-400")} />
            </button>

            {/* Mark All Read */}
            <button 
              onClick={() => {
                if (confirm('Mark all articles as read?')) {
                  markAllAsRead('all');
                }
              }}
              className="p-1.5 hover:text-gray-100 hover:bg-gray-800/60 rounded-md transition-colors cursor-pointer"
              title="Mark all as read"
            >
              <CheckCheck size={18} />
            </button>
          </div>
        </div>
      </header>

      {/* 2. Likelihood Filter & Sort Segmented Bar */}
      <div className="px-4 py-2 border-b border-gray-900/80 bg-gray-950/70 shrink-0">
        <div className="w-full flex items-center justify-between gap-2 overflow-x-auto">
          {/* Likelihood multi-selection chips */}
          <div className="flex items-center gap-1.5 shrink-0">
            <button
              onClick={handleSelectAll}
              className={clsx(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold transition-all border cursor-pointer",
                isAllActive
                  ? "bg-blue-600/30 text-blue-400 border-blue-500/40 shadow-sm"
                  : "text-gray-400 border-transparent hover:text-gray-200 hover:bg-gray-900/60"
              )}
              title="All articles regardless of likelihood"
            >
              <span>All</span>
            </button>

            <button
              onClick={() => handleToggleLikelihood('likely')}
              className={clsx(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold transition-all border cursor-pointer",
                isLikelyActive
                  ? "bg-blue-600/30 text-blue-400 border-blue-500/40 shadow-sm"
                  : "text-gray-400 border-transparent hover:text-gray-200 hover:bg-gray-900/60"
              )}
              title="Articles most likely to match your interests (high & medium)"
            >
              <Sparkles size={14} className={isLikelyActive ? "text-blue-400" : "text-gray-400"} />
              <span>Likely</span>
            </button>

            <button
              onClick={() => handleToggleLikelihood('not_likely')}
              className={clsx(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold transition-all border cursor-pointer",
                isNotLikelyActive
                  ? "bg-blue-600/30 text-blue-400 border-blue-500/40 shadow-sm"
                  : "text-gray-400 border-transparent hover:text-gray-200 hover:bg-gray-900/60"
              )}
              title="Lower priority or less likely articles"
            >
              <Moon size={14} className={isNotLikelyActive ? "text-blue-400" : "text-gray-400"} />
              <span>Less Likely</span>
            </button>
          </div>

          {/* Right: Sort controls */}
          <div className="flex items-center gap-2 shrink-0">
            <div className="flex items-center gap-1 bg-gray-900/60 p-0.5 rounded-full border border-gray-800/80">
              <button
                onClick={() => setSortMode('score')}
                className={clsx(
                  "flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold transition-all cursor-pointer",
                  sortMode === 'score'
                    ? "bg-blue-600/30 text-blue-400 shadow-sm border border-blue-500/40"
                    : "text-gray-400 hover:text-gray-200 border border-transparent"
                )}
                title="Sort by relevance score (highest first)"
              >
                <ArrowDownWideNarrow size={13} className={sortMode === 'score' ? "text-blue-400" : "text-gray-400"} />
                <span>Relevance</span>
              </button>
              <button
                onClick={() => setSortMode('date')}
                className={clsx(
                  "flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold transition-all cursor-pointer",
                  sortMode === 'date'
                    ? "bg-blue-600/30 text-blue-400 shadow-sm border border-blue-500/40"
                    : "text-gray-400 hover:text-gray-200 border border-transparent"
                )}
                title="Sort by published date (newest first)"
              >
                <Clock size={13} className={sortMode === 'date' ? "text-blue-400" : "text-gray-400"} />
                <span>Date</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Board Content Area */}
      <div className="flex-1 min-h-0 overflow-hidden relative">
        {interestBoardLoading && interestGroups.length === 0 ? (
          /* Skeleton Loading State */
          <div className="h-full p-4 md:p-6 overflow-x-auto flex gap-4 md:gap-5">
            {[1, 2, 3, 4].map(idx => (
              <div 
                key={idx}
                className="w-[85vw] sm:w-80 md:w-88 lg:w-96 shrink-0 flex flex-col bg-gray-900/30 border border-gray-800/60 rounded-2xl p-3 animate-pulse"
              >
                <div className="flex items-center justify-between pb-3 mb-3 border-b border-gray-800/60">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-lg bg-gray-800/80" />
                    <div className="h-4 w-28 bg-gray-800/80 rounded" />
                  </div>
                  <div className="h-5 w-8 bg-gray-800/80 rounded-full" />
                </div>
                <div className="space-y-3 flex-1 overflow-hidden">
                  {[1, 2, 3].map(cardIdx => (
                    <div key={cardIdx} className="h-28 bg-gray-900/50 border border-gray-800/40 rounded-xl p-3 space-y-2">
                      <div className="h-3.5 bg-gray-800/80 rounded w-3/4" />
                      <div className="h-2.5 bg-gray-800/60 rounded w-1/2" />
                      <div className="h-2.5 bg-gray-800/40 rounded w-full" />
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : !interestBoardLoading && (interestGroups.length === 0 || totalBoardArticles === 0) ? (
          /* Empty State */
          <div className="h-full flex flex-col items-center justify-center p-6 text-center max-w-md mx-auto">
            {interestGroups.length === 0 ? (
              <>
                <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-4 shadow-inner">
                  <Sparkles size={28} />
                </div>
                <h2 className="text-lg font-semibold text-gray-100 mb-1.5">
                  All caught up!
                </h2>
                <p className="text-sm text-gray-400 mb-6 leading-relaxed">
                  No unread or read later articles to group right now. As new feeds sync or you save articles for read later, Feeda will cluster articles into your dynamic interest board.
                </p>
                <button
                  onClick={() => fetchInterestBoard()}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-gray-800 hover:bg-gray-700 text-gray-200 text-sm font-medium transition-colors border border-gray-700/60 shadow-sm cursor-pointer"
                >
                  <RefreshCw size={15} />
                  <span>Refresh Board</span>
                </button>
              </>
            ) : (
              <>
                <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-4 shadow-inner">
                  <Inbox size={28} />
                </div>
                <h2 className="text-lg font-semibold text-gray-100 mb-1.5">
                  No matching articles
                </h2>
                <p className="text-sm text-gray-400 mb-6 leading-relaxed">
                  No articles match your active likelihood filter or read status across any topic.
                </p>
                <div className="flex flex-wrap items-center justify-center gap-3">
                  {!isAllActive && (
                    <button
                      onClick={handleSelectAll}
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 text-sm font-medium transition-colors border border-blue-500/30 shadow-sm cursor-pointer"
                    >
                      <Sparkles size={15} />
                      <span>Show All Likelihoods</span>
                    </button>
                  )}
                  {!showRead && (
                    <button
                      onClick={toggleShowRead}
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-gray-800 hover:bg-gray-700 text-gray-200 text-sm font-medium transition-colors border border-gray-700/60 shadow-sm cursor-pointer"
                    >
                      <Eye size={15} />
                      <span>Show Read Articles</span>
                    </button>
                  )}
                </div>
              </>
            )}
          </div>
        ) : (
          /* Horizontal Kanban Board */
          <div className="h-full overflow-x-auto overflow-y-hidden px-4 md:px-6 py-4 flex gap-4 md:gap-5 snap-x snap-mandatory md:snap-none scroll-smooth">
            {filteredGroups.map(group => {
              const displayArticles = group.articles;
              const unreadArticles = displayArticles.filter(a => !a.is_read);
              const hasUnread = unreadArticles.length > 0;

              return (
                <div 
                  key={group.slug}
                  className="w-[85vw] sm:w-80 md:w-88 lg:w-96 shrink-0 flex flex-col bg-gray-900/30 border border-gray-800/60 rounded-2xl overflow-hidden snap-center max-h-full shadow-sm"
                >
                  {/* Column Header */}
                  <div className="p-3.5 border-b border-gray-800/60 bg-gray-900/60 backdrop-blur-sm flex items-center justify-between shrink-0">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className="text-xl shrink-0 select-none" role="img" aria-label={group.name}>
                        {group.emoji || '📰'}
                      </span>
                      <div className="min-w-0">
                        <h2 className="text-sm font-semibold text-gray-100 truncate" title={group.name}>
                          {group.name}
                        </h2>
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      <span 
                        className={clsx(
                          "px-2 py-0.5 rounded-full text-xs font-semibold border",
                          hasUnread 
                            ? "bg-indigo-500/15 text-indigo-300 border-indigo-500/30" 
                            : "bg-gray-800/60 text-gray-500 border-gray-700/40"
                        )}
                        title={`${displayArticles.length} articles (${unreadArticles.length} unread)`}
                      >
                        {displayArticles.length}
                      </span>

                      {/* Quick mark column as read */}
                      {hasUnread && (
                        <button
                          onClick={() => markGroupAsRead(displayArticles)}
                          className="p-1 text-gray-500 hover:text-gray-300 hover:bg-gray-800/80 rounded transition-colors cursor-pointer"
                          title="Mark matching articles in topic as read"
                        >
                          <CheckCheck size={14} />
                        </button>
                      )}

                      {/* Scroll column to top */}
                      <button
                        onClick={() => scrollToColumnTop(group.slug)}
                        className="p-1 text-gray-500 hover:text-gray-300 hover:bg-gray-800/80 rounded transition-colors cursor-pointer"
                        title="Scroll to top"
                      >
                        <ArrowUp size={13} />
                      </button>
                    </div>
                  </div>

                  {/* Column Articles List */}
                  <div 
                    ref={el => { columnRefs.current[group.slug] = el; }}
                    className="flex-1 overflow-y-auto p-3 space-y-3 min-h-0"
                  >
                    {displayArticles && displayArticles.length > 0 ? (
                      displayArticles.map(article => (
                        <div 
                          key={article.id}
                          className={clsx(
                            "rounded-xl overflow-hidden border transition-all duration-150 shadow-xs",
                            article.is_read
                              ? "bg-gray-950/40 border-gray-900 opacity-60 hover:opacity-100"
                              : "bg-gray-900/60 hover:bg-gray-900/90 border-gray-800/70 hover:border-gray-700/80"
                          )}
                        >
                          <ArticleCard article={article} viewMode={viewMode} />
                        </div>
                      ))
                    ) : (
                      <div className="py-12 flex flex-col items-center justify-center text-center text-gray-500">
                        <Inbox size={24} className="mb-2 opacity-50" />
                        <span className="text-xs">No matching articles in this topic</span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
