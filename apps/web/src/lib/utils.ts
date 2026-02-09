import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(num: number): string {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M';
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K';
  }
  return num.toFixed(2);
}

export function formatPercent(num: number): string {
  const sign = num >= 0 ? '+' : '';
  return sign + num.toFixed(2) + '%';
}

export function formatPrice(price: number | null): string {
  if (price === null) return 'N/A';
  if (price < 0.01) return '$' + price.toFixed(8);
  if (price < 1) return '$' + price.toFixed(4);
  return '$' + price.toFixed(2);
}

export function timeAgo(date: string | Date): string {
  const now = new Date();
  const then = typeof date === 'string' ? new Date(date) : date;
  
  // Check if date is valid
  if (isNaN(then.getTime())) {
    return 'unknown';
  }
  
  const seconds = Math.floor((now.getTime() - then.getTime()) / 1000);

  // Handle future dates or very recent
  if (seconds < 0) return 'just now';
  if (seconds < 10) return 'just now';
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) {
    const mins = Math.floor(seconds / 60);
    return `${mins}m ago`;
  }
  if (seconds < 86400) {
    const hours = Math.floor(seconds / 3600);
    return `${hours}h ago`;
  }
  if (seconds < 604800) {
    const days = Math.floor(seconds / 86400);
    return `${days}d ago`;
  }
  // Show actual date for older items
  return then.toLocaleDateString();
}

export function getSentimentColor(sentiment: string): string {
  switch (sentiment) {
    case 'BULLISH':
      return 'text-green-500';
    case 'BEARISH':
      return 'text-red-500';
    default:
      return 'text-yellow-500';
  }
}

export function getSentimentBgColor(sentiment: string): string {
  switch (sentiment) {
    case 'BULLISH':
      return 'bg-green-500/10 border-green-500/20';
    case 'BEARISH':
      return 'bg-red-500/10 border-red-500/20';
    default:
      return 'bg-yellow-500/10 border-yellow-500/20';
  }
}

export function getChainUrl(chain: string | undefined, address: string) {
  // If we want to return a URL that CAN be opened in a new tab, we keep the /explorer structure
  const safeChain = chain ? chain.toLowerCase() : 'eth';
  return `/explorer/${encodeURIComponent(safeChain)}/${encodeURIComponent(address)}`;
}

