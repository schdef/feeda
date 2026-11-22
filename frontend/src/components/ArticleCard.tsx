import React, { useState } from 'react';
import { Bookmark, Layers, ExternalLink, Sparkles, FolderPlus, Trash2, StickyNote } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import type { Article, ViewMode } from '../types';
import { useAppStore } from '../stores/appStore';
import clsx from 'clsx';

interface Props {
  article: Article;
  viewMode: ViewMode;
}

export function ArticleCard({ article, viewMode }: Props) {
  const { 
    selectedArticle, 
    selectArticle, 
    toggleArticleStar, 
    filterView,
    likelihoodFilter,
    openArticleWebsite,
    selectedBoardId,
    setSaveToBoardModalOpen,
    removeArticleFromBoard
  } = useAppStore();
  const isSelected = selectedArticle?.id === article.id;
  const [imageError, setImageError] = useState(false);

  const handleClick = () => {
    selectArticle(article);
  };

  const handleTitleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    openArticleWebsite(article.id, article.url);
  };

  const handleStarClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    toggleArticleStar(article.id);
  };

  const timeAgo = article.published_at 
    ? formatDistanceToNow(new Date(article.published_at), { addSuffix: false })
        .replace('about ', '')
        .replace('less than a minute', 'now')
    : 'now';

  const isLikely = article.likelihood_tier === 'high';
  const isMedium = article.likelihood_tier === 'medium';

  const likelihoodBadge = isLikely ? (
    <span className="inline-flex items-center gap-1 text-[10px] font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30 px-1.5 py-0.5 rounded shrink-0">
      <Sparkles size={10} className="text-amber-400" />
      Top Match
    </span>
  ) : isMedium ? (
    <span className="inline-flex items-center gap-1 text-[10px] font-medium bg-blue-500/15 text-blue-300 border border-blue-500/30 px-1.5 py-0.5 rounded shrink-0">
      <Sparkles size={10} className="text-blue-400" />
      Likely
    </span>
  ) : likelihoodFilter === 'likely' && article.likelihood_tier === 'low' ? (
    <span className="inline-flex items-center gap-1 text-[10px] font-normal text-gray-500 bg-gray-900 border border-gray-800 px-1.5 py-0.5 rounded shrink-0">
      Suggested
    </span>
  ) : null;

  if (viewMode === 'compact') {
    return (
      <div 
        onClick={handleClick}
        data-article-id={article.id}
        data-is-read={article.is_read}
        className={clsx(
          'flex items-center gap-3 px-4 py-2.5 cursor-pointer transition-colors border-b border-gray-900',
          isSelected ? 'bg-gray-800/90' : 'hover:bg-gray-900/60'
        )}
      >
        <button onClick={handleStarClick} className="shrink-0 p-1 text-gray-500 hover:text-gray-300">
          <Bookmark 
            size={16} 
            className={article.is_starred ? "text-amber-400 fill-amber-400" : ""} 
          />
        </button>

        <div className="flex-1 min-w-0 flex items-baseline gap-2">
          <h3 
            onClick={handleTitleClick}
            title="Open original website"
            className={clsx(
              "truncate text-sm leading-snug cursor-pointer transition-colors hover:text-blue-400 hover:underline",
              !article.is_read ? "font-bold text-gray-100" : "font-normal text-gray-400"
            )}
          >
            {article.title}
          </h3>
          <span className="text-xs text-gray-500 shrink-0 hidden sm:inline">
            {article.feed_title} / {timeAgo}
          </span>
        </div>

        {article.board_note && (
          <span className="inline-flex items-center gap-1 text-[10px] bg-amber-500/15 text-amber-300 border border-amber-500/30 px-1.5 py-0.5 rounded shrink-0" title={`Note: ${article.board_note}`}>
            <StickyNote size={10} />
            Note
          </span>
        )}

        {likelihoodBadge}
        
        {article.cluster_count > 1 && (
          <div 
            className="shrink-0 flex items-center gap-1 text-[10px] font-medium bg-gray-800 text-gray-400 px-1.5 py-0.5 rounded cursor-help"
            title={article.cluster_sources && article.cluster_sources.length > 0 ? `Also reported by: ${article.cluster_sources.join(', ')}` : `Reported in ${article.cluster_count} sources`}
          >
            <Layers size={10} />
            <span>+{article.cluster_count - 1}</span>
          </div>
        )}

        <button
          onClick={(e) => {
            e.stopPropagation();
            setSaveToBoardModalOpen(true, article);
          }}
          className="shrink-0 p-1 text-gray-500 hover:text-blue-400 transition-colors"
          title="Save to Board"
        >
          <FolderPlus size={15} />
        </button>

        {selectedBoardId && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              if (confirm('Remove article from this board?')) {
                removeArticleFromBoard(selectedBoardId, article.id);
              }
            }}
            className="shrink-0 p-1 text-gray-500 hover:text-red-400 transition-colors"
            title="Remove from board"
          >
            <Trash2 size={15} />
          </button>
        )}

        <button
          onClick={(e) => {
            e.stopPropagation();
            openArticleWebsite(article.id, article.url);
          }}
          className="shrink-0 p-1 text-gray-500 hover:text-blue-400 transition-colors"
          title="Open original website (learns interest)"
        >
          <ExternalLink size={15} />
        </button>
      </div>
    );
  }

  // Magazine View layout
  const hasImage = !!article.image_url && !imageError;
  const isReadLater = filterView === 'starred';

  return (
    <div 
      onClick={handleClick}
      data-article-id={article.id}
      data-is-read={article.is_read}
      className={clsx(
        'px-4 py-2.5 sm:py-3 cursor-pointer transition-colors border-b border-gray-900/80',
        isSelected ? 'bg-gray-800/80' : 'hover:bg-gray-900/40'
      )}
    >
      <div className="flex items-start justify-between gap-3">
        {/* Left Column: Title, Source / Time, Snippet */}
        <div className="flex-1 min-w-0">
          {/* Article Title */}
          <h3 
            onClick={handleTitleClick}
            title="Open original website"
            className={clsx(
              "text-[14px] sm:text-[15px] leading-snug tracking-tight mb-1 cursor-pointer transition-colors hover:text-blue-400 hover:underline",
              !article.is_read 
                ? "font-bold text-gray-100" 
                : "font-normal text-gray-400"
            )}
          >
            {article.title}
          </h3>

          {/* Source / relative time (e.g. "The Verge - All Posts / now") */}
          <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-1 font-medium">
            {isReadLater && (
              <>
                <button 
                  onClick={handleStarClick}
                  className="text-emerald-500 hover:text-red-400 font-medium text-xs flex items-center gap-1 cursor-pointer transition-colors group"
                  title="Remove from Read Later"
                >
                  <Bookmark size={14} className="fill-emerald-500 group-hover:fill-red-400 text-emerald-500 group-hover:text-red-400" />
                  <span className="group-hover:line-through">Read later</span>
                </button>
                <span>&middot;</span>
              </>
            )}
            <span>{article.feed_title}</span>
            <span>/</span>
            <span>{timeAgo}</span>

            {/* Likelihood badge */}
            {likelihoodBadge}

            {/* Cluster duplication badge */}
            {article.cluster_count > 1 && (
              <span 
                className="ml-1 inline-flex items-center gap-1 text-[10px] bg-gray-800 text-gray-400 px-1.5 py-0.5 rounded font-normal cursor-help"
                title={article.cluster_sources && article.cluster_sources.length > 0 ? `Also reported by: ${article.cluster_sources.join(', ')}` : `Reported in ${article.cluster_count} sources`}
              >
                <Layers size={9} />
                +{article.cluster_count - 1}
              </span>
            )}
          </div>

          {/* Snippet / Preview text */}
          {!isReadLater && article.summary && (
            <p className="text-xs text-gray-400 leading-relaxed line-clamp-2">
              {article.summary}
            </p>
          )}

          {/* Personal board note callout box */}
          {article.board_note && (
            <div className="mt-2.5 flex items-start gap-2 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-200 text-xs">
              <StickyNote size={14} className="text-amber-400 shrink-0 mt-0.5" />
              <div className="flex-1 leading-relaxed whitespace-pre-wrap text-gray-300">
                <span className="font-semibold text-amber-300 mr-1.5">Note:</span>
                {article.board_note}
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Square Thumbnail Image & Bookmark */}
        {isReadLater ? (
          <div className="flex flex-col items-end gap-1 sm:gap-1.5 shrink-0">
            {hasImage ? (
              <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-lg overflow-hidden shrink-0 shadow-sm border border-gray-800">
                <img 
                  src={article.image_url!} 
                  alt="" 
                  className="w-full h-full object-cover"
                  loading="lazy"
                  onError={() => setImageError(true)}
                />
              </div>
            ) : (
              <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-lg border border-gray-800 bg-gray-900/30 shrink-0" />
            )}
            <div className="flex items-center gap-0.5 sm:gap-1">
              <button
                onClick={handleStarClick}
                className="p-1 text-emerald-400 hover:text-red-400 transition-colors"
                title="Remove from Read Later"
              >
                <Bookmark size={15} className="fill-emerald-400 hover:fill-none" />
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setSaveToBoardModalOpen(true, article);
                }}
                className="p-1 text-gray-500 hover:text-blue-400 transition-colors"
                title="Save to Board"
              >
                <FolderPlus size={15} />
              </button>
              {selectedBoardId && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm('Remove article from this board?')) {
                      removeArticleFromBoard(selectedBoardId, article.id);
                    }
                  }}
                  className="p-1 text-gray-500 hover:text-red-400 transition-colors"
                  title="Remove from board"
                >
                  <Trash2 size={15} />
                </button>
              )}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  openArticleWebsite(article.id, article.url);
                }}
                className="p-1 text-gray-500 hover:text-blue-400 transition-colors"
                title="Open original website (learns interest)"
              >
                <ExternalLink size={15} />
              </button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-end gap-1 sm:gap-1.5 shrink-0">
            {hasImage && (
              <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-lg overflow-hidden bg-gray-800 shrink-0 border border-gray-800/80 shadow-sm">
                <img 
                  src={article.image_url!} 
                  alt="" 
                  className="w-full h-full object-cover"
                  loading="lazy"
                  onError={() => setImageError(true)}
                />
              </div>
            )}

            <div className="flex items-center gap-0.5 sm:gap-1">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setSaveToBoardModalOpen(true, article);
                }}
                className="p-1 text-gray-500 hover:text-blue-400 transition-colors"
                title="Save to Board"
              >
                <FolderPlus size={15} />
              </button>

              {selectedBoardId && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm('Remove article from this board?')) {
                      removeArticleFromBoard(selectedBoardId, article.id);
                    }
                  }}
                  className="p-1 text-gray-500 hover:text-red-400 transition-colors"
                  title="Remove from board"
                >
                  <Trash2 size={15} />
                </button>
              )}

              <button
                onClick={(e) => {
                  e.stopPropagation();
                  openArticleWebsite(article.id, article.url);
                }}
                className="p-1 text-gray-500 hover:text-blue-400 transition-colors"
                title="Open original website (learns interest)"
              >
                <ExternalLink size={15} />
              </button>

              <button
                onClick={handleStarClick}
                className={clsx(
                  "p-1 transition-colors",
                  article.is_starred ? "text-amber-400" : "text-gray-500 hover:text-amber-400"
                )}
                title={article.is_starred ? "Remove from Read Later" : "Save to Read Later"}
              >
                <Bookmark size={15} className={article.is_starred ? "fill-amber-400" : ""} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
