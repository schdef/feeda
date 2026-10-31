import { useEffect, useRef, useCallback } from 'react';

export function useInfiniteScroll(onLoadMore: () => void, hasMore: boolean, isLoading: boolean) {
  const observerRef = useRef<IntersectionObserver | null>(null);
  const loadMoreRef = useRef<HTMLDivElement | null>(null);

  const handleObserver = useCallback(
    (entries: IntersectionObserverEntry[]) => {
      const target = entries[0];
      if (target.isIntersecting && hasMore && !isLoading) {
        onLoadMore();
      }
    },
    [onLoadMore, hasMore, isLoading]
  );

  useEffect(() => {
    const option = {
      root: null,
      rootMargin: '200px',
      threshold: 0,
    };
    observerRef.current = new IntersectionObserver(handleObserver, option);
    if (loadMoreRef.current) {
      observerRef.current.observe(loadMoreRef.current);
    }
    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect();
      }
    };
  }, [handleObserver]);

  return loadMoreRef;
}
