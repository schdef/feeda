import { useEffect } from 'react';
import { 
  TrendingUp, 
  BrainCircuit, 
  Sparkles, 
  RefreshCw, 
  Zap, 
  Search
} from 'lucide-react';
import { useAppStore } from '../stores/appStore';
import { formatUnreadCount } from './Sidebar';
import { SurgeRadar } from './visualizations/SurgeRadar';
import { NeuralMindMap } from './visualizations/NeuralMindMap';
import { LearningInspector } from './visualizations/LearningInspector';

export function InterestTrendsView() {
  const {
    trendsPeriod,
    setTrendsPeriod,
    activeTrendsTab,
    setActiveTrendsTab,
    interestTrends,
    learningData,
    trendsLoading,
    learningLoading,
    fetchInterestTrends,
    fetchLearningInspector,
    seedDemoAnalytics,
    toggleSidebar,
    stats
  } = useAppStore();

  useEffect(() => {
    if (!interestTrends && !trendsLoading) {
      fetchInterestTrends();
    }
    if (!learningData && !learningLoading) {
      fetchLearningInspector();
    }
  }, [interestTrends, learningData, trendsLoading, learningLoading, fetchInterestTrends, fetchLearningInspector]);

  const periods: { key: '7d' | '14d' | '30d' | 'all'; label: string }[] = [
    { key: '7d', label: '7 Days' },
    { key: '14d', label: '14 Days' },
    { key: '30d', label: '30 Days' },
    { key: 'all', label: 'All Time' },
  ];

  const isLoading = trendsLoading || learningLoading;
  const isDemo = interestTrends?.is_demo || learningData?.is_demo || false;

  return (
    <div className="flex flex-col h-full bg-gray-950 text-gray-200 overflow-hidden">
      {/* 1. Header matching Feeda's header standard */}
      <header className="px-4 py-3 border-b border-gray-900 bg-gray-950/90 backdrop-blur-md sticky top-0 z-20 shrink-0">
        <div className="w-full flex items-center justify-between gap-3">
          {/* Left: Mobile drawer button + Title */}
          <div className="flex items-center gap-3 min-w-0">
            <button 
              onClick={toggleSidebar}
              className="flex items-center justify-center min-w-[32px] h-7 px-2 rounded-full border border-gray-800 text-xs font-semibold text-gray-400 hover:text-gray-200 hover:border-gray-700 active:scale-95 transition-all md:hidden shrink-0 cursor-pointer"
              title="Open Feeds Drawer"
            >
              {formatUnreadCount(stats?.unread_count || 0) || 'Feeds'}
            </button>

            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-7 h-7 rounded-lg bg-blue-500/15 border border-blue-500/30 flex items-center justify-center text-blue-400 shrink-0">
                <TrendingUp size={16} />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h1 className="font-bold text-gray-100 text-base truncate">
                    Trends & Insights
                  </h1>
                  <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20 shrink-0">
                    <Sparkles size={10} />
                    Personalized Intelligence
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Right: Period Selector Pills & Refresh */}
          <div className="flex items-center gap-2 shrink-0">
            {/* Time Window Pills */}
            <div className="flex items-center bg-gray-900/90 p-1 rounded-xl border border-gray-800">
              {periods.map((p) => {
                const isActive = trendsPeriod === p.key;
                return (
                  <button
                    key={p.key}
                    onClick={() => setTrendsPeriod(p.key)}
                    className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-all ${
                      isActive
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'text-gray-400 hover:text-gray-200'
                    }`}
                  >
                    {p.label}
                  </button>
                );
              })}
            </div>

            {/* Refresh Button */}
            <button
              onClick={() => {
                fetchInterestTrends(trendsPeriod);
                fetchLearningInspector();
              }}
              disabled={isLoading}
              className="p-1.5 hover:text-gray-100 hover:bg-gray-800/60 rounded-lg border border-gray-800 text-gray-400 transition-colors cursor-pointer disabled:opacity-50"
              title="Refresh trends and learning insights"
            >
              <RefreshCw size={16} className={isLoading ? 'animate-spin text-blue-400' : ''} />
            </button>
          </div>
        </div>
      </header>

      {/* 2. Sub-Header: Segmented Primary Tabs */}
      <div className="px-4 py-2.5 border-b border-gray-900/80 bg-gray-950/70 shrink-0 flex flex-wrap items-center justify-between gap-3">
        {/* Clean Tab Selector: ⚡ Surge Radar | 🧠 Neural Map | 🔍 Model Inspector */}
        <div className="flex items-center gap-1.5 bg-gray-900/90 p-1 rounded-xl border border-gray-800">
          <button
            onClick={() => setActiveTrendsTab('radar')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              activeTrendsTab === 'radar' || activeTrendsTab === 'visual'
                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-sm'
                : 'text-gray-400 hover:text-gray-200 border border-transparent'
            }`}
          >
            <Zap size={13} className={activeTrendsTab === 'radar' || activeTrendsTab === 'visual' ? 'text-amber-400' : ''} />
            <span>⚡ Surge Radar</span>
          </button>

          <button
            onClick={() => setActiveTrendsTab('mindmap')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              activeTrendsTab === 'mindmap'
                ? 'bg-purple-600/25 text-purple-300 border border-purple-500/40 shadow-sm'
                : 'text-gray-400 hover:text-gray-200 border border-transparent'
            }`}
          >
            <BrainCircuit size={13} className={activeTrendsTab === 'mindmap' ? 'text-purple-400' : ''} />
            <span>🧠 Neural Map</span>
          </button>

          <button
            onClick={() => setActiveTrendsTab('learning')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              activeTrendsTab === 'learning'
                ? 'bg-indigo-600/25 text-indigo-300 border border-indigo-500/40 shadow-sm'
                : 'text-gray-400 hover:text-gray-200 border border-transparent'
            }`}
          >
            <Search size={13} className={activeTrendsTab === 'learning' ? 'text-indigo-400' : ''} />
            <span>🔍 Model Inspector</span>
          </button>
        </div>
      </div>

      {/* 3. Scrollable Content Area */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {/* Demo Mode Notification Banner */}
        {isDemo && (
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 rounded-xl bg-gradient-to-r from-blue-950/40 to-indigo-950/40 border border-blue-800/40 text-xs text-blue-200">
            <div className="flex items-center gap-2.5">
              <span className="p-1.5 rounded-lg bg-blue-900/60 text-blue-300">
                <Sparkles size={15} />
              </span>
              <div>
                <span className="font-semibold text-gray-200">Viewing Sample Trend Activity</span>
                <p className="text-gray-400 text-[11px] mt-0.5">
                  Read more articles, star stories, or simulate reading behavior to see your live personal profile.
                </p>
              </div>
            </div>

            <button
              onClick={() => seedDemoAnalytics()}
              disabled={isLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold transition-all shadow active:scale-95 disabled:opacity-50 cursor-pointer"
            >
              <Zap size={13} />
              <span>Simulate Reading Activity</span>
            </button>
          </div>
        )}

        {/* Tab 1: ⚡ Surge Radar (Default) */}
        {(activeTrendsTab === 'radar' || activeTrendsTab === 'visual') && (
          <div>
            {interestTrends && interestTrends.categories.length > 0 ? (
              <SurgeRadar
                categories={interestTrends.categories}
                hotspot={interestTrends.hotspot}
                dailyTimeline={interestTrends.daily_timeline || []}
                unreadCatchUp={interestTrends.unread_catch_up || []}
                period={trendsPeriod}
              />
            ) : (
              <div className="flex flex-col items-center justify-center h-80 bg-gray-950/80 rounded-2xl border border-gray-800 p-8 text-center">
                <TrendingUp size={36} className="text-gray-500 mb-2" />
                <h3 className="text-sm font-semibold text-gray-300">No trend data available yet</h3>
                <p className="text-xs text-gray-500 mt-1 max-w-sm">
                  Feeda will generate rich engagement clusters once more RSS articles have been fetched and read.
                </p>
                <button
                  onClick={() => seedDemoAnalytics()}
                  className="mt-4 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold cursor-pointer"
                >
                  Generate Sample Trends
                </button>
              </div>
            )}
          </div>
        )}

        {/* Tab 2: 🧠 Neural Map */}
        {activeTrendsTab === 'mindmap' && (
          <div>
            {interestTrends && interestTrends.categories.length > 0 ? (
              <NeuralMindMap
                categories={interestTrends.categories}
                hotspot={interestTrends.hotspot}
                period={trendsPeriod}
              />
            ) : (
              <div className="flex flex-col items-center justify-center h-80 bg-gray-950/80 rounded-2xl border border-gray-800 p-8 text-center">
                <TrendingUp size={36} className="text-gray-500 mb-2" />
                <h3 className="text-sm font-semibold text-gray-300">No trend data available yet</h3>
                <p className="text-xs text-gray-500 mt-1 max-w-sm">
                  Feeda will generate rich neural clusters once more RSS articles have been fetched and read.
                </p>
                <button
                  onClick={() => seedDemoAnalytics()}
                  className="mt-4 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold cursor-pointer"
                >
                  Generate Sample Trends
                </button>
              </div>
            )}
          </div>
        )}

        {/* Tab 3: 🔍 Model Inspector */}
        {activeTrendsTab === 'learning' && (
          <LearningInspector
            data={learningData}
            loading={learningLoading}
            onRefresh={fetchLearningInspector}
          />
        )}
      </div>
    </div>
  );
}
