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

export type ViewMode = 'magazine' | 'compact';
export type SortMode = 'date' | 'score';
export type FilterView = 'all' | 'unread' | 'starred' | 'for-you' | 'today' | 'interests';
export type LikelihoodFilter = 'likely' | 'not_likely' | 'all';
