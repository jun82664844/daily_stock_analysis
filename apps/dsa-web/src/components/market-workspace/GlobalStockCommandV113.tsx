import { Search, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { MarketSearchItem } from '../../api/marketWorkspace';

type Props = {
  language: 'zh' | 'en';
  loading: boolean;
  results: MarketSearchItem[];
  onSearch: (query: string) => void;
  onSelect: (item: MarketSearchItem) => void;
};

export default function GlobalStockCommandV113({ language, loading, results, onSearch, onSelect }: Props) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const en = language === 'en';

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setOpen(true);
        window.setTimeout(() => inputRef.current?.focus(), 0);
      }
      if (event.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const submit = () => {
    const trimmed = query.trim();
    if (!trimmed) return;
    setOpen(true);
    onSearch(trimmed);
  };

  return (
    <section className="border-y border-border/70 py-5" aria-label={en ? 'Global stock search' : '全局股票搜索'}>
      <div className="flex flex-col gap-3 md:flex-row md:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-secondary-text" />
          <input
            ref={inputRef}
            type="search"
            value={query}
            aria-label={en ? 'Search stock symbol or company name' : '搜索股票代码或公司名称'}
            placeholder={en ? 'Search AAPL, 600519, Tencent...' : '搜索 AAPL、600519、腾讯...'}
            onFocus={() => setOpen(true)}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => { if (event.key === 'Enter') submit(); }}
            className="h-12 w-full rounded-lg border border-border bg-surface pl-11 pr-11 text-foreground outline-none focus:border-primary"
          />
          {query ? (
            <button type="button" aria-label={en ? 'Clear search' : '清空搜索'} onClick={() => setQuery('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-secondary-text hover:text-foreground">
              <X className="h-5 w-5" />
            </button>
          ) : null}
        </div>
        <button type="button" onClick={submit} disabled={!query.trim() || loading} className="btn-primary h-12 px-6">
          <Search className="h-4 w-4" />
          {loading ? (en ? 'Searching' : '搜索中') : (en ? 'Search' : '搜索')}
        </button>
        <span className="text-xs text-secondary-text">Ctrl / Cmd + K</span>
      </div>
      {open && results.length ? (
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3" role="listbox" aria-label={en ? 'Search results' : '搜索结果'}>
          {results.map((item) => (
            <button
              type="button"
              key={`${item.market}:${item.symbol}`}
              onClick={() => { onSelect(item); setOpen(false); }}
              className="flex min-h-16 items-center justify-between rounded-lg border border-border bg-surface px-4 py-3 text-left hover:border-primary"
              aria-label={`${item.symbol} ${item.name}`}
            >
              <span><strong className="block text-foreground">{item.symbol}</strong><span className="text-sm text-secondary-text">{item.name}</span></span>
              <span className="text-xs uppercase text-primary">{item.market}</span>
            </button>
          ))}
        </div>
      ) : null}
    </section>
  );
}
