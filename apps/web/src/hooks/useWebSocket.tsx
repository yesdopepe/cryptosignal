'use client';

import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type {
  WebSocketMessage,
  WebSocketCommand,
  NewSignalMessage,
  SentimentUpdateMessage,
  TrendingUpdateMessage,
  MarketUpdateMessage,
  TrackedPriceUpdateMessage,
  TrackedTransferMessage,
  TrackedTokenPrice,
  TrackedTransfer,
  Sentiment,
} from '@crypto-signal/shared';
import { getAuthToken } from '@/lib/api';

interface SignalData {
  id: number;
  token_symbol: string;
  token_name: string;
  channel_name: string;
  sentiment: Sentiment;
  price_at_signal: number | null;
  confidence_score: number;
  timestamp: string;
}

interface SentimentData {
  overall: Sentiment;
  score: number;
}

interface TrendingData {
  top_tokens: Array<{
    symbol: string;
    count: number;
    change: number;
  }>;
}

interface ChannelMessage {
  channel_name: string;
  channel_id: number;
  text: string;
  message_id: number;
  timestamp: string;
  has_signal: boolean;
  signal_type?: string | null;
  token_symbol?: string | null;
  contract_addresses?: string[];
  chain?: string | null;
  sentiment?: string | null;
}

interface WebSocketContextValue {
  isConnected: boolean;
  signals: SignalData[];
  marketUpdates: MarketUpdateMessage[];
  sentiment: SentimentData | null;
  trending: TrendingData | null;
  trackedPrices: Record<string, TrackedTokenPrice>;
  trackedTransfers: TrackedTransfer[];
  priceHistory: Record<string, { t: string; p: number }[]>;
  channelMessages: ChannelMessage[];
  subscribe: (type: 'token' | 'channel', value: string) => void;
  unsubscribe: (type: 'token' | 'channel', value: string) => void;
  clearSignals: () => void;
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

const getWebSocketUrl = () => {
  if (typeof window === 'undefined') return ''; // Server-side check

  // 1. Explicit WebSocket URL (highest priority)
  if (process.env.NEXT_PUBLIC_WS_URL) {
    return process.env.NEXT_PUBLIC_WS_URL;
  }

  // 2. Derive from API URL
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';
  
  // If API URL is a full URL starting with http/https
  if (apiUrl.startsWith('http')) {
    const isSecure = apiUrl.startsWith('https');
    const wsProtocol = isSecure ? 'wss://' : 'ws://';
    let baseUrl = apiUrl.replace(/^https?:\/\//, wsProtocol);
    
    // Remove trailing slash
    if (baseUrl.endsWith('/')) {
      baseUrl = baseUrl.slice(0, -1);
    }
    
    // Remove /api/v1 suffix if present to avoid duplication
    // We already know we want to append /api/v1/live/stream
    if (baseUrl.endsWith('/api/v1')) {
      baseUrl = baseUrl.replace(/\/api\/v1$/, '');
    }
    
    return baseUrl + '/api/v1/live/stream';
  }

  // 3. Default to localhost:8000 for development (backend runs on 8000)
  // This handles the case where API_URL is relative (e.g., '/api/v1') 
  // and we're using Next.js rewrites
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    return 'ws://localhost:8000/api/v1/live/stream';
  }

  // 4. Production fallback: use current host (assumes reverse proxy)
  const wsProtocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
  return `${wsProtocol}${window.location.host}/api/v1/live/stream`;
};

const MAX_SIGNALS = 100;
const RECONNECT_INTERVAL = 3000;
const MAX_RECONNECT_ATTEMPTS = 10;

export function WebSocketProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [isConnected, setIsConnected] = useState(false);
  const [signals, setSignals] = useState<SignalData[]>([]);
  const [marketUpdates, setMarketUpdates] = useState<MarketUpdateMessage[]>([]);
  const [sentiment, setSentiment] = useState<SentimentData | null>(null);
  const [trending, setTrending] = useState<TrendingData | null>(null);
  const [trackedPrices, setTrackedPrices] = useState<Record<string, TrackedTokenPrice>>({});
  const [trackedTransfers, setTrackedTransfers] = useState<TrackedTransfer[]>([]);
  const [priceHistory, setPriceHistory] = useState<Record<string, { t: string; p: number }[]>>({});
  const [channelMessages, setChannelMessages] = useState<ChannelMessage[]>([]);
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimeout = useRef<NodeJS.Timeout | null>(null);
  const pingInterval = useRef<NodeJS.Timeout | null>(null);

