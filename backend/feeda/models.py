from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime

class FolderCreate(BaseModel):
    name: str

class FolderUpdate(BaseModel):
    name: Optional[str] = None
    position: Optional[int] = None

class FolderResponse(BaseModel):
    id: int
    name: str
    position: int
    feed_count: int = 0
    unread_count: int = 0

class FeedCreate(BaseModel):
    url: str
    folder_id: Optional[int] = None
    poll_interval_minutes: Optional[int] = 30

class FeedUpdate(BaseModel):
    title: Optional[str] = None
    folder_id: Optional[int] = None
    poll_interval_minutes: Optional[int] = None

class FeedResponse(BaseModel):
    id: int
    folder_id: Optional[int] = None
    title: str
    url: str
    site_url: Optional[str] = None
    favicon_url: Optional[str] = None
    description: Optional[str] = None
    poll_interval_minutes: int
    last_polled_at: Optional[datetime] = None
    error_count: int
    last_error: Optional[str] = None
    created_at: datetime
    unread_count: int = 0

class FeedListResponse(BaseModel):
    feeds: List[FeedResponse]
    folders: List[FolderResponse]

class ArticleResponse(BaseModel):
    id: int
    feed_id: int
    cluster_id: Optional[int] = None
    guid: Optional[str] = None
    url: str
    title: str
    author: Optional[str] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    image_url: Optional[str] = None
    published_at: Optional[datetime] = None
    is_read: bool
    is_starred: bool
    user_vote: int
    interest_score: float
    likelihood_tier: Optional[str] = None
    feed_title: str = "Feed"
    feed_favicon_url: Optional[str] = None
    cluster_count: int = 1
    cluster_sources: List[str] = []
    board_note: Optional[str] = None
    board_added_at: Optional[Any] = None
    ai_summary: Optional[str] = None
    story_signature: Optional[str] = None

class ArticleListResponse(BaseModel):
    articles: List[ArticleResponse]
    total: int
    page: int
    limit: int
    has_more: bool

class InteractionCreate(BaseModel):
    action: str
    dwell_time: Optional[float] = None

class VoteRequest(BaseModel):
    direction: int = Field(..., ge=-1, le=1)

class MarkAllReadRequest(BaseModel):
    feed_id: Optional[int] = None
    folder_id: Optional[int] = None
    older_than: Optional[str] = None
    days: Optional[int] = None

class SearchResponse(BaseModel):
    articles: List[ArticleResponse]
    total: int

class StatsResponse(BaseModel):
    total_feeds: int
    total_articles: int
    unread_count: int
    starred_count: int
    today_unread_count: int = 0
    for_you_unread_count: int = 0

class FeedSearchResult(BaseModel):
    title: str
    url: str
    site_url: Optional[str] = None
    description: Optional[str] = None
    favicon_url: Optional[str] = None
    subscribers: int = 0
    is_subscribed: bool = False
    reason: Optional[str] = None

class FeedSearchResponse(BaseModel):
    results: List[FeedSearchResult]

class FeedSuggestionsResponse(BaseModel):
    suggestions: List[FeedSearchResult]
    topics: List[str]

class BoardCreate(BaseModel):
    name: str
    description: Optional[str] = None

class BoardUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    position: Optional[int] = None

class BoardResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    position: int = 0
    article_count: int = 0
    created_at: Optional[Any] = None
    updated_at: Optional[Any] = None

class BoardListResponse(BaseModel):
    boards: List[BoardResponse]

class SaveToBoardRequest(BaseModel):
    article_id: int
    note: Optional[str] = None

class UpdateBoardNoteRequest(BaseModel):
    note: Optional[str] = None

class BoardMembership(BaseModel):
    board_id: int
    board_name: str
    note: Optional[str] = None
    added_at: Optional[Any] = None

class ArticleBoardsResponse(BaseModel):
    article_id: int
    boards: List[BoardMembership]


