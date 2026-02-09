'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { getTokenByAddress, TokenSearchResult } from '@/lib/api';
import { TokenCandleChart } from '@/components/charts/TokenCandleChart';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { ArrowLeft, ExternalLink, Copy, Check, TrendingUp } from 'lucide-react';
import { useTrackedTokens } from '@/hooks/useTrackedTokens';
import Link from 'next/link';
import { cn } from '@/lib/utils';

export default function ExplorerPage() {
    const params = useParams();
    // Decode params if they come encoded
    const chain = decodeURIComponent(params.chain as string);
    const address = decodeURIComponent(params.address as string);

    const [token, setToken] = useState<TokenSearchResult | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [copied, setCopied] = useState(false);

    const { trackToken, untrackToken, isTracked } = useTrackedTokens();

    useEffect(() => {
        if (!address) return;
        setLoading(true);
        getTokenByAddress(address, chain)
            .then((res) => {
                if (res.results && res.results.length > 0) {
                    setToken(res.results[0]);
                } else if (res.results.length === 0) {
                     // If api returns empty list, maybe try to construct a dummy token if we assume it exists?
                     // Or just show error.
                     setError('Token not found on ' + chain);
                }
            })
            .catch((err) => {
                console.error(err);
                setError('Failed to load token data');
            })
            .finally(() => setLoading(false));
    }, [address, chain]);

    const isTokenTracked = token ? isTracked(token.symbol) : false;

    const copyAddress = () => {
        navigator.clipboard.writeText(address);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    if (loading) {
        return (
            <div className="container py-8 space-y-6">
                <Skeleton className="h-12 w-64" />
                <Skeleton className="h-96 w-full rounded-xl" />
            </div>
        );
    }

    if (error || !token) {
        return (
            <div className="container py-8 flex flex-col items-center justify-center min-h-[50vh] text-center space-y-4">
                <div className="h-16 w-16 bg-muted rounded-full flex items-center justify-center">
                    <TrendingUp className="h-8 w-8 text-muted-foreground" />
                </div>
                <div>
                     <h2 className="text-xl font-bold">Token not found</h2>
                     <p className="text-muted-foreground">Could not resolve token data for {address} on {chain}.</p>
                </div>
                <Link href="/dashboard"><Button>Back to Dashboard</Button></Link>
            </div>
        );
    }

    // Determine external explorer URL for fallback
    const getExtUrl = () => {
        const c = chain ? chain.toLowerCase() : 'eth';
        if (c === 'solana') return `https://solscan.io/token/${address}`;
        if (c === 'bsc') return `https://bscscan.com/token/${address}`;
        if (c === 'base') return `https://basescan.org/token/${address}`;
        if (c === 'arbitrum') return `https://arbiscan.io/token/${address}`;
        return `https://etherscan.io/token/${address}`;
    };

    return (
        <div className="container max-w-7xl py-8 space-y-8 animate-in fade-in duration-500">
             {/* Header */}
             <div className="flex flex-col md:flex-row md:items-center gap-6 justify-between">
                 <div className="flex items-center gap-4">
                     <Link href="/dashboard" className="text-muted-foreground hover:text-foreground transition-colors p-2 hover:bg-muted/50 rounded-full">
                         <ArrowLeft className="h-5 w-5" />
                     </Link>
                     <div className="flex items-center gap-4">
                         {token.logo ? (
                             <img src={token.logo} alt={token.symbol} className="w-12 h-12 rounded-full border border-border/50" />
                         ) : (
                             <div className="w-12 h-12 rounded-full border border-primary/20 bg-primary/10 flex items-center justify-center text-primary font-bold">
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
                                     {chain}
                                 </Badge>
                                 <div 
                                     className="flex items-center gap-1.5 bg-muted/40 px-2 py-0.5 rounded-md border border-border/50 cursor-pointer hover:bg-muted transition-colors group" 
                                     onClick={copyAddress}
                                     title="Copy address"
                                 >
                                     <code className="text-xs font-mono text-muted-foreground group-hover:text-foreground transition-colors">
                                         {address}
                                     </code>
                                     {copied ? <Check className="h-3 w-3 text-green-500" /> : <Copy className="h-3 w-3 opacity-50" />}
                                 </div>
                             </div>
                         </div>
                     </div>
                 </div>

                 <div className="flex gap-2 ml-14 md:ml-0">
                     <a href={getExtUrl()} target="_blank" rel="noreferrer">
                         <Button variant="outline" size="sm" className="h-9">
                             <ExternalLink className="h-4 w-4 mr-2" />
                             External Explorer
                         </Button>
                     </a>
                     <Button
                        variant={isTokenTracked ? "secondary" : "default"}
                        size="sm"
                        className="h-9 min-w-[100px]"
                        onClick={() => isTokenTracked 
                             ? untrackToken(token.symbol) 
                             : trackToken(token.symbol, token.name, chain, address)
                        }
                     >
                         {isTokenTracked ? "Untrack" : "Track Token"}
                     </Button>
                 </div>
             </div>

             {/* Content Grid */}
             <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                 {/* Main Chart Column */}
                 <div className="lg:col-span-2 space-y-6">
                     <Card className="overflow-hidden border-border/50 shadow-sm">
                         <CardHeader className="border-b border-border/50 bg-muted/20 pb-4">
                             <CardTitle className="text-base font-medium flex items-center gap-2">
                                 <TrendingUp className="h-4 w-4 text-primary" />
                                 Price Chart
                             </CardTitle>
                         </CardHeader>
                         <CardContent className="p-0">
                             <div className="p-6">
                                 <TokenCandleChart symbol={token.symbol} height={450} days={30} />
                             </div>
                         </CardContent>
                     </Card>
                 </div>

                 {/* Stats Column */}
                 <div className="space-y-6">
                     <Card className="border-border/50 shadow-sm">
                         <CardHeader className="border-b border-border/50 bg-muted/20 pb-4">
                             <CardTitle className="text-base font-medium">Market Data</CardTitle>
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
    );
}