import React, { useState, useEffect, useCallback } from 'react';
import { ArrowLeft, X, Plus, Rss, Sparkles, RefreshCw, Check, Search, Loader2 } from 'lucide-react';
import { useAppStore } from '../stores/appStore';
import { api } from '../api/client';

const DEFAULT_TOPICS = ['tech', 'coding', 'ai', 'news', 'design'];

const DEFAULT_SUGGESTIONS = [
  {
    title: 'Hacker News',
    url: 'https://news.ycombinator.com/rss',
    site: 'news.ycombinator.com',
    description: 'News, discussion and discoveries for hackers and developers.',
    reason: 'Popular tech community',
  },
  {
    title: 'The Verge',
    url: 'https://www.theverge.com/rss/index.xml',
    site: 'theverge.com',
    description: 'Technology, science, art, and culture.',
    reason: 'Trending in Tech',
  },
  {
    title: 'TechCrunch',
    url: 'https://techcrunch.com/feed/',
    site: 'techcrunch.com',
    description: 'Startup and technology news.',
    reason: 'Venture & Startups',
  },
  {
    title: 'Ars Technica',
    url: 'https://feeds.arstechnica.com/arstechnica/index',
    site: 'arstechnica.com',
    description: 'In-depth technology and science journalism.',
    reason: 'Deep tech & hardware',
  },
  {
    title: 'Product Hunt',
    url: 'https://www.producthunt.com/feed',
    site: 'producthunt.com',
    description: 'The best new products in tech.',
    reason: 'New apps & tools',
  },
  {
    title: 'GitHub Blog',
    url: 'https://github.blog/feed/',
    site: 'github.blog',
    description: 'Updates and stories from the GitHub team.',
    reason: 'Developer tools',
  },
];

