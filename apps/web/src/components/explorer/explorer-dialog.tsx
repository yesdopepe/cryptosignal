'use client';

import { useEffect, useState } from 'react';
import { getTokenByAddress, TokenSearchResult } from '@/lib/api';
import { TokenCandleChart } from '@/components/charts/TokenCandleChart';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { ExternalLink, Copy, Check, TrendingUp, X } from 'lucide-react';
import { useTrackedTokens } from '@/hooks/useTrackedTokens';
import { Dialog, DialogContent } from '@/components/ui/dialog';
import { useExplorer } from '@/hooks/useExplorer';

export function ExplorerDialog() {
    const { isOpen, chain, address, closeExplorer } = useExplorer();
    const [token, setToken] = useState<TokenSearchResult | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [copied, setCopied] = useState(false);

    const { trackToken, untrackToken, isTracked } = useTrackedTokens();

    useEffect(() => {
        if (!isOpen || !address) return;
        
        setLoading(true);
        setError('');
        setToken(null);
        
        getTokenByAddress(address, chain)
            .then((res) => {
                if (res.results && res.results.length > 0) {
                    setToken(res.results[0]);
                } else if (res.results.length === 0) {
                     setError('Token not found on ' + (chain || 'network'));
                }
            })
            .catch((err) => {
                console.error(err);
                setError('Failed to load token data');
            })
            .finally(() => setLoading(false));
    }, [isOpen, address, chain]);

    const isTokenTracked = token ? isTracked(token.symbol) : false;

    const copyAddress = () => {
        if (!address) return;
        navigator.clipboard.writeText(address);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    // External URL Fallback
    const getExtUrl = () => {
        const c = chain ? chain.toLowerCase() : 'eth';
        const addr = address || '';
        if (c === 'solana') return `https://solscan.io/token/${addr}`;
        if (c === 'bsc') return `https://bscscan.com/token/${addr}`;
        if (c === 'base') return `https://basescan.org/token/${addr}`;
        if (c === 'arbitrum') return `https://arbiscan.io/token/${addr}`;
        return `https://etherscan.io/token/${addr}`;
    };

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && closeExplorer()}>
            <DialogContent className="max-w-5xl h-[90vh] p-0 overflow-hidden flex flex-col gap-0 border-border/50 sm:rounded-2xl">
                 {/* Custom Header with close button */}
                 <div className="flex items-center justify-between p-4 px-6 border-b border-border/40 bg-muted/20">
                    <h2 className="text-lg font-semibold flex items-center gap-2">
                        <TrendingUp className="h-5 w-5 text-primary" />
                        Token Explorer
                    </h2>
                    {/* Close button is automatically added by DialogContent usually, but we can have custom header too */}
                 </div>

                 <div className="flex-1 overflow-y-auto p-6 scrollbar-thin">
                    {loading ? (
                        <div className="space-y-6 h-full flex flex-col">
                            <div className="flex items-center gap-4">
                                <Skeleton className="h-12 w-12 rounded-full" />
                                <div className="space-y-2">
                                    <Skeleton className="h-6 w-48" />
                                    <Skeleton className="h-4 w-24" />
                                </div>
                            </div>
                            <Skeleton className="h-96 w-full rounded-xl flex-1" />
                        </div>
                    ) : error || !token ? (
                        <div className="flex flex-col items-center justify-center h-full text-center space-y-4 min-h-[400px]">
                            <div className="h-16 w-16 bg-muted rounded-full flex items-center justify-center">
                                <TrendingUp className="h-8 w-8 text-muted-foreground" />
                            </div>
                            <div>
                                <h3 className="text-xl font-bold">Token not found</h3>
                                <p className="text-muted-foreground">Could not resolve token data for {address} on {chain}.</p>
                            </div>
                            <div className="flex gap-2">
                                <Button variant="outline" onClick={closeExplorer}>Close</Button>
                                <a href={getExtUrl()} target="_blank" rel="noreferrer">
                                    <Button>View on Explorer</Button>
                                </a>
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-8 animate-in fade-in zoom-in-95 duration-200">
                             {/* Top Info Bar */}
                             <div className="flex flex-col md:flex-row md:items-center gap-6 justify-between">
                                 <div className="flex items-center gap-4">
                                     {token.logo ? (
                                         <img src={token.logo} alt={token.symbol} className="w-12 h-12 rounded-full border border-border/50" />
                                     ) : (
                                         <div className="w-12 h-12 rounded-full border border-primary/20 bg-primary/10 flex items-center justify-center text-primary font-bold text-lg">
                                             {token.symbol.substring(0,2)}
                                         </div>
                                     )}
                                     <div>
                                         <h1 className="text-2xl font-bold flex items-center gap-3">
                                             {token.name} 
                                             <Badge variant="secondary" className="text-base font-normal px-2">
                                                 {token.symbol}
                                             </Badge>
                                         </h1>
                                         <div className="flex items-center gap-3 mt-1.5">
                                             <Badge variant="outline" className="uppercase text-[10px] tracking-wider font-semibold">
                                                 {chain || 'unknown'}
                                             </Badge>
                                             <div 
                                                 className="flex items-center gap-1.5 bg-muted/40 px-2 py-0.5 rounded-md border border-border/50 cursor-pointer hover:bg-muted transition-colors group" 
                                                 onClick={copyAddress}
                                                 title="Copy address"
                                             >
                                                 <code className="text-xs font-mono text-muted-foreground group-hover:text-foreground transition-colors">
                                                     {address?.substring(0, 8)}...{address?.substring(address.length - 8)}
                                                 </code>
                                                 {copied ? <Check className="h-3 w-3 text-green-500" /> : <Copy className="h-3 w-3 opacity-50" />}
                                             </div>
                                         </div>
                                     </div>
                                 </div>

                                 <div className="flex gap-2 ml-16 md:ml-0">
                                     <a href={getExtUrl()} target="_blank" rel="noreferrer">
                                         <Button variant="outline" size="sm" className="h-9">
                                             <ExternalLink className="h-4 w-4 mr-2" />
                                             External
                                         </Button>
                                     </a>
                                     <Button
                                        variant={isTokenTracked ? "secondary" : "default"}
                                        size="sm"
                                        className="h-9 min-w-[100px]"
                                        onClick={() => isTokenTracked 
                                             ? untrackToken(token.symbol) 
                                             : trackToken(token.symbol, token.name, chain || 'unknown', address || undefined)
                                        }
                                     >
                                         {isTokenTracked ? "Untrack" : "Track"}
                                     </Button>
                                 </div>
                             </div>

                             {/* Content Grid */}
                             <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                                 {/* Main Chart Column */}
                                 <div className="lg:col-span-2 space-y-6">
                                     <Card className="overflow-hidden border-border/50 shadow-sm">
                                         <CardHeader className="border-b border-border/50 bg-muted/20 pb-4 py-3">
                                             <CardTitle className="text-sm font-medium flex items-center gap-2 text-muted-foreground">
                                                 Price Chart (30D)
                                             </CardTitle>
                                         </CardHeader>
                                         <CardContent className="p-0">
                                             <div className="h-[400px] w-full">
                                                 <TokenCandleChart symbol={token.symbol} height={400} days={30} />
                                             </div>
                                         </CardContent>
                                     </Card>
                                 </div>

                                 {/* Stats Column */}
                                 <div className="space-y-6">
                                     <Card className="border-border/50 shadow-sm h-full">
                                         <CardHeader className="border-b border-border/50 bg-muted/20 pb-4 py-3">
                                             <CardTitle className="text-sm font-medium text-muted-foreground">Market Data</CardTitle>
                                         </CardHeader>
                                         <CardContent className="p-6 space-y-6">
                                             <div>
                                                 <p className="text-sm font-medium text-muted-foreground mb-1">Price USD</p>
                                                 <div className="flex items-baseline gap-2">
                                                     <p className="text-3xl font-bold tracking-tight">
                                                         ${token.price_usd !== null && token.price_usd !== undefined 
                                                            ? (token.price_usd < 0.01 ? token.price_usd.toFixed(8) : token.price_usd.toFixed(4)) 
                                                            : 'N/A'}
                                                     </p>
                                                     {token.price_change_24h !== undefined && token.price_change_24h !== null && (
                                                         <Badge variant={token.price_change_24h >= 0 ? "success" : "destructive"} className="h-6">
                                                             {token.price_change_24h > 0 ? '+' : ''}{token.price_change_24h.toFixed(2)}%
                                                         </Badge>
                                                     )}
                                                 </div>
                                             </div>

                                             <div className="grid grid-cols-2 gap-4">
                                                 <div className="p-3 bg-muted/30 rounded-lg space-y-1">
                                                     <p className="text-xs text-muted-foreground uppercase font-semibold">Decimals</p>
                                                     <p className="font-mono font-medium">{token.decimals || '?'}</p>
                                                 </div>
                                                 <div className="p-3 bg-muted/30 rounded-lg space-y-1">
                                                     <p className="text-xs text-muted-foreground uppercase font-semibold">Rank</p>
                                                     <p className="font-mono font-medium">#{token.market_cap_rank || 'N/A'}</p>
                                                 </div>
                                             </div>
                                             
                                             <div className="text-xs text-muted-foreground pt-4 border-t border-border/50">
                                                 Data provided by CoinGecko & Moralis
                                             </div>
                                         </CardContent>
                                     </Card>
                                 </div>
                             </div>
                        </div>
                    )}
                 </div>
            </DialogContent>
        </Dialog>
    );
}