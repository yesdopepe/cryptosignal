'use client';

import { useMarketData } from '@/hooks/useApi';
import { useTrackedTokens } from '@/hooks/useTrackedTokens';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { 
  TrendingUp, TrendingDown, Star, Globe, RefreshCw 
} from 'lucide-react';
import { TokenDetailsDialog } from '@/components/dashboard/TokenDetailsDialog';
import { cn, formatPrice, formatPercent, timeAgo } from '@/lib/utils';
import { useState, useEffect } from 'react';
import type { MarketCoin } from '@/lib/api';

function MiniSparkline({ data, positive }: { data: number[]; positive: boolean }) {
  if (!data || data.length < 2) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const width = 80;
  const height = 24;

  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((v - min) / range) * height;
    return `${x},${y}`;
  }).join(' ');

  return (
    <svg width={width} height={height} className="inline-block">
      <polyline
        fill="none"
        stroke={positive ? '#22c55e' : '#ef4444'}
        strokeWidth="1.5"
        points={points}
      />
    </svg>
  );
}

function formatCompact(num: number | null | undefined): string {
  if (num == null) return '-';
  if (num >= 1e12) return `$${(num / 1e12).toFixed(2)}T`;
  if (num >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
  if (num >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
  if (num >= 1e3) return `$${(num / 1e3).toFixed(1)}K`;
  return `$${num.toFixed(2)}`;
}

function ChangeCell({ value }: { value: number | null | undefined }) {
  if (value == null) return <span className="text-muted-foreground">-</span>;
  const positive = value >= 0;
  return (
    <span className={cn(
      'flex items-center gap-0.5 text-xs font-medium',
      positive ? 'text-green-500' : 'text-red-500'
    )}>
      {positive ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
      {Math.abs(value).toFixed(2)}%
    </span>
  );
}

export function MarketOverview() {
  const { data: marketData, isLoading, refetch, isFetching, dataUpdatedAt } = useMarketData(50);
  const { isTracked, trackToken, untrackToken } = useTrackedTokens();
  const [showCount, setShowCount] = useState(20);
  const [, setTick] = useState(0);
  const [selectedToken, setSelectedToken] = useState<{symbol: string, name: string} | null>(null);

  // Re-render every 10s to update the "updated X ago" text
  useEffect(() => {
    const interval = setInterval(() => setTick(t => t + 1), 10000);
    return () => clearInterval(interval);
  }, []);

  const coins = marketData?.coins ?? [];
  const globalStats = marketData?.global;

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-medium flex items-center gap-2">
            <Globe className="h-4 w-4 text-blue-500" />
            Market Overview
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {Array.from({ length: 10 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <div>
          <CardTitle className="text-base font-medium flex items-center gap-2">
            <Globe className="h-4 w-4 text-blue-500" />
            Market Overview
            {dataUpdatedAt > 0 && (
              <span className="text-[10px] font-normal text-muted-foreground ml-1">
                Updated {timeAgo(new Date(dataUpdatedAt))}
              </span>
            )}
          </CardTitle>
          {globalStats && (
            <div className="flex flex-wrap items-center gap-3 mt-2 text-xs text-muted-foreground">
              {globalStats.total_market_cap_usd && (
                <span>Market Cap: <strong className="text-foreground">{formatCompact(globalStats.total_market_cap_usd)}</strong></span>
              )}
              {globalStats.market_cap_change_24h_pct != null && (
                <ChangeCell value={globalStats.market_cap_change_24h_pct} />
              )}
              {globalStats.btc_dominance != null && (
                <span>BTC: <strong className="text-foreground">{globalStats.btc_dominance.toFixed(1)}%</strong></span>
              )}
              {globalStats.eth_dominance != null && (
                <span>ETH: <strong className="text-foreground">{globalStats.eth_dominance.toFixed(1)}%</strong></span>
              )}
            </div>
          )}
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => refetch()}
          disabled={isFetching}
          className="h-8 w-8 p-0"
        >
          <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
        </Button>
      </CardHeader>
      <CardContent>
        {coins.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <Globe className="h-10 w-10 mx-auto mb-3 opacity-30" />
            <p className="text-sm">Unable to fetch market data</p>
            <p className="text-xs mt-1">CoinGecko API may be temporarily unavailable</p>
          </div>
        ) : (
          <>
            {/* Table wrapper for horizontal scroll on small screens */}
            <div className="overflow-x-auto">
              {/* Header row */}
              <div className="grid grid-cols-[2rem_1fr_5.5rem_4.5rem_4.5rem_4.5rem_5rem_5.5rem] min-w-[640px] gap-2 px-3 pb-2 text-[10px] font-medium text-muted-foreground uppercase tracking-wider border-b">
                <span>#</span>
                <span>Name</span>
                <span className="text-right">Price</span>
                <span className="text-right">1h</span>
                <span className="text-right">24h</span>
                <span className="text-right">7d</span>
                <span className="text-right">Volume</span>
                <span className="text-right">7d Chart</span>
              </div>

              <div className="max-h-[600px] overflow-y-auto">
                {coins.slice(0, showCount).map((coin: MarketCoin) => {
                  const tracked = isTracked(coin.symbol);
                  const sparkPositive = (coin.price_change_percentage_7d ?? 0) >= 0;

                  return (
                    <div
                      key={coin.id}
                      className="grid grid-cols-[2rem_1fr_5.5rem_4.5rem_4.5rem_4.5rem_5rem_5.5rem] min-w-[640px] gap-2 items-center px-3 py-2.5 hover:bg-secondary/30 transition-colors rounded-lg group cursor-pointer"
                      onClick={() => setSelectedToken({ symbol: coin.symbol, name: coin.name })}
                    >
                    {/* Rank */}
                    <span className="text-xs text-muted-foreground font-medium">
                      {coin.market_cap_rank ?? '-'}
                    </span>

                    {/* Name + symbol + track button */}
                    <div className="flex items-center gap-2 min-w-0">
                      {coin.image && (
                        <img src={coin.image} alt="" className="h-6 w-6 rounded-full shrink-0" />
                      )}
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="font-semibold text-sm truncate">{coin.name}</span>
                          <span className="text-xs text-muted-foreground uppercase">{coin.symbol}</span>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className={cn(
                          "h-5 w-5 p-0 opacity-0 group-hover:opacity-100 transition-opacity shrink-0",
                          tracked ? "text-yellow-500 opacity-100" : "text-muted-foreground hover:text-yellow-500"
                        )}
                        onClick={(e) => {
                          e.stopPropagation();
                          if (tracked) {
                            untrackToken(coin.symbol);
                          } else {
                            trackToken(coin.symbol, coin.name);
                          }
                        }}
                      >
                        <Star className={cn("h-3.5 w-3.5", tracked && "fill-current")} />
                      </Button>
                    </div>

                    {/* Price */}
                    <span className="text-right font-mono text-sm font-medium">
                      {coin.current_price != null ? formatPrice(coin.current_price) : '-'}
                    </span>

                    {/* 1h change */}
                    <div className="flex justify-end">
                      <ChangeCell value={coin.price_change_percentage_1h} />
                    </div>

                    {/* 24h change */}
                    <div className="flex justify-end">
                      <ChangeCell value={coin.price_change_percentage_24h} />
                    </div>

                    {/* 7d change */}
                    <div className="flex justify-end">
                      <ChangeCell value={coin.price_change_percentage_7d} />
                    </div>

                    {/* Volume */}
                    <span className="text-right text-xs text-muted-foreground">
                      {formatCompact(coin.total_volume)}
                    </span>

                    {/* Sparkline */}
                    <div className="flex justify-end">
                      {coin.sparkline_7d && coin.sparkline_7d.length > 0 ? (
                        <MiniSparkline
                          data={coin.sparkline_7d.filter((_, i) => i % 4 === 0)}
                          positive={sparkPositive}
                        />
                      ) : (
                        <span className="text-muted-foreground text-xs">-</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
            </div>

            {/* Show more / less */}
            {coins.length > 20 && (
              <div className="flex justify-center pt-3 border-t mt-2">
                {showCount < coins.length ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowCount(Math.min(showCount + 20, coins.length))}
                  >
                    Show More ({coins.length - showCount} remaining)
                  </Button>
                ) : (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowCount(20)}
                  >
                    Show Less
                  </Button>
                )}
              </div>
            )}
          </>
        )}
      <TokenDetailsDialog 
        open={!!selectedToken} 
        onOpenChange={(open) => !open && setSelectedToken(null)}
        symbol={selectedToken?.symbol ?? null}
        name={selectedToken?.name}
      />
      </CardContent>
    </Card>
  );
}
