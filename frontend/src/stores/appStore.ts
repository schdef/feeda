import { create } from 'zustand';
import { isToday } from 'date-fns';
import { api } from '../api/client';
import type { Article, Board, Feed, FilterView, Folder, LikelihoodFilter, SortMode, Stats, ViewMode } from '../types';
import {
  saveArticlesOffline,
  getArticlesOffline,
  updateArticleOffline,
  saveFeedsAndFoldersOffline,
  getFeedsAndFoldersOffline,
  queueOfflineAction,
  getOutboxItems,
  removeOutboxItem
} from '../utils/offlineDb';

function deduplicateArticles(existing: Article[], incoming: Article[]): Article[] {
  const seenIds = new Set<number>();
  const seenUrls = new Set<string>();
  const seenTitles = new Set<string>();
  const result: Article[] = [];

  const normalizeTitle = (title: string) => {
    return title.toLowerCase().replace(/<[^>]+>/g, '').replace(/\s+[-–—|»/•]\s+.*$/, '').replace(/[^a-z0-9]/g, '').trim();
  };

  const normalizeUrl = (url?: string) => {
    if (!url) return '';
    try {
      const u = new URL(url);
      return `${u.hostname}${u.pathname}`.toLowerCase().replace(/\/+$/, '');
    } catch {
      return url.toLowerCase().trim();
    }
  };

  const addArticle = (a: Article) => {
    if (a.id && seenIds.has(a.id)) return;
    const nUrl = normalizeUrl(a.url);
    if (nUrl && seenUrls.has(nUrl)) return;
    const nTitle = normalizeTitle(a.title || '');
    if (nTitle && nTitle.length > 10 && seenTitles.has(nTitle)) return;

    if (a.id) seenIds.add(a.id);
    if (nUrl) seenUrls.add(nUrl);
    if (nTitle && nTitle.length > 10) seenTitles.add(nTitle);
    result.push(a);
  };

  existing.forEach(addArticle);
  incoming.forEach(addArticle);
  return result;
}

interface AppState {
  feeds: Feed[];
  folders: Folder[];
  articles: Article[];
  selectedArticle: Article | null;
  stats: Stats | null;
  
  viewMode: ViewMode;
  sortMode: SortMode;
  filterView: FilterView;
  likelihoodFilter: LikelihoodFilter;
  selectedFeedId: number | null;
  selectedFolderId: number | null;
  boards: Board[];
  selectedBoardId: number | null;
  saveToBoardModalOpen: boolean;
  targetArticleForBoard: Article | null;
  createBoardModalOpen: boolean;
  editingBoard: Board | null;
  sidebarOpen: boolean;
  addFeedModalOpen: boolean;
  searchQuery: string;
  isLoading: boolean;
  isRefreshing: boolean;
  isOffline: boolean;
  
  selectFolderModalOpen: boolean;
  targetFeedForFolder: Feed | null;
  discoverViewOpen: boolean;
  shortcutsModalOpen: boolean;
  boardSwitcherModalOpen: boolean;

  page: number;
  hasMore: boolean;
  showRead: boolean;

  // Actions
  fetchStats: () => Promise<void>;
  fetchFeeds: () => Promise<void>;
  fetchBoards: () => Promise<void>;
  fetchArticles: (reset?: boolean) => Promise<void>;
  loadMoreArticles: () => Promise<void>;
  selectArticle: (article: Article | null) => void;
  selectFeed: (feedId: number | null) => void;
  selectFolder: (folderId: number | null) => void;
  selectBoard: (boardId: number | null) => void;
  setShowRead: (show: boolean) => void;
  toggleShowRead: () => void;
  setViewMode: (mode: ViewMode) => void;
  setSortMode: (mode: SortMode) => void;
  setFilterView: (view: FilterView) => void;
  setLikelihoodFilter: (filter: LikelihoodFilter) => void;
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
  setAddFeedModalOpen: (open: boolean) => void;
  setSelectFolderModalOpen: (open: boolean, feed?: Feed | null) => void;
  setSaveToBoardModalOpen: (open: boolean, article?: Article | null) => void;
  setCreateBoardModalOpen: (open: boolean, board?: Board | null) => void;
  setShortcutsModalOpen: (open: boolean) => void;
  setBoardSwitcherModalOpen: (open: boolean) => void;
  setDiscoverViewOpen: (open: boolean) => void;
  setSearchQuery: (query: string) => void;
  setOffline: (offline: boolean) => void;
  syncOfflineActions: () => Promise<void>;

