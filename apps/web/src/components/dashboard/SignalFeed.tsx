'use client';

import { useWebSocket } from '@/hooks/useWebSocket';
import { useTrackedTokens } from '@/hooks/useTrackedTokens';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn, timeAgo, formatPrice } from '@/lib/utils';
import { Trash2, Eye, EyeOff, Activity, Zap } from 'lucide-react';
import { useState, useMemo } from 'react';

// Define a union type for display
type FeedItem = 
  | { type: 'signal'; data: any; timestamp: string }
  | { type: 'market'; data: any; timestamp: string; source: string };

export function SignalFeed() {
  const { signals, marketUpdates, clearSignals, isConnected } = useWebSocket();
  const { trackedTokens, isTracked } = useTrackedTokens();
  const [showAllSignals, setShowAllSignals] = useState(false);
  
  const hasTrackedTokens = trackedTokens.length > 0;
  const effectiveShowAll = showAllSignals || !hasTrackedTokens;

  // Combine and sort
  const feedItems: FeedItem[] = useMemo(() => {
    const combined: FeedItem[] = [
      ...signals.map(s => ({ type: 'signal' as const, data: s, timestamp: s.timestamp })),
      ...marketUpdates.map(m => ({ type: 'market' as const, data: m.data, timestamp: m.timestamp, source: m.source }))
    ];
    return combined.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  }, [signals, marketUpdates]);

  const filteredItems = effectiveShowAll
    ? feedItems 
    : feedItems.filter(item => {
        if (item.type === 'signal') return isTracked(item.data.token_symbol);
        // For market updates, we check if 'symbol' or 'tokenSymbol' exists in data
        const symbol = item.data.symbol || item.data.tokenSymbol || item.data.token_symbol;
        if (symbol) return isTracked(symbol);
        return true; // Show if we can't determine symbol (system messages)
      });


  return (
    <Card className="h-[500px] flex flex-col">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <div className="flex items-center gap-2">
          <CardTitle className="text-sm font-medium">Live Feed</CardTitle>
          <div className={cn(
            "h-2 w-2 rounded-full",
            isConnected ? "bg-green-500" : "bg-red-500"
          )} />
          <span className="text-xs text-muted-foreground">
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setShowAllSignals(!showAllSignals)}
            title={effectiveShowAll ? "Showing all signals" : "Showing tracked only"}
            disabled={!hasTrackedTokens}
          >
            {effectiveShowAll ? (
              <Eye className="h-4 w-4" />
            ) : (
              <EyeOff className="h-4 w-4" />
            )}
          </Button>
          <Button 
            variant="ghost" 
            size="icon"
            onClick={clearSignals}
            title="Clear feed"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex-1 overflow-auto">
        {filteredItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center p-4">
            <p className="text-sm text-muted-foreground mb-2">No signals yet</p>
            {!effectiveShowAll && (
              <p className="text-xs text-muted-foreground">
                Waiting for signals from your tracked tokens...
              </p>
            )}
            {effectiveShowAll && (
              <p className="text-xs text-muted-foreground">
                Monitoring all channels for new signals...
              </p>
            )}
            {!isConnected && (
              <p className="text-xs text-red-400 mt-2">
                WebSocket is disconnected. Reconnecting...
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {filteredItems.map((item, index) => {
              if (item.type === 'signal') {
                const signal = item.data;
                return (
                  <div key={`${item.timestamp}-${index}`} className="flex items-start justify-between p-3 border rounded-lg bg-card/50">
                    <div className="flex gap-3">
                      <div className="mt-1">
                        <Activity className="h-5 w-5 text-blue-500" />
                      </div>
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-bold">{signal.token_symbol}</span>
                          <Badge variant="outline" className="text-xs">
                            {signal.channel_name}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <span>{formatPrice(signal.price_at_signal)}</span>
                            <span>•</span>
                            <span>Conf: {Math.round(signal.confidence_score * 100)}%</span>
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                       <span className="text-xs text-muted-foreground block">
                        {timeAgo(item.timestamp)}
                      </span>
                    </div>
                  </div>
                );
              } else {
                const marketData = item.data;
                const eventType = marketData.eventType || 'Market Update';
                const price = marketData.priceUsd || (marketData.price ? Number(marketData.price) : null);
                
                return (
                  <div key={`${item.timestamp}-${index}`} className="flex items-start justify-between p-3 border rounded-lg bg-slate-50 dark:bg-slate-900/50">
                    <div className="flex gap-3">
                      <div className="mt-1">
                        <Zap className="h-5 w-5 text-yellow-500" />
                      </div>
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-sm">
                             {marketData.symbol || marketData.tokenSymbol || 'Unknown Token'}
                          </span>
                          <Badge variant="secondary" className="text-[10px] h-5">
                            {item.source}
                          </Badge>
                        </div>
                         <div className="text-xs text-muted-foreground">
                            {price ? formatPrice(price) : eventType}
                            {/* Render a few key fields if available */}
                            {marketData.volume && <span className="ml-2">Vol: {marketData.volume}</span>}
                         </div>
                         {/* Fallback for completely unknown structure */}
                         {!price && !marketData.volume && (
                             <div className="text-[10px] text-muted-foreground break-all max-w-[200px]">
                                 {JSON.stringify(marketData).slice(0, 50)}...
                             </div>
                         )}
                      </div>
                    </div>
                    <div className="text-right">
                      <span className="text-xs text-muted-foreground block">
                        {timeAgo(item.timestamp)}
                      </span>
                    </div>
                  </div>
                );
              }
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
