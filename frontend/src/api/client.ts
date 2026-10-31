import type { Article, ArticleBoardsResponse, ArticleListResponse, Board, Feed, Folder, Stats } from '../types';

const API_BASE = '/api';

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`API Error: ${response.statusText}`);
  }

  // Handle empty responses
  if (response.status === 204 || response.headers.get('content-length') === '0') {
    return {} as T;
  }

  return response.json();
}

export const api = {
  // Feeds
  getFeeds: () => fetchApi<{ feeds: Feed[]; folders: Folder[] }>('/feeds'),
  searchFeeds: (query: string) =>
    fetchApi<{ results: any[] }>(`/feeds/search?q=${encodeURIComponent(query)}`),
  getFeedSuggestions: (seed?: number) => {
    const q = seed !== undefined ? `?refresh=${encodeURIComponent(seed.toString())}` : '';
    return fetchApi<{ suggestions: any[]; topics: string[] }>(`/feeds/suggestions${q}`);
  },
  addFeed: (url: string, folderId?: number) =>
    fetchApi<Feed>('/feeds', {
      method: 'POST',
      body: JSON.stringify({ url, folder_id: folderId }),
    }),
  updateFeed: (id: number, data: Partial<Feed>) =>
    fetchApi<Feed>(`/feeds/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  deleteFeed: (id: number) => fetchApi<void>(`/feeds/${id}`, { method: 'DELETE' }),
  refreshFeed: (id: number) => fetchApi<void>(`/feeds/${id}/refresh`, { method: 'POST' }),
  refreshAllFeeds: async () => {
    try {
      return await fetchApi<{ status: string; count?: number }>('/feeds/refresh-all', { method: 'POST' });
    } catch {
      const { feeds } = await api.getFeeds();
      await Promise.allSettled(feeds.map(f => api.refreshFeed(f.id)));
      return { status: 'refreshing', count: feeds.length };
    }
  },

  // Folders
  getFolders: () => fetchApi<Folder[]>('/folders'),
  createFolder: (name: string) =>
    fetchApi<Folder>('/folders', {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),
  updateFolder: (id: number, name: string) =>
    fetchApi<Folder>(`/folders/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    }),
  deleteFolder: (id: number) => fetchApi<void>(`/folders/${id}`, { method: 'DELETE' }),

  // Boards
  getBoards: () => fetchApi<{ boards: Board[] }>('/boards'),
  createBoard: (name: string, description?: string) =>
    fetchApi<Board>('/boards', {
      method: 'POST',
      body: JSON.stringify({ name, description }),
    }),
  updateBoard: (id: number, name?: string, description?: string) =>
    fetchApi<Board>(`/boards/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ name, description }),
    }),
  deleteBoard: (id: number) => fetchApi<void>(`/boards/${id}`, { method: 'DELETE' }),
  getBoardArticles: (boardId: number, sort?: 'date_added' | 'date') => {
    const q = sort ? `?sort=${sort}` : '';
    return fetchApi<ArticleListResponse>(`/boards/${boardId}/articles${q}`);
  },
  saveArticleToBoard: (boardId: number, articleId: number, note?: string) =>
    fetchApi<void>(`/boards/${boardId}/articles`, {
      method: 'POST',
      body: JSON.stringify({ article_id: articleId, note }),
    }),
  removeArticleFromBoard: (boardId: number, articleId: number) =>
    fetchApi<void>(`/boards/${boardId}/articles/${articleId}`, { method: 'DELETE' }),
  updateBoardArticleNote: (boardId: number, articleId: number, note: string) =>
    fetchApi<void>(`/boards/${boardId}/articles/${articleId}/note`, {
      method: 'PUT',
      body: JSON.stringify({ note }),
    }),
  getArticleBoards: (articleId: number) =>
    fetchApi<ArticleBoardsResponse>(`/articles/${articleId}/boards`),

  // Articles
  getArticles: (params: {
    feed_id?: number;
    folder_id?: number;
    is_read?: boolean;
    is_starred?: boolean;
    today?: boolean;
    sort?: 'date' | 'score';
    page?: number;
    limit?: number;
    likelihood?: 'likely' | 'not_likely' | 'all';
  }) => {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        searchParams.append(key, value.toString());
      }
    });
    return fetchApi<ArticleListResponse>(`/articles?${searchParams.toString()}`);
  },
  getForYouArticles: (page?: number, limit?: number, is_read?: boolean | string) => {
    const searchParams = new URLSearchParams();
    if (page !== undefined) searchParams.append('page', page.toString());
    if (limit !== undefined) searchParams.append('limit', limit.toString());
    if (is_read !== undefined) {
      searchParams.append('is_read', is_read.toString());
    } else {
      searchParams.append('is_read', 'all');
    }
    return fetchApi<ArticleListResponse>(`/articles/for-you?${searchParams.toString()}`);
  },
  getArticle: (id: number) => fetchApi<Article>(`/articles/${id}`),
  searchArticles: (query: string) =>
    fetchApi<ArticleListResponse>(`/articles/search?q=${encodeURIComponent(query)}`),

  // Actions
  openArticle: async (id: number) => {
    try {
      return await fetchApi<{ status: string; article_id?: number }>(`/articles/${id}/open`, {
        method: 'POST',
      });
    } catch {
      return await fetchApi<{ status: string; article_id?: number }>(`/articles/${id}/interact`, {
        method: 'POST',
        body: JSON.stringify({ action: 'open_website', dwell_time: 0 }),
      });
    }
  },
  markAsRead: (id: number) => fetchApi<void>(`/articles/${id}/read`, { method: 'POST' }),
  markAsUnread: (id: number) => fetchApi<void>(`/articles/${id}/unread`, { method: 'POST' }),
  toggleStar: (id: number) => fetchApi<void>(`/articles/${id}/star`, { method: 'POST' }),
  voteArticle: (id: number, direction: 1 | 0 | -1) =>
    fetchApi<void>(`/articles/${id}/vote`, {
      method: 'POST',
      body: JSON.stringify({ direction }),
    }),
  logInteraction: (id: number, action: string, dwellTime?: number) =>
    fetchApi<void>(`/articles/${id}/interact`, {
      method: 'POST',
      body: JSON.stringify({ action, dwell_time: dwellTime }),
    }),
  markAllRead: (feedId?: number, folderId?: number, olderThan?: '1d' | '1w' | 'all') => {
    const body: any = {};
    if (feedId) body.feed_id = feedId;
    if (folderId) body.folder_id = folderId;
    if (olderThan) body.older_than = olderThan;
    return fetchApi<void>('/articles/mark-all-read', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  },

  // OPML & System
  importOpml: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(`${API_BASE}/feeds/opml/import`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      let errorMsg = response.statusText;
      try {
        const errorData = await response.json();
        if (errorData.detail) errorMsg = errorData.detail;
      } catch {}
      throw new Error(errorMsg);
    }
    return response.json() as Promise<{ imported_feeds: number; imported_folders: number; skipped_feeds: number }>;
  },
  exportOpmlUrl: () => `${API_BASE}/feeds/opml/export`,
  seedFeeds: () => fetchApi<any>('/feeds/seed', { method: 'POST' }),

  // Stats
  getStats: () => fetchApi<Stats>('/stats'),
  getHealth: () => fetchApi<{ status: string; version: string }>('/health'),
};
