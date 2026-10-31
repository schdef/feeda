import React, { useState, useEffect } from 'react';
import { 
  X, 
  FolderKanban, 
  Check, 
  Plus, 
  StickyNote, 
  Loader2 
} from 'lucide-react';
import { useAppStore } from '../stores/appStore';
import { api } from '../api/client';
import clsx from 'clsx';

export function SaveToBoardModal() {
  const {
    saveToBoardModalOpen,
    targetArticleForBoard,
    setSaveToBoardModalOpen,
    boards,
    createBoard,
    saveArticleToBoard,
    removeArticleFromBoard,
    updateBoardArticleNote
  } = useAppStore();

  const [savedBoardIds, setSavedBoardIds] = useState<Set<number>>(new Set());
  const [personalNote, setPersonalNote] = useState<string>('');
  const [initialNote, setInitialNote] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isCreatingBoard, setIsCreatingBoard] = useState<boolean>(false);
  const [newBoardName, setNewBoardName] = useState<string>('');
  const [actionInProgress, setActionInProgress] = useState<number | null>(null);
  const [isSavingNote, setIsSavingNote] = useState<boolean>(false);
  const [noteSavedMessage, setNoteSavedMessage] = useState<boolean>(false);

  useEffect(() => {
    if (!saveToBoardModalOpen || !targetArticleForBoard) {
      setSavedBoardIds(new Set());
      setPersonalNote('');
      setInitialNote('');
      setIsCreatingBoard(false);
      setNewBoardName('');
      return;
    }

    let isMounted = true;
    setIsLoading(true);

    api.getArticleBoards(targetArticleForBoard.id)
      .then(res => {
        if (!isMounted) return;
        const ids = new Set((res.boards || []).map(b => b.board_id));
        setSavedBoardIds(ids);

        // Prefill personal note if any board membership has a note, or from article
        const existingNote = res.boards?.find(b => b.note)?.note || targetArticleForBoard.board_note || '';
        setPersonalNote(existingNote);
        setInitialNote(existingNote);
      })
      .catch(err => {
        console.warn('Failed to get article boards:', err);
        // Fallback: check targetArticleForBoard.board_note
        if (targetArticleForBoard.board_note) {
          setPersonalNote(targetArticleForBoard.board_note);
          setInitialNote(targetArticleForBoard.board_note);
        }
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [saveToBoardModalOpen, targetArticleForBoard]);

  if (!saveToBoardModalOpen || !targetArticleForBoard) return null;

  const handleClose = () => {
    setSaveToBoardModalOpen(false);
  };

  const handleToggleBoard = async (boardId: number) => {
    if (!targetArticleForBoard || actionInProgress !== null) return;
    setActionInProgress(boardId);

    const isCurrentlySaved = savedBoardIds.has(boardId);

    try {
      if (isCurrentlySaved) {
        await removeArticleFromBoard(boardId, targetArticleForBoard.id);
        setSavedBoardIds(prev => {
          const next = new Set(prev);
          next.delete(boardId);
          return next;
        });
      } else {
        await saveArticleToBoard(
          boardId, 
          targetArticleForBoard.id, 
          personalNote.trim() ? personalNote.trim() : undefined
        );
        setSavedBoardIds(prev => {
          const next = new Set(prev);
          next.add(boardId);
          return next;
        });
      }
    } catch (err) {
      console.error('Error toggling board membership:', err);
    } finally {
      setActionInProgress(null);
    }
  };

  const handleCreateAndSave = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = newBoardName.trim();
    if (!trimmed || !targetArticleForBoard) return;

    try {
      const newBoard = await createBoard(trimmed);
      setNewBoardName('');
      setIsCreatingBoard(false);

      // Auto-save article to the newly created board
      await saveArticleToBoard(
        newBoard.id, 
        targetArticleForBoard.id, 
        personalNote.trim() ? personalNote.trim() : undefined
      );
      setSavedBoardIds(prev => {
        const next = new Set(prev);
        next.add(newBoard.id);
        return next;
      });
    } catch (err) {
      console.error('Error creating board:', err);
    }
  };

  const handleSaveNote = async () => {
    if (!targetArticleForBoard || savedBoardIds.size === 0) return;
    setIsSavingNote(true);

    try {
      for (const boardId of savedBoardIds) {
        await updateBoardArticleNote(boardId, targetArticleForBoard.id, personalNote.trim());
      }
      setInitialNote(personalNote.trim());
      setNoteSavedMessage(true);
      setTimeout(() => setNoteSavedMessage(false), 2000);
    } catch (err) {
      console.error('Error saving note:', err);
    } finally {
      setIsSavingNote(false);
    }
  };

  const noteHasChanged = personalNote.trim() !== initialNote.trim();

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-end sm:items-center justify-center sm:p-4">
      <div className="bg-gray-900 border border-gray-800 w-full sm:max-w-md rounded-t-2xl sm:rounded-2xl overflow-hidden shadow-2xl flex flex-col max-h-[85vh] animate-in slide-in-from-bottom-4 sm:slide-in-from-bottom-0 sm:zoom-in-95 duration-200">
        
        {/* Top Header */}
        <div className="flex items-center justify-between px-4 py-3.5 border-b border-gray-800 shrink-0">
          <div className="flex items-center gap-2">
            <FolderKanban size={18} className="text-blue-400" />
            <h2 className="font-semibold text-gray-100 text-base">Save to Board</h2>
          </div>
          <button 
            onClick={handleClose}
            className="p-1 text-gray-400 hover:text-gray-200 rounded-lg hover:bg-gray-800 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Article Preview */}
        <div className="px-4 py-3 bg-gray-950/60 border-b border-gray-800 shrink-0">
          <div className="text-[11px] font-medium text-gray-400 mb-1 truncate">
            {targetArticleForBoard.feed_title}
          </div>
          <div className="text-sm font-semibold text-gray-200 line-clamp-2 leading-snug">
            {targetArticleForBoard.title}
          </div>
        </div>

        {/* Boards List & Form */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          
          {/* Quick Create Board Section */}
          {isCreatingBoard ? (
            <form onSubmit={handleCreateAndSave} className="flex gap-2">
              <input
                type="text"
                autoFocus
                placeholder="Board name"
                value={newBoardName}
                onChange={e => setNewBoardName(e.target.value)}
                className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
              <button 
                type="submit" 
                disabled={!newBoardName.trim()}
                className="bg-blue-600 hover:bg-blue-500 text-white px-3.5 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
              >
                Create
              </button>
              <button 
                type="button" 
                onClick={() => setIsCreatingBoard(false)}
                className="text-gray-400 hover:text-gray-200 px-2 py-2 text-sm"
              >
                Cancel
              </button>
            </form>
          ) : (
            <button
              onClick={() => setIsCreatingBoard(true)}
              className="w-full flex items-center justify-center gap-2 py-2 px-3 border border-dashed border-gray-700 hover:border-blue-500/50 rounded-lg text-xs font-medium text-gray-300 hover:text-blue-400 bg-gray-800/40 hover:bg-gray-800/80 transition-colors"
            >
              <Plus size={14} />
              <span>Create new board</span>
            </button>
          )}

          {/* Boards List */}
          <div className="space-y-1">
            <div className="text-[11px] font-bold text-gray-500 uppercase tracking-wider mb-2">
              Your Boards
            </div>

            {isLoading ? (
              <div className="flex items-center justify-center py-6 text-gray-500">
                <Loader2 size={20} className="animate-spin text-blue-400 mr-2" />
                <span className="text-sm">Loading boards...</span>
              </div>
            ) : boards.length === 0 ? (
              <div className="text-center py-6 text-gray-500 text-xs">
                No boards yet. Create your first board above!
              </div>
            ) : (
              boards.map(board => {
                const isSaved = savedBoardIds.has(board.id);
                const isPending = actionInProgress === board.id;

                return (
                  <div
                    key={board.id}
                    onClick={() => handleToggleBoard(board.id)}
                    className={clsx(
                      "flex items-center justify-between p-3 rounded-xl cursor-pointer transition-colors border",
                      isSaved
                        ? "bg-blue-500/10 border-blue-500/30 text-gray-100"
                        : "bg-gray-800/40 hover:bg-gray-800 border-gray-800/60 text-gray-300"
                    )}
                  >
                    <div className="flex items-center gap-3 min-w-0 flex-1 mr-3">
                      <FolderKanban 
                        size={18} 
                        className={isSaved ? "text-blue-400 shrink-0" : "text-gray-500 shrink-0"} 
                      />
                      <div className="min-w-0">
                        <div className="text-sm font-medium truncate">{board.name}</div>
                        <div className="text-xs text-gray-500">
                          {board.article_count} {board.article_count === 1 ? 'article' : 'articles'}
                        </div>
                      </div>
                    </div>

                    <button
                      type="button"
                      disabled={isPending}
                      className={clsx(
                        "flex items-center justify-center w-7 h-7 rounded-lg border text-xs font-medium transition-colors shrink-0",
                        isSaved 
                          ? "bg-blue-600 border-blue-500 text-white" 
                          : "border-gray-700 bg-gray-800 text-gray-400 hover:text-gray-200"
                      )}
                    >
                      {isPending ? (
                        <Loader2 size={13} className="animate-spin" />
                      ) : isSaved ? (
                        <Check size={14} />
                      ) : (
                        <Plus size={14} />
                      )}
                    </button>
                  </div>
                );
              })
            )}
          </div>

          {/* Personal Note Section */}
          <div className="pt-2 border-t border-gray-800">
            <div className="flex items-center justify-between mb-1.5">
              <label htmlFor="board-note" className="flex items-center gap-1.5 text-xs font-semibold text-gray-300">
                <StickyNote size={14} className="text-amber-400" />
                <span>Personal Note</span>
              </label>
              {noteSavedMessage && (
                <span className="text-[11px] text-green-400 font-medium animate-pulse">
                  Note saved!
                </span>
              )}
            </div>
            
            <textarea
              id="board-note"
              rows={3}
              value={personalNote}
              onChange={e => setPersonalNote(e.target.value)}
              placeholder="Add your personal insights, takeaways, or tags..."
              className="w-full bg-gray-800 border border-gray-700 rounded-lg p-2.5 text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500 resize-none leading-relaxed"
            />

            {savedBoardIds.size > 0 && noteHasChanged && (
              <div className="flex justify-end mt-2">
                <button
                  type="button"
                  onClick={handleSaveNote}
                  disabled={isSavingNote}
                  className="flex items-center gap-1.5 bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 text-xs px-3 py-1.5 rounded-lg transition-colors font-medium disabled:opacity-50"
                >
                  {isSavingNote && <Loader2 size={12} className="animate-spin" />}
                  <span>Save note changes</span>
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="px-4 py-3 bg-gray-950 border-t border-gray-800 flex justify-end shrink-0">
          <button
            onClick={handleClose}
            className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