  createBoard: (name: string, description?: string) => Promise<Board>;
  updateBoard: (id: number, name: string, description?: string) => Promise<void>;
  deleteBoard: (id: number) => Promise<void>;
  saveArticleToBoard: (boardId: number, articleId: number, note?: string) => Promise<void>;
  removeArticleFromBoard: (boardId: number, articleId: number) => Promise<void>;
  updateBoardArticleNote: (boardId: number, articleId: number, note: string) => Promise<void>;
  
  markArticleRead: (id: number) => Promise<void>;
  markArticleUnread: (id: number) => Promise<void>;
  openArticleWebsite: (id: number, url: string) => Promise<void>;
  toggleArticleStar: (id: number) => Promise<void>;
  voteArticle: (id: number, direction: 1 | 0 | -1) => Promise<void>;
  markAllAsRead: (olderThan?: '1d' | '1w' | 'all') => Promise<void>;
  addFeed: (url: string, folderId?: number) => Promise<void>;
  updateFeedFolder: (feedId: number, folderId: number | null) => Promise<void>;
  createFolder: (name: string) => Promise<Folder>;
  deleteFeed: (id: number) => Promise<void>;
  refreshFeed: (id: number) => Promise<void>;
  refreshAllFeeds: () => Promise<void>;
  navigateArticle: (direction: 'next' | 'prev') => void;
  importOpml: (file: File) => Promise<void>;
  seedFeeds: () => Promise<void>;
}

