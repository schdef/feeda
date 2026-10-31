import { useEffect, useRef } from 'react';
import { api } from '../api/client';

export function useDwellTime(articleId: number | undefined) {
  const startTimeRef = useRef<number | null>(null);

  useEffect(() => {
    if (!articleId) return;

    startTimeRef.current = Date.now();

    return () => {
      if (startTimeRef.current && articleId) {
        const dwellTime = Math.floor((Date.now() - startTimeRef.current) / 1000);
        let action = 'skip';
        if (dwellTime >= 5 && dwellTime <= 30) {
          action = 'read_short';
        } else if (dwellTime > 30) {
          action = 'read_long';
        }

        api.logInteraction(articleId, action, dwellTime).catch(console.error);
      }
    };
  }, [articleId]);
}