  const sendCommand = useCallback((command: WebSocketCommand) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(command));
    }
  }, []);

  const subscribe = useCallback((type: 'token' | 'channel', value: string) => {
    sendCommand({ action: 'subscribe', type, value });
  }, [sendCommand]);

  const unsubscribe = useCallback((type: 'token' | 'channel', value: string) => {
    sendCommand({ action: 'unsubscribe', type, value });
  }, [sendCommand]);

  const clearSignals = useCallback(() => {
    setSignals([]);
    setMarketUpdates([]);
    setChannelMessages([]);
  }, []);

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const message: WebSocketMessage = JSON.parse(event.data);

      switch (message.type) {
        case 'connected':
          console.log('WebSocket connected:', message.message);
          break;

        case 'new_signal': {
          const signalMsg = message as NewSignalMessage;
          setSignals((prev) => {
            const newSignals = [signalMsg.data, ...prev];
            return newSignals.slice(0, MAX_SIGNALS);
          });
          // Invalidate signals query so REST-based pages refresh
          queryClient.invalidateQueries({ queryKey: ['signals'] });
          break;
        }

        case 'MARKET_UPDATE': {
          const marketMsg = message as MarketUpdateMessage;
          setMarketUpdates((prev) => {
            const newUpdates = [marketMsg, ...prev];
            return newUpdates.slice(0, MAX_SIGNALS);
          });
          break;
        }

        case 'sentiment_update': {
          const sentimentMsg = message as SentimentUpdateMessage;
          setSentiment(sentimentMsg.data);
          break;
        }

        case 'trending_update': {
          const trendingMsg = message as TrendingUpdateMessage;
          setTrending(trendingMsg.data);
          break;
        }

        case 'tracked_price_update': {
          const priceMsg = message as TrackedPriceUpdateMessage;
          if (priceMsg.data?.tokens) {
            setTrackedPrices((prev) => {
              const updated = { ...prev };
              for (const token of priceMsg.data.tokens) {
                updated[token.symbol.toUpperCase()] = token;
              }
              return updated;
            });
            // Accumulate price history for candlestick charts
            setPriceHistory((prev) => {
              const next = { ...prev };
              for (const token of priceMsg.data.tokens) {
                const sym = token.symbol.toUpperCase();
                if (token.price_usd != null) {
                  const arr = next[sym] ? [...next[sym]] : [];
                  arr.push({ t: new Date().toISOString(), p: token.price_usd });
                  next[sym] = arr.length > 500 ? arr.slice(-500) : arr;
                }
              }
              return next;
            });
          }
          break;
        }

        case 'tracked_transfer': {
          const transferMsg = message as TrackedTransferMessage;
          if (transferMsg.data) {
            setTrackedTransfers((prev) => {
              const next = [transferMsg.data, ...prev];
              return next.slice(0, 50); // keep last 50
            });
          }
          break;
        }

        case 'notification': {
          // Real-time notification push — invalidate notification caches
          console.log('WebSocket notification received:', (message as any).data);
          queryClient.invalidateQueries({ queryKey: ['notifications'] });
          break;
        }

        case 'channel_message': {
          // Live channel message from background monitoring
          const cm = (message as any).data as ChannelMessage;
          if (cm) {
            setChannelMessages((prev) => {
              const next = [cm, ...prev];
              return next.slice(0, 200); // keep last 200
            });
          }
          break;
        }

        case 'monitoring_status': {
          // Monitoring started/stopped — refresh monitoring status queries
          queryClient.invalidateQueries({ queryKey: ['monitoringStatus'] });
          queryClient.invalidateQueries({ queryKey: ['userTelegramStatus'] });
          break;
        }

        case 'pong':
          // Heartbeat response
          break;

        case 'error':
          console.error('WebSocket error:', message);
          break;
      }
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  }, [queryClient]);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      // Add auth token to WebSocket URL if available
      const token = getAuthToken();
      const baseUrl = getWebSocketUrl();
      const wsUrl = token ? `${baseUrl}?token=${encodeURIComponent(token)}` : baseUrl;
      
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        reconnectAttempts.current = 0;

        // Start ping interval
        pingInterval.current = setInterval(() => {
          sendCommand({ action: 'ping' });
        }, 30000);
      };

      wsRef.current.onmessage = handleMessage;

      wsRef.current.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason);
        setIsConnected(false);

        if (pingInterval.current) {
          clearInterval(pingInterval.current);
        }

        // Attempt reconnect
        if (reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttempts.current++;
          const delay = Math.min(RECONNECT_INTERVAL * reconnectAttempts.current, 30000);
          console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current})`);
          
          reconnectTimeout.current = setTimeout(() => {
            connect();
          }, delay);
        }
      };

      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
    }
  }, [handleMessage, sendCommand]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
      }
      if (pingInterval.current) {
        clearInterval(pingInterval.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  return (
    <WebSocketContext.Provider
      value={{
        isConnected,
        signals,
        marketUpdates,
        sentiment,
        trending,
        trackedPrices,
        trackedTransfers,
        priceHistory,
        channelMessages,
        subscribe,
        unsubscribe,
        clearSignals,
      }}
    >
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWebSocket() {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
}
