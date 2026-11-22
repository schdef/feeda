import React, { useEffect } from 'react';
import { useAppStore } from '../stores/appStore';
import { AddFeedModal } from './AddFeedModal';
import { SelectFolderModal } from './SelectFolderModal';
import { SaveToBoardModal } from './SaveToBoardModal';
import { CreateBoardModal } from './CreateBoardModal';
import { KeyboardShortcutsModal } from './KeyboardShortcutsModal';
import { BoardSwitcherModal } from './BoardSwitcherModal';
import { ManageFeedsModal } from './ManageFeedsModal';
import { BottomNav } from './BottomNav';

interface LayoutProps {
  sidebar: React.ReactNode;
  articleList: React.ReactNode;
  articleReader: React.ReactNode;
}

export function Layout({ sidebar, articleList, articleReader }: LayoutProps) {
  const { selectedArticle, addFeedModalOpen, selectFolderModalOpen, sidebarOpen, setSidebarOpen } = useAppStore();

  useEffect(() => {
    const handlePopState = () => {
      const state = useAppStore.getState();
      if (state.selectedArticle) {
        state.selectArticle(null);
      } else if (state.manageFeedsModalOpen) {
        state.setManageFeedsModalOpen(false);
      } else if (state.discoverViewOpen) {
        state.setDiscoverViewOpen(false);
      } else if (state.sidebarOpen) {
        state.setSidebarOpen(false);
      }
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  return (
    <div className="flex h-screen overflow-hidden bg-gray-950 text-gray-200">
      {/* 1. Mobile Backdrop overlay when drawer is open */}
      {sidebarOpen && (
        <div 
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 bg-black/70 backdrop-blur-xs z-40 md:hidden transition-opacity duration-200"
        />
      )}

      {/* 2. Sidebar / Mobile Slide-in Drawer */}
      <aside className={`
        fixed inset-y-0 left-0 z-50 w-72 bg-gray-950 border-r border-gray-800/80 transition-transform duration-200 ease-in-out md:static md:w-64 md:translate-x-0 md:flex md:flex-col md:z-10 shrink-0
        ${sidebarOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full'}
      `}>
        {sidebar}
      </aside>

      {/* 3. Main Article List Stream */}
      <main className={`
        flex flex-col min-w-0 bg-gray-950 transition-all duration-200
        ${selectedArticle 
          ? 'hidden md:flex md:w-80 lg:w-[420px] xl:w-[460px] md:shrink-0 md:flex-none border-r border-gray-800/80' 
          : 'flex-1 w-full'
        }
      `}>
        {articleList}
      </main>

      {/* 4. Article Reader Panel (Right on desktop, Fullscreen on mobile) */}
      <section className={`
        bg-gray-950 transition-all duration-200
        ${!selectedArticle 
          ? 'hidden' 
          : 'fixed inset-0 z-50 md:static md:flex flex-1 min-w-0'
        }
      `}>
        {articleReader}
      </section>

      {/* 5. Mobile Bottom Navigation Bar */}
      {!selectedArticle && <BottomNav />}

      {/* 6. Modals */}
      {addFeedModalOpen && <AddFeedModal />}
      {selectFolderModalOpen && <SelectFolderModal />}
      <SaveToBoardModal />
      <CreateBoardModal />
      <KeyboardShortcutsModal />
      <BoardSwitcherModal />
      <ManageFeedsModal />
    </div>
  );
}