export function DiscoverView() {
  const { setDiscoverViewOpen, setSelectFolderModalOpen, addFeed, feeds } = useAppStore();

  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [suggestionTopics, setSuggestionTopics] = useState<string[]>([]);
  const [isLoadingSuggestions, setIsLoadingSuggestions] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [refreshCount, setRefreshCount] = useState(0);
  const [addingUrl, setAddingUrl] = useState<string | null>(null);
  const [imgErrors, setImgErrors] = useState<Record<string, boolean>>({});

  const fetchSuggestions = useCallback(async (seed?: number) => {
    setIsLoadingSuggestions(true);
    try {
      const res = await api.getFeedSuggestions(seed);
      if (res && res.suggestions && res.suggestions.length > 0) {
        setSuggestions(res.suggestions);
      } else if (seed === undefined) {
        setSuggestions(DEFAULT_SUGGESTIONS);
      }
      if (res && res.topics && res.topics.length > 0) {
        setSuggestionTopics(res.topics);
      }
    } catch (err) {
      console.error('Failed to load feed suggestions:', err);
      setSuggestions(prev => (prev.length === 0 ? DEFAULT_SUGGESTIONS : prev));
    } finally {
      setIsLoadingSuggestions(false);
    }
  }, []);

  useEffect(() => {
    fetchSuggestions();
  }, [fetchSuggestions]);

  const handleBack = () => {
    setDiscoverViewOpen(false);
  };

  const handleQueryChange = (val: string) => {
    setSearchQuery(val);
    if (!val.trim()) {
      setSearchResults([]);
    }
  };

  const handleClearQuery = () => {
    setSearchQuery('');
    setSearchResults([]);
  };

  const executeSearch = async (term: string) => {
    const q = term.trim();
    if (!q) {
      setSearchResults([]);
      return;
    }

    setIsSearching(true);
    try {
      const res = await api.searchFeeds(q);
      setSearchResults(res && res.results ? res.results : []);
    } catch (err) {
      console.error('Failed to search feeds:', err);
      if (q.startsWith('http://') || q.startsWith('https://')) {
        try {
          const urlObj = new URL(q);
          setSearchResults([
            {
              title: urlObj.hostname,
              url: q,
              site: urlObj.hostname,
              description: 'Custom RSS Feed URL',
            },
          ]);
        } catch {
          setSearchResults([]);
        }
      } else {
        setSearchResults([]);
      }
    } finally {
      setIsSearching(false);
    }
  };

  const handleSearchSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    executeSearch(searchQuery);
  };

  const handleTopicClick = (topic: string) => {
    const cleaned = topic.replace(/^#\s*/, '');
    setSearchQuery(cleaned);
    executeSearch(cleaned);
  };

  const handleRefreshSuggestions = () => {
    const nextCount = refreshCount + 1;
    setRefreshCount(nextCount);
    fetchSuggestions(nextCount);
  };

  const isSubscribed = (url?: string) => {
    if (!url) return false;
    const cleanUrl = url.trim().toLowerCase().replace(/\/$/, '');
    return feeds.some(
      f => (f.url || '').trim().toLowerCase().replace(/\/$/, '') === cleanUrl
    );
  };

  const handleAddFeed = async (feedItem: any) => {
    const feedUrl = feedItem.url || feedItem.feed_url;
    if (!feedUrl) return;

    const normalizedFeedUrl = feedUrl.trim().toLowerCase().replace(/\/$/, '');
    let existingFeed = feeds.find(
      f => (f.url || '').trim().toLowerCase().replace(/\/$/, '') === normalizedFeedUrl
    );

    if (!existingFeed) {
      setAddingUrl(feedUrl);
      try {
        await addFeed(feedUrl);
        existingFeed = useAppStore
          .getState()
          .feeds.find(
            f => (f.url || '').trim().toLowerCase().replace(/\/$/, '') === normalizedFeedUrl
          );
      } catch (err) {
        console.error('Failed to add feed:', err);
      } finally {
        setAddingUrl(null);
      }
    }

    if (existingFeed) {
      setSelectFolderModalOpen(true, existingFeed);
    }
  };

  const formatSubscribers = (count?: number | null) => {
    if (count === undefined || count === null) return null;
    if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M subscribers`;
    if (count >= 1000) return `${(count / 1000).toFixed(1)}k subscribers`;
    return `${count} subscribers`;
  };

  const displayTopics = suggestionTopics.length > 0 ? suggestionTopics : DEFAULT_TOPICS;
  const isSearchActive = searchQuery.trim().length > 0;

  return (
    <div className="flex flex-col h-full bg-gray-950 text-gray-200">
      {/* Header / Search Bar */}
      <div className="pt-4 pb-2 px-3 flex items-center gap-3 border-b border-gray-900 bg-gray-950/90 backdrop-blur-md sticky top-0 z-10 shrink-0">
        <button
          onClick={handleBack}
          className="p-2 text-gray-400 hover:text-gray-100 transition-colors shrink-0"
          title="Go back"
        >
          <ArrowLeft size={22} />
        </button>

        <form onSubmit={handleSearchSubmit} className="flex-1 relative flex items-center">
          <Search size={16} className="absolute left-3.5 text-gray-400 pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={e => handleQueryChange(e.target.value)}
            placeholder="Search by topic, website or RSS link"
            className="w-full bg-gray-800/80 border border-gray-700/50 rounded-full py-2 pl-9 pr-10 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-gray-600 focus:bg-gray-800 transition-colors"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={handleClearQuery}
              className="absolute right-3 text-gray-400 hover:text-gray-200 p-1"
              title="Clear search"
            >
              <X size={15} />
            </button>
          )}
        </form>
      </div>

      {/* Topic Pills */}
      <div className="flex items-center gap-2 px-4 py-2.5 overflow-x-auto no-scrollbar border-b border-gray-800/60 bg-gray-950/60 shrink-0">
        {displayTopics.map((topic, idx) => {
          const topicLabel = topic.startsWith('#') ? topic : `#${topic}`;
          return (
            <button
              key={idx}
              onClick={() => handleTopicClick(topic)}
              className="whitespace-nowrap px-3 py-1 rounded-full border border-gray-800 bg-gray-900/80 text-gray-300 text-xs font-medium hover:bg-gray-800 hover:border-gray-700 transition-colors"
            >
              {topicLabel}
            </button>
          );
        })}
      </div>

      <div className="flex-1 overflow-y-auto">
        {isSearchActive ? (
          /* Search Results Section */
          <div>
            <div className="px-4 pt-4 pb-2 flex items-center justify-between">
              <h3 className="text-blue-400 font-semibold text-sm">
                Search Results {isSearching ? '(Searching...)' : `(${searchResults.length})`}
              </h3>
              {isSearching && <Loader2 size={16} className="animate-spin text-blue-400" />}
            </div>

            <div className="flex flex-col divide-y divide-gray-900/60">
              {searchResults.map((feed, idx) => {
                const feedUrl = feed.url || feed.feed_url || '';
                const site = feed.site || feed.site_url || feed.website || '';
                const icon = feed.favicon_url || feed.icon_url || feed.image_url;
                const subscribers = formatSubscribers(feed.subscribers ?? feed.subscriber_count);
                const subscribed = isSubscribed(feedUrl);
                const isAdding = addingUrl === feedUrl;

                return (
                  <div
                    key={idx}
                    className="flex items-start gap-3.5 px-4 py-3 hover:bg-gray-900/40 transition-colors"
                  >
                    <div className="w-10 h-10 rounded-lg bg-gray-900 border border-gray-800 flex items-center justify-center overflow-hidden shrink-0 mt-0.5">
                      {icon && !imgErrors[feedUrl] ? (
                        <img
                          src={icon}
                          alt=""
                          className="w-6 h-6 object-contain"
                          onError={() => setImgErrors(prev => ({ ...prev, [feedUrl]: true }))}
                        />
                      ) : (
                        <Rss size={18} className="text-gray-400" />
                      )}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-gray-200 text-sm truncate">
                          {feed.title || feedUrl}
                        </span>
                      </div>

                      {site && <div className="text-xs text-gray-500 truncate mt-0.5">{site}</div>}

                      {feed.description && (
                        <div className="text-xs text-gray-400 line-clamp-2 mt-1">
                          {feed.description}
                        </div>
                      )}

                      {subscribers && (
                        <div className="text-[11px] text-gray-500 mt-1 font-medium">
                          {subscribers}
                        </div>
                      )}
                    </div>

                    <div className="shrink-0 pt-1">
                      {subscribed ? (
                        <button
                          onClick={() => handleAddFeed(feed)}
                          className="p-1.5 rounded-full bg-emerald-950/30 border border-emerald-800/40 text-emerald-400 hover:bg-emerald-900/40 transition-colors"
                          title="Subscribed (click to organize folder)"
                        >
                          <Check size={16} />
                        </button>
                      ) : (
                        <button
                          onClick={() => handleAddFeed(feed)}
                          disabled={isAdding}
                          className="p-1.5 rounded-full bg-gray-900 border border-gray-800 text-gray-300 hover:text-gray-100 hover:border-gray-700 transition-colors disabled:opacity-50"
                          title="Add feed"
                        >
                          {isAdding ? (
                            <Loader2 size={16} className="animate-spin text-blue-400" />
                          ) : (
                            <Plus size={16} />
                          )}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}

              {!isSearching && searchResults.length === 0 && (
                <div className="px-4 py-12 text-center text-gray-500 text-sm">
                  <p>No feeds found for "{searchQuery}".</p>
                  <p className="mt-1 text-xs text-gray-600">
                    Try searching for another topic or paste a direct RSS feed URL.
                  </p>
                </div>
              )}
            </div>
          </div>
        ) : (
          /* Profile-Based Suggestions View */
          <div>
            {/* Suggested for you header card with profile topics & refresh button */}
            <div className="px-4 py-3 bg-gradient-to-r from-blue-950/25 via-gray-900/30 to-transparent border-b border-gray-800/60">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Sparkles size={16} className="text-blue-400" />
                  <h3 className="text-sm font-semibold text-gray-200">Suggested for you</h3>
                </div>
                <button
                  onClick={handleRefreshSuggestions}
                  disabled={isLoadingSuggestions}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium text-gray-300 hover:text-gray-100 bg-gray-900 border border-gray-800 hover:border-gray-700 transition-colors disabled:opacity-50"
                  title="Refresh suggestions"
                >
                  <RefreshCw
                    size={13}
                    className={isLoadingSuggestions ? 'animate-spin text-blue-400' : 'text-gray-400'}
                  />
                  <span>Refresh suggestions</span>
                </button>
              </div>

              {suggestionTopics.length > 0 && (
                <div className="mt-2.5 text-xs text-gray-400 flex items-center flex-wrap gap-1.5">
                  <span className="text-gray-500">Based on your profile:</span>
                  {suggestionTopics.map((topic, idx) => {
                    const tag = topic.startsWith('#') ? topic : `#${topic}`;
                    return (
                      <button
                        key={idx}
                        onClick={() => handleTopicClick(topic)}
                        className="text-blue-400 hover:text-blue-300 bg-blue-950/40 border border-blue-800/40 px-2 py-0.5 rounded-full font-medium transition-colors"
                      >
                        {tag}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Suggestions list */}
            <div className="flex flex-col divide-y divide-gray-900/60">
              {suggestions.map((feed, idx) => {
                const feedUrl = feed.url || feed.feed_url || '';
                const site = feed.site || feed.site_url || feed.website || '';
                const icon = feed.favicon_url || feed.icon_url || feed.image_url;
                const reason = feed.reason || feed.reason_tag;
                const subscribed = isSubscribed(feedUrl);
                const isAdding = addingUrl === feedUrl;

                return (
                  <div
                    key={idx}
                    className="flex items-start gap-3.5 px-4 py-3 hover:bg-gray-900/40 transition-colors"
                  >
                    <div className="w-10 h-10 rounded-lg bg-gray-900 border border-gray-800 flex items-center justify-center overflow-hidden shrink-0 mt-0.5">
                      {icon && !imgErrors[feedUrl] ? (
                        <img
                          src={icon}
                          alt=""
                          className="w-6 h-6 object-contain"
                          onError={() => setImgErrors(prev => ({ ...prev, [feedUrl]: true }))}
                        />
                      ) : (
                        <Rss size={18} className="text-gray-400" />
                      )}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-gray-200 text-sm truncate">
                          {feed.title || feedUrl}
                        </span>
                      </div>

                      {site && <div className="text-xs text-gray-500 truncate mt-0.5">{site}</div>}

                      {feed.description && (
                        <div className="text-xs text-gray-400 line-clamp-2 mt-1">
                          {feed.description}
                        </div>
                      )}

                      {reason && (
                        <div className="mt-1.5 flex items-center gap-1">
                          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-blue-400 bg-blue-950/40 border border-blue-900/40 px-2 py-0.5 rounded">
                            <Sparkles size={10} className="shrink-0" />
                            <span className="truncate">{reason}</span>
                          </span>
                        </div>
                      )}
                    </div>

                    <div className="shrink-0 pt-1">
                      {subscribed ? (
                        <button
                          onClick={() => handleAddFeed(feed)}
                          className="p-1.5 rounded-full bg-emerald-950/30 border border-emerald-800/40 text-emerald-400 hover:bg-emerald-900/40 transition-colors"
                          title="Subscribed (click to organize folder)"
                        >
                          <Check size={16} />
                        </button>
                      ) : (
                        <button
                          onClick={() => handleAddFeed(feed)}
                          disabled={isAdding}
                          className="p-1.5 rounded-full bg-gray-900 border border-gray-800 text-gray-300 hover:text-gray-100 hover:border-gray-700 transition-colors disabled:opacity-50"
                          title="Add feed"
                        >
                          {isAdding ? (
                            <Loader2 size={16} className="animate-spin text-blue-400" />
                          ) : (
                            <Plus size={16} />
                          )}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}

              {!isLoadingSuggestions && suggestions.length === 0 && (
                <div className="px-4 py-12 text-center text-gray-500 text-sm">
                  No suggestions available right now.
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
