import { useEffect, useRef } from 'react';
import { useAppStore } from '../stores/appStore';
import type { LikelihoodFilter } from '../types';

export function useKeyboard() {
  const {
    navigateArticle,
    selectedArticle,
    markArticleRead,
    markArticleUnread,
    toggleArticleStar,
    markAllAsRead,
    refreshFeed,
    refreshAllFeeds,
    selectedFeedId,
    selectArticle,
    openArticleWebsite,
    setFilterView,
    likelihoodFilter,
    setLikelihoodFilter,
    shortcutsModalOpen,
    setShortcutsModalOpen,
    boardSwitcherModalOpen,
    setBoardSwitcherModalOpen
  } = useAppStore();

  const lastGPressRef = useRef<number>(0);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if focus is in an input or textarea
      if (
        document.activeElement?.tagName === 'INPUT' ||
        document.activeElement?.tagName === 'TEXTAREA' ||
        (document.activeElement as HTMLElement)?.isContentEditable
      ) {
        // Still allow Escape to blur or close
        if (e.key === 'Escape') {
          (document.activeElement as HTMLElement)?.blur();
        }
        return;
      }

      const now = Date.now();
      const isGChord = now - lastGPressRef.current < 1500;

      // Two-key chord handler for 'g' navigation (gt, gf, gu, gs, ga)
      if (isGChord) {
        lastGPressRef.current = 0;
        switch (e.key.toLowerCase()) {
          case 't':
            e.preventDefault();
            setFilterView('today');
            return;
          case 'f':
            e.preventDefault();
            setFilterView('for-you');
            return;
          case 'u':
            e.preventDefault();
            setFilterView('unread');
            return;
          case 's':
            e.preventDefault();
            setFilterView('starred');
            return;
          case 'a':
            e.preventDefault();
            setFilterView('all');
            return;
        }
      }

      // Record 'g' press for chord
      if (e.key === 'g' && !e.metaKey && !e.ctrlKey && !e.altKey && !e.shiftKey) {
        lastGPressRef.current = now;
        return;
      }

      // Mark read tiers: Shift+A, Shift+D, Shift+W
      if (e.shiftKey && (e.key === 'A' || e.key === 'a')) {
        e.preventDefault();
        markAllAsRead('all');
        return;
      }
      if (e.shiftKey && (e.key === 'D' || e.key === 'd')) {
        e.preventDefault();
        markAllAsRead('1d');
        return;
      }
      if (e.shiftKey && (e.key === 'W' || e.key === 'w')) {
        e.preventDefault();
        markAllAsRead('1w');
        return;
      }

      // Show Shortcuts Modal: '?' or 'Shift + /'
      if (e.key === '?' || (e.key === '/' && e.shiftKey)) {
        e.preventDefault();
        setShortcutsModalOpen(true);
        return;
      }

      // Quick Board Switcher: 'b'
      if (e.key === 'b' && !e.metaKey && !e.ctrlKey && !e.altKey) {
        e.preventDefault();
        setBoardSwitcherModalOpen(true);
        return;
      }

      // Likelihood keys: 1 (Likely), 2 (All), 3 (Less Likely), l (Cycle)
      if (e.key === '1') {
        setLikelihoodFilter('likely');
        return;
      }
      if (e.key === '2') {
        setLikelihoodFilter('all');
        return;
      }
      if (e.key === '3') {
        setLikelihoodFilter('not_likely');
        return;
      }
      if (e.key === 'l' && !e.metaKey && !e.ctrlKey && !e.altKey) {
        const cycleMap: Record<string, LikelihoodFilter> = {
          likely: 'all',
          all: 'not_likely',
          not_likely: 'likely'
        };
        setLikelihoodFilter(cycleMap[likelihoodFilter] || 'all');
        return;
      }

      // Other actions
      switch (e.key) {
        case 'j':
          navigateArticle('next');
          break;
        case 'k':
          navigateArticle('prev');
          break;
        case 'm':
          if (selectedArticle) {
            if (selectedArticle.is_read) {
              markArticleUnread(selectedArticle.id);
            } else {
              markArticleRead(selectedArticle.id);
            }
          }
          break;
        case 's':
          if (selectedArticle) {
            toggleArticleStar(selectedArticle.id);
          }
          break;
        case 'v':
          if (selectedArticle?.url) {
            openArticleWebsite(selectedArticle.id, selectedArticle.url);
          }
          break;
        case 'r':
          if (selectedFeedId) {
            refreshFeed(selectedFeedId);
          } else {
            refreshAllFeeds();
          }
          break;
        case '/':
          e.preventDefault();
          const searchInput = document.getElementById('search-input');
          if (searchInput) {
            searchInput.focus();
          }
          break;
        case 'Escape':
          if (shortcutsModalOpen) {
            setShortcutsModalOpen(false);
          } else if (boardSwitcherModalOpen) {
            setBoardSwitcherModalOpen(false);
          } else if (selectedArticle) {
            selectArticle(null);
          }
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [
    navigateArticle,
    selectedArticle,
    markArticleRead,
    markArticleUnread,
    toggleArticleStar,
    markAllAsRead,
    refreshFeed,
    refreshAllFeeds,
    selectedFeedId,
    selectArticle,
    openArticleWebsite,
    setFilterView,
    likelihoodFilter,
    setLikelihoodFilter,
    shortcutsModalOpen,
    setShortcutsModalOpen,
    boardSwitcherModalOpen,
    setBoardSwitcherModalOpen
  ]);
}
