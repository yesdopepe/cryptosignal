// ============== Entity Types ==============

export interface Signal {
  id: number;
  channel_id: number;
  channel_name: string;
  token_symbol: string;
  token_name: string;
  price_at_signal: number | null;
  current_price: number | null;
  signal_type: 'full_signal' | 'contract_detection' | 'token_mention';
  contract_addresses: string[];
  chain: string | null;
  sentiment: Sentiment;
  message_text: string;
  confidence_score: number;
  timestamp: string;
  success: boolean | null;
  roi_percent: number | null;
  tags: string[];
}

export interface Channel {
  id: number;
  name: string;
  telegram_id: string;
  description: string | null;
  subscriber_count: number;
  success_rate: number;
  total_signals: number;
  avg_roi: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Token {
  id: number;
  symbol: string;
  name: string;
  current_price: number | null;
  market_cap: number | null;
  volume_24h: number | null;
  price_change_24h: number | null;
  first_seen: string;
  last_updated: string;
}

// ============== Enums ==============

export type Sentiment = 'BULLISH' | 'BEARISH' | 'NEUTRAL';

// ============== API Response Types ==============

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface SignalListResponse extends PaginatedResponse<Signal> {}

export interface ChannelListResponse extends PaginatedResponse<Channel> {}

// ============== Analytics Types ==============

export interface TrendingToken {
  rank: number;
  symbol: string;
  name: string;
  signal_count_24h: number;
  signal_change_percent: number;
  momentum_score: number;
  avg_roi_24h: number;
  dominant_sentiment: Sentiment;
  price?: number | null;
  price_change_24h?: number | null;
}

export interface MarketSentiment {
  overall_sentiment: Sentiment;
  sentiment_score: number; // -1 to 1
  fear_greed_index: number; // 0 to 100
  bullish_percent: number;
  bearish_percent: number;
  neutral_percent: number;
  signals_analyzed: number;
  time_period_hours: number;
  top_bullish_tokens: string[];
  top_bearish_tokens: string[];
  timestamp: string;
}

export interface ChannelLeaderboardEntry {
  rank: number;
  channel_id: number;
  channel_name: string;
  success_rate: number;
  avg_roi: number;
  total_signals: number;
  score: number;
  win_streak: number;
  best_call: string | null;
}

export interface TokenStats {
  symbol: string;
  name: string;
  total_signals: number;
  success_rate: number;
  avg_roi: number;
  volatility: number;
  sentiment_distribution: {
    bullish: number;
    bearish: number;
    neutral: number;
  };
  roi_distribution: {
    positive: number;
    negative: number;
    neutral: number;
  };
  performance_trend: PerformanceTrendPoint[];
  first_signal_date: string;
  last_signal_date: string;
}

export interface PerformanceTrendPoint {
  date: string;
  avg_roi: number;
  signal_count: number;
  success_rate: number;
}

export interface PatternInfo {
  pattern_type: string;
  confidence: number;
  description: string;
  tokens_affected: string[];
  supporting_signals: number;
  detected_at: string;
}

export interface PlatformStats {
  websocket_connections: number;
  total_signals: number;
  total_channels: number;
  total_tokens: number;
  signals_last_hour: number;
  active_channels: number;
  tokens_tracked: number;
  success_rate: number;
  signals_24h: number;
  avg_roi_24h: number;
  timestamp: string;
  status: string;
}

// ============== WebSocket Types ==============

export type WebSocketMessageType =
  | 'connected'
  | 'new_signal'
  | 'sentiment_update'
  | 'trending_update'
  | 'tracked_price_update'
  | 'tracked_transfer'
  | 'MARKET_UPDATE'
  | 'notification'
  | 'channel_message'
  | 'monitoring_status'
  | 'subscribed'
  | 'unsubscribed'
  | 'pong'
  | 'error';

export interface BaseWebSocketMessage {
  type: WebSocketMessageType;
  timestamp: string;
}

export interface ConnectedMessage extends BaseWebSocketMessage {
  type: 'connected';
  message: string;
}

export interface NewSignalMessage extends BaseWebSocketMessage {
  type: 'new_signal';
  data: {
    id: number;
    token_symbol: string;
    token_name: string;
    channel_name: string;
    sentiment: Sentiment;
    price_at_signal: number | null;
    confidence_score: number;
    signal_type: string;
    contract_addresses: string[];
    chain: string | null;
    timestamp: string;
  };
}

export interface SentimentUpdateMessage extends BaseWebSocketMessage {
  type: 'sentiment_update';
  data: {
    overall: Sentiment;
    score: number;
  };
}

export interface TrendingUpdateMessage extends BaseWebSocketMessage {
  type: 'trending_update';
  data: {
    top_tokens: Array<{
      symbol: string;
      count: number;
      change: number;
    }>;
  };
}

export interface TrackedTokenPrice {
  symbol: string;
  chain?: string;
  address?: string;
  price_usd: number | null;
  price_change_24h: number | null;
  token_name?: string;
  token_logo?: string;
  market_cap?: number | null;
  volume_24h?: number | null;
  cmc_rank?: number | null;
  updated_at?: string;
}

export interface TrackedPriceUpdateMessage extends BaseWebSocketMessage {
  type: 'tracked_price_update';
  data: {
    tokens: TrackedTokenPrice[];
  };
}

export interface TrackedTransfer {
  symbol: string;
  chain_id: string;
  address: string;
  from: string;
  to: string;
  value: string;
  token_name: string;
  token_symbol: string;
  tx_hash: string;
  confirmed: boolean;
  block_number: string | null;
  block_timestamp: string | null;
  timestamp: string;
}

export interface TrackedTransferMessage extends BaseWebSocketMessage {
  type: 'tracked_transfer';
  data: TrackedTransfer;
}

export interface MarketUpdateMessage extends BaseWebSocketMessage {
  type: 'MARKET_UPDATE';
  source: string;
  data: any;
}

export interface SubscribedMessage extends BaseWebSocketMessage {
  type: 'subscribed';
  sub_type: 'token' | 'channel';
  value: string;
}

export interface UnsubscribedMessage extends BaseWebSocketMessage {
  type: 'unsubscribed';
  sub_type: 'token' | 'channel';
  value: string;
}

export interface PongMessage extends BaseWebSocketMessage {
  type: 'pong';
}

export interface ErrorMessage extends BaseWebSocketMessage {
  type: 'error';
  message: string;
}

export interface NotificationMessage extends BaseWebSocketMessage {
  type: 'notification';
  data: Record<string, any>;
}

export interface ChannelMessageMessage extends BaseWebSocketMessage {
  type: 'channel_message';
  data: {
    channel_name: string;
    channel_id: number;
    text: string;
    message_id: number;
    timestamp: string;
    has_signal: boolean;
    signal_type: string | null;
    token_symbol: string | null;
    contract_addresses: string[];
    chain: string | null;
    sentiment: string | null;
  };
}

export interface MonitoringStatusMessage extends BaseWebSocketMessage {
  type: 'monitoring_status';
  data: {
    is_monitoring: boolean;
    channels_count: number;
    message: string;
  };
}

export type WebSocketMessage =
  | ConnectedMessage
  | NewSignalMessage
  | SentimentUpdateMessage
  | TrendingUpdateMessage
  | TrackedPriceUpdateMessage
  | TrackedTransferMessage
  | MarketUpdateMessage
  | NotificationMessage
  | ChannelMessageMessage
  | MonitoringStatusMessage
  | SubscribedMessage
  | UnsubscribedMessage
  | PongMessage
  | ErrorMessage;

// ============== WebSocket Client Commands ==============

export type WebSocketAction = 'subscribe' | 'unsubscribe' | 'ping';

export interface SubscribeCommand {
  action: 'subscribe';
  type: 'token' | 'channel';
  value: string;
}

export interface UnsubscribeCommand {
  action: 'unsubscribe';
  type: 'token' | 'channel';
  value: string;
}

export interface PingCommand {
  action: 'ping';
}

export type WebSocketCommand = SubscribeCommand | UnsubscribeCommand | PingCommand;

// ============== Telegram Types ==============

export type AuthState = 'not_started' | 'awaiting_code' | 'awaiting_2fa' | 'authenticated' | 'error';

export interface TelegramStatus {
  is_running: boolean;
  is_connected: boolean;
  mock_mode: boolean;
  auth_state: AuthState;
  phone_number: string | null;
  channels_monitored: number;
  channels: string[];
  callbacks_registered: number;
  auth_error: string | null;
}

export interface TelegramAuthResponse {
  success: boolean;
  message?: string;
  error?: string;
  auth_state: AuthState;
  requires_2fa?: boolean;
}

// ============== Chart Data Types ==============

export interface SignalChartPoint {
  timestamp: string;
  count: number;
  bullish: number;
  bearish: number;
  neutral: number;
}

export interface ROIChartPoint {
  timestamp: string;
  roi: number;
  cumulative_roi: number;
}

export interface TokenDistribution {
  symbol: string;
  count: number;
  percentage: number;
}
