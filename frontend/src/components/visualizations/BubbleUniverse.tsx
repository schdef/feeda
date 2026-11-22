import { useState, useEffect, useMemo, useRef } from 'react';
import { 
  Play, 
  Pause, 
  RotateCcw, 
  Sparkles, 
  Flame, 
  Clock, 
  BookOpen, 
  TrendingUp, 
  X
} from 'lucide-react';
import type { CategoryTrend, DailyTimelineItem, HotspotCategory, TopicTrendItem } from '../../types';

interface BubbleUniverseProps {
  categories: CategoryTrend[];
  hotspot?: HotspotCategory | null;
  dailyTimeline: DailyTimelineItem[];
  period: string;
}

interface BubbleLayout {
  category: CategoryTrend;
  x: number;
  y: number;
  radius: number;
  isHotspot: boolean;
  activeReads: number;
  growthPct: number;
}

interface Palette {
  gradient: string;
  fill: string;
  stroke: string;
  glow: string;
  text: string;
  badge: string;
}

function safeFloat(val: number | string | undefined | null, fallback = 0): number {
  if (val === undefined || val === null) return fallback;
  const n = typeof val === 'number' ? val : parseFloat(val);
  return isNaN(n) ? fallback : n;
}

function getCategoryPalette(slug: string, name: string): Palette {
  const s = (slug + ' ' + name).toLowerCase();
  if (s.includes('ai') || s.includes('machine') || s.includes('intelligence') || s.includes('neural')) {
    return {
      gradient: 'url(#aiGradient)',
      fill: '#7c3aed',
      stroke: '#a78bfa',
      glow: 'rgba(167, 139, 250, 0.5)',
      text: '#ede9fe',
      badge: 'bg-violet-900/60 text-violet-200 border-violet-700/60',
    };
  }
  if (s.includes('tech') || s.includes('software') || s.includes('cloud') || s.includes('code')) {
    return {
      gradient: 'url(#techGradient)',
      fill: '#2563eb',
      stroke: '#60a5fa',
      glow: 'rgba(96, 165, 250, 0.5)',
      text: '#dbeafe',
      badge: 'bg-blue-900/60 text-blue-200 border-blue-700/60',
    };
  }
  if (s.includes('ev') || s.includes('auto') || s.includes('hardware') || s.includes('chip') || s.includes('energy')) {
    return {
      gradient: 'url(#hardwareGradient)',
      fill: '#d97706',
      stroke: '#fbbf24',
      glow: 'rgba(251, 191, 36, 0.5)',
      text: '#fef3c7',
      badge: 'bg-amber-900/60 text-amber-200 border-amber-700/60',
    };
  }
  if (s.includes('sec') || s.includes('privacy') || s.includes('cyber') || s.includes('crypto')) {
    return {
      gradient: 'url(#secGradient)',
      fill: '#059669',
      stroke: '#34d399',
      glow: 'rgba(52, 211, 153, 0.5)',
      text: '#d1fae5',
      badge: 'bg-emerald-900/60 text-emerald-200 border-emerald-700/60',
    };
  }
  if (s.includes('science') || s.includes('space') || s.includes('health') || s.includes('bio')) {
    return {
      gradient: 'url(#scienceGradient)',
      fill: '#c026d3',
      stroke: '#e879f9',
      glow: 'rgba(232, 121, 249, 0.5)',
      text: '#fae8ff',
      badge: 'bg-fuchsia-900/60 text-fuchsia-200 border-fuchsia-700/60',
    };
  }
  if (s.includes('market') || s.includes('biz') || s.includes('finance') || s.includes('economy')) {
    return {
      gradient: 'url(#bizGradient)',
      fill: '#e11d48',
      stroke: '#fb7185',
      glow: 'rgba(251, 113, 133, 0.5)',
      text: '#ffe4e6',
      badge: 'bg-rose-900/60 text-rose-200 border-rose-700/60',
    };
  }
  return {
    gradient: 'url(#defaultGradient)',
    fill: '#0284c7',
    stroke: '#38bdf8',
    glow: 'rgba(56, 189, 248, 0.5)',
    text: '#e0f2fe',
    badge: 'bg-sky-900/60 text-sky-200 border-sky-700/60',
  };
}

