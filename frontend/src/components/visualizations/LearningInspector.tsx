import { useState, useMemo } from 'react';
import { 
  BrainCircuit, 
  Search, 
  Star, 
  FolderPlus, 
  Clock, 
  ThumbsUp, 
  ThumbsDown, 
  SkipForward, 
  ExternalLink, 
  Rss, 
  Activity, 
  Sparkles, 
  TrendingUp, 
  TrendingDown,
  Info,
  RefreshCw
} from 'lucide-react';
import type { 
  LearningInspectorResponse, 
  FeedAffinityItem, 
  LearningEventItem 
} from '../../types';

interface LearningInspectorProps {
  data: LearningInspectorResponse | null;
  loading: boolean;
  onRefresh?: () => void;
}

function safeFloat(val: number | string | undefined | null, fallback = 0): number {
  if (val === undefined || val === null) return fallback;
  const n = typeof val === 'number' ? val : parseFloat(val);
  return isNaN(n) ? fallback : n;
}

export function LearningInspector({ data, loading, onRefresh }: LearningInspectorProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [activeTab, setActiveTab] = useState<'vocabulary' | 'affinities' | 'events'>('vocabulary');

  // Filter positive and negative terms based on search term
  const filteredPositiveTerms = useMemo(() => {
    if (!data?.top_positive_terms) return [];
    if (!searchTerm.trim()) return data.top_positive_terms;
    const q = searchTerm.toLowerCase().trim();
    return data.top_positive_terms.filter((t) => t.term.toLowerCase().includes(q));
  }, [data?.top_positive_terms, searchTerm]);

  const filteredNegativeTerms = useMemo(() => {
    if (!data?.top_negative_terms) return [];
    if (!searchTerm.trim()) return data.top_negative_terms;
    const q = searchTerm.toLowerCase().trim();
    return data.top_negative_terms.filter((t) => t.term.toLowerCase().includes(q));
  }, [data?.top_negative_terms, searchTerm]);

  const maxPositiveScore = useMemo(() => {
    if (!data?.top_positive_terms || data.top_positive_terms.length === 0) return 10;
    return Math.max(...data.top_positive_terms.map((t) => safeFloat(t.net_score, 1)));
  }, [data?.top_positive_terms]);

  const maxNegativeScore = useMemo(() => {
    if (!data?.top_negative_terms || data.top_negative_terms.length === 0) return 10;
    return Math.max(...data.top_negative_terms.map((t) => Math.abs(safeFloat(t.net_score, 1))));
  }, [data?.top_negative_terms]);

  // Standard action weights mapping with human explanations & icons
  const actionDetails = [
    {
      key: 'save_to_board',
      title: 'Save to Board',
      weight: data?.action_weights?.['save_to_board'] ?? 4.0,
      description: 'Intentional curation & deep topic interest',
      icon: <FolderPlus size={16} className="text-violet-400" />,
      badgeClass: 'bg-violet-950/60 text-violet-300 border-violet-800/60',
      positive: true,
    },
    {
      key: 'star',
      title: 'Star Article',
      weight: data?.action_weights?.['star'] ?? 3.5,
      description: 'Saved for reading later or bookmarking',
      icon: <Star size={16} className="text-amber-400" />,
      badgeClass: 'bg-amber-950/60 text-amber-300 border-amber-800/60',
      positive: true,
    },
    {
      key: 'open_website',
      title: 'Open External URL',
      weight: data?.action_weights?.['open_website'] ?? 3.0,
      description: 'Navigated to primary publisher source',
      icon: <ExternalLink size={16} className="text-blue-400" />,
      badgeClass: 'bg-blue-950/60 text-blue-300 border-blue-800/60',
      positive: true,
    },
    {
      key: 'vote_up',
      title: 'Upvote',
      weight: data?.action_weights?.['vote_up'] ?? 2.0,
      description: 'Explicit positive feedback on quality',
      icon: <ThumbsUp size={16} className="text-emerald-400" />,
      badgeClass: 'bg-emerald-950/60 text-emerald-300 border-emerald-800/60',
      positive: true,
    },
    {
      key: 'read_long',
      title: 'Long Dwell (>30s)',
      weight: data?.action_weights?.['read_long'] ?? 1.5,
      description: 'Attentive deep read duration',
      icon: <Clock size={16} className="text-cyan-400" />,
      badgeClass: 'bg-cyan-950/60 text-cyan-300 border-cyan-800/60',
      positive: true,
    },
    {
      key: 'skip',
      title: 'Fast Skip (<3s)',
      weight: data?.action_weights?.['skip'] ?? -0.5,
      description: 'Dismissed quickly without reading',
      icon: <SkipForward size={16} className="text-orange-400" />,
      badgeClass: 'bg-orange-950/60 text-orange-300 border-orange-800/60',
      positive: false,
    },
    {
      key: 'vote_down',
      title: 'Downvote',
      weight: data?.action_weights?.['vote_down'] ?? -3.0,
      description: 'Explicit disinterest or low relevance',
      icon: <ThumbsDown size={16} className="text-rose-400" />,
      badgeClass: 'bg-rose-950/60 text-rose-300 border-rose-800/60',
      positive: false,
    },
  ];

  if (loading && !data) {
    return (
      <div className="flex flex-col items-center justify-center h-96 bg-gray-950/80 rounded-2xl border border-gray-800/80 p-8 text-center">
        <BrainCircuit size={40} className="text-indigo-400 animate-pulse mb-3" />
        <h3 className="text-base font-semibold text-gray-200">Inspecting Feeda ML Model...</h3>
        <p className="text-xs text-gray-400 mt-1 max-w-sm">
          Extracting Bayesian term weights, action decay factors, and feed affinity statistics.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Top Section: Overview & Model Stats */}
      <div className="bg-gray-950/80 rounded-2xl border border-gray-800/80 p-5 backdrop-blur-md">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-5">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-indigo-950/90 border border-indigo-700/60 text-indigo-400 shadow">
              <BrainCircuit size={22} />
            </div>
            <div>
              <h2 className="text-base font-bold text-gray-100 flex items-center gap-2">
                How Feeda Learned from My Reading
                <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-900/50 text-indigo-300 border border-indigo-700/40">
                  Bayesian Engine
                </span>
              </h2>
              <p className="text-xs text-gray-400 mt-0.5">
                Feeda transparently tracks keyword affinity and publisher relevance using your daily reading signals.
              </p>
            </div>
          </div>

          {/* Model Summary Metrics */}
          {data?.model_summary && (
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-4 bg-gray-900/80 px-4 py-2 rounded-xl border border-gray-800 text-xs">
                <div>
                  <span className="text-gray-400 block text-[11px]">Learned Terms</span>
                  <span className="font-bold text-gray-200 font-mono text-sm">
                    {data.model_summary.total_learned_terms.toLocaleString()}
                  </span>
                </div>
                <div className="w-px h-6 bg-gray-800" />
                <div>
                  <span className="text-gray-400 block text-[11px]">Positive Boosts</span>
                  <span className="font-bold text-emerald-400 font-mono text-sm">
                    {data.model_summary.positive_terms_count.toLocaleString()}
                  </span>
                </div>
                <div className="w-px h-6 bg-gray-800" />
                <div>
                  <span className="text-gray-400 block text-[11px]">Negative Penalties</span>
                  <span className="font-bold text-rose-400 font-mono text-sm">
                    {data.model_summary.negative_terms_count.toLocaleString()}
                  </span>
                </div>
                <div className="w-px h-6 bg-gray-800" />
                <div>
                  <span className="text-gray-400 block text-[11px]">Daily Decay</span>
                  <span className="font-bold text-indigo-300 font-mono text-sm">
                    {safeFloat(data.model_summary.decay_factor).toFixed(2)}
                  </span>
                </div>
              </div>
              {onRefresh && (
                <button
                  onClick={onRefresh}
                  disabled={loading}
                  className="p-2.5 rounded-xl bg-gray-900/80 border border-gray-800 text-gray-400 hover:text-gray-200 transition-colors disabled:opacity-50"
                  title="Refresh ML Inspector"
                >
                  <RefreshCw size={14} className={loading ? 'animate-spin text-indigo-400' : ''} />
                </button>
              )}
            </div>
          )}
        </div>

        {/* 1. Behavioral Action Weights Cards */}
        <div>
          <div className="flex items-center gap-1.5 text-xs font-semibold text-gray-300 mb-2.5">
            <Info size={14} className="text-indigo-400" />
            <span>Behavioral Action Weights (Signal Strengths)</span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2.5">
            {actionDetails.map((act) => {
              const sign = act.weight > 0 ? '+' : '';
              return (
                <div
                  key={act.key}
                  className="flex flex-col justify-between p-3 rounded-xl bg-gray-900/60 border border-gray-800/80 hover:border-gray-700/80 transition-colors"
                >
                  <div className="flex items-center justify-between gap-1 mb-2">
                    <span className="p-1 rounded-lg bg-gray-800/80">{act.icon}</span>
                    <span
                      className={`px-1.5 py-0.5 rounded text-[11px] font-bold font-mono border ${act.badgeClass}`}
                    >
                      {sign}{safeFloat(act.weight).toFixed(1)}
                    </span>
                  </div>
                  <div>
                    <h4 className="text-xs font-semibold text-gray-200 leading-tight">{act.title}</h4>
                    <p className="text-[10px] text-gray-400 leading-snug mt-1 line-clamp-2">{act.description}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Segmented Sub-Tabs: Vocabulary / Feed Affinities / Activity Stream */}
      <div className="flex items-center justify-between border-b border-gray-800/80 pb-2">
        <div className="flex items-center gap-1.5 bg-gray-900/80 p-1 rounded-xl border border-gray-800">
          <button
            onClick={() => setActiveTab('vocabulary')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'vocabulary'
                ? 'bg-indigo-600 text-white shadow'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <Sparkles size={14} />
            <span>Learned Vocabulary Weights</span>
          </button>

          <button
            onClick={() => setActiveTab('affinities')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'affinities'
                ? 'bg-indigo-600 text-white shadow'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <Rss size={14} />
            <span>Feed Affinity Leaderboard</span>
          </button>

          <button
            onClick={() => setActiveTab('events')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'events'
                ? 'bg-indigo-600 text-white shadow'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <Activity size={14} />
            <span>Recent Learning Events</span>
          </button>
        </div>

        {activeTab === 'vocabulary' && (
          <div className="relative w-64">
            <Search size={14} className="absolute left-3 top-2.5 text-gray-400" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search keyword weight..."
              className="w-full bg-gray-900/90 border border-gray-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:border-indigo-500 transition-colors"
            />
          </div>
        )}
      </div>

      {/* Tab 1: Learned Vocabulary (Boosts vs Penalties) */}
      {activeTab === 'vocabulary' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {/* Positive Terms */}
          <div className="bg-gray-950/80 rounded-2xl border border-gray-800/80 p-4 backdrop-blur-md">
            <div className="flex items-center justify-between pb-3 border-b border-gray-800/80 mb-3">
              <div className="flex items-center gap-2">
                <TrendingUp size={16} className="text-emerald-400" />
                <h3 className="text-sm font-bold text-gray-100">Top Boosted Keywords</h3>
              </div>
              <span className="text-xs text-gray-400">
                {filteredPositiveTerms.length} terms
              </span>
            </div>

            {filteredPositiveTerms.length > 0 ? (
              <div className="space-y-2 max-h-[460px] overflow-y-auto pr-1">
                {filteredPositiveTerms.map((t) => {
                  const net = safeFloat(t.net_score);
                  const barPct = Math.min(100, Math.max(8, (net / maxPositiveScore) * 100));
                  return (
                    <div
                      key={t.term}
                      className="p-2.5 rounded-xl bg-gray-900/60 border border-gray-800 hover:border-emerald-800/50 transition-colors"
                    >
                      <div className="flex items-center justify-between text-xs mb-1.5">
                        <span className="font-semibold text-gray-200">{t.term}</span>
                        <div className="flex items-center gap-2 font-mono">
                          <span className="text-[11px] text-gray-400">
                            +{safeFloat(t.positive_score).toFixed(1)} / -{safeFloat(t.negative_score).toFixed(1)}
                          </span>
                          <span className="font-bold text-emerald-400">
                            +{net.toFixed(1)}
                          </span>
                        </div>
                      </div>
                      <div className="w-full h-1.5 bg-gray-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-emerald-600 to-teal-400 rounded-full transition-all duration-500"
                          style={{ width: `${barPct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-xs text-gray-400 italic py-8 text-center">
                {searchTerm ? 'No matching positive keywords found.' : 'No positive keywords learned yet.'}
              </p>
            )}
          </div>

          {/* Negative Terms */}
          <div className="bg-gray-950/80 rounded-2xl border border-gray-800/80 p-4 backdrop-blur-md">
            <div className="flex items-center justify-between pb-3 border-b border-gray-800/80 mb-3">
              <div className="flex items-center gap-2">
                <TrendingDown size={16} className="text-rose-400" />
                <h3 className="text-sm font-bold text-gray-100">Top Penalized Keywords</h3>
              </div>
              <span className="text-xs text-gray-400">
                {filteredNegativeTerms.length} terms
              </span>
            </div>

            {filteredNegativeTerms.length > 0 ? (
              <div className="space-y-2 max-h-[460px] overflow-y-auto pr-1">
                {filteredNegativeTerms.map((t) => {
                  const net = safeFloat(t.net_score);
                  const barPct = Math.min(100, Math.max(8, (Math.abs(net) / maxNegativeScore) * 100));
                  return (
                    <div
                      key={t.term}
                      className="p-2.5 rounded-xl bg-gray-900/60 border border-gray-800 hover:border-rose-800/50 transition-colors"
                    >
                      <div className="flex items-center justify-between text-xs mb-1.5">
                        <span className="font-semibold text-gray-200">{t.term}</span>
                        <div className="flex items-center gap-2 font-mono">
                          <span className="text-[11px] text-gray-400">
                            +{safeFloat(t.positive_score).toFixed(1)} / -{safeFloat(t.negative_score).toFixed(1)}
                          </span>
                          <span className="font-bold text-rose-400">
                            {net.toFixed(1)}
                          </span>
                        </div>
                      </div>
                      <div className="w-full h-1.5 bg-gray-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-rose-600 to-pink-500 rounded-full transition-all duration-500"
                          style={{ width: `${barPct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-xs text-gray-400 italic py-8 text-center">
                {searchTerm ? 'No matching penalized keywords found.' : 'No negative keywords penalized yet.'}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Tab 2: Feed Affinity Leaderboard */}
      {activeTab === 'affinities' && (
        <div className="bg-gray-950/80 rounded-2xl border border-gray-800/80 p-5 backdrop-blur-md">
          <div className="flex items-center justify-between pb-3 border-b border-gray-800/80 mb-4">
            <div>
              <h3 className="text-sm font-bold text-gray-100 flex items-center gap-2">
                <Rss size={16} className="text-blue-400" />
                Feed Affinity Leaderboard
              </h3>
              <p className="text-xs text-gray-400 mt-0.5">
                Feeds with higher read conversion rates receive a proportional boost in your "For You" feed.
              </p>
            </div>
            <span className="text-xs text-gray-400">
              {data?.feed_affinities?.length || 0} feeds tracked
            </span>
          </div>

          {data?.feed_affinities && data.feed_affinities.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-[500px] overflow-y-auto pr-1">
              {data.feed_affinities.map((feed: FeedAffinityItem, idx: number) => {
                const affinity = safeFloat(feed.affinity_score);
                const pct = Math.min(100, Math.round(affinity * 100));
                const readRatio = feed.articles_received > 0 
                  ? ((feed.articles_read / feed.articles_received) * 100).toFixed(0)
                  : '0';

                return (
                  <div
                    key={feed.feed_id}
                    className="p-3.5 rounded-xl bg-gray-900/60 border border-gray-800 hover:border-gray-700 transition-colors"
                  >
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2 truncate">
                        <span className="w-5 h-5 rounded-full bg-gray-800 text-[11px] font-bold text-gray-400 flex items-center justify-center shrink-0">
                          {idx + 1}
                        </span>
                        <span className="font-semibold text-gray-100 text-xs truncate">
                          {feed.feed_title}
                        </span>
                      </div>
                      <span className="px-2 py-0.5 rounded-full bg-blue-950/80 text-blue-300 font-mono text-xs font-bold border border-blue-800/50">
                        {pct}% affinity
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-gray-400 mb-1.5">
                      <span>
                        {feed.articles_read} read of {feed.articles_received} received ({readRatio}% rate)
                      </span>
                      <span className="font-mono text-gray-400">
                        score: {affinity.toFixed(2)}
                      </span>
                    </div>

                    <div className="w-full h-2 bg-gray-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-blue-600 via-indigo-500 to-cyan-400 rounded-full transition-all duration-500"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-xs text-gray-400 italic py-8 text-center">
              No feed affinity data recorded yet.
            </p>
          )}
        </div>
      )}

      {/* Tab 3: Recent Learning Activity Stream */}
      {activeTab === 'events' && (
        <div className="bg-gray-950/80 rounded-2xl border border-gray-800/80 p-5 backdrop-blur-md">
          <div className="flex items-center justify-between pb-3 border-b border-gray-800/80 mb-4">
            <div>
              <h3 className="text-sm font-bold text-gray-100 flex items-center gap-2">
                <Activity size={16} className="text-indigo-400" />
                Recent Learning Events Audit Trail
              </h3>
              <p className="text-xs text-gray-400 mt-0.5">
                Real-time log of reading actions influencing the Bayesian interest model.
              </p>
            </div>
            <span className="text-xs text-gray-400">
              {data?.recent_events?.length || 0} events
            </span>
          </div>

          {data?.recent_events && data.recent_events.length > 0 ? (
            <div className="space-y-2.5 max-h-[500px] overflow-y-auto pr-1">
              {data.recent_events.map((event: LearningEventItem) => {
                const dateStr = new Date(event.created_at).toLocaleDateString([], {
                  month: 'short',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                });
                const dwell = event.dwell_time_seconds ? safeFloat(event.dwell_time_seconds) : null;

                return (
                  <div
                    key={event.id}
                    className="p-3 rounded-xl bg-gray-900/60 border border-gray-800 hover:border-gray-700 transition-colors"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2 mb-1.5">
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider bg-indigo-950/80 text-indigo-300 border border-indigo-800/50">
                          {event.action.replace(/_/g, ' ')}
                        </span>
                        {dwell !== null && dwell > 0 && (
                          <span className="flex items-center gap-1 text-[11px] text-gray-400">
                            <Clock size={11} />
                            {dwell.toFixed(0)}s dwell
                          </span>
                        )}
                      </div>
                      <span className="text-[11px] text-gray-500 font-mono">{dateStr}</span>
                    </div>

                    <h4 className="text-xs font-semibold text-gray-200 mb-2">{event.article_title}</h4>

                    {event.boosted_terms && event.boosted_terms.length > 0 && (
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="text-[10px] text-gray-500 font-medium">Keywords influenced:</span>
                        {event.boosted_terms.map((term: string, idx: number) => (
                          <span
                            key={term + idx}
                            className="px-1.5 py-0.5 rounded bg-gray-800 text-[10px] font-medium text-gray-300 border border-gray-700/60"
                          >
                            {term}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-xs text-gray-400 italic py-8 text-center">
              No recent learning activity events recorded yet.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
