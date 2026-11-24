export interface Folder {
  id: number;
  name: string;
  position: number;
  feed_count: number;
  unread_count: number;
}

export interface Feed {
  id: number;
  folder_id: number | null;
  title: string;
  url: string;
  site_url: string | null;
  favicon_url: string | null;
  description: string | null;
  poll_interval_minutes: number;
  last_polled_at: string | null;
  error_count: number;
  last_error: string | null;
  unread_count: number;
  created_at: string;
}

export interface Article {
  id: number;
  feed_id: number;
  feed_title: string;
  feed_favicon_url: string | null;
  cluster_id: number | null;
  cluster_count: number;
  cluster_sources: string[];
  guid: string | null;
  url: string;
  title: string;
  author: string | null;
  summary: string | null;
  content: string | null;
  image_url: string | null;
  published_at: string | null;
  is_read: boolean;
  is_starred: boolean;
  user_vote: number;
  interest_score: number;
  likelihood_tier?: 'high' | 'medium' | 'low';
  board_note?: string | null;
  board_added_at?: string | null;
  ai_summary?: string | null;
  story_signature?: string | null;
  category?: string | null;
  category_slug?: string | null;
  category_emoji?: string | null;
}

export interface Board {
  id: number;
  name: string;
  description: string | null;
  position: number;
  article_count: number;
  created_at: string;
  updated_at: string;
}

export interface BoardMembership {
  board_id: number;
  board_name: string;
  note: string | null;
  added_at: string | null;
}

export interface ArticleBoardsResponse {
  article_id: number;
  boards: BoardMembership[];
}

export interface ArticleListResponse {
  articles: Article[];
  total: number;
  page: number;
  limit: number;
  has_more: boolean;
}

export interface Stats {
  total_feeds: number;
  total_articles: number;
  unread_count: number;
  starred_count: number;
  today_unread_count?: number;
  for_you_unread_count?: number;
}

export interface InterestGroup {
  name: string;
  emoji: string;
  slug: string;
  article_count: number;
  articles: Article[];
}

export interface InterestBoardResponse {
  groups: InterestGroup[];
}

export interface TopicTrendItem {
  name: string;
  count: number;
  avg_dwell: number;
  score: number;
}

export interface ArticleHeadline {
  id: number;
  title: string;
  feed_title?: string;
  url: string;
  published_at?: string;
  is_read: boolean;
  interest_score: number;
}

export interface CategoryTrend {
  name: string;
  slug: string;
  emoji: string;
  article_count: number;
  read_count: number;
  total_dwell_seconds: number;
  share_pct: number;
  growth_pct: number;
  daily_trend: number[];
  top_topics: TopicTrendItem[];
  top_articles?: ArticleHeadline[];
  source_feeds?: string[];
}

export interface HotspotCategory {
  name: string;
  slug: string;
  emoji: string;
  article_count: number;
  read_count: number;
  total_dwell_seconds: number;
  growth_pct: number;
  top_topics: TopicTrendItem[];
  top_articles?: ArticleHeadline[];
  source_feeds?: string[];
}

export interface DailyTimelineItem {
  date: string;
  total_reads: number;
  by_category: Record<string, number>;
}

export interface InterestTrendsResponse {
  period: string;
  start_date: string;
  end_date: string;
  is_demo: boolean;
  hotspot?: HotspotCategory | null;
  categories: CategoryTrend[];
  daily_timeline: DailyTimelineItem[];
  unread_catch_up?: ArticleHeadline[];
}

export interface ModelSummary {
  total_learned_terms: number;
  positive_terms_count: number;
  negative_terms_count: number;
  decay_factor: number;
}

export interface TermWeightItem {
  term: string;
  positive_score: number;
  negative_score: number;
  net_score: number;
}

export interface FeedAffinityItem {
  feed_id: number;
  feed_title: string;
  articles_received: number;
  articles_read: number;
  affinity_score: number;
}

export interface LearningEventItem {
  id: number;
  article_title: string;
  action: string;
  dwell_time_seconds?: number | null;
  created_at: string;
  boosted_terms: string[];
}

export interface LearningInspectorResponse {
  model_summary: ModelSummary;
  top_positive_terms: TermWeightItem[];
  top_negative_terms: TermWeightItem[];
  feed_affinities: FeedAffinityItem[];
  action_weights: Record<string, number>;
  recent_events: LearningEventItem[];
  is_demo: boolean;
}

export type ViewMode = 'magazine' | 'compact';
export type SortMode = 'date' | 'score';
export type FilterView = 'all' | 'unread' | 'starred' | 'for-you' | 'today' | 'interests' | 'trends';
export type LikelihoodFilter = 'likely' | 'not_likely' | 'all';
