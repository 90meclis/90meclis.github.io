import { useEffect, useState, type DependencyList } from "react";
import { NoDataError } from "./data";

export interface AsyncState<T> { data: T | undefined; loading: boolean; error: "offline" | "error" | null }

const cache = new Map<string, { at: number; value: unknown }>();
const TTL = 120_000;

/** Basit veri kancası: önbellek (2 dk), yükleniyor/hata durumları. */
export function useAsync<T>(key: string | null, fn: () => Promise<T>, deps: DependencyList = []): AsyncState<T> {
  const cached = key ? (cache.get(key) as { at: number; value: T } | undefined) : undefined;
  const fresh = cached && Date.now() - cached.at < TTL;
  const [state, setState] = useState<AsyncState<T>>({ data: cached?.value, loading: !fresh && key !== null, error: null });

  useEffect(() => {
    if (key === null) return;
    const c = cache.get(key) as { at: number; value: T } | undefined;
    if (c && Date.now() - c.at < TTL) {
      setState({ data: c.value, loading: false, error: null });
      return;
    }
    let alive = true;
    setState({ data: c?.value, loading: true, error: null });
    fn()
      .then((value) => {
        cache.set(key, { at: Date.now(), value });
        if (alive) setState({ data: value, loading: false, error: null });
      })
      .catch((e: unknown) => {
        if (alive) setState({ data: c?.value, loading: false, error: e instanceof NoDataError ? "offline" : "error" });
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, ...deps]);

  return state;
}
