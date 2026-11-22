import { useState, useMemo } from 'react';
import { 
  Zap, 
  Flame, 
  BookOpen, 
  Clock, 
  Calendar, 
  Sparkles, 
  ExternalLink, 
  TrendingUp, 
  CheckCircle2, 
  ArrowUpRight,
  Radio,
  Layers
} from 'lucide-react';
import { useAppStore } from '../../stores/appStore';
import type { CategoryTrend, DailyTimelineItem, HotspotCategory, ArticleHeadline } from '../../types';

export interface SurgeRadarProps {
  categories: CategoryTrend[];
  hotspot?: HotspotCategory | null;
  dailyTimeline?: DailyTimelineItem[];
  unreadCatchUp?: ArticleHeadline[];
  period: string;
}

function safeFloat(val: number | string | undefined | null, fallback = 0): number {
  if (val === undefined || val === null) return fallback;
  const n = typeof val === 'number' ? val : parseFloat(val);
  return isNaN(n) ? fallback : n;
}

function formatDwellTime(totalSeconds: number): string {
  if (!totalSeconds || totalSeconds <= 0) return '0m';
  const mins = Math.round(totalSeconds / 60);
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  const remainingMins = mins % 60;
  return remainingMins > 0 ? `${hours}h ${remainingMins}m` : `${hours}h`;
}