export function BubbleUniverse({ categories, hotspot, dailyTimeline, period }: BubbleUniverseProps) {
  // Timeline Scrubber state: null = Period cumulative summary; number = specific day index
  const [selectedDayIndex, setSelectedDayIndex] = useState<number | null>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [hoveredSlug, setHoveredSlug] = useState<string | null>(null);
  const [selectedSlug, setSelectedSlug] = useState<string | null>(hotspot?.slug || (categories[0]?.slug ?? null));
  const playTimerRef = useRef<number | null>(null);

  // Playback timer loop
  useEffect(() => {
    if (isPlaying && dailyTimeline.length > 0) {
      playTimerRef.current = window.setInterval(() => {
        setSelectedDayIndex((prev) => {
          if (prev === null) return 0;
          const next = prev + 1;
          if (next >= dailyTimeline.length) {
            setIsPlaying(false);
            return null; // wrap back to summary
          }
          return next;
        });
      }, 1200);
    } else {
      if (playTimerRef.current) {
        clearInterval(playTimerRef.current);
        playTimerRef.current = null;
      }
    }
    return () => {
      if (playTimerRef.current) {
        clearInterval(playTimerRef.current);
      }
    };
  }, [isPlaying, dailyTimeline.length]);

  // Compute radii and dynamic 2D physics layout
  const bubbleLayouts = useMemo<BubbleLayout[]>(() => {
    if (!categories || categories.length === 0) return [];

    const width = 940;
    const height = 560;
    const centerX = width / 2;
    const centerY = height / 2;

    // 1. Calculate radii
    const initial = categories.map((cat, idx) => {
      const isHotspot = hotspot ? cat.slug === hotspot.slug : idx === 0;
      let activeReads = cat.read_count;

      if (selectedDayIndex !== null && dailyTimeline[selectedDayIndex]) {
        const dayRecord = dailyTimeline[selectedDayIndex];
        activeReads = dayRecord.by_category[cat.slug] ?? 0;
      }

      // Radius scaling
      let radius: number;
      if (selectedDayIndex !== null) {
        radius = Math.max(46, Math.min(100, 46 + Math.sqrt(Math.max(0, activeReads)) * 16));
      } else {
        const dwellBonus = Math.sqrt(safeFloat(cat.total_dwell_seconds) / 100);
        radius = Math.max(50, Math.min(115, 48 + Math.sqrt(Math.max(1, activeReads)) * 10 + dwellBonus * 3));
      }

      if (isHotspot) {
        radius = Math.max(radius, 84);
      }

      // Initial placement in an orbital circle
      const angle = (idx / categories.length) * Math.PI * 2 - Math.PI / 2;
      const initialDist = isHotspot ? 40 : 170 + (idx % 2) * 50;
      const x = centerX + Math.cos(angle) * initialDist;
      const y = centerY + Math.sin(angle) * (initialDist * 0.85);

      return {
        category: cat,
        x,
        y,
        radius,
        isHotspot,
        activeReads,
        growthPct: safeFloat(cat.growth_pct),
      };
    });

    // 2. Physics-inspired collision relaxation (30 iterations)
    const iterations = 35;
    for (let it = 0; it < iterations; it++) {
      for (let i = 0; i < initial.length; i++) {
        for (let j = i + 1; j < initial.length; j++) {
          const b1 = initial[i];
          const b2 = initial[j];
          const dx = b2.x - b1.x;
          const dy = b2.y - b1.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const minDist = b1.radius + b2.radius + 16; // 16px buffer
          if (dist < minDist) {
            const overlap = (minDist - dist) * 0.5;
            const nx = dx / dist;
            const ny = dy / dist;

            // Hotspot moves less
            const w1 = b1.isHotspot ? 0.2 : 0.5;
            const w2 = b2.isHotspot ? 0.2 : 0.5;

            b1.x -= nx * overlap * w1;
            b1.y -= ny * overlap * w1;
            b2.x += nx * overlap * w2;
            b2.y += ny * overlap * w2;
          }
        }

        // Mild gravity toward center
        const b = initial[i];
        const toCenterX = centerX - b.x;
        const toCenterY = centerY - b.y;
        b.x += toCenterX * 0.02;
        b.y += toCenterY * 0.02;

        // Keep inside bounds
        const pad = b.radius + 20;
        b.x = Math.max(pad, Math.min(width - pad, b.x));
        b.y = Math.max(pad, Math.min(height - pad, b.y));
      }
    }

    return initial;
  }, [categories, hotspot, selectedDayIndex, dailyTimeline]);

  // Selected category info
  const selectedBubble = useMemo(() => {
    return bubbleLayouts.find((b) => b.category.slug === selectedSlug) || bubbleLayouts[0];
  }, [bubbleLayouts, selectedSlug]);

  const activeDayLabel = useMemo(() => {
    if (selectedDayIndex === null) {
      return `Full Period Summary (${period.toUpperCase()})`;
    }
    const day = dailyTimeline[selectedDayIndex];
    if (!day) return '';
    return `Day ${selectedDayIndex + 1}: ${day.date} · ${day.total_reads} reads logged`;
  }, [selectedDayIndex, dailyTimeline, period]);

  return (
    <div className="flex flex-col h-full bg-gray-950/80 rounded-2xl border border-gray-800/80 backdrop-blur-md overflow-hidden select-none">
      {/* Top Controls / Status Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5 border-b border-gray-800/60 bg-gray-900/40">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-violet-950/80 border border-violet-700/50 text-violet-400">
            <Sparkles size={16} />
          </div>
          <div>
            <span className="text-sm font-semibold text-gray-200">Interactive Bubble Universe</span>
            <span className="text-xs text-gray-400 ml-2 hidden sm:inline">
              Bubble size represents reading volume and engagement
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {hotspot && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-950/50 border border-amber-600/40 text-amber-300 text-xs font-medium">
              <Flame size={13} className="text-amber-400 animate-pulse" />
              <span>Hotspot: {hotspot.name}</span>
            </div>
          )}
        </div>
      </div>

      {/* Main SVG Visualization Canvas */}
      <div className="relative flex-1 min-h-[460px] w-full overflow-hidden flex items-center justify-center p-2">
        <svg
          viewBox="0 0 940 560"
          className="w-full h-full max-h-[580px] object-contain transition-all duration-300"
          style={{ filter: 'drop-shadow(0 0 24px rgba(0,0,0,0.4))' }}
        >
          <defs>
            {/* Gradients */}
            <radialGradient id="aiGradient" cx="35%" cy="35%" r="65%">
              <stop offset="0%" stopColor="#8b5cf6" />
              <stop offset="60%" stopColor="#6d28d9" />
              <stop offset="100%" stopColor="#4c1d95" />
            </radialGradient>
            <radialGradient id="techGradient" cx="35%" cy="35%" r="65%">
              <stop offset="0%" stopColor="#38bdf8" />
              <stop offset="60%" stopColor="#0284c7" />
              <stop offset="100%" stopColor="#0369a1" />
            </radialGradient>
            <radialGradient id="hardwareGradient" cx="35%" cy="35%" r="65%">
              <stop offset="0%" stopColor="#f59e0b" />
              <stop offset="60%" stopColor="#d97706" />
              <stop offset="100%" stopColor="#b45309" />
            </radialGradient>
            <radialGradient id="secGradient" cx="35%" cy="35%" r="65%">
              <stop offset="0%" stopColor="#10b981" />
              <stop offset="60%" stopColor="#059669" />
              <stop offset="100%" stopColor="#047857" />
            </radialGradient>
            <radialGradient id="scienceGradient" cx="35%" cy="35%" r="65%">
              <stop offset="0%" stopColor="#d946ef" />
              <stop offset="60%" stopColor="#c026d3" />
              <stop offset="100%" stopColor="#a21caf" />
            </radialGradient>
            <radialGradient id="bizGradient" cx="35%" cy="35%" r="65%">
              <stop offset="0%" stopColor="#f43f5e" />
              <stop offset="60%" stopColor="#e11d48" />
              <stop offset="100%" stopColor="#be123c" />
            </radialGradient>
            <radialGradient id="defaultGradient" cx="35%" cy="35%" r="65%">
              <stop offset="0%" stopColor="#0284c7" />
              <stop offset="60%" stopColor="#0369a1" />
              <stop offset="100%" stopColor="#075985" />
            </radialGradient>

            {/* Glowing filters */}
            <filter id="hotspotGlow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="12" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="softGlow" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Background subtle starry grid dots */}
          <g opacity="0.15">
            {Array.from({ length: 12 }).map((_, r) =>
              Array.from({ length: 18 }).map((_, c) => (
                <circle
                  key={`dot-${r}-${c}`}
                  cx={35 + c * 50}
                  cy={30 + r * 44}
                  r="1.2"
                  fill="#94a3b8"
                />
              ))
            )}
          </g>

          {/* Connecting energy lines to selected bubble */}
          {selectedBubble && (
            <g opacity="0.3">
              {bubbleLayouts
                .filter((b) => b.category.slug !== selectedBubble.category.slug)
                .map((b) => (
                  <line
                    key={`line-${b.category.slug}`}
                    x1={selectedBubble.x}
                    y1={selectedBubble.y}
                    x2={b.x}
                    y2={b.y}
                    stroke="#475569"
                    strokeDasharray="4 6"
                    strokeWidth="1.2"
                  />
                ))}
            </g>
          )}

          {/* Render Bubble Nodes */}
          {bubbleLayouts.map((layout) => {
            const { category, x, y, radius, isHotspot, activeReads, growthPct } = layout;
            const palette = getCategoryPalette(category.slug, category.name);
            const isSelected = selectedSlug === category.slug;
            const isHovered = hoveredSlug === category.slug;

            return (
              <g
                key={category.slug}
                className="cursor-pointer transition-transform duration-300"
                onClick={() => setSelectedSlug(category.slug)}
                onMouseEnter={() => setHoveredSlug(category.slug)}
                onMouseLeave={() => setHoveredSlug(null)}
                style={{
                  transformOrigin: `${x}px ${y}px`,
                  transform: isHovered || isSelected ? 'scale(1.04)' : 'scale(1)',
                }}
              >
                {/* Hotspot Pulsing Halo Ring */}
                {isHotspot && (
                  <circle
                    cx={x}
                    cy={y}
                    r={radius + 14}
                    fill="none"
                    stroke="#fbbf24"
                    strokeWidth="2.5"
                    strokeDasharray="6 6"
                    opacity="0.85"
                    className="animate-spin"
                    style={{ animationDuration: '24s', transformOrigin: `${x}px ${y}px` }}
                  />
                )}

                {/* Selected Outer Glowing Ring */}
                {isSelected && (
                  <circle
                    cx={x}
                    cy={y}
                    r={radius + 8}
                    fill="none"
                    stroke="#60a5fa"
                    strokeWidth="2.5"
                    opacity="0.9"
                    filter="url(#softGlow)"
                  />
                )}

                {/* Main Bubble Body */}
                <circle
                  cx={x}
                  cy={y}
                  r={radius}
                  fill={palette.gradient}
                  stroke={palette.stroke}
                  strokeWidth={isHotspot || isSelected ? 3 : 1.8}
                  filter={isHotspot ? 'url(#hotspotGlow)' : undefined}
                  className="transition-all duration-300"
                />

                {/* Specular inner light reflection */}
                <ellipse
                  cx={x - radius * 0.28}
                  cy={y - radius * 0.32}
                  rx={radius * 0.45}
                  ry={radius * 0.22}
                  fill="white"
                  opacity="0.18"
                  transform={`rotate(-25, ${x - radius * 0.28}, ${y - radius * 0.32})`}
                />

                {/* Text Content */}
                {/* Emoji */}
                <text
                  x={x}
                  y={y - radius * 0.3}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize={radius > 70 ? 26 : 20}
                  className="pointer-events-none"
                >
                  {category.emoji || '📰'}
                </text>

                {/* Category Name */}
                <text
                  x={x}
                  y={y + (radius > 70 ? 2 : -2)}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fill="#ffffff"
                  fontSize={radius > 70 ? 13 : 11}
                  fontWeight="600"
                  className="pointer-events-none drop-shadow"
                >
                  {category.name.length > 18 ? category.name.substring(0, 16) + '…' : category.name}
                </text>

                {/* Read metrics & Growth */}
                <text
                  x={x}
                  y={y + radius * 0.42}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fill="#e2e8f0"
                  fontSize={radius > 70 ? 11 : 9.5}
                  fontWeight="500"
                  className="pointer-events-none"
                >
                  {activeReads} reads {growthPct > 0 ? `· +${growthPct.toFixed(0)}%` : ''}
                </text>

                {/* Hotspot Badge */}
                {isHotspot && (
                  <g transform={`translate(${x - 36}, ${y + radius * 0.65})`}>
                    <rect
                      width="72"
                      height="18"
                      rx="9"
                      fill="#b45309"
                      stroke="#f59e0b"
                      strokeWidth="1"
                    />
                    <text
                      x="36"
                      y="10"
                      textAnchor="middle"
                      dominantBaseline="central"
                      fill="#fef3c7"
                      fontSize="9.5"
                      fontWeight="bold"
                    >
                      🔥 HOTSPOT
                    </text>
                  </g>
                )}
              </g>
            );
          })}
        </svg>

        {/* Selected Category Details Floating Inspector Card */}
        {selectedBubble && (
          <div className="absolute top-4 right-4 max-w-sm w-full bg-gray-900/90 border border-gray-800 rounded-xl p-4 shadow-2xl backdrop-blur-md transition-all duration-300">
            <div className="flex items-start justify-between gap-2 border-b border-gray-800/80 pb-3">
              <div className="flex items-center gap-2.5">
                <span className="text-2xl">{selectedBubble.category.emoji}</span>
                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="text-sm font-bold text-gray-100">{selectedBubble.category.name}</h4>
                    {selectedBubble.isHotspot && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                        HOTSPOT
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-xs text-gray-400 mt-0.5">
                    <span className="flex items-center gap-1">
                      <BookOpen size={12} className="text-gray-400" />
                      {selectedBubble.category.read_count} reads ({safeFloat(selectedBubble.category.share_pct).toFixed(1)}% share)
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock size={12} className="text-gray-400" />
                      {(safeFloat(selectedBubble.category.total_dwell_seconds) / 60).toFixed(0)}m dwell
                    </span>
                  </div>
                </div>
              </div>
              <button
                onClick={() => setSelectedSlug(null)}
                className="text-gray-400 hover:text-gray-200 p-1 rounded-md transition-colors"
                title="Close inspector"
              >
                <X size={15} />
              </button>
            </div>

            {/* Top 5 Topics in this Category */}
            <div className="mt-3">
              <div className="flex items-center justify-between text-xs font-semibold text-gray-300 mb-2">
                <span className="flex items-center gap-1.5">
                  <TrendingUp size={13} className="text-blue-400" />
                  Top Hot Topics in {selectedBubble.category.name}
                </span>
                <span className="text-[11px] text-gray-400">Dwell · Score</span>
              </div>

              {selectedBubble.category.top_topics && selectedBubble.category.top_topics.length > 0 ? (
                <div className="space-y-1.5 max-h-52 overflow-y-auto pr-1">
                  {selectedBubble.category.top_topics.slice(0, 5).map((topic: TopicTrendItem, idx: number) => (
                    <div
                      key={topic.name + idx}
                      className="flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-gray-800/60 border border-gray-800 text-xs hover:border-gray-700 transition-colors"
                    >
                      <div className="flex items-center gap-2 truncate">
                        <span className="w-4 h-4 rounded-full bg-gray-800 flex items-center justify-center text-[10px] font-bold text-gray-400 shrink-0">
                          {idx + 1}
                        </span>
                        <span className="font-medium text-gray-200 truncate">{topic.name}</span>
                        <span className="text-[11px] text-gray-400 font-mono">({topic.count})</span>
                      </div>
                      <div className="flex items-center gap-2 text-[11px] text-gray-400 shrink-0">
                        <span>{safeFloat(topic.avg_dwell).toFixed(0)}s</span>
                        <span className="px-1.5 py-0.5 rounded bg-blue-950/80 text-blue-300 font-mono text-[10px] font-bold border border-blue-800/50">
                          {safeFloat(topic.score).toFixed(1)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-gray-400 italic py-2">No individual hot topics detected yet.</p>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Interactive Time Scrubber Bottom Bar */}
      <div className="px-5 py-3.5 border-t border-gray-800/60 bg-gray-900/60 flex flex-col sm:flex-row items-center justify-between gap-3">
        {/* Playback Controls */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            disabled={dailyTimeline.length === 0}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow transition-colors disabled:opacity-50"
          >
            {isPlaying ? <Pause size={14} /> : <Play size={14} />}
            <span>{isPlaying ? 'Pause' : 'Play Timeline'}</span>
          </button>

          <button
            onClick={() => {
              setIsPlaying(false);
              setSelectedDayIndex(null);
            }}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs font-medium border border-gray-700/60 transition-colors"
            title="Reset to Full Period"
          >
            <RotateCcw size={13} />
            <span>Summary</span>
          </button>

          <span className="text-xs font-medium text-gray-300 ml-1">
            {activeDayLabel}
          </span>
        </div>

        {/* Timeline Day Pills / Slider */}
        {dailyTimeline.length > 0 && (
          <div className="flex items-center gap-1 overflow-x-auto max-w-full py-1">
            <button
              onClick={() => {
                setIsPlaying(false);
                setSelectedDayIndex(null);
              }}
              className={`px-2 py-1 rounded-md text-[11px] font-medium transition-colors ${
                selectedDayIndex === null
                  ? 'bg-blue-600 text-white shadow'
                  : 'bg-gray-800/80 text-gray-400 hover:text-gray-200'
              }`}
            >
              All
            </button>
            {dailyTimeline.map((item, idx) => {
              const isActive = selectedDayIndex === idx;
              const datePart = item.date.split('-').slice(1).join('/');
              return (
                <button
                  key={item.date}
                  onClick={() => {
                    setIsPlaying(false);
                    setSelectedDayIndex(idx);
                  }}
                  className={`px-2 py-1 rounded-md text-[11px] font-medium whitespace-nowrap transition-colors ${
                    isActive
                      ? 'bg-blue-600 text-white shadow font-semibold'
                      : 'bg-gray-800/80 text-gray-400 hover:text-gray-200 hover:bg-gray-700/60'
                  }`}
                  title={`${item.date} (${item.total_reads} reads)`}
                >
                  {datePart}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
