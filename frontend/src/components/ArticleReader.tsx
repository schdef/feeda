import { useEffect, useRef, useState } from 'react';
import { 
  Bookmark,
  ExternalLink, 
  ThumbsUp, 
  ThumbsDown, 
  CheckCircle, 
  Circle, 
  ChevronLeft, 
  X,
  FolderPlus,
  FolderKanban,
  StickyNote,
  Pencil,
  Layers
} from 'lucide-react';
import { format } from 'date-fns';
import { useAppStore } from '../stores/appStore';
import { useDwellTime } from '../hooks/useDwellTime';
import { api } from '../api/client';
import type { BoardMembership } from '../types';

export function ArticleReader() {
  const { 
    selectedArticle, 
    selectArticle,
    markArticleRead, 
    markArticleUnread, 
    toggleArticleStar,
    voteArticle,
    openArticleWebsite,
    setSaveToBoardModalOpen,
    saveToBoardModalOpen
  } = useAppStore();

  const contentRef = useRef<HTMLDivElement>(null);
  const [articleBoards, setArticleBoards] = useState<BoardMembership[]>([]);

  useDwellTime(selectedArticle?.id);

  // Scroll to top and fetch article boards when article changes
  useEffect(() => {
    if (contentRef.current) {
      contentRef.current.scrollTop = 0;
    }

    if (selectedArticle) {
      let isMounted = true;
      api.getArticleBoards(selectedArticle.id)
        .then(res => {
          if (isMounted) setArticleBoards(res.boards || []);
        })
        .catch(() => {
          if (isMounted) setArticleBoards([]);
        });
      return () => {
        isMounted = false;
      };
    } else {
      setArticleBoards([]);
    }
  }, [selectedArticle?.id, saveToBoardModalOpen]);

  if (!selectedArticle) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-gray-500 h-full">
        <div className="w-16 h-16 mb-4 rounded-full bg-gray-800 flex items-center justify-center">
          <CheckCircle size={32} className="text-gray-600" />
        </div>
        <p className="text-lg font-medium text-gray-400">No article selected</p>
        <p className="text-sm mt-2">Select an article from the list to start reading</p>
        <div className="mt-8 text-xs text-gray-600 space-y-1 text-center">
          <p>Keyboard shortcuts:</p>
          <p><kbd className="bg-gray-800 px-1.5 py-0.5 rounded">j</kbd> / <kbd className="bg-gray-800 px-1.5 py-0.5 rounded">k</kbd> to navigate</p>
          <p><kbd className="bg-gray-800 px-1.5 py-0.5 rounded">m</kbd> to toggle read</p>
          <p><kbd className="bg-gray-800 px-1.5 py-0.5 rounded">s</kbd> to star</p>
        </div>
      </div>
    );
  }

  const publishedDate = selectedArticle.published_at 
    ? format(new Date(selectedArticle.published_at), 'PPP at p')
    : '';

  return (
    <div className="flex flex-col h-full w-full relative bg-gray-950">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-3 py-2.5 border-b border-gray-800/80 bg-gray-950/90 backdrop-blur-md shrink-0">
        {/* Mobile Back Button */}
        <button 
          onClick={() => selectArticle(null)}
          className="md:hidden p-1.5 -ml-1 text-gray-400 hover:text-gray-100 hover:bg-gray-800 rounded-md transition-colors"
          title="Back to articles"
        >
          <ChevronLeft size={22} />
        </button>
        <button 
          onClick={() => selectedArticle.is_read ? markArticleUnread(selectedArticle.id) : markArticleRead(selectedArticle.id)}
          className="p-2 text-gray-400 hover:text-gray-200 hover:bg-gray-800 rounded-md transition-colors"
          title={selectedArticle.is_read ? "Keep unread (m)" : "Mark read (m)"}
        >
          {selectedArticle.is_read ? <CheckCircle size={18} className="text-green-500" /> : <Circle size={18} />}
        </button>
        
        <button 
          onClick={() => toggleArticleStar(selectedArticle.id)}
          className="p-2 text-gray-400 hover:text-gray-200 hover:bg-gray-800 rounded-md transition-colors"
          title={selectedArticle.is_starred ? "Remove from Read Later (s)" : "Save to Read Later (s)"}
        >
          <Bookmark size={18} className={selectedArticle.is_starred ? "text-amber-500 fill-amber-500" : ""} />
        </button>
        
        <div className="w-px h-5 bg-gray-700 mx-1" />
        
        <button 
          onClick={() => voteArticle(selectedArticle.id, selectedArticle.user_vote === 1 ? 0 : 1)}
          className={`p-2 rounded-md transition-colors ${selectedArticle.user_vote === 1 ? 'text-blue-500 bg-blue-500/10' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'}`}
          title="More like this"
        >
          <ThumbsUp size={18} />
        </button>
        
        <button 
          onClick={() => voteArticle(selectedArticle.id, selectedArticle.user_vote === -1 ? 0 : -1)}
          className={`p-2 rounded-md transition-colors ${selectedArticle.user_vote === -1 ? 'text-red-500 bg-red-500/10' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'}`}
          title="Less like this"
        >
          <ThumbsDown size={18} />
        </button>

        <div className="w-px h-5 bg-gray-700 mx-1" />

        <button 
          onClick={() => setSaveToBoardModalOpen(true, selectedArticle)}
          className="p-2 text-gray-400 hover:text-blue-400 hover:bg-gray-800 rounded-md transition-colors flex items-center gap-1.5 text-sm font-medium"
          title="Save to Board"
        >
          <FolderPlus size={18} />
          <span className="hidden sm:inline">Save to Board</span>
        </button>
        
        <div className="flex-1" />
        
        <button 
          onClick={() => openArticleWebsite(selectedArticle.id, selectedArticle.url)}
          className="p-2 text-gray-400 hover:text-gray-200 hover:bg-gray-800 rounded-md transition-colors flex items-center gap-2 text-sm font-medium"
          title="Open original website (learns interest) (v)"
        >
          <span className="hidden sm:inline">Original</span>
          <ExternalLink size={18} />
        </button>

        <button 
          onClick={() => selectArticle(null)}
          className="p-2 text-gray-400 hover:text-gray-200 hover:bg-gray-800 rounded-md transition-colors ml-1"
          title="Close article (Esc)"
        >
          <X size={20} />
        </button>
      </div>

      {/* Content */}
      <div 
        ref={contentRef}
        className="flex-1 overflow-y-auto px-6 py-8 md:px-12 lg:px-24"
      >
        <div className="max-w-3xl mx-auto">
          {/* Article Header */}
          <div className="mb-8 space-y-4">
            <div className="flex items-center gap-2 text-sm text-gray-400">
              {selectedArticle.feed_favicon_url && (
                <img src={selectedArticle.feed_favicon_url} alt="" className="w-4 h-4 rounded-sm" />
              )}
              <span className="font-medium text-gray-300">{selectedArticle.feed_title}</span>
              {selectedArticle.author && (
                <>
                  <span>•</span>
                  <span>{selectedArticle.author}</span>
                </>
              )}
              <span>•</span>
              <span>{publishedDate}</span>
            </div>
            
            <h1 className="text-3xl md:text-4xl font-bold text-gray-100 leading-tight">
              {selectedArticle.title}
            </h1>

            {/* Multi-source cluster attribution */}
            {selectedArticle.cluster_count > 1 && selectedArticle.cluster_sources && selectedArticle.cluster_sources.length > 0 && (
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-900/90 border border-gray-800 text-xs text-gray-400">
                <Layers size={14} className="text-blue-400 shrink-0" />
                <span>
                  <span className="text-gray-300 font-medium">Also published in:</span>{' '}
                  {selectedArticle.cluster_sources.join(', ')}
                </span>
              </div>
            )}
          </div>

          {/* Personal Boards & Notes Display */}
          {(articleBoards.length > 0 || selectedArticle.board_note) && (
            <div className="p-3.5 rounded-xl bg-gray-900 border border-gray-800/80 mb-6 space-y-2.5">
              {articleBoards.length > 0 && (
                <div className="flex items-center gap-2 flex-wrap text-xs">
                  <span className="text-gray-400 font-medium flex items-center gap-1.5">
                    <FolderKanban size={14} className="text-blue-400" />
                    Saved to:
                  </span>
                  {articleBoards.map(b => (
                    <span 
                      key={b.board_id}
                      className="inline-flex items-center gap-1 bg-blue-500/10 text-blue-300 border border-blue-500/20 px-2 py-0.5 rounded-md text-xs font-medium"
                    >
                      {b.board_name}
                    </span>
                  ))}
                  <button
                    onClick={() => setSaveToBoardModalOpen(true, selectedArticle)}
                    className="text-[11px] text-gray-400 hover:text-blue-400 underline underline-offset-2 ml-1"
                  >
                    Manage
                  </button>
                </div>
              )}

              {/* Note callout box */}
              {(selectedArticle.board_note || articleBoards.some(b => b.note)) && (
                <div 
                  onClick={() => setSaveToBoardModalOpen(true, selectedArticle)}
                  className="group cursor-pointer flex items-start gap-2.5 p-2.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/15 border border-amber-500/20 text-xs transition-colors"
                  title="Click to edit personal note"
                >
                  <StickyNote size={15} className="text-amber-400 shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="font-semibold text-amber-300 text-[11px] uppercase tracking-wider">Personal Note</span>
                      <span className="text-[10px] text-gray-500 group-hover:text-amber-300 flex items-center gap-1">
                        <Pencil size={10} />
                        Edit
                      </span>
                    </div>
                    <p className="text-gray-200 leading-relaxed whitespace-pre-wrap">
                      {selectedArticle.board_note || articleBoards.find(b => b.note)?.note}
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Article Body */}
          <div className="prose prose-invert prose-blue max-w-none">
            {selectedArticle.content ? (
              <div dangerouslySetInnerHTML={{ __html: selectedArticle.content }} />
            ) : selectedArticle.summary ? (
              <div dangerouslySetInnerHTML={{ __html: selectedArticle.summary }} />
            ) : (
              <p className="text-gray-500 italic">No content available for this article.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
