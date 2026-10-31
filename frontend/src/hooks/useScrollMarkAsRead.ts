import { useEffect, useRef } from 'react';

interface Options {
  containerRef: React.RefObject<HTMLDivElement | null>;
  onMarkRead: (articleId: number) => void;
  enabled?: boolean;
}

export function useScrollMarkAsRead({
  containerRef,
  onMarkRead,
  enabled = true
}: Options) {
  const lastScrollTopRef = useRef<number>(0);
  const tickingRef = useRef<boolean>(false);
  const markedIdsRef = useRef<Set<number>>(new Set());

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !enabled) return;

    const checkScrolledArticles = () => {
      const currentScrollTop = container.scrollTop;
      const isScrollingDown = currentScrollTop > lastScrollTopRef.current;
      lastScrollTopRef.current = currentScrollTop;

      const distanceFromBottom = container.scrollHeight - currentScrollTop - container.clientHeight;
      const isAtBottom = distanceFromBottom <= 60;

      if (!isScrollingDown && !isAtBottom) {
        tickingRef.current = false;
        return;
      }

      const containerRect = container.getBoundingClientRect();
      // Threshold: article bottom has passed above container's top boundary
      const topThreshold = containerRect.top;

      const articleElements = container.querySelectorAll<HTMLElement>('[data-article-id]');

      articleElements.forEach((el) => {
        const idStr = el.getAttribute('data-article-id');
        const isRead = el.getAttribute('data-is-read') === 'true';

        if (!idStr || isRead) return;

        const id = parseInt(idStr, 10);
        if (markedIdsRef.current.has(id)) return;

        const rect = el.getBoundingClientRect();

        // If the bottom of the article card is above the top of the container,
        // it is completely out of view above the scroll viewport!
        if (rect.bottom <= topThreshold + 8) {
          markedIdsRef.current.add(id);
          onMarkRead(id);
        } else if (isAtBottom && rect.top < containerRect.bottom) {
          // When scrolled to the bottom of the feed, mark visible articles as read
          markedIdsRef.current.add(id);
          onMarkRead(id);
        }
      });

      tickingRef.current = false;
    };

    const handleScroll = () => {
      if (!tickingRef.current) {
        tickingRef.current = true;
        requestAnimationFrame(checkScrolledArticles);
      }
    };

    container.addEventListener('scroll', handleScroll, { passive: true });

    return () => {
      container.removeEventListener('scroll', handleScroll);
    };
  }, [containerRef, onMarkRead, enabled]);

  return { markedIdsRef };
}
