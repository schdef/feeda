import { useState, useMemo } from 'react';
import { 
  Brain, 
  Layers, 
  ZoomIn, 
  ZoomOut, 
  RotateCcw,
  BookOpen,
  Clock,
  TrendingUp,
  X
} from 'lucide-react';
import type { CategoryTrend, HotspotCategory, TopicTrendItem } from '../../types';

interface NeuralMindMapProps {
  categories: CategoryTrend[];
  hotspot?: HotspotCategory | null;
  period: string;
}

interface Palette {
  lineColor: string;
  glowColor: string;
  nodeFill: string;
  nodeStroke: string;
  badgeBg: string;
}

function safeFloat(val: number | string | undefined | null, fallback = 0): number {
  if (val === undefined || val === null) return fallback;
  const n = typeof val === 'number' ? val : parseFloat(val);
  return isNaN(n) ? fallback : n;
}

function getCategoryColor(slug: string, name: string): Palette {
  const s = (slug + ' ' + name).toLowerCase();
  if (s.includes('ai') || s.includes('machine') || s.includes('intelligence') || s.includes('neural')) {
    return {
      lineColor: '#a78bfa',
      glowColor: 'rgba(167, 139, 250, 0.45)',
      nodeFill: '#4c1d95',
      nodeStroke: '#8b5cf6',
      badgeBg: 'rgba(124, 58, 237, 0.25)',
    };
  }
  if (s.includes('tech') || s.includes('software') || s.includes('cloud') || s.includes('code')) {
    return {
      lineColor: '#60a5fa',
      glowColor: 'rgba(96, 165, 250, 0.45)',
      nodeFill: '#1e3a8a',
      nodeStroke: '#3b82f6',
      badgeBg: 'rgba(37, 99, 235, 0.25)',
    };
  }
  if (s.includes('ev') || s.includes('auto') || s.includes('hardware') || s.includes('chip') || s.includes('energy')) {
    return {
      lineColor: '#fbbf24',
      glowColor: 'rgba(251, 191, 36, 0.45)',
      nodeFill: '#78350f',
      nodeStroke: '#f59e0b',
      badgeBg: 'rgba(217, 119, 6, 0.25)',
    };
  }
  if (s.includes('sec') || s.includes('privacy') || s.includes('cyber')) {
    return {
      lineColor: '#34d399',
      glowColor: 'rgba(52, 211, 153, 0.45)',
      nodeFill: '#064e3b',
      nodeStroke: '#10b981',
      badgeBg: 'rgba(5, 150, 105, 0.25)',
    };
  }
  if (s.includes('science') || s.includes('space') || s.includes('bio')) {
    return {
      lineColor: '#e879f9',
      glowColor: 'rgba(232, 121, 249, 0.45)',
      nodeFill: '#701a75',
      nodeStroke: '#d946ef',
      badgeBg: 'rgba(192, 38, 211, 0.25)',
    };
  }
  if (s.includes('market') || s.includes('finance') || s.includes('biz')) {
    return {
      lineColor: '#fb7185',
      glowColor: 'rgba(251, 113, 133, 0.45)',
      nodeFill: '#881337',
      nodeStroke: '#f43f5e',
      badgeBg: 'rgba(225, 29, 72, 0.25)',
    };
  }
  return {
    lineColor: '#38bdf8',
    glowColor: 'rgba(56, 189, 248, 0.45)',
    nodeFill: '#0c4a6e',
    nodeStroke: '#0284c7',
    badgeBg: 'rgba(2, 132, 199, 0.25)',
  };
}

