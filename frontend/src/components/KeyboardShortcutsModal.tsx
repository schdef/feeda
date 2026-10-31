import React from 'react';
import { X, Keyboard } from 'lucide-react';
import { useAppStore } from '../stores/appStore';

interface ShortcutItem {
  keys: string[];
  description: string;
}

interface ShortcutCategory {
  title: string;
  shortcuts: ShortcutItem[];
}

export function KeyboardShortcutsModal() {
  const { shortcutsModalOpen, setShortcutsModalOpen } = useAppStore();

  if (!shortcutsModalOpen) return null;

  const categories: ShortcutCategory[] = [
    {
      title: 'Navigation',
      shortcuts: [
        { keys: ['j'], description: 'Next article' },
        { keys: ['k'], description: 'Previous article' },
        { keys: ['g', 't'], description: 'Go to Today' },
        { keys: ['g', 'f'], description: 'Go to For You' },
        { keys: ['g', 'u'], description: 'Go to Unread' },
        { keys: ['g', 's'], description: 'Go to Read Later' },
        { keys: ['g', 'a'], description: 'Go to All' },
        { keys: ['b'], description: 'Quick Board Switcher' },
      ],
    },
    {
      title: 'Likelihood',
      shortcuts: [
        { keys: ['1'], description: 'Likely articles' },
        { keys: ['2'], description: 'All articles' },
        { keys: ['3'], description: 'Less Likely articles' },
        { keys: ['l'], description: 'Cycle likelihood filter' },
      ],
    },
    {
      title: 'Mark Read Tiers',
      shortcuts: [
        { keys: ['Shift', 'A'], description: 'Mark all as read' },
        { keys: ['Shift', 'D'], description: 'Mark older than 1 day as read' },
        { keys: ['Shift', 'W'], description: 'Mark older than 1 week as read' },
      ],
    },
    {
      title: 'Reading & Actions',
      shortcuts: [
        { keys: ['m'], description: 'Toggle read / unread' },
        { keys: ['s'], description: 'Toggle star / Read later' },
        { keys: ['v'], description: 'Open website' },
        { keys: ['r'], description: 'Refresh current feed' },
        { keys: ['/'], description: 'Focus search' },
        { keys: ['?'], description: 'Show keyboard shortcuts' },
        { keys: ['Esc'], description: 'Close reader or modal' },
      ],
    },
  ];

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs animate-in fade-in duration-150"
      onClick={() => setShortcutsModalOpen(false)}
    >
      <div 
        className="bg-gray-900 border border-gray-800 rounded-xl shadow-2xl w-full max-w-2xl overflow-hidden flex flex-col max-h-[85vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800/80 bg-gray-950/60">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20">
              <Keyboard size={18} />
            </div>
            <div>
              <h2 className="text-base font-semibold text-gray-100">Keyboard Shortcuts</h2>
              <p className="text-xs text-gray-400">Navigate and manage feeds with your keyboard</p>
            </div>
          </div>
          <button 
            onClick={() => setShortcutsModalOpen(false)}
            className="p-1.5 text-gray-400 hover:text-gray-200 hover:bg-gray-800/60 rounded-lg transition-colors"
            title="Close"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 overflow-y-auto space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {categories.map((cat) => (
              <div key={cat.title} className="space-y-2.5">
                <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider px-1">
                  {cat.title}
                </h3>
                <div className="bg-gray-950/50 rounded-lg border border-gray-800/60 p-2 divide-y divide-gray-800/40">
                  {cat.shortcuts.map((item, idx) => (
                    <div 
                      key={idx}
                      className="flex items-center justify-between py-2 px-2 text-xs hover:bg-gray-800/30 rounded transition-colors"
                    >
                      <span className="text-gray-300 font-medium">{item.description}</span>
                      <div className="flex items-center gap-1">
                        {item.keys.map((k, kIdx) => (
                          <React.Fragment key={kIdx}>
                            {kIdx > 0 && <span className="text-gray-500 text-[10px]">+</span>}
                            <kbd className="px-2 py-0.5 text-[11px] font-mono font-medium rounded bg-gray-800 border border-gray-700 text-gray-200 shadow-xs min-w-[20px] text-center">
                              {k}
                            </kbd>
                          </React.Fragment>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="px-5 py-3 bg-gray-950/60 border-t border-gray-800 flex justify-between items-center text-xs text-gray-500">
          <span>Press <kbd className="px-1.5 py-0.5 rounded bg-gray-800 border border-gray-700 text-gray-300 font-mono text-[10px]">Esc</kbd> anytime to dismiss</span>
          <button
            onClick={() => setShortcutsModalOpen(false)}
            className="px-3.5 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-200 font-medium rounded-lg text-xs transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
