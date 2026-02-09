'use client';

import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTrending, useTokenSearch } from '@/hooks/useApi';
import { useTrackedTokens } from '@/hooks/useTrackedTokens';
import { useWebSocket } from '@/hooks/useWebSocket';
import { getTrackedTokenPrices, TrackedTokenPriceData } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn, formatPrice, formatPercent } from '@/lib/utils';
import {
  Search,
  TrendingUp,
  TrendingDown,
  Star,
  Loader2,
  Flame,
} from 'lucide-react';
import { useDebounce } from '@/hooks/useDebounce';

function TokenCard({
  token,
  logo,
  rank,
  price,
  change,
  trailing,
  onToggle,
  tracked,
}: {
  token: { symbol: string; name?: string };
  logo?: string | null;
  rank?: number | null;
  price?: number | null;
  change?: number | null;
  trailing?: React.ReactNode;
  onToggle: () => void;
  tracked: boolean;
}) {
  return (
    <Card className="relative overflow-hidden hover:border-primary/50 transition-colors">
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3 min-w-0 flex-1">
            {logo ? (
              <img src={logo} alt="" className="h-8 w-8 rounded-full shrink-0" />
            ) : (
              <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center text-xs font-bold shrink-0">
                {token.symbol.slice(0, 2)}
              </div>
            )}
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg">{token.symbol}</span>
                {rank && (
                  <Badge variant="secondary" className="text-[10px]">
                    #{rank}
                  </Badge>
                )}
              </div>
              {token.name && (
                <div className="text-sm text-muted-foreground truncate">{token.name}</div>
              )}
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className={cn(
              'h-8 w-8 p-0 shrink-0',
              tracked ? 'text-yellow-500' : 'text-muted-foreground',
            )}
            onClick={onToggle}
            title={tracked ? 'Untrack token' : 'Track token'}
          >
            <Star className={cn('h-5 w-5', tracked && 'fill-current')} />
          </Button>
        </div>
        <div className="mt-4 space-y-2">
          {price != null && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Price</span>
              <span className="font-mono font-medium">{formatPrice(price)}</span>
            </div>
          )}
          {change != null && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">24h</span>
              <span
                className={cn(
                  'font-medium flex items-center gap-1',
                  change >= 0 ? 'text-green-500' : 'text-red-500',
                )}
              >
                {change >= 0 ? (
                  <TrendingUp className="h-3 w-3" />
                ) : (
                  <TrendingDown className="h-3 w-3" />
                )}
                {formatPercent(change)}
              </span>
            </div>
          )}
          {trailing}
        </div>
      </CardContent>
    </Card>
  );
}

export default function ExplorePage() {
  const [searchQuery, setSearchQuery] = useState('');
  const debouncedSearch = useDebounce(searchQuery, 400);

  const { trackedTokens, isTracked, trackToken, untrackToken } = useTrackedTokens();
  const { trending } = useWebSocket();
  const { data: trendingData } = useTrending();

  const { data: searchResults, isLoading: isSearching } = useTokenSearch(
    debouncedSearch,
    debouncedSearch.length >= 2,
  );

  const { data: trackedPrices = [] } = useQuery({
    queryKey: ['tracked-token-prices'],
    queryFn: getTrackedTokenPrices,
    enabled: trackedTokens.length > 0,
    refetchInterval: 60_000,
  });

  const priceMap = useMemo(() => {
    const map = new Map<string, TrackedTokenPriceData>();
    trackedPrices.forEach((p) => map.set(p.symbol.toUpperCase(), p));
    return map;
  }, [trackedPrices]);

  const trendingTokens = useMemo(() => {
    const wsTokens = trending?.top_tokens || [];
    const apiTokens = trendingData?.trending || [];
    const merged = new Map();
    wsTokens.forEach((t) => merged.set(t.symbol, t));
    apiTokens.forEach((t) => merged.set(t.symbol, { ...merged.get(t.symbol), ...t }));
    return Array.from(merged.values());
  }, [trending, trendingData]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Explore</h1>
        <p className="text-muted-foreground">
          Search tokens, track prices & discover trending coins
        </p>
      </div>

      {/* Search */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-2 border rounded-md px-3 py-2">
            <Search className="h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search tokens by name, symbol, or contract address…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="flex-1 bg-transparent border-none outline-none text-sm placeholder:text-muted-foreground"
            />
            {isSearching && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
          </div>
        </CardContent>
      </Card>

      {/* Search results */}
      {debouncedSearch.length >= 2 && searchResults && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">
            Results for &ldquo;{debouncedSearch}&rdquo;
          </h2>
          {searchResults.results.length === 0 ? (
            <Card>
              <CardContent className="p-8 text-center text-muted-foreground">
                <Search className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No tokens found</p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {searchResults.results.map((t) => (
                <TokenCard
                  key={`${t.symbol}_${t.chain}_${t.address || t.name}`}
                  token={{ symbol: t.symbol, name: t.name }}
                  logo={t.logo}
                  rank={(t as any).market_cap_rank}
                  price={t.price_usd}
                  change={t.price_change_24h}
                  tracked={isTracked(t.symbol)}
                  onToggle={() =>
                    isTracked(t.symbol) ? untrackToken(t.symbol) : trackToken(t.symbol, t.name)
                  }
                  trailing={
                    t.address ? (
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-muted-foreground">Address</span>
                        <span
                          className="text-xs font-mono text-muted-foreground truncate max-w-[140px]"
                          title={t.address}
                        >
                          {t.address.slice(0, 6)}…{t.address.slice(-4)}
                        </span>
                      </div>
                    ) : null
                  }
                />
              ))}
            </div>
          )}
        </section>
      )}

      {/* Tracked tokens */}
      {trackedTokens.length > 0 && (
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <Star className="h-5 w-5 text-yellow-500 fill-yellow-500" />
            <h2 className="text-lg font-semibold">Tracked Tokens</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {trackedTokens.map((t) => {
              const pd = priceMap.get(t.symbol.toUpperCase());
              return (
                <TokenCard
                  key={t.symbol}
                  token={{ symbol: t.symbol, name: pd?.token_name || t.notes || t.symbol }}
                  logo={pd?.token_logo}
                  rank={pd?.cmc_rank}
                  price={pd?.price_usd}
                  change={pd?.price_change_24h}
                  tracked
                  onToggle={() => untrackToken(t.symbol)}
                  trailing={
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Chain</span>
                      <Badge variant="outline" className="text-xs capitalize">
                        {t.chain}
                      </Badge>
                    </div>
                  }
                />
              );
            })}
          </div>
        </section>
      )}

      {/* Trending */}
      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <Flame className="h-5 w-5 text-orange-500" />
          <h2 className="text-lg font-semibold">Trending</h2>
        </div>
        {trendingTokens.length === 0 ? (
          <Card>
            <CardContent className="p-8 text-center text-muted-foreground">
              <TrendingUp className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No trending tokens right now — check back soon!</p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {trendingTokens.map((t) => (
              <TokenCard
                key={t.symbol}
                token={{ symbol: t.symbol, name: t.name }}
                logo={t.image}
                rank={t.market_cap_rank}
                price={t.current_price}
                change={t.change ?? t.price_change_24h ?? t.price_change_percentage_24h}
                tracked={isTracked(t.symbol)}
                onToggle={() =>
                  isTracked(t.symbol) ? untrackToken(t.symbol) : trackToken(t.symbol)
                }
                trailing={
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Signals</span>
                    <span className="text-sm font-medium">{t.count || t.signal_count || 0}</span>
                  </div>
                }
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
