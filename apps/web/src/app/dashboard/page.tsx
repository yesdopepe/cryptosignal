'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { useTrackedTokens } from '@/hooks/useTrackedTokens';
import { useStats, useTokenSearch, useTrending, useSignals } from '@/hooks/useApi';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useNotificationBadge } from '@/hooks/useNotifications';
import { StatsCards } from '@/components/dashboard/StatsCards';
import { MarketOverview } from '@/components/dashboard/MarketOverview';
import { TokenDetailsDialog } from '@/components/dashboard/TokenDetailsDialog';

import { TokenCandleChart } from '@/components/charts/TokenCandleChart';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { 
  TrendingUp, 
  TrendingDown, 
  Star, 
  RefreshCw, 
  Activity,
  Radio,
  Wifi,
  WifiOff,
  BarChart3,
} from 'lucide-react';
import { cn, formatPrice, formatPercent } from '@/lib/utils';
import Link from 'next/link';
import * as api from '@/lib/api';
import type { TrendingCoin } from '@/lib/api';

// Component to show tracked token prices with realtime WebSocket updates
function TrackedTokenPrices() {
  const { trackedTokens, untrackToken, isLoading: isTrackingLoading } = useTrackedTokens();
  const { trackedPrices, isConnected } = useWebSocket();
  const [initialData, setInitialData] = useState<Record<string, api.TrackedTokenPriceData>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [selectedToken, setSelectedToken] = useState<{symbol: string, name: string} | null>(null);
  const [initialFetchDone, setInitialFetchDone] = useState(false);

  // Stable key that changes when actual tracked symbols change (not just count)
  const trackedKey = trackedTokens.map(t => t.symbol).sort().join(',');

  // Fetch tracked prices via REST (used as fallback until WebSocket delivers)
  const fetchInitialPrices = async () => {
    if (trackedTokens.length === 0) {
      setInitialData({});
      setInitialFetchDone(true);
      return;
    }
    setIsLoading(true);
    try {
      const prices = await api.getTrackedTokenPrices();
      const dataMap: Record<string, api.TrackedTokenPriceData> = {};
      for (const p of prices) {
        dataMap[p.symbol.toUpperCase()] = p;
      }
      setInitialData(dataMap);
      setLastUpdate(new Date());
    } catch (error) {
      console.error('Failed to fetch tracked prices:', error);
    }
    setIsLoading(false);
    setInitialFetchDone(true);
  };

  // Re-fetch whenever the actual set of tracked tokens changes
  useEffect(() => {
    fetchInitialPrices();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trackedKey]);

  // Poll REST as fallback when WebSocket is disconnected (every 30s)
  useEffect(() => {
    if (isConnected || trackedTokens.length === 0) return;
    const interval = setInterval(fetchInitialPrices, 30000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isConnected, trackedKey]);

  // After tracking a new token, the backend instant-fetch might take ~2s.
  // Do one extra REST poll after a short delay when tokens change.
  useEffect(() => {
    if (trackedTokens.length === 0) return;
    const timer = setTimeout(fetchInitialPrices, 3000);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trackedKey]);

  // Update lastUpdate whenever we get fresh WebSocket data
  useEffect(() => {
    if (Object.keys(trackedPrices).length > 0) {
      setLastUpdate(new Date());
    }
  }, [trackedPrices]);

  // Merge: prefer WebSocket data over REST fallback
  const getTokenDisplayData = (symbol: string, chain: string) => {
    const wsKey = symbol.toUpperCase();
    const wsData = trackedPrices[wsKey];
    const restData = initialData[wsKey];

    if (wsData) {
      return {
        name: wsData.token_name || symbol,
        logo: wsData.token_logo || null,
        price_usd: wsData.price_usd,
        price_change_24h: wsData.price_change_24h != null ? Number(wsData.price_change_24h) : null,
        chain: wsData.chain || chain,
        market_cap: wsData.market_cap ?? null,
        volume_24h: wsData.volume_24h ?? null,
      };
    }
    if (restData) {
      return {
        name: restData.token_name || symbol,
        logo: restData.token_logo || null,
        price_usd: restData.price_usd,
        price_change_24h: restData.price_change_24h != null ? Number(restData.price_change_24h) : null,
        chain: restData.chain || chain,
        market_cap: (restData as any).market_cap ?? null,
        volume_24h: (restData as any).volume_24h ?? null,
      };
    }
    return null;
  };

  if (isTrackingLoading) {
    return (
      <Card className="h-full">
        <CardHeader>
          <CardTitle className="text-base font-medium flex items-center gap-2">
            <Star className="h-4 w-4 text-yellow-500" />
            Tracked Tokens
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
             <Skeleton className="h-10 w-full" />
             <Skeleton className="h-10 w-full" />
             <Skeleton className="h-10 w-full" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (trackedTokens.length === 0) {
    return (
      <Card className="h-full">
        <CardHeader>
          <CardTitle className="text-base font-medium flex items-center gap-2">
            <Star className="h-4 w-4 text-yellow-500" />
            Tracked Tokens
          </CardTitle>
        </CardHeader>
        <CardContent className="text-center py-8 text-muted-foreground">
          <Star className="h-10 w-10 mx-auto mb-3 opacity-30" />
          <p className="font-medium">No tokens tracked yet</p>
          <p className="text-sm mt-1">
            Go to <Link href="/explore" className="text-primary hover:underline">Explore</Link> to search & track tokens
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="h-full">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-base font-medium flex items-center gap-2">
          <Star className="h-4 w-4 text-yellow-500" />
          Tracked Tokens
          <Badge variant="secondary" className="ml-1">{trackedTokens.length}</Badge>
        </CardTitle>
        <div className="flex items-center gap-2">
          {isConnected && (
            <Badge variant="outline" className="text-[10px] gap-1 py-0.5">
              <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
              Live
            </Badge>
          )}
          {lastUpdate && (
            <span className="text-xs text-muted-foreground">
              {lastUpdate.toLocaleTimeString()}
            </span>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchInitialPrices}
            disabled={isLoading}
            className="h-8 w-8 p-0"
          >
            <RefreshCw className={cn("h-4 w-4", isLoading && "animate-spin")} />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-2 max-h-[400px] overflow-y-auto">
        {trackedTokens.map((token) => {
          const data = getTokenDisplayData(token.symbol, token.chain);
          
          return (
            <div
              key={token.symbol}
              className="flex items-center justify-between p-3 rounded-lg bg-secondary/30 hover:bg-secondary/50 transition-colors cursor-pointer"
              onClick={() => setSelectedToken({ symbol: token.symbol, name: data?.name || token.symbol })}
            >
              <div className="flex items-center gap-3 min-w-0">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 w-6 p-0 text-yellow-500"
                  onClick={(e) => {
                    e.stopPropagation();
                    untrackToken(token.symbol);
                  }}
                  title="Untrack token"
                >
                  <Star className="h-4 w-4 fill-current" />
                </Button>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    {data?.logo && (
                      <img src={data.logo} alt="" className="h-5 w-5 rounded-full" />
                    )}
                    <span className="font-bold">{token.symbol}</span>
                  </div>
                  <div className="text-xs text-muted-foreground truncate">
                    {data?.name || token.symbol}
                    {(data?.chain || token.chain) && <span className="ml-1 opacity-60">({data?.chain || token.chain})</span>}
                  </div>
                </div>
              </div>
              
              {data ? (
                <div className="text-right">
                  <div className="font-mono font-medium">
                    {data.price_usd ? formatPrice(data.price_usd) : '-'}
                  </div>
                  {data.price_change_24h !== null && data.price_change_24h !== undefined && (
                    <div className={cn(
                      "text-xs flex items-center justify-end gap-1",
                      data.price_change_24h >= 0 ? "text-green-500" : "text-red-500"
                    )}>
                      {data.price_change_24h >= 0 ? (
                        <TrendingUp className="h-3 w-3" />
                      ) : (
                        <TrendingDown className="h-3 w-3" />
                      )}
                      {formatPercent(data.price_change_24h)}
                    </div>
                  )}
                  {(data.market_cap || data.volume_24h) && (
                    <div className="text-[10px] text-muted-foreground mt-0.5 space-x-2">
                      {data.market_cap != null && (
                        <span>MCap ${(data.market_cap / 1e6).toFixed(1)}M</span>
                      )}
                      {data.volume_24h != null && (
                        <span>Vol ${(data.volume_24h / 1e6).toFixed(1)}M</span>
                      )}
                    </div>
                  )}
                </div>
              ) : initialFetchDone ? (
                <span className="text-xs text-muted-foreground italic">Loading price…</span>
              ) : (
                <Skeleton className="h-8 w-20" />
              )}
            </div>
          );
        })}
      </CardContent>
      <TokenDetailsDialog 
        open={!!selectedToken} 
        onOpenChange={(open) => !open && setSelectedToken(null)}
        symbol={selectedToken?.symbol ?? null}
        name={selectedToken?.name}
      />
    </Card>
  );
}

// Trending overview using CoinGecko trending data
function TrendingOverview() {
  const { data: trendingData, isLoading } = useTrending();
  const { isTracked, trackToken, untrackToken } = useTrackedTokens();
  const [selectedToken, setSelectedToken] = useState<{symbol: string, name: string} | null>(null);

  const trendingList: TrendingCoin[] = (trendingData as any)?.trending || [];

  if (isLoading) {
    return (
      <Card className="h-full">
        <CardHeader>
          <CardTitle className="text-base font-medium flex items-center gap-2">
            <Activity className="h-4 w-4 text-cyan-500" />
            Trending Tokens
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="text-base font-medium flex items-center gap-2">
          <Activity className="h-4 w-4 text-cyan-500" />
          Trending Tokens
          <Badge variant="secondary" className="ml-1">24h</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 max-h-[400px] overflow-y-auto">
        {trendingList.length === 0 ? (
          <div className="text-center py-6 text-muted-foreground">
            <Activity className="h-10 w-10 mx-auto mb-3 opacity-30" />
            <p className="text-sm">No trending data yet</p>
          </div>
        ) : (
          trendingList.map((token, index) => (
            <div
              key={token.symbol}
              className="flex items-center justify-between p-3 rounded-lg bg-secondary/30 hover:bg-secondary/50 transition-colors cursor-pointer"
              onClick={() => setSelectedToken({ symbol: token.symbol, name: token.name })}
            >
              <div className="flex items-center gap-3">
                {token.image ? (
                  <img src={token.image} alt="" className="h-7 w-7 rounded-full shrink-0" />
                ) : (
                  <span className={cn(
                    "w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0",
                    index === 0 ? "bg-yellow-500/20 text-yellow-500" :
                    index === 1 ? "bg-gray-400/20 text-gray-400" :
                    index === 2 ? "bg-orange-500/20 text-orange-500" :
                    "bg-muted text-muted-foreground"
                  )}>
                    {index + 1}
                  </span>
                )}
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold">{token.symbol}</span>
                    <span className="text-xs text-muted-foreground truncate max-w-[100px]">{token.name}</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      className={cn(
                        "h-5 w-5 p-0",
                        isTracked(token.symbol) ? "text-yellow-500" : "text-muted-foreground hover:text-yellow-500"
                      )}
                      onClick={(e) => {
                        e.stopPropagation();
                        if (isTracked(token.symbol)) {
                          untrackToken(token.symbol);
                        } else {
                          trackToken(token.symbol, token.name);
                        }
                      }}
                    >
                      <Star className={cn("h-3 w-3", isTracked(token.symbol) && "fill-current")} />
                    </Button>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {token.market_cap_rank ? `Rank #${token.market_cap_rank}` : ''}
                  </div>
                </div>
              </div>
              <div className="text-right">
                {token.current_price != null ? (
                  <>
                    <div className="font-mono font-medium text-sm">
                      {formatPrice(token.current_price)}
                    </div>
                    {token.price_change_percentage_24h != null && (
                      <div className={cn(
                        "text-xs flex items-center justify-end gap-1",
                        token.price_change_percentage_24h >= 0 ? "text-green-500" : "text-red-500"
                      )}>
                        {token.price_change_percentage_24h >= 0 ? (
                          <TrendingUp className="h-3 w-3" />
                        ) : (
                          <TrendingDown className="h-3 w-3" />
                        )}
                        {formatPercent(token.price_change_percentage_24h)}
                      </div>
                    )}
                  </>
                ) : (
                  <span className="text-xs text-muted-foreground">-</span>
                )}
              </div>
            </div>
          ))
        )}
      </CardContent>
      <TokenDetailsDialog 
        open={!!selectedToken} 
        onOpenChange={(open) => !open && setSelectedToken(null)}
        symbol={selectedToken?.symbol ?? null}
        name={selectedToken?.name}
      />
    </Card>
  );
}

// Price charts using OHLC candlestick data from CoinGecko (works for any token)
function TrackedTokenCharts() {
  const { trackedTokens, isLoading: isTrackingLoading } = useTrackedTokens();
  
  // 'range' controls the visible zoom window
  const [range, setRange] = useState<number | string>(7);
  
  // 'fetchMode' controls data granularity vs history depth
  // 'auto': Fetch only what is needed (best resolution for the range)
  // 'max': Fetch FULL history (allows zooming out, but lower resolution)
  const [fetchMode, setFetchMode] = useState<'auto' | 'max'>('auto');

  const timeOptions = [
    { label: '1D', value: 1 },
    { label: '7D', value: 7 },
    { label: '30D', value: 30 },
    { label: '90D', value: 90 },
    { label: '1Y', value: 'max' },
  ];

  if (isTrackingLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-medium flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-orange-500" />
            Price Charts
          </CardTitle>
        </CardHeader>
        <CardContent><Skeleton className="h-[220px] w-full" /></CardContent>
      </Card>
    );
  }

  if (trackedTokens.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-medium flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-orange-500" />
            Price Charts
          </CardTitle>
        </CardHeader>
        <CardContent className="text-center py-8 text-muted-foreground">
          <BarChart3 className="h-10 w-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">Track tokens to see price charts</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <CardTitle className="text-base font-medium flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-orange-500" />
            Price Charts
          </CardTitle>
          
          <div className="flex items-center gap-4">
            {/* Resolution/History Mode Toggle */}
            <div className="flex items-center border rounded-md overflow-hidden h-7">
              <button
                onClick={() => setFetchMode('auto')}
                className={cn(
                  "px-3 text-[10px] font-medium h-full transition-colors",
                  fetchMode === 'auto' 
                    ? "bg-primary/10 text-primary" 
                    : "bg-transparent text-muted-foreground hover:bg-muted"
                )}
                title="Best resolution for the selected range"
              >
                High Res
              </button>
              <div className="w-[1px] bg-border h-full" />
              <button
                onClick={() => setFetchMode('max')}
                className={cn(
                  "px-3 text-[10px] font-medium h-full transition-colors",
                  fetchMode === 'max' 
                    ? "bg-primary/10 text-primary" 
                    : "bg-transparent text-muted-foreground hover:bg-muted"
                )}
                title="Full history (Max 1 Year)"
              >
                1 Year
              </button>
            </div>

            {/* Time Range Selectors */}
            <div className="flex items-center gap-1">
              {timeOptions.map((opt) => (
                <Button
                  key={opt.label}
                  variant={range === opt.value ? "default" : "ghost"}
                  size="sm"
                  className="h-7 px-2.5 text-xs"
                  onClick={() => setRange(opt.value)}
                >
                  {opt.label}
                </Button>
              ))}
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6 max-h-[900px] overflow-y-auto">
        {trackedTokens.map((token) => {
          const sym = token.symbol.toUpperCase();
          
          // Logic: 
          // If Max History is ON, we fetch 'max' and initialZoom to 'range'.
          // If Auto is ON, we fetch 'range'.
          //   - Note: 90D and Max always effectively fetch low-res on CoinGecko.
          
          const effectiveDays = fetchMode === 'max' ? 'max' : range;
          const initialVisible = fetchMode === 'max' && typeof range === 'number' ? range : undefined;

          // Display badge to explain resolution
          let resLabel = '';
          if (fetchMode === 'max' || range === 'max' || range === 90) {
            resLabel = 'Daily (1 Year)';
          } else if (range === 1) {
            resLabel = '30m (High Res)';
          } else {
            resLabel = '4h (Med Res)';
          }

          return (
            <div key={`${sym}-${effectiveDays}`}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                    <span className="font-bold text-sm">{sym}</span>
                    <Badge variant="secondary" className="text-[10px] h-5">
                      {resLabel}
                    </Badge>
                </div>
              </div>
              <div className="rounded-lg overflow-hidden border border-border/40 bg-secondary/10">
                <TokenCandleChart 
                  symbol={sym} 
                  days={effectiveDays}
                  initialVisibleDays={initialVisible}
                  height={220} 
                />
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

// Recent signals summary for dashboard
function RecentSignals() {
  const { data, isLoading } = useSignals({ limit: 5 });
  const { data: badge } = useNotificationBadge();
  const signals = data?.items || [];
  const total = data?.total || 0;

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-medium flex items-center gap-2">
            <Radio className="h-4 w-4 text-blue-500" />
            Recent Signals
            {total > 0 && <Badge variant="secondary" className="ml-1">{total}</Badge>}
          </CardTitle>
          <div className="flex items-center gap-2">
            {(badge?.unread_count ?? 0) > 0 && (
              <Badge variant="default" className="text-[10px]">
                {badge!.unread_count} unread
              </Badge>
            )}
            <Link href="/explore">
              <Button variant="ghost" size="sm" className="text-xs">
                View all
              </Button>
            </Link>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : signals.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <Radio className="h-8 w-8 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No signals yet</p>
            <p className="text-xs mt-1">Connect Telegram & subscribe to channels to detect signals</p>
          </div>
        ) : (
          <div className="space-y-2">
            {signals.map((s: any) => (
              <div
                key={s.id}
                className={cn(
                  'flex items-center justify-between p-2.5 rounded-lg border-l-4',
                  s.sentiment === 'BULLISH'
                    ? 'border-l-green-500 bg-green-500/5'
                    : s.sentiment === 'BEARISH'
                      ? 'border-l-red-500 bg-red-500/5'
                      : 'border-l-yellow-500 bg-yellow-500/5',
                )}
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-sm">${s.token_symbol}</span>
                    <Badge
                      variant="outline"
                      className={cn(
                        'text-[9px] h-4',
                        s.sentiment === 'BULLISH' && 'text-green-500 border-green-500/30',
                        s.sentiment === 'BEARISH' && 'text-red-500 border-red-500/30',
                        s.sentiment === 'NEUTRAL' && 'text-yellow-500 border-yellow-500/30',
                      )}
                    >
                      {s.sentiment}
                    </Badge>
                  </div>
                  <div className="text-[10px] text-muted-foreground truncate">
                    {s.channel_name} · {s.timestamp ? new Date(s.timestamp).toLocaleTimeString() : ''}
                  </div>
                </div>
                {s.price_at_signal != null && (
                  <span className="text-xs font-mono text-muted-foreground">
                    {formatPrice(s.price_at_signal)}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const { isAuthenticated, isLoading, user } = useAuth();
  const { data: stats } = useStats();
  const { isConnected } = useWebSocket();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="space-y-6">
      {/* Page Header with inline stats */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">
            Welcome back{user?.username ? `, ${user.username}` : ''}
          </p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <Badge variant="outline" className="text-sm py-1 gap-1.5">
            {isConnected ? (
              <Wifi className="h-3 w-3 text-green-500" />
            ) : (
              <WifiOff className="h-3 w-3 text-red-500" />
            )}
            {isConnected ? 'Live' : 'Disconnected'}
          </Badge>
          <Link href="/explore">
            <Button variant="outline" size="sm">
              <Star className="h-4 w-4 mr-2" />
              Track Tokens
            </Button>
          </Link>
        </div>
      </div>

      {/* Stats Cards */}
      {/* <StatsCards /> removed as requested */}

      {/* Main Grid - Tracked Tokens + Trending */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <TrackedTokenPrices />
        <TrendingOverview />
      </div>

      {/* Market Overview - real prices, no tracking required */}
      <MarketOverview />

      {/* Candlestick Charts for tracked tokens */}
      <TrackedTokenCharts />
    </div>
  );
}
