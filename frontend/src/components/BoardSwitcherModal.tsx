import { useState, useEffect, useRef } from 'react';
import { X, FolderKanban, Search, Plus, Check } from 'lucide-react';
import { useAppStore } from '../stores/appStore';
import clsx from 'clsx';

export function BoardSwitcherModal() {
  const { 
    boardSwitcherModalOpen, 
    setBoardSwitcherModalOpen, 
    boards, 
    selectedBoardId, 
    selectBoard,
    setCreateBoardModalOpen 
  } = useAppStore();

  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const filteredBoards = boards.filter(b => 
    b.name.toLowerCase().includes(query.toLowerCase()) || 
    (b.description && b.description.toLowerCase().includes(query.toLowerCase()))
  );

  useEffect(() => {
    if (boardSwitcherModalOpen) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [boardSwitcherModalOpen]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  if (!boardSwitcherModalOpen) return null;

  const handleSelect = (boardId: number) => {
    selectBoard(boardId);
    setBoardSwitcherModalOpen(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(prev => (filteredBoards.length > 0 ? (prev + 1) % filteredBoards.length : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(prev => (filteredBoards.length > 0 ? (prev - 1 + filteredBoards.length) % filteredBoards.length : 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filteredBoards.length > 0 && filteredBoards[selectedIndex]) {
        handleSelect(filteredBoards[selectedIndex].id);
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      setBoardSwitcherModalOpen(false);
    }
  };

  return (
    <div 
      className="fixed inset-0 z-50 flex items-start justify-center pt-20 p-4 bg-black/70 backdrop-blur-xs animate-in fade-in duration-150"
      onClick={() => setBoardSwitcherModalOpen(false)}
    >
      <div 
        className="bg-gray-900 border border-gray-800 rounded-xl shadow-2xl w-full max-w-lg overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        {/* Search header */}
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-gray-800 bg-gray-950/60">
          <Search size={18} className="text-gray-400 shrink-0" />
          <input 
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Switch to board... (type to filter)"
            className="flex-1 bg-transparent text-sm text-gray-100 placeholder-gray-500 focus:outline-none"
          />
          <button 
            onClick={() => setBoardSwitcherModalOpen(false)}
            className="p-1 text-gray-400 hover:text-gray-200 rounded-md transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Boards List */}
        <div className="p-2 max-h-80 overflow-y-auto space-y-1">
          {filteredBoards.length === 0 ? (
            <div className="text-center py-8 text-gray-500 text-xs">
              {boards.length === 0 ? (
                <div className="space-y-3">
                  <p>You haven't created any boards yet.</p>
                  <button
                    onClick={() => {
                      setBoardSwitcherModalOpen(false);
                      setCreateBoardModalOpen(true);
                    }}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-gray-100 rounded-lg text-xs font-medium transition-colors"
                  >
                    <Plus size={14} />
                    <span>Create a board</span>
                  </button>
                </div>
              ) : (
                <p>No boards match "{query}"</p>
              )}
            </div>
          ) : (
            filteredBoards.map((board, idx) => {
              const isSelected = selectedBoardId === board.id;
              const isHighlighted = idx === selectedIndex;

              return (
                <div
                  key={board.id}
                  onClick={() => handleSelect(board.id)}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={clsx(
                    "flex items-center justify-between px-3 py-2.5 rounded-lg cursor-pointer transition-colors border text-sm",
                    isHighlighted 
                      ? "bg-gray-800 border-gray-700/80 text-gray-100" 
                      : "bg-transparent border-transparent text-gray-300 hover:bg-gray-800/40"
                  )}
                >
                  <div className="flex items-center gap-3 min-w-0 flex-1 mr-3">
                    <FolderKanban 
                      size={18} 
                      className={isSelected ? "text-blue-400 shrink-0" : "text-gray-500 shrink-0"} 
                    />
                    <div className="min-w-0">
                      <div className="font-medium truncate flex items-center gap-2">
                        <span>{board.name}</span>
                        {isSelected && (
                          <span className="text-[10px] bg-blue-500/10 text-blue-400 border border-blue-500/20 px-1.5 py-0.2 rounded font-normal">
                            Current
                          </span>
                        )}
                      </div>
                      {board.description && (
                        <div className="text-xs text-gray-500 truncate">{board.description}</div>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-xs text-gray-500 font-mono">
                      {board.article_count} {board.article_count === 1 ? 'article' : 'articles'}
                    </span>
                    {isSelected && <Check size={16} className="text-blue-400" />}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-2.5 bg-gray-950/60 border-t border-gray-800 flex items-center justify-between text-[11px] text-gray-500">
          <div className="flex items-center gap-3">
            <span><kbd className="px-1.5 py-0.5 rounded bg-gray-800 border border-gray-700 text-gray-300 font-mono text-[10px]">↑↓</kbd> Navigate</span>
            <span><kbd className="px-1.5 py-0.5 rounded bg-gray-800 border border-gray-700 text-gray-300 font-mono text-[10px]">↵</kbd> Select</span>
            <span><kbd className="px-1.5 py-0.5 rounded bg-gray-800 border border-gray-700 text-gray-300 font-mono text-[10px]">Esc</kbd> Close</span>
          </div>
          <button
            onClick={() => {
              setBoardSwitcherModalOpen(false);
              setCreateBoardModalOpen(true);
            }}
            className="flex items-center gap-1 text-blue-400 hover:text-blue-300 font-medium"
          >
            <Plus size={13} />
            <span>New Board</span>
          </button>
        </div>
      </div>
    </div>
  );
}
