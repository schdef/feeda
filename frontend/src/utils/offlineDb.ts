import type { Article, Feed, Folder } from '../types';

const DB_NAME = 'feeda_offline_db';
const DB_VERSION = 1;

let dbPromise: Promise<IDBDatabase> | null = null;

function getDb(): Promise<IDBDatabase> {
  if (dbPromise) return dbPromise;

  dbPromise = new Promise((resolve, reject) => {
    if (typeof window === 'undefined' || !window.indexedDB) {
      reject(new Error('IndexedDB not available'));
      return;
    }

    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;

      // 1. Articles store
      if (!db.objectStoreNames.contains('articles')) {
        const articleStore = db.createObjectStore('articles', { keyPath: 'id' });
        articleStore.createIndex('feed_id', 'feed_id', { unique: false });
        articleStore.createIndex('is_read', 'is_read', { unique: false });
        articleStore.createIndex('is_starred', 'is_starred', { unique: false });
        articleStore.createIndex('published_at', 'published_at', { unique: false });
      }

      // 2. Feeds store
      if (!db.objectStoreNames.contains('feeds')) {
        db.createObjectStore('feeds', { keyPath: 'id' });
      }

      // 3. Folders store
      if (!db.objectStoreNames.contains('folders')) {
        db.createObjectStore('folders', { keyPath: 'id' });
      }

      // 4. Outbox store for actions taken while offline
      if (!db.objectStoreNames.contains('outbox')) {
        db.createObjectStore('outbox', { keyPath: 'id', autoIncrement: true });
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });

  return dbPromise;
}

// ---------------- Articles ---------------- //

export async function saveArticlesOffline(articles: Article[]): Promise<void> {
  try {
    const db = await getDb();
    const tx = db.transaction('articles', 'readwrite');
    const store = tx.objectStore('articles');

    for (const article of articles) {
      store.put(article);
    }

    return new Promise((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } catch (err) {
    console.warn('[OfflineDB] Error saving articles:', err);
  }
}

export async function getArticlesOffline(options?: {
  feedId?: number | null;
  folderId?: number | null;
  isRead?: boolean;
  isStarred?: boolean;
  limit?: number;
}): Promise<Article[]> {
  try {
    const db = await getDb();
    const tx = db.transaction('articles', 'readonly');
    const store = tx.objectStore('articles');
    const request = store.getAll();

    return new Promise((resolve) => {
      request.onsuccess = () => {
        let results = (request.result as Article[]) || [];

        // Apply filters
        if (options?.feedId) {
          results = results.filter(a => a.feed_id === options.feedId);
        }
        if (options?.isRead !== undefined) {
          results = results.filter(a => a.is_read === options.isRead);
        }
        if (options?.isStarred) {
          results = results.filter(a => a.is_starred);
        }

        // Sort by published_at DESC
        results.sort((a, b) => {
          const dateA = a.published_at ? new Date(a.published_at).getTime() : 0;
          const dateB = b.published_at ? new Date(b.published_at).getTime() : 0;
          return dateB - dateA;
        });

        if (options?.limit) {
          results = results.slice(0, options.limit);
        }

        resolve(results);
      };
      request.onerror = () => resolve([]);
    });
  } catch (err) {
    console.warn('[OfflineDB] Error getting articles:', err);
    return [];
  }
}

export async function updateArticleOffline(id: number, updates: Partial<Article>): Promise<void> {
  try {
    const db = await getDb();
    const tx = db.transaction('articles', 'readwrite');
    const store = tx.objectStore('articles');
    const getReq = store.get(id);

    getReq.onsuccess = () => {
      if (getReq.result) {
        const updated = { ...getReq.result, ...updates };
        store.put(updated);
      }
    };
  } catch (err) {
    console.warn('[OfflineDB] Error updating article:', err);
  }
}

// ---------------- Feeds & Folders ---------------- //

export async function saveFeedsAndFoldersOffline(feeds: Feed[], folders: Folder[]): Promise<void> {
  try {
    const db = await getDb();
    const tx = db.transaction(['feeds', 'folders'], 'readwrite');
    const feedStore = tx.objectStore('feeds');
    const folderStore = tx.objectStore('folders');

    for (const feed of feeds) feedStore.put(feed);
    for (const folder of folders) folderStore.put(folder);
  } catch (err) {
    console.warn('[OfflineDB] Error saving feeds/folders:', err);
  }
}

export async function getFeedsAndFoldersOffline(): Promise<{ feeds: Feed[]; folders: Folder[] }> {
  try {
    const db = await getDb();
    const tx = db.transaction(['feeds', 'folders'], 'readonly');
    const feedStore = tx.objectStore('feeds');
    const folderStore = tx.objectStore('folders');

    const [feedsReq, foldersReq] = [feedStore.getAll(), folderStore.getAll()];

    return new Promise((resolve) => {
      tx.oncomplete = () => {
        resolve({
          feeds: (feedsReq.result as Feed[]) || [],
          folders: (foldersReq.result as Folder[]) || [],
        });
      };
      tx.onerror = () => resolve({ feeds: [], folders: [] });
    });
  } catch {
    return { feeds: [], folders: [] };
  }
}

// ---------------- Outbox (Offline Action Queue) ---------------- //

export interface OutboxItem {
  id?: number;
  action: 'read' | 'unread' | 'star' | 'vote';
  articleId: number;
  payload?: any;
  createdAt: number;
}

export async function queueOfflineAction(action: 'read' | 'unread' | 'star' | 'vote', articleId: number, payload?: any): Promise<void> {
  try {
    const db = await getDb();
    const tx = db.transaction('outbox', 'readwrite');
    const store = tx.objectStore('outbox');
    store.add({
      action,
      articleId,
      payload,
      createdAt: Date.now(),
    });
  } catch (err) {
    console.warn('[OfflineDB] Error queuing action:', err);
  }
}

export async function getOutboxItems(): Promise<OutboxItem[]> {
  try {
    const db = await getDb();
    const tx = db.transaction('outbox', 'readonly');
    const store = tx.objectStore('outbox');
    const req = store.getAll();

    return new Promise((resolve) => {
      req.onsuccess = () => resolve((req.result as OutboxItem[]) || []);
      req.onerror = () => resolve([]);
    });
  } catch {
    return [];
  }
}

export async function removeOutboxItem(id: number): Promise<void> {
  try {
    const db = await getDb();
    const tx = db.transaction('outbox', 'readwrite');
    tx.objectStore('outbox').delete(id);
  } catch (err) {
    console.warn('[OfflineDB] Error deleting outbox item:', err);
  }
}
