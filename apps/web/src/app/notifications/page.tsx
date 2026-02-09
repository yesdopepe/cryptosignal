'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import {
  useNotifications,
  useMarkNotificationsRead,
  useMarkAllRead,
  useDeleteNotification,
  useClearAllNotifications,
} from '@/hooks/useNotifications';
import { useTrackedTokens } from '@/hooks/useTrackedTokens';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Bell,
  BellOff,
  Check,
  CheckCheck,
  Trash2,
  Radio,
  ArrowRight,
  Copy,
  ExternalLink,
  Plus,
  Ban,
  Search
} from 'lucide-react';
import { cn, getChainUrl } from '@/lib/utils';
import type { AppNotification, TrackedToken } from '@/lib/api';
import { getTokenByAddress } from '@/lib/api';
import { useExplorer } from '@/hooks/useExplorer';

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString();
}


function DetectionItem({
  notification,
  onMarkRead,
  onDelete,
  tracking
}: {
  notification: AppNotification;
  onMarkRead: (id: number) => void;
  onDelete: (id: number) => void;
  tracking: {
      track: (s: string, n?: string, c?: string, a?: string) => void;
      untrack: (s: string) => void;
      isTracking: (s: string) => boolean;
      trackedTokens: TrackedToken[];
  }
}) {
  const [copied, setCopied] = useState(false);
  const { openExplorer } = useExplorer();

  // Safely extract data with fallbacks
  const data = notification.data || {};
  const contractAddr = notification.contract_address || data.contract_addresses?.[0] || data.address;
  const tokenSymbol = notification.token_symbol || data.token_symbol || 'UNKNOWN';
  const tokenName = data.token_name || tokenSymbol;
  const channelName = notification.channel_name || data.channel || 'Telegram';
  const chain = data.chain || 'ETH';
  
  // Robust tracking check: matches symbol OR address
  const matchedToken = tracking.trackedTokens.find(t => 
      t.symbol.toUpperCase() === tokenSymbol.toUpperCase() || 
      (contractAddr && t.address?.toLowerCase() === contractAddr.toLowerCase())
  );
  const isTracked = !!matchedToken;

  const copyAddress = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!contractAddr) return;
    navigator.clipboard.writeText(contractAddr);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleTrackToggle = async (e: React.MouseEvent) => {
      e.stopPropagation();
      if (isTracked && matchedToken) {
          tracking.untrack(matchedToken.symbol);
      } else {
        let nameToTrack = tokenName;
        let symbolToTrack = tokenSymbol;

        // If unknown, same as symbol, or contains "CA:" prefix, try to fetch details
        const needsResolution = !nameToTrack || 
                                nameToTrack === tokenSymbol || 
                                nameToTrack === 'Unknown' ||
                                tokenSymbol.startsWith('CA:');

        if (needsResolution && contractAddr) {
             try {
                 const res = await getTokenByAddress(contractAddr, chain);
                 if (res && res.results && res.results.length > 0) {
                     nameToTrack = res.results[0].name;
                     // Only update symbol if we got a valid one (not a synthesized one)
                     if (res.results[0].symbol && !res.results[0].symbol.startsWith('CA:')) {
                         symbolToTrack = res.results[0].symbol;
                     }
                 }
             } catch (err) {
                 console.error("Failed to fetch token name", err);
             }
        }
        
        tracking.track(symbolToTrack, nameToTrack, chain, contractAddr);
      }
  };

  const explorerUrl = getChainUrl(chain, contractAddr);

  return (
    <Card className={cn(
        "group relative transition-all duration-200 border-l-4",
        notification.is_read 
          ? "border-l-muted" 
          : "border-l-primary shadow-md bg-card/50",
    )}>
      <CardContent className="p-5">
        <div className="flex items-start gap-4">
          {/* Main Content */}
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-start justify-between gap-y-2 gap-x-4 mb-2">
                <div className="space-y-1">
                    <div className="flex items-center gap-2">
                        <span className={cn('text-base font-semibold tracking-tight', !notification.is_read && 'text-foreground')}>
                            Contract Detected
                        </span>
                        {!notification.is_read && (
                            <Badge variant="default" className="text-[10px] px-1.5 h-4.5 bg-primary/90 text-primary-foreground">New</Badge>
                        )}
                    </div>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <span>via</span>
                        <Badge variant="secondary" className="font-normal bg-secondary/50 text-secondary-foreground hover:bg-secondary/70 h-5">
                            {channelName}
                        </Badge>
                        <span>•</span>
                        <span>{timeAgo(notification.created_at)}</span>
                    </div>
                </div>
            </div>

            <div className="flex items-center gap-3 mt-4">
                 <div className="flex flex-col">
                     <span className="text-[10px] uppercase text-muted-foreground font-semibold">Token</span>
                     <div className="flex items-center gap-2">
                         <span className="font-bold text-lg">{tokenSymbol}</span>
                         {chain && (
                             <Badge variant="outline" className="text-[10px] h-5 uppercase px-1.5">
                                {chain}
                             </Badge>
                         )}
                     </div>
                 </div>

                 {tokenName && tokenName !== tokenSymbol && (
                     <>
                        <div className="w-px h-8 bg-border/50" />
                        <div className="flex flex-col">
                             <span className="text-[10px] uppercase text-muted-foreground font-semibold">Name</span>
                             <span className="text-sm font-medium truncate max-w-[150px]">{tokenName}</span>
                        </div>
                     </>
                 )}
            </div>

            {/* Action Row */}
            <div className="flex flex-wrap items-end justify-between gap-4 mt-5">
              {contractAddr ? (
                  <div className="flex items-center gap-2 max-w-full">
                      <div className="flex items-center bg-muted/40 rounded-lg border border-border/50 hover:bg-muted/60 transition-colors group/addr relative overflow-hidden">
                          <code className="px-3 py-1.5 text-xs font-mono text-muted-foreground">
                              {contractAddr.slice(0, 8)}...{contractAddr.slice(-8)}
                          </code>
                          <div className="h-5 w-px bg-border/50" />
                          <button
                              className="h-8 w-8 flex items-center justify-center hover:bg-background/80 hover:text-foreground transition-colors cursor-pointer"
                              onClick={copyAddress}
                              title="Copy Address"
                          >
                              {copied ? (
                                  <Check className="h-3.5 w-3.5 text-green-500" />
                              ) : (
                                  <Copy className="h-3.5 w-3.5 opacity-70" />
                              )}
                          </button>
                      </div>
                      
                      {/* Integrated Explorer Link */}
                        <a
                            href={explorerUrl}
                            onClick={(e) => {
                               e.preventDefault();
                               openExplorer(chain, contractAddr);
                            }}
                            className="h-8 w-8 flex items-center justify-center rounded-lg border border-border/50 bg-muted/40 text-muted-foreground hover:text-foreground hover:bg-muted/60 hover:border-border transition-all cursor-pointer"
                            title={`View on internal explorer`}
                        >
                            <ExternalLink className="h-4 w-4" />
                        </a>
                  </div>
              ) : <div />}

              <div className="flex items-center gap-2">
                  <Button
                      variant={isTracked ? "secondary" : "default"}
                      size="sm"
                      className={cn(
                          "h-9 px-4 text-xs font-medium shadow-sm transition-all",
                          !isTracked && "bg-primary hover:bg-primary/90 hover:shadow-primary/20",
                          isTracked && "hover:bg-destructive/10 hover:text-destructive"
                      )}
                      onClick={handleTrackToggle}
                  >
                      {isTracked ? (
                          <>
                              <Ban className="mr-2 h-3.5 w-3.5" />
                              Untrack
                          </>
                      ) : (
                          <>
                              <Plus className="mr-2 h-3.5 w-3.5" />
                              Track Token
                          </>
                      )}
                  </Button>
                  
                  <Button
                      variant="ghost"
                      size="icon"
                      className="h-9 w-9 text-muted-foreground/50 hover:text-destructive hover:bg-destructive/10"
                      onClick={() => onDelete(notification.id)}
                  >
                      <Trash2 className="h-4 w-4" />
                  </Button>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function NotificationsPage() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const router = useRouter();
  
  // Hooks
  const { data, isLoading: notifLoading } = useNotifications({ limit: 50 });
  const { 
      trackToken, 
      untrackToken, 
      isTracked,
      trackedTokens 
  } = useTrackedTokens();
  
  const markRead = useMarkNotificationsRead();
  const markAllRead = useMarkAllRead();
  const deleteNotif = useDeleteNotification();
  const clearAll = useClearAllNotifications();

  // Redirect if not auth
  if (!authLoading && !isAuthenticated) {
    router.push('/login');
    return null;
  }

  // Loading state
  if (authLoading || notifLoading) {
     return (
       <div className="container max-w-4xl py-8 space-y-6">
           <Skeleton className="h-12 w-48" />
           <div className="space-y-4">
               {[1, 2, 3].map((i) => (
                   <div key={i} className="h-32 rounded-xl border bg-card p-6">
                       <div className="flex gap-4">
                           <Skeleton className="h-10 w-10 rounded-full" />
                           <div className="space-y-2 flex-1">
                               <Skeleton className="h-4 w-1/3" />
                               <Skeleton className="h-4 w-2/3" />
                           </div>
                       </div>
                   </div>
               ))}
           </div>
       </div>
     );
  }

  const notifications = data?.notifications || [];
  const unreadCount = data?.unread_count || 0;

  return (
    <div className="container max-w-4xl py-8 space-y-8 animate-in fade-in duration-500">
      {/* Header Section */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b pb-6">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight">Detections</h1>
          <p className="text-muted-foreground text-lg">
            Real-time contract discoveries from your monitored channels
          </p>
        </div>
        
        <div className="flex items-center gap-2">
            {notifications.length > 0 && (
                <>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => markAllRead.mutate()}
                        disabled={markAllRead.isPending || unreadCount === 0}
                    >
                        <CheckCheck className="h-4 w-4 mr-2" />
                        Mark all read
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => clearAll.mutate()}
                        disabled={clearAll.isPending}
                        className="text-destructive hover:text-destructive hover:bg-destructive/10 hover:border-destructive/20"
                    >
                        <Trash2 className="h-4 w-4 mr-2" />
                        Clear History
                    </Button>
                </>
            )}
        </div>
      </div>

      {/* Main Content */}
      <div className="min-h-[400px]">
          {notifications.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-center border-2 border-dashed rounded-xl bg-muted/10">
                  <div className="h-16 w-16 rounded-full bg-muted/30 flex items-center justify-center mb-4">
                      <Search className="h-8 w-8 text-muted-foreground/50" />
                  </div>
                  <h3 className="text-xl font-semibold mb-2">No detections yet</h3>
                  <p className="text-muted-foreground max-w-md mx-auto mb-6">
                      We're scanning your channels for new contract addresses. 
                      Once a contract is detected, it will appear here.
                  </p>
                  <Button onClick={() => router.push('/dashboard')}>
                      Go to Dashboard
                  </Button>
              </div>
          ) : (
              <div className="space-y-4">
                  {notifications.map((notif) => (
                      <DetectionItem
                          key={notif.id}
                          notification={notif}
                          onMarkRead={(id) => markRead.mutate([id])}
                          onDelete={(id) => deleteNotif.mutate(id)}
                          tracking={{
                              track: trackToken,
                              untrack: untrackToken,
                              isTracking: isTracked,
                              trackedTokens: trackedTokens
                          }}
                      />
                  ))}
              </div>
          )}
      </div>
    </div>
  );
}