export const useAppStore = create<AppState>((set, get) => ({
  feeds: [],
  folders: [],
  articles: [],
  selectedArticle: null,
  stats: null,
  
  viewMode: 'magazine',
  sortMode: 'date',
  filterView: 'for-you',
  likelihoodFilter: 'likely',
  selectedFeedId: null,
  selectedFolderId: null,
  boards: [],
  selectedBoardId: null,
  saveToBoardModalOpen: false,
  targetArticleForBoard: null,
  createBoardModalOpen: false,
  editingBoard: null,
  sidebarOpen: false,
  addFeedModalOpen: false,
  selectFolderModalOpen: false,
  targetFeedForFolder: null,
  discoverViewOpen: false,
  shortcutsModalOpen: false,
  boardSwitcherModalOpen: false,
  showRead: false,
  searchQuery: '',
  isLoading: false,
  isRefreshing: false,
  isOffline: typeof navigator !== 'undefined' ? !navigator.onLine : false,
  
  page: 1,
  hasMore: true,

  fetchStats: async () => {
    try {
      const stats = await api.getStats();
      set({ stats });
    } catch (e) {
      console.warn('Failed to fetch stats', e);
    }
  },

  fetchFeeds: async () => {
    // 1. Immediately hydrate from IndexedDB if in-memory list is empty
    const offlineCache = await getFeedsAndFoldersOffline();
    if (offlineCache.feeds.length > 0 && get().feeds.length === 0) {
      set({ feeds: offlineCache.feeds, folders: offlineCache.folders });
    }

    try {
      const [data, stats] = await Promise.all([
        api.getFeeds(),
        api.getStats().catch(() => null)
      ]);
      set({ 
        feeds: data.feeds, 
        folders: data.folders,
        stats: stats || get().stats,
        isOffline: false
      });
      // Save updated data to IndexedDB
      saveFeedsAndFoldersOffline(data.feeds, data.folders);
      // Fetch boards
      get().fetchBoards().catch(console.error);
      // Sync any offline actions pending in outbox
      get().syncOfflineActions();
    } catch (error) {
      console.warn('Network error fetching feeds, using offline cache:', error);
      set({ isOffline: true });
    }
  },

  fetchArticles: async (reset = true) => {
    const state = get();
    set({ isLoading: true });
    
    if (reset) {
      set({ page: 1, articles: [], hasMore: true, selectedArticle: null });
    }

    const currentPage = reset ? 1 : state.page;
    
    try {
      let response;
      if (state.searchQuery) {
        response = await api.searchArticles(state.searchQuery);
      } else if (state.selectedBoardId) {
        response = await api.getBoardArticles(state.selectedBoardId);
      } else if (state.filterView === 'for-you') {
        response = await api.getForYouArticles(currentPage, 20, state.showRead ? undefined : false);
      } else {
        const params: any = {
          page: currentPage,
          limit: 20,
          sort: state.sortMode,
          likelihood: state.likelihoodFilter,
        };
        if (state.selectedFeedId) params.feed_id = state.selectedFeedId;
        if (state.selectedFolderId) params.folder_id = state.selectedFolderId;
        if (state.filterView === 'unread') {
          params.is_read = false;
        } else if (state.filterView === 'today') {
          params.is_read = false;
          params.today = true;
          params.likelihood = 'all';
        } else if (state.filterView !== 'starred') {
          if (!state.showRead) {
            params.is_read = false;
          }
        }
        if (state.filterView === 'starred') params.is_starred = true;
        
        response = await api.getArticles(params);
      }

      set((s) => ({
        articles: deduplicateArticles(reset ? [] : s.articles, response.articles),
        hasMore: response.has_more,
        page: currentPage,
        isLoading: false,
        isOffline: false
      }));

      if (state.filterView === 'for-you' && response.total !== undefined && !state.showRead) {
        set(s => ({ stats: s.stats ? { ...s.stats, for_you_unread_count: response.total } : s.stats }));
      } else if (state.filterView === 'today' && response.total !== undefined) {
        set(s => ({ stats: s.stats ? { ...s.stats, today_unread_count: response.total } : s.stats }));
      } else if (state.filterView === 'unread' && response.total !== undefined) {
        set(s => ({ stats: s.stats ? { ...s.stats, unread_count: response.total } : s.stats }));
      } else if (state.filterView === 'starred' && response.total !== undefined) {
        set(s => ({ stats: s.stats ? { ...s.stats, starred_count: response.total } : s.stats }));
      }

      // Cache articles in IndexedDB for offline reading
      saveArticlesOffline(response.articles);
    } catch (error) {
      console.warn('Network error fetching articles, loading from offline database:', error);
      // Fallback: Query from IndexedDB
      const cached = await getArticlesOffline({
        feedId: state.selectedFeedId,
        isRead: (state.filterView === 'unread' || state.filterView === 'today' || (!state.showRead && state.filterView !== 'starred')) ? false : undefined,
        isStarred: state.filterView === 'starred' ? true : undefined,
        limit: 50
      });

      set((s) => ({
        articles: deduplicateArticles(reset ? [] : s.articles, cached),
        hasMore: false,
        isLoading: false,
        isOffline: true
      }));
    }
  },

  loadMoreArticles: async () => {
    const state = get();
    if (!state.hasMore || state.isLoading) return;
    set({ page: state.page + 1 });
    await get().fetchArticles(false);
  },

  selectArticle: (article) => {
    set({ selectedArticle: article });
    if (article) {
      if (!article.is_read) {
        get().markArticleRead(article.id);
      }
      api.logInteraction(article.id, 'open_article', 0).catch(console.error);
    }
  },

  selectFeed: (feedId) => {
    set({ 
      selectedFeedId: feedId, 
      selectedFolderId: null, 
      selectedBoardId: null,
      filterView: 'all',
      searchQuery: '',
      sidebarOpen: false,
      discoverViewOpen: false,
      articles: [],
      page: 1
    });
    get().fetchArticles(true);
  },

  selectFolder: (folderId) => {
    set({ 
      selectedFolderId: folderId, 
      selectedFeedId: null, 
      selectedBoardId: null,
      filterView: 'all',
      searchQuery: '',
      sidebarOpen: false,
      discoverViewOpen: false,
      articles: [],
      page: 1
    });
    get().fetchArticles(true);
  },

  selectBoard: (boardId) => {
    set({
      selectedBoardId: boardId,
      selectedFeedId: null,
      selectedFolderId: null,
      filterView: 'all',
      searchQuery: '',
      sidebarOpen: false,
      discoverViewOpen: false,
      articles: [],
      page: 1
    });
    get().fetchArticles(true);
  },

  setShowRead: (show) => {
    set({ showRead: show });
    get().fetchArticles(true);
  },

  toggleShowRead: () => {
    set((s) => ({ showRead: !s.showRead }));
    get().fetchArticles(true);
  },

  setViewMode: (mode) => set({ viewMode: mode }),
  setSortMode: (mode) => {
    set({ sortMode: mode });
    get().fetchArticles(true);
  },
  
  setFilterView: (view) => {
    set({ 
      filterView: view, 
      selectedFeedId: null, 
      selectedFolderId: null, 
      selectedBoardId: null,
      searchQuery: '',
      sidebarOpen: false,
      discoverViewOpen: false,
      articles: [],
      page: 1,
      isLoading: false
    });
    get().fetchStats();
    get().fetchArticles(true);
  },

  setLikelihoodFilter: (filter) => {
    set({ likelihoodFilter: filter });
    get().fetchArticles(true);
  },

  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setAddFeedModalOpen: (open) => set({ addFeedModalOpen: open }),
  setSelectFolderModalOpen: (open, feed) => set({ selectFolderModalOpen: open, targetFeedForFolder: feed || null }),
  setSaveToBoardModalOpen: (open, article) => set({ saveToBoardModalOpen: open, targetArticleForBoard: article || null }),
  setCreateBoardModalOpen: (open, board) => set({ createBoardModalOpen: open, editingBoard: board || null }),
  setShortcutsModalOpen: (open) => set({ shortcutsModalOpen: open }),
  setBoardSwitcherModalOpen: (open) => set({ boardSwitcherModalOpen: open }),
  setDiscoverViewOpen: (open) => {
    set({ discoverViewOpen: open });
    if (open) {
      set({ 
        selectedFeedId: null, 
        selectedFolderId: null, 
        selectedBoardId: null,
        filterView: 'all',
        sidebarOpen: false,
        searchQuery: ''
      });
    }
  },
  
  setSearchQuery: (query) => {
    set({ searchQuery: query });
    if (query) {
      get().fetchArticles(true);
    }
  },

  setOffline: (offline: boolean) => set({ isOffline: offline }),

  syncOfflineActions: async () => {
    const items = await getOutboxItems();
    if (!items || items.length === 0) return;

    for (const item of items) {
      try {
        if (item.action === 'read') {
          await api.markAsRead(item.articleId);
        } else if (item.action === 'unread') {
          await api.markAsUnread(item.articleId);
        } else if (item.action === 'star') {
          await api.toggleStar(item.articleId);
        } else if (item.action === 'vote') {
          await api.voteArticle(item.articleId, item.payload?.direction ?? 1);
        }
        if (item.id) await removeOutboxItem(item.id);
      } catch (err) {
        console.warn('[Sync] Still offline, stopping outbox sync:', err);
        break;
      }
    }
  },

  markArticleRead: async (id) => {
    const state = get();
    const article = state.articles.find(a => a.id === id);
    if (article && article.is_read) {
      return;
    }
    const wasUnread = article ? !article.is_read : true;
    const isArticleToday = article?.published_at 
      ? (isToday(new Date(article.published_at)) || (Date.now() - new Date(article.published_at).getTime()) <= 24 * 3600 * 1000)
      : false;
    const isArticleForYou = article ? (article.likelihood_tier === 'high') : false;

    // 1. Optimistic update in UI store
    set((s) => {
      const feedId = article?.feed_id;
      const feed = feedId ? s.feeds.find(f => f.id === feedId) : null;
      const folderId = feed?.folder_id;

      return {
        articles: s.articles.map(a => a.id === id ? { ...a, is_read: true } : a),
        selectedArticle: s.selectedArticle?.id === id ? { ...s.selectedArticle, is_read: true } : s.selectedArticle,
        stats: wasUnread && s.stats ? {
          ...s.stats,
          unread_count: Math.max(0, s.stats.unread_count - 1),
          today_unread_count: isArticleToday && s.stats.today_unread_count !== undefined
            ? Math.max(0, s.stats.today_unread_count - 1)
            : s.stats.today_unread_count,
          for_you_unread_count: isArticleForYou && s.stats.for_you_unread_count !== undefined
            ? Math.max(0, s.stats.for_you_unread_count - 1)
            : s.stats.for_you_unread_count
        } : s.stats,
        feeds: wasUnread && feedId ? s.feeds.map(f => f.id === feedId ? {
          ...f,
          unread_count: Math.max(0, f.unread_count - 1)
        } : f) : s.feeds,
        folders: wasUnread && folderId ? s.folders.map(fol => fol.id === folderId ? {
          ...fol,
          unread_count: Math.max(0, fol.unread_count - 1)
        } : fol) : s.folders
      };
    });

    // 2. Persist immediately to IndexedDB
    updateArticleOffline(id, { is_read: true });

    // 3. Send to API or queue if offline
    try {
      await api.markAsRead(id);
    } catch (error) {
      console.warn('[Offline] Queuing mark-read action for article', id);
      queueOfflineAction('read', id);
      set({ isOffline: true });
    }
  },

  markArticleUnread: async (id) => {
    const state = get();
    const article = state.articles.find(a => a.id === id);
    if (article && !article.is_read) {
      return;
    }
    const wasRead = article ? article.is_read : false;
    const isArticleToday = article?.published_at 
      ? (isToday(new Date(article.published_at)) || (Date.now() - new Date(article.published_at).getTime()) <= 24 * 3600 * 1000)
      : false;
    const isArticleForYou = article ? (article.likelihood_tier === 'high') : false;

    // 1. Optimistic update
    set((s) => {
      const feedId = article?.feed_id;
      const feed = feedId ? s.feeds.find(f => f.id === feedId) : null;
      const folderId = feed?.folder_id;

      return {
        articles: s.articles.map(a => a.id === id ? { ...a, is_read: false } : a),
        selectedArticle: s.selectedArticle?.id === id ? { ...s.selectedArticle, is_read: false } : s.selectedArticle,
        stats: wasRead && s.stats ? {
          ...s.stats,
          unread_count: s.stats.unread_count + 1,
          today_unread_count: isArticleToday && s.stats.today_unread_count !== undefined
            ? s.stats.today_unread_count + 1
            : s.stats.today_unread_count,
          for_you_unread_count: isArticleForYou && s.stats.for_you_unread_count !== undefined
            ? s.stats.for_you_unread_count + 1
            : s.stats.for_you_unread_count
        } : s.stats,
        feeds: wasRead && feedId ? s.feeds.map(f => f.id === feedId ? {
          ...f,
          unread_count: f.unread_count + 1
        } : f) : s.feeds,
        folders: wasRead && folderId ? s.folders.map(fol => fol.id === folderId ? {
          ...fol,
          unread_count: fol.unread_count + 1
        } : fol) : s.folders
      };
    });

    // 2. Persist to IndexedDB
    updateArticleOffline(id, { is_read: false });

    // 3. Send to API or queue
    try {
      await api.markAsUnread(id);
    } catch (error) {
      console.warn('[Offline] Queuing mark-unread action for article', id);
      queueOfflineAction('unread', id);
      set({ isOffline: true });
    }
  },

  openArticleWebsite: async (id, url) => {
    if (typeof window !== 'undefined' && url) {
      window.open(url, '_blank', 'noopener,noreferrer');
    }
    await get().markArticleRead(id);
    try {
      await api.openArticle(id);
    } catch (error) {
      console.warn('Failed to report openArticle to backend:', error);
    }
  },

  toggleArticleStar: async (id) => {
    let nextStarred = false;
    set((s) => {
      const article = s.articles.find(a => a.id === id) || (s.selectedArticle?.id === id ? s.selectedArticle : null);
      nextStarred = article ? !article.is_starred : false;
      return {
        articles: s.filterView === 'starred' && !nextStarred 
          ? s.articles.filter(a => a.id !== id) 
          : s.articles.map(a => a.id === id ? { ...a, is_starred: nextStarred } : a),
        selectedArticle: s.selectedArticle?.id === id ? { ...s.selectedArticle, is_starred: nextStarred } : s.selectedArticle,
        stats: s.stats ? {
          ...s.stats,
          starred_count: nextStarred 
            ? (s.stats.starred_count || 0) + 1 
            : Math.max(0, (s.stats.starred_count || 1) - 1)
        } : s.stats,
      };
    });

    updateArticleOffline(id, { is_starred: nextStarred });

    try {
      await api.toggleStar(id);
    } catch (error) {
      console.warn('[Offline] Queuing toggle-star action for article', id);
      queueOfflineAction('star', id);
      set({ isOffline: true });
    }
  },

  voteArticle: async (id, direction) => {
    set((s) => ({
      articles: s.articles.map(a => a.id === id ? { ...a, user_vote: direction } : a),
      selectedArticle: s.selectedArticle?.id === id ? { ...s.selectedArticle, user_vote: direction } : s.selectedArticle
    }));

    updateArticleOffline(id, { user_vote: direction });

    try {
      await api.voteArticle(id, direction);
    } catch (error) {
      console.warn('[Offline] Queuing vote action for article', id);
      queueOfflineAction('vote', id, { direction });
      set({ isOffline: true });
    }
  },

  markAllAsRead: async (olderThan?: '1d' | '1w' | 'all') => {
    const { selectedFeedId, selectedFolderId } = get();
    try {
      await api.markAllRead(selectedFeedId || undefined, selectedFolderId || undefined, olderThan);
      
      const now = Date.now();
      const oneDayAgo = now - 24 * 60 * 60 * 1000;
      const oneWeekAgo = now - 7 * 24 * 60 * 60 * 1000;

      set((s) => ({
        articles: s.articles.map(a => {
          if (!a.published_at) return { ...a, is_read: true };
          const pubTime = new Date(a.published_at).getTime();
          if (olderThan === '1d' && pubTime < oneDayAgo) return { ...a, is_read: true };
          if (olderThan === '1w' && pubTime < oneWeekAgo) return { ...a, is_read: true };
          if (!olderThan || olderThan === 'all') return { ...a, is_read: true };
          return a;
        }),
        selectedArticle: s.selectedArticle ? {
          ...s.selectedArticle,
          is_read: (() => {
            if (!olderThan || olderThan === 'all') return true;
            if (!s.selectedArticle.published_at) return true;
            const pubTime = new Date(s.selectedArticle.published_at).getTime();
            if (olderThan === '1d' && pubTime < oneDayAgo) return true;
            if (olderThan === '1w' && pubTime < oneWeekAgo) return true;
            return s.selectedArticle.is_read;
          })()
        } : null
      }));
      await Promise.all([get().fetchFeeds(), get().fetchArticles(true), get().fetchStats()]);
    } catch (error) {
      console.error('Failed to mark all as read:', error);
    }
  },

  addFeed: async (url, folderId) => {
    try {
      await api.addFeed(url, folderId);
      await get().fetchFeeds();
      set({ addFeedModalOpen: false });
    } catch (error) {
      console.error('Failed to add feed:', error);
      throw error;
    }
  },

  updateFeedFolder: async (feedId, folderId) => {
    // Optimistic update
    set((s) => {
      const newFeeds = s.feeds.map(f => f.id === feedId ? { ...f, folder_id: folderId } : f);
      return { 
        feeds: newFeeds,
        targetFeedForFolder: s.targetFeedForFolder?.id === feedId 
          ? { ...s.targetFeedForFolder, folder_id: folderId } 
          : s.targetFeedForFolder
      };
    });
    
    try {
      await api.updateFeed(feedId, { folder_id: folderId });
      await get().fetchFeeds();
    } catch (error) {
      console.error('Failed to update feed folder:', error);
      await get().fetchFeeds();
      throw error;
    }
  },

  createFolder: async (name) => {
    try {
      const folder = await api.createFolder(name);
      await get().fetchFeeds();
      return folder;
    } catch (error) {
      console.error('Failed to create folder:', error);
      throw error;
    }
  },

  deleteFeed: async (id) => {
    try {
      await api.deleteFeed(id);
      await get().fetchFeeds();
    } catch (error) {
      console.error('Failed to delete feed:', error);
    }
  },

  refreshFeed: async (id) => {
    try {
      await api.refreshFeed(id);
      await Promise.all([get().fetchArticles(true), get().fetchStats()]);
    } catch (error) {
      console.error('Failed to refresh feed:', error);
    }
  },

  refreshAllFeeds: async () => {
    set({ isRefreshing: true });
    try {
      await api.refreshAllFeeds();
      await new Promise(r => setTimeout(r, 600));
      await Promise.all([get().fetchFeeds(), get().fetchArticles(true), get().fetchStats()]);
    } catch (error) {
      console.error('Failed to refresh feeds:', error);
    } finally {
      set({ isRefreshing: false });
    }
  },

  navigateArticle: (direction) => {
    const { articles, selectedArticle } = get();
    if (articles.length === 0) return;

    if (!selectedArticle) {
      get().selectArticle(articles[0]);
      return;
    }

    const currentIndex = articles.findIndex(a => a.id === selectedArticle.id);
    if (currentIndex === -1) return;

    if (direction === 'next' && currentIndex < articles.length - 1) {
      get().selectArticle(articles[currentIndex + 1]);
    } else if (direction === 'prev' && currentIndex > 0) {
      get().selectArticle(articles[currentIndex - 1]);
    }
  },

  importOpml: async (file) => {
    try {
      await api.importOpml(file);
      await get().fetchFeeds();
      await get().fetchArticles(true);
      set({ addFeedModalOpen: false });
    } catch (error) {
      console.error('Failed to import OPML:', error);
      throw error;
    }
  },

  seedFeeds: async () => {
    try {
      await api.seedFeeds();
      await get().fetchFeeds();
      await get().fetchArticles(true);
      set({ addFeedModalOpen: false });
    } catch (error) {
      console.error('Failed to seed feeds:', error);
      throw error;
    }
  },

  fetchBoards: async () => {
    try {
      const data = await api.getBoards();
      const boardsList = Array.isArray(data) ? data : (data.boards || []);
      set({ boards: boardsList });
    } catch (error) {
      console.warn('Failed to fetch boards:', error);
    }
  },

  createBoard: async (name, description) => {
    const newBoard = await api.createBoard(name, description);
    set((s) => ({ boards: [...s.boards, newBoard] }));
    return newBoard;
  },

  updateBoard: async (id, name, description) => {
    const updated = await api.updateBoard(id, name, description);
    set((s) => ({
      boards: s.boards.map(b => b.id === id ? { ...b, ...updated } : b),
    }));
  },

  deleteBoard: async (id) => {
    await api.deleteBoard(id);
    const wasSelected = get().selectedBoardId === id;
    set((s) => ({
      boards: s.boards.filter(b => b.id !== id),
      selectedBoardId: s.selectedBoardId === id ? null : s.selectedBoardId,
    }));
    if (wasSelected) {
      get().setFilterView('all');
    }
  },

  saveArticleToBoard: async (boardId, articleId, note) => {
    await api.saveArticleToBoard(boardId, articleId, note);
    set((s) => ({
      boards: s.boards.map(b => b.id === boardId ? { ...b, article_count: b.article_count + 1 } : b),
    }));
    if (get().selectedBoardId === boardId) {
      get().fetchArticles(false);
    }
  },

  removeArticleFromBoard: async (boardId, articleId) => {
    await api.removeArticleFromBoard(boardId, articleId);
    set((s) => ({
      boards: s.boards.map(b => b.id === boardId ? { ...b, article_count: Math.max(0, b.article_count - 1) } : b),
      articles: s.selectedBoardId === boardId ? s.articles.filter(a => a.id !== articleId) : s.articles,
      selectedArticle: s.selectedArticle?.id === articleId && s.selectedBoardId === boardId ? null : s.selectedArticle,
    }));
  },

  updateBoardArticleNote: async (boardId, articleId, note) => {
    await api.updateBoardArticleNote(boardId, articleId, note);
    set((s) => ({
      articles: s.articles.map(a => a.id === articleId ? { ...a, board_note: note } : a),
      selectedArticle: s.selectedArticle?.id === articleId ? { ...s.selectedArticle, board_note: note } : s.selectedArticle,
    }));
  }
}));
