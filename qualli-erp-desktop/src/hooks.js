import { useCallback, useEffect, useRef, useState } from 'react';
import { errorMessage } from './api/client';

/** Lädt eine paginierte Liste neu, sobald sich die Parameter ändern. */
export function usePagedList(fetcher, params) {
  const [data, setData] = useState({ items: [], page: 1, pages: 1, total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const key = JSON.stringify(params);
  const requestId = useRef(0);

  const reload = useCallback(async () => {
    const id = ++requestId.current;
    setLoading(true);
    setError('');
    try {
      const result = await fetcher(JSON.parse(key));
      if (id === requestId.current) setData(result);
    } catch (e) {
      if (id === requestId.current) setError(errorMessage(e));
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, [fetcher, key]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { data, loading, error, reload, setError };
}

export function useDebounced(value, delay = 300) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}