export function NeuralMindMap({ categories, hotspot, period }: NeuralMindMapProps) {
  const [selectedSlug, setSelectedSlug] = useState<string | null>(hotspot?.slug || (categories[0]?.slug ?? null));
  const [hoveredSlug, setHoveredSlug] = useState<string | null>(null);
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const [expandAll, setExpandAll] = useState<boolean>(false);

  const cx = 500;
  const cy = 340;
  const mapWidth = 1000;
  const mapHeight = 680;

  // Active category node
  const activeCategory = useMemo(() => {
    return categories.find((c) => c.slug === selectedSlug) || categories[0];
  }, [categories, selectedSlug]);

  // Compute category positions and synapses
  const nodes = useMemo(() => {
    if (!categories || categories.length === 0) return [];

    const total = categories.length;
    const radiusX = 260;
    const radiusY = 200;

    return categories.map((cat, idx) => {
      const isHotspot = hotspot ? cat.slug === hotspot.slug : idx === 0;
      const angle = (idx / total) * Math.PI * 2 - Math.PI / 2;
      const x = cx + Math.cos(angle) * radiusX;
      const y = cy + Math.sin(angle) * radiusY;

      // Bezier control point: curved outwards
      const midDist = 130;
      const curveAngle = angle + 0.15;
      const cpx = cx + Math.cos(curveAngle) * midDist;
      const cpy = cy + Math.sin(curveAngle) * midDist;

      const palette = getCategoryColor(cat.slug, cat.name);
      const synapseWidth = Math.max(2, Math.min(6, 2 + Math.sqrt(cat.read_count) * 0.8));

      // Calculate Topic Leaf Nodes (Top 5 Hot Topics)
      const shouldExpandTopics = expandAll || isHotspot || cat.slug === selectedSlug || cat.slug === hoveredSlug;
      const topics = cat.top_topics || [];
      const topicLeaves = shouldExpandTopics
        ? topics.slice(0, 5).map((topic, tIdx) => {
            const fanSpread = 0.24;
            const topicAngle = angle + (tIdx - 2) * fanSpread;
            const branchDist = 110 + (tIdx % 2) * 22;
            const tx = x + Math.cos(topicAngle) * branchDist;
            const ty = y + Math.sin(topicAngle) * branchDist;

            // Curved branch control point
            const tMidDist = branchDist * 0.55;
            const tcpx = x + Math.cos(topicAngle + 0.08) * tMidDist;
            const tcpy = y + Math.sin(topicAngle + 0.08) * tMidDist;

            return {
              topic,
              x: tx,
              y: ty,
              cpx: tcpx,
              cpy: tcpy,
            };
          })
        : [];

      return {
        category: cat,
        x,
        y,
        cpx,
        cpy,
        angle,
        isHotspot,
        palette,
        synapseWidth,
        topicLeaves,
      };
    });
  }, [categories, hotspot, cx, cy, expandAll, selectedSlug, hoveredSlug]);

  return (
    <div className="flex flex-col h-full bg-gray-950/80 rounded-2xl border border-gray-800/80 backdrop-blur-md overflow-hidden select-none">
      {/* Top Header & Map Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5 border-b border-gray-800/60 bg-gray-900/40">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-indigo-950/80 border border-indigo-700/50 text-indigo-400">
            <Brain size={16} />
          </div>
          <div>
            <span className="text-sm font-semibold text-gray-200">Neural Mind Map</span>
            <span className="text-xs text-gray-400 ml-2 hidden sm:inline">
              Synaptic tree radiating into categories and active hot subtopics
            </span>
          </div>
        </div>

        {/* View Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setExpandAll(!expandAll)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors ${
              expandAll
                ? 'bg-blue-600 text-white border-blue-500'
                : 'bg-gray-800 text-gray-300 border-gray-700 hover:bg-gray-700'
            }`}
          >
            <Layers size={13} />
            <span>{expandAll ? 'Collapse Topics' : 'Expand All Topics'}</span>
          </button>

          <div className="flex items-center bg-gray-800/80 rounded-lg border border-gray-700/60 p-0.5">
            <button
              onClick={() => setZoomLevel((z) => Math.max(0.7, z - 0.1))}
              className="p-1 text-gray-400 hover:text-gray-200 transition-colors"
              title="Zoom out"
            >
              <ZoomOut size={14} />
            </button>
            <span className="text-[11px] font-mono text-gray-400 px-1.5">{Math.round(zoomLevel * 100)}%</span>
            <button
              onClick={() => setZoomLevel((z) => Math.min(1.4, z + 0.1))}
              className="p-1 text-gray-400 hover:text-gray-200 transition-colors"
              title="Zoom in"
            >
              <ZoomIn size={14} />
            </button>
            <button
              onClick={() => setZoomLevel(1)}
              className="p-1 text-gray-400 hover:text-gray-200 transition-colors"
              title="Reset Zoom"
            >
              <RotateCcw size={12} />
            </button>
          </div>
        </div>
      </div>

      {/* Main SVG Radial Mind Map Canvas */}
      <div className="relative flex-1 min-h-[480px] w-full overflow-hidden flex items-center justify-center p-2">
        <svg
          viewBox={`0 0 ${mapWidth} ${mapHeight}`}
          className="w-full h-full max-h-[660px] object-contain transition-all duration-300"
          style={{ transform: `scale(${zoomLevel})`, transformOrigin: 'center center' }}
        >
          <defs>
            {/* Center Brain Node Gradient */}
            <radialGradient id="centerBrainGrad" cx="40%" cy="40%" r="60%">
              <stop offset="0%" stopColor="#818cf8" />
              <stop offset="60%" stopColor="#4f46e5" />
              <stop offset="100%" stopColor="#312e81" />
            </radialGradient>

            {/* Glowing filter */}
            <filter id="synapseGlow" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="mindCoreGlow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="10" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Concentric subtle neural orbit rings */}
          <circle cx={cx} cy={cy} r="140" fill="none" stroke="#334155" strokeWidth="1" strokeDasharray="3 6" opacity="0.3" />
          <circle cx={cx} cy={cy} r="240" fill="none" stroke="#334155" strokeWidth="1" strokeDasharray="4 8" opacity="0.25" />
          <circle cx={cx} cy={cy} r="340" fill="none" stroke="#334155" strokeWidth="1" strokeDasharray="5 10" opacity="0.15" />

          {/* Synaptic Curved Connections from Center to Categories */}
          {nodes.map((node) => {
            const isSelected = selectedSlug === node.category.slug;
            const isHovered = hoveredSlug === node.category.slug;
            const isActive = isSelected || isHovered || node.isHotspot;

            return (
              <g key={`synapse-${node.category.slug}`}>
                {/* Curved Main Synapse Path */}
                <path
                  d={`M ${cx} ${cy} Q ${node.cpx} ${node.cpy} ${node.x} ${node.y}`}
                  fill="none"
                  stroke={node.palette.lineColor}
                  strokeWidth={isActive ? node.synapseWidth + 1.5 : node.synapseWidth}
                  strokeOpacity={isActive ? 0.9 : 0.45}
                  filter={isActive ? 'url(#synapseGlow)' : undefined}
                  className="transition-all duration-300"
                />

                {/* Animated electrical impulse pulse along active synapse */}
                {isActive && (
                  <circle r="3" fill="#ffffff" filter="url(#synapseGlow)">
                    <animateMotion
                      path={`M ${cx} ${cy} Q ${node.cpx} ${node.cpy} ${node.x} ${node.y}`}
                      dur="2.4s"
                      repeatCount="indefinite"
                    />
                  </circle>
                )}

                {/* Sprouting Topic Leaf Branches */}
                {node.topicLeaves.map((leaf, lIdx) => (
                  <g key={`branch-${node.category.slug}-${leaf.topic.name}-${lIdx}`}>
                    {/* Branch connector */}
                    <path
                      d={`M ${node.x} ${node.y} Q ${leaf.cpx} ${leaf.cpy} ${leaf.x} ${leaf.y}`}
                      fill="none"
                      stroke={node.palette.lineColor}
                      strokeWidth="1.4"
                      strokeDasharray="3 3"
                      strokeOpacity="0.75"
                    />

                    {/* Topic Leaf Badge Node */}
                    <g
                      transform={`translate(${leaf.x}, ${leaf.y})`}
                      className="cursor-pointer transition-transform hover:scale-105"
                    >
                      <rect
                        x="-58"
                        y="-12"
                        width="116"
                        height="24"
                        rx="12"
                        fill="#0f172a"
                        stroke={node.palette.nodeStroke}
                        strokeWidth="1.2"
                        filter="url(#synapseGlow)"
                      />
                      <text
                        x="-14"
                        y="1"
                        textAnchor="middle"
                        dominantBaseline="central"
                        fill="#f1f5f9"
                        fontSize="9.5"
                        fontWeight="600"
                      >
                        {leaf.topic.name.length > 12 ? leaf.topic.name.substring(0, 11) + '…' : leaf.topic.name}
                      </text>
                      {/* Topic Score Badge */}
                      <rect
                        x="24"
                        y="-8"
                        width="26"
                        height="16"
                        rx="8"
                        fill={node.palette.nodeFill}
                      />
                      <text
                        x="37"
                        y="0"
                        textAnchor="middle"
                        dominantBaseline="central"
                        fill="#e0e7ff"
                        fontSize="8.5"
                        fontWeight="bold"
                        fontFamily="monospace"
                      >
                        {safeFloat(leaf.topic.score).toFixed(1)}
                      </text>
                    </g>
                  </g>
                ))}
              </g>
            );
          })}

          {/* Render Category Nodes */}
          {nodes.map((node) => {
            const isSelected = selectedSlug === node.category.slug;
            const isHovered = hoveredSlug === node.category.slug;
            const r = node.isHotspot ? 40 : 34;

            return (
              <g
                key={`cat-node-${node.category.slug}`}
                transform={`translate(${node.x}, ${node.y})`}
                className="cursor-pointer transition-transform duration-200"
                onClick={() => setSelectedSlug(node.category.slug)}
                onMouseEnter={() => setHoveredSlug(node.category.slug)}
                onMouseLeave={() => setHoveredSlug(null)}
                style={{
                  transform: isSelected || isHovered ? 'scale(1.08)' : 'scale(1)',
                }}
              >
                {/* Hotspot Outer Halo */}
                {node.isHotspot && (
                  <circle
                    r={r + 10}
                    fill="none"
                    stroke="#fbbf24"
                    strokeWidth="2"
                    strokeDasharray="4 4"
                    className="animate-spin"
                    style={{ animationDuration: '20s' }}
                  />
                )}

                {/* Selected Halo */}
                {isSelected && (
                  <circle
                    r={r + 6}
                    fill="none"
                    stroke="#60a5fa"
                    strokeWidth="2.5"
                    filter="url(#synapseGlow)"
                  />
                )}

                {/* Category Node Circle */}
                <circle
                  r={r}
                  fill={node.palette.nodeFill}
                  stroke={node.palette.nodeStroke}
                  strokeWidth={node.isHotspot || isSelected ? 2.5 : 1.8}
                  filter={node.isHotspot ? 'url(#mindCoreGlow)' : 'url(#synapseGlow)'}
                />

                {/* Node Emoji */}
                <text
                  y="-8"
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize={node.isHotspot ? 20 : 17}
                >
                  {node.category.emoji || '📰'}
                </text>

                {/* Node Label */}
                <text
                  y="12"
                  textAnchor="middle"
                  dominantBaseline="central"
                  fill="#ffffff"
                  fontSize="10"
                  fontWeight="600"
                >
                  {node.category.name.length > 13 ? node.category.name.substring(0, 11) + '…' : node.category.name}
                </text>

                {/* Hotspot Badge */}
                {node.isHotspot && (
                  <g transform="translate(0, 32)">
                    <rect
                      x="-26"
                      y="-8"
                      width="52"
                      height="16"
                      rx="8"
                      fill="#b45309"
                      stroke="#f59e0b"
                      strokeWidth="1"
                    />
                    <text
                      x="0"
                      y="1"
                      textAnchor="middle"
                      dominantBaseline="central"
                      fill="#fef3c7"
                      fontSize="8"
                      fontWeight="bold"
                    >
                      HOTSPOT
                    </text>
                  </g>
                )}
              </g>
            );
          })}

          {/* Central Root Node: "Your Reading Mind" */}
          <g transform={`translate(${cx}, ${cy})`} className="cursor-default">
            {/* Pulsing outer aura ring */}
            <circle
              r="62"
              fill="none"
              stroke="#818cf8"
              strokeWidth="2"
              strokeDasharray="6 6"
              opacity="0.8"
              className="animate-pulse"
            />

            {/* Core Brain Sphere */}
            <circle
              r="48"
              fill="url(#centerBrainGrad)"
              stroke="#a5b4fc"
              strokeWidth="2.8"
              filter="url(#mindCoreGlow)"
            />

            {/* Specular shine */}
            <ellipse cx="-12" cy="-14" rx="20" ry="10" fill="white" opacity="0.22" transform="rotate(-25, -12, -14)" />

            {/* Brain icon representation */}
            <g transform="translate(-14, -20) scale(1.15)">
              <Brain size={24} color="#e0e7ff" />
            </g>

            <text
              y="12"
              textAnchor="middle"
              dominantBaseline="central"
              fill="#ffffff"
              fontSize="10.5"
              fontWeight="bold"
            >
              Reading Mind
            </text>
            <text
              y="25"
              textAnchor="middle"
              dominantBaseline="central"
              fill="#c7d2fe"
              fontSize="8.5"
              fontWeight="500"
            >
              {period.toUpperCase()} Model
            </text>
          </g>
        </svg>

        {/* Selected Category Details Floating Card */}
        {activeCategory && (
          <div className="absolute top-4 right-4 max-w-sm w-full bg-gray-900/90 border border-gray-800 rounded-xl p-4 shadow-2xl backdrop-blur-md transition-all duration-300">
            <div className="flex items-start justify-between gap-2 border-b border-gray-800/80 pb-3">
              <div className="flex items-center gap-2.5">
                <span className="text-2xl">{activeCategory.emoji}</span>
                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="text-sm font-bold text-gray-100">{activeCategory.name}</h4>
                    {hotspot && hotspot.slug === activeCategory.slug && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                        HOTSPOT
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-xs text-gray-400 mt-0.5">
                    <span className="flex items-center gap-1">
                      <BookOpen size={12} className="text-gray-400" />
                      {activeCategory.read_count} reads ({safeFloat(activeCategory.share_pct).toFixed(1)}% share)
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock size={12} className="text-gray-400" />
                      {(safeFloat(activeCategory.total_dwell_seconds) / 60).toFixed(0)}m dwell
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
                  <TrendingUp size={13} className="text-indigo-400" />
                  Neural Leaf Topics
                </span>
                <span className="text-[11px] text-gray-400">Dwell · Score</span>
              </div>

              {activeCategory.top_topics && activeCategory.top_topics.length > 0 ? (
                <div className="space-y-1.5 max-h-52 overflow-y-auto pr-1">
                  {activeCategory.top_topics.slice(0, 5).map((topic: TopicTrendItem, idx: number) => (
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
                        <span className="px-1.5 py-0.5 rounded bg-indigo-950/80 text-indigo-300 font-mono text-[10px] font-bold border border-indigo-800/50">
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

      {/* Mind Map Footer Guide */}
      <div className="px-5 py-3 border-t border-gray-800/60 bg-gray-900/40 flex flex-wrap items-center justify-between gap-2 text-xs text-gray-400">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full bg-indigo-500 shadow" />
            <span>Root Model</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full bg-blue-500 shadow" />
            <span>Category Hubs</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full bg-amber-500 shadow" />
            <span>Hotspot Hub</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-gray-500" />
            <span>Subtopic Leaves</span>
          </div>
        </div>
        <div className="text-[11px] text-gray-400">
          Tip: Click any category hub to sprout and focus its top 5 hot topics
        </div>
      </div>
    </div>
  );
}
