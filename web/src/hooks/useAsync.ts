import { useCallback, useEffect, useState } from "react";

/** Loads data on mount and exposes reload; keeps loading and error state in one place. */
export function useAsync<T>(load: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const reload = useCallback(() => {
    setLoading(true);
    return load().then((d) => { setData(d); setError(""); }).catch((e: Error) => setError(e.message)).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => { void reload(); }, [reload]);
  return { data, error, loading, reload };
}