function formatArticleDate(dateStr?: string): string {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return '';
    const now = new Date();
    const diffHours = Math.round((now.getTime() - d.getTime()) / (1000 * 60 * 60));
    if (diffHours < 1) return 'Just now';
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.round(diffHours / 24);
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays}d ago`;
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch {
    return '';
  }
}

interface Palette {
  color: string;
  badgeBg: string;
  badgeText: string;
  badgeBorder: string;
  cardBorderHover: string;
  glow: string;
}

const PALETTES: Palette[] = [
  {
    color: '#3b82f6', // blue
    badgeBg: 'bg-blue-500/15',
    badgeText: 'text-blue-300',
    badgeBorder: 'border-blue-500/30',
    cardBorderHover: 'hover:border-blue-500/40',
    glow: 'rgba(59, 130, 246, 0.25)',
  },
  {
    color: '#8b5cf6', // purple
    badgeBg: 'bg-purple-500/15',
    badgeText: 'text-purple-300',
    badgeBorder: 'border-purple-500/30',
    cardBorderHover: 'hover:border-purple-500/40',
    glow: 'rgba(139, 92, 246, 0.25)',
  },
  {
    color: '#10b981', // emerald
    badgeBg: 'bg-emerald-500/15',
    badgeText: 'text-emerald-300',
    badgeBorder: 'border-emerald-500/30',
    cardBorderHover: 'hover:border-emerald-500/40',
    glow: 'rgba(16, 185, 129, 0.25)',
  },
  {
    color: '#f59e0b', // amber
    badgeBg: 'bg-amber-500/15',
    badgeText: 'text-amber-300',
    badgeBorder: 'border-amber-500/30',
    cardBorderHover: 'hover:border-amber-500/40',
    glow: 'rgba(245, 158, 11, 0.25)',
  },
  {
    color: '#f43f5e', // rose
    badgeBg: 'bg-rose-500/15',
    badgeText: 'text-rose-300',
    badgeBorder: 'border-rose-500/30',
    cardBorderHover: 'hover:border-rose-500/40',
    glow: 'rgba(244, 63, 94, 0.25)',
  },
  {
    color: '#06b6d4', // cyan
    badgeBg: 'bg-cyan-500/15',
    badgeText: 'text-cyan-300',
    badgeBorder: 'border-cyan-500/30',
    cardBorderHover: 'hover:border-cyan-500/40',
    glow: 'rgba(6, 182, 212, 0.25)',
  },
  {
    color: '#ec4899', // pink
    badgeBg: 'bg-pink-500/15',
    badgeText: 'text-pink-300',
    badgeBorder: 'border-pink-500/30',
    cardBorderHover: 'hover:border-pink-500/40',
    glow: 'rgba(236, 72, 153, 0.25)',
  },
  {
    color: '#6366f1', // indigo
    badgeBg: 'bg-indigo-500/15',
    badgeText: 'text-indigo-300',
    badgeBorder: 'border-indigo-500/30',
    cardBorderHover: 'hover:border-indigo-500/40',
    glow: 'rgba(99, 102, 241, 0.25)',
  },
];

function getCategoryPalette(slug: string, name: string, index: number): Palette {
  const s = (slug + ' ' + name).toLowerCase();
  if (s.includes('ai') || s.includes('machine') || s.includes('intelligence') || s.includes('neural')) {
    return PALETTES[1]; // purple
  }
  if (s.includes('tech') || s.includes('dev') || s.includes('software') || s.includes('cloud') || s.includes('code')) {
    return PALETTES[0]; // blue
  }
  if (s.includes('sec') || s.includes('cyber') || s.includes('privacy')) {
    return PALETTES[2]; // emerald
  }
  if (s.includes('ev') || s.includes('energy') || s.includes('auto') || s.includes('hardware')) {
    return PALETTES[3]; // amber
  }
  if (s.includes('market') || s.includes('finance') || s.includes('biz') || s.includes('economy')) {
    return PALETTES[4]; // rose
  }
  if (s.includes('science') || s.includes('space') || s.includes('bio')) {
    return PALETTES[5]; // cyan
  }
  return PALETTES[index % PALETTES.length];
}

export function SurgeRadar({
  categories,
  hotspot,
  dailyTimeline = [],
  unreadCatchUp = [],
  period
}: SurgeRadarProps) {
  const { selectArticle } = useAppStore();
  const [hoveredCategorySlug, setHoveredCategorySlug] = useState<string | null>(null);

  // 1. Sort categories for Surge Radar: top topics sorted by growth/velocity
  const sortedCategories = useMemo(() => {
    return [...categories].sort((a, b) => {
      const growthA = safeFloat(a.growth_pct);
      const growthB = safeFloat(b.growth_pct);
      if (growthB !== growthA) return growthB - growthA;
      return safeFloat(b.read_count) - safeFloat(a.read_count);
    });
  }, [categories]);

  // 2. Metrics calculation for Proportional Reading Breakdown Bar
  const totalDwellSeconds = useMemo(() => {
    return categories.reduce((sum, c) => sum + safeFloat(c.total_dwell_seconds), 0);
  }, [categories]);

  const totalArticlesRead = useMemo(() => {
    return categories.reduce((sum, c) => sum + safeFloat(c.read_count), 0);
  }, [categories]);

  // Most active reading day
  const mostActiveDay = useMemo(() => {
    if (!dailyTimeline || dailyTimeline.length === 0) {
      return { label: 'Active Period', count: 0 };
    }
    let best = dailyTimeline[0];
    let maxReads = safeFloat(best.total_reads);
    for (const item of dailyTimeline) {
      const count = safeFloat(item.total_reads);
      if (count > maxReads) {
        maxReads = count;
        best = item;
      }
    }
    if (maxReads === 0) {
      return { label: 'Reading recorded', count: 0 };
    }
    try {
      const d = new Date(best.date);
      const formatted = isNaN(d.getTime())
        ? best.date
        : d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
      return { label: formatted, count: maxReads };
    } catch {
      return { label: best.date, count: maxReads };
    }
  }, [dailyTimeline]);

  // Proportional slices
  const slices = useMemo(() => {
    if (categories.length === 0) return [];
    const useDwell = totalDwellSeconds > 0;
    const baseTotal = useDwell
      ? totalDwellSeconds
      : totalArticlesRead > 0
      ? totalArticlesRead
      : 1;

    let computed = categories.map((cat, idx) => {
      const dwell = safeFloat(cat.total_dwell_seconds);
      const reads = safeFloat(cat.read_count);
      const val = useDwell ? dwell : reads;
      let rawPct = baseTotal > 0 ? (val / baseTotal) * 100 : 0;
      if (rawPct === 0 && safeFloat(cat.share_pct) > 0) {
        rawPct = safeFloat(cat.share_pct);
      }
      return {
        slug: cat.slug,
        name: cat.name,
        emoji: cat.emoji,
        dwell,
        reads,
        pct: rawPct,
        palette: getCategoryPalette(cat.slug, cat.name, idx),
      };
    });

    const sumPct = computed.reduce((acc, s) => acc + s.pct, 0);
    if (sumPct > 0) {
      computed = computed.map((s) => ({
        ...s,
        pct: (s.pct / sumPct) * 100,
      }));
    } else {
      // Even split fallback
      const even = 100 / computed.length;
      computed = computed.map((s) => ({ ...s, pct: even }));
    }

    return computed;
  }, [categories, totalDwellSeconds, totalArticlesRead]);

  return (
    <div className="space-y-6 pb-8">
      {/* ─────────────────────────────────────────────────────────────
          SECTION 1: SURGE RADAR CARDS
          ───────────────────────────────────────────────────────────── */}
      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-amber-500/15 border border-amber-500/30 text-amber-400">
              <Radio size={16} className="animate-pulse" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-gray-100 flex items-center gap-2">
                Surge Radar
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-300 border border-amber-500/20">
                  Top Velocity
                </span>
              </h2>
              <p className="text-xs text-gray-400">
                Trending topics sorted by acceleration and growth across your feeds.
              </p>
            </div>
          </div>
          <div className="text-xs text-gray-500 font-mono">
            {categories.length} active radar topics ({period})
          </div>
        </div>

        {/* Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {sortedCategories.map((cat, idx) => {
            const isHotspot = hotspot?.slug === cat.slug;
            const growth = safeFloat(cat.growth_pct);
            const palette = getCategoryPalette(cat.slug, cat.name, idx);
            const topArticles = (cat.top_articles || []).slice(0, 3);
            const sourceFeeds = cat.source_feeds || [];

            return (
              <div
                key={cat.slug}
                className={`flex flex-col justify-between rounded-xl p-4 bg-gray-900/60 backdrop-blur-sm border transition-all duration-200 ${
                  isHotspot
                    ? 'border-amber-500/50 shadow-md shadow-amber-500/5 bg-gradient-to-b from-amber-950/20 to-gray-900/80'
                    : `border-gray-800 ${palette.cardBorderHover}`
                }`}
              >
                <div>
                  {/* Card Header: Emoji, Title, Badges */}
                  <div className="flex items-start justify-between gap-2 mb-3">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className="text-xl shrink-0 p-1 rounded-lg bg-gray-800/80 border border-gray-700/60">
                        {cat.emoji || '📌'}
                      </span>
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          <h3 className="text-sm font-bold text-gray-100 truncate">
                            {cat.name}
                          </h3>
                          {isHotspot && (
                            <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">
                              <Flame size={10} className="animate-pulse" /> HOT
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 text-xs text-gray-400 mt-0.5">
                          <span>{cat.read_count || cat.article_count} articles</span>
                          <span>•</span>
                          <span>{formatDwellTime(safeFloat(cat.total_dwell_seconds))}</span>
                        </div>
                      </div>
                    </div>

                    {/* Surge Badge */}
                    <div className="shrink-0">
                      {growth > 0 ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                          <Zap size={11} className="text-emerald-400" />
                          +{growth.toFixed(1)}% Surge
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-gray-800/80 text-gray-400 border border-gray-700/50">
                          <TrendingUp size={11} />
                          {growth.toFixed(0)}%
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Source Feeds Tags */}
                  {sourceFeeds.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1.5 mb-3">
                      {sourceFeeds.slice(0, 3).map((feed, fIdx) => (
                        <span
                          key={feed + fIdx}
                          className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-gray-800/70 text-gray-300 border border-gray-700/50 truncate max-w-[130px]"
                          title={feed}
                        >
                          {feed}
                        </span>
                      ))}
                      {sourceFeeds.length > 3 && (
                        <span className="text-[10px] text-gray-500 font-medium">
                          +{sourceFeeds.length - 3} more
                        </span>
                      )}
                    </div>
                  )}

                  {/* Top 3 Headlines List */}
                  <div className="border-t border-gray-800/80 pt-2.5 space-y-1.5">
                    <div className="text-[11px] font-semibold text-gray-400 flex items-center justify-between mb-1">
                      <span>Top Headlines</span>
                      <span className="text-[10px] text-gray-500">1-click to open</span>
                    </div>

                    {topArticles.length > 0 ? (
                      topArticles.map((art) => (
                        <div
                          key={art.id}
                          onClick={() => selectArticle(art.id)}
                          role="button"
                          tabIndex={0}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault();
                              selectArticle(art.id);
                            }
                          }}
                          className="group relative flex items-start justify-between gap-2 p-2 rounded-lg bg-gray-950/60 hover:bg-gray-800/60 border border-gray-800/60 hover:border-blue-500/40 cursor-pointer transition-all"
                        >
                          <div className="min-w-0 flex-1">
                            {art.feed_title && (
                              <div className="text-[10px] font-medium text-gray-400 group-hover:text-blue-300 truncate mb-0.5">
                                {art.feed_title}
                              </div>
                            )}
                            <h4 className="text-xs font-medium text-gray-200 group-hover:text-white line-clamp-2 leading-snug">
                              {art.title}
                            </h4>
                            {art.published_at && (
                              <div className="text-[10px] text-gray-500 mt-1">
                                {formatArticleDate(art.published_at)}
                              </div>
                            )}
                          </div>

                          <div className="shrink-0 flex items-center gap-1 text-gray-500 group-hover:text-blue-400 transition-colors pt-0.5">
                            <ArrowUpRight size={14} />
                          </div>
                        </div>
                      ))
                    ) : (
                      // Fallback when top_articles is empty: show top topics tags
                      <div className="p-2.5 rounded-lg bg-gray-950/40 border border-gray-800/40 text-center">
                        <p className="text-xs text-gray-400 mb-1.5">Key topics in this focus area:</p>
                        <div className="flex flex-wrap justify-center gap-1.5">
                          {cat.top_topics && cat.top_topics.length > 0 ? (
                            cat.top_topics.slice(0, 4).map((topic, tIdx) => (
                              <span
                                key={topic.name + tIdx}
                                className="px-2 py-0.5 rounded text-[10px] font-medium bg-gray-800/60 text-gray-300 border border-gray-700/40"
                              >
                                {topic.name}
                              </span>
                            ))
                          ) : (
                            <span className="text-xs text-gray-500">Tracking incoming stories</span>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────
          SECTION 2: PROPORTIONAL READING BREAKDOWN BAR & METRICS
          ───────────────────────────────────────────────────────────── */}
      <section className="p-4 rounded-2xl bg-gray-900/60 border border-gray-800 backdrop-blur-sm space-y-4">
        {/* Header & Metrics Row */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-800/80 pb-3">
          <div className="flex items-center gap-2">
            <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-blue-500/15 border border-blue-500/30 text-blue-400">
              <Layers size={16} />
            </div>
            <div>
              <h3 className="text-sm font-bold text-gray-100">
                Weekly Digest & Reading Allocation
              </h3>
              <p className="text-xs text-gray-400">
                True distribution of your reading time across interest clusters.
              </p>
            </div>
          </div>

          {/* Summary Metric Pills */}
          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            {/* Total Dwell Time */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-gray-950/80 border border-gray-800">
              <Clock size={14} className="text-blue-400" />
              <div>
                <div className="text-[10px] text-gray-400 font-medium">Total Dwell</div>
                <div className="text-xs font-bold text-gray-100 font-mono">
                  {formatDwellTime(totalDwellSeconds)}
                </div>
              </div>
            </div>

            {/* Articles Read */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-gray-950/80 border border-gray-800">
              <BookOpen size={14} className="text-indigo-400" />
              <div>
                <div className="text-[10px] text-gray-400 font-medium">Articles Read</div>
                <div className="text-xs font-bold text-gray-100 font-mono">
                  {totalArticlesRead} stories
                </div>
              </div>
            </div>

            {/* Most Active Reading Day */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-gray-950/80 border border-gray-800">
              <Calendar size={14} className="text-amber-400" />
              <div>
                <div className="text-[10px] text-gray-400 font-medium">Most Active Day</div>
                <div className="text-xs font-bold text-gray-100 truncate max-w-[140px]">
                  {mostActiveDay.label}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Proportional Stacked Horizontal Bar */}
        <div className="space-y-2">
          <div className="w-full h-5 rounded-xl bg-gray-950 border border-gray-800 overflow-hidden flex shadow-inner">
            {slices.map((slice) => {
              const isHovered = hoveredCategorySlug === slice.slug;
              return (
                <div
                  key={slice.slug}
                  style={{
                    width: `${slice.pct}%`,
                    backgroundColor: slice.palette.color,
                  }}
                  onMouseEnter={() => setHoveredCategorySlug(slice.slug)}
                  onMouseLeave={() => setHoveredCategorySlug(null)}
                  className={`h-full transition-all duration-150 cursor-pointer relative ${
                    isHovered ? 'brightness-125 ring-2 ring-white/50 z-10' : 'opacity-90 hover:opacity-100'
                  }`}
                  title={`${slice.name}: ${slice.pct.toFixed(1)}% (${formatDwellTime(slice.dwell)})`}
                />
              );
            })}
          </div>

          {/* Legend / Category Breakdown Chips */}
          <div className="flex flex-wrap items-center gap-2 pt-1">
            {slices.map((slice) => {
              const isHovered = hoveredCategorySlug === slice.slug;
              return (
                <div
                  key={slice.slug}
                  onMouseEnter={() => setHoveredCategorySlug(slice.slug)}
                  onMouseLeave={() => setHoveredCategorySlug(null)}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs transition-colors cursor-pointer border ${
                    isHovered
                      ? 'bg-gray-800 text-gray-100 border-gray-700'
                      : 'bg-gray-950/60 text-gray-400 border-gray-800/80 hover:text-gray-200'
                  }`}
                >
                  <span
                    className="w-2.5 h-2.5 rounded-full shrink-0"
                    style={{ backgroundColor: slice.palette.color }}
                  />
                  <span className="font-medium truncate max-w-[120px]">
                    {slice.emoji} {slice.name}
                  </span>
                  <span className="font-mono text-[11px] text-gray-500 font-semibold">
                    {slice.pct.toFixed(1)}%
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────
          SECTION 3: UNREAD CATCH-UP SHELF
          ───────────────────────────────────────────────────────────── */}
      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-400">
              <Sparkles size={16} />
            </div>
            <div>
              <h2 className="text-sm font-bold text-gray-100 flex items-center gap-2">
                Unread Catch-Up Shelf
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                  High Signal
                </span>
              </h2>
              <p className="text-xs text-gray-400">
                Key unread articles recommended from your surging topics to keep you up to speed.
              </p>
            </div>
          </div>
          {unreadCatchUp.length > 0 && (
            <div className="text-xs text-emerald-400 font-medium">
              {unreadCatchUp.length} unread recommendations
            </div>
          )}
        </div>

        {unreadCatchUp && unreadCatchUp.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
            {unreadCatchUp.map((art) => {
              const score = safeFloat(art.interest_score);

              return (
                <div
                  key={art.id}
                  onClick={() => selectArticle(art.id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      selectArticle(art.id);
                    }
                  }}
                  className="group relative flex flex-col justify-between p-4 rounded-xl bg-gray-900/60 hover:bg-gray-900 border border-gray-800 hover:border-blue-500/40 transition-all duration-200 cursor-pointer shadow-sm hover:shadow-md"
                >
                  <div>
                    {/* Top Meta: Source Feed & Interest Score */}
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <span className="text-xs font-semibold text-gray-400 group-hover:text-blue-300 truncate max-w-[180px]">
                        {art.feed_title || 'Feed'}
                      </span>
                      {score > 0 ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-blue-500/15 text-blue-300 border border-blue-500/30">
                          ★ {score.toFixed(1)} score
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold bg-gray-800 text-gray-400">
                          Recommended
                        </span>
                      )}
                    </div>

                    {/* Article Title */}
                    <h4 className="text-sm font-semibold text-gray-100 group-hover:text-white line-clamp-2 leading-snug mb-2">
                      {art.title}
                    </h4>
                  </div>

                  {/* Bottom Footer: Date & 1-Click Action */}
                  <div className="flex items-center justify-between gap-2 pt-3 border-t border-gray-800/60 mt-2">
                    <span className="text-xs text-gray-500">
                      {formatArticleDate(art.published_at)}
                    </span>

                    <div className="flex items-center gap-2">
                      {art.url && (
                        <a
                          href={art.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="p-1 rounded-md text-gray-500 hover:text-gray-300 hover:bg-gray-800 transition-colors"
                          title="Open original link"
                        >
                          <ExternalLink size={13} />
                        </a>
                      )}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          selectArticle(art.id);
                        }}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-blue-600/30 hover:bg-blue-600 text-blue-300 hover:text-white border border-blue-500/40 hover:border-transparent transition-all"
                      >
                        <BookOpen size={12} />
                        <span>Read</span>
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="flex items-center justify-center p-6 rounded-xl bg-gray-900/40 border border-gray-800/80 text-center">
            <div className="flex flex-col items-center gap-1.5 max-w-sm">
              <CheckCircle2 size={24} className="text-emerald-400 mb-1" />
              <div className="text-xs font-semibold text-gray-200">
                You're all caught up!
              </div>
              <p className="text-xs text-gray-500">
                No high-signal unread stories pending in your top topics for this period.
              </p>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
