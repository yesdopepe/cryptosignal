import type {
  Signal,
  Channel,
  PaginatedResponse,
  PlatformStats,
  MarketSentiment,
  TrendingToken,
  ChannelLeaderboardEntry,
  TokenStats,
  PatternInfo,
  TelegramStatus,
  TelegramAuthResponse,
} from "@crypto-signal/shared";

// Use relative path by default to leverage Next.js rewrites and avoid CORS/Mixed Content issues
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

// Auth token storage key
const AUTH_TOKEN_KEY = "crypto_signal_auth_token";

// Get/set auth token
export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

export function setAuthToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) {
    localStorage.setItem(AUTH_TOKEN_KEY, token);
  } else {
    localStorage.removeItem(AUTH_TOKEN_KEY);
  }
}

export function isAuthenticated(): boolean {
  return !!getAuthToken();
}

class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit,
): Promise<T> {
  // Ensure we don't double-slash or missing slash when combining
  const base = API_BASE.endsWith("/") ? API_BASE.slice(0, -1) : API_BASE;
  const path = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;

  // If endpoint is already full URL (unlikely but possible), use it as is
  const url = endpoint.startsWith("http")
    ? endpoint
    : `${base}${path.replace(/^\/api\/v1/, "")}`;

  // Add auth header if token exists
  const token = getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorData = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new ApiError(
      errorData.detail || response.statusText,
      response.status,
    );
  }

  return response.json();
}

// ============== Signals API ==============

export interface LimitOffsetParams {
  limit?: number;
  offset?: number;
}

export interface SignalsParams extends LimitOffsetParams {
  token_symbol?: string;
  channel_name?: string;
  sentiment?: string;
  start_date?: string;
  end_date?: string;
}

export async function getSignals(
  params: SignalsParams = {},
): Promise<PaginatedResponse<Signal>> {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      searchParams.append(key, String(value));
    }
  });

  const query = searchParams.toString();
  return fetchApi<PaginatedResponse<Signal>>(
    `/api/v1/signals${query ? `?${query}` : ""}`,
  );
}

export async function getSignal(id: number): Promise<Signal> {
  return fetchApi<Signal>(`/api/v1/signals/${id}`);
}

export async function createSignal(data: Partial<Signal>): Promise<Signal> {
  return fetchApi<Signal>("/api/v1/signals", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function deleteSignal(id: number): Promise<void> {
  await fetchApi(`/api/v1/signals/${id}`, { method: "DELETE" });
}

// ============== Channels API ==============

export async function getChannels(
  params: LimitOffsetParams = {},
): Promise<PaginatedResponse<Channel>> {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined) {
      searchParams.append(key, String(value));
    }
  });

  const query = searchParams.toString();
  return fetchApi<PaginatedResponse<Channel>>(
    `/api/v1/channels${query ? `?${query}` : ""}`,
  );
}

export async function getChannel(id: number): Promise<Channel> {
  return fetchApi<Channel>(`/api/v1/channels/${id}`);
}

// ============== Live/Stats API ==============

export async function getStats(): Promise<PlatformStats> {
  return fetchApi<PlatformStats>("/api/v1/live/stats");
}

export async function getSentiment(): Promise<MarketSentiment> {
  return fetchApi<MarketSentiment>("/api/v1/live/sentiment");
}

export interface TrendingCoin {
  id: string;
  symbol: string;
  name: string;
  image: string | null;
  market_cap_rank: number | null;
  current_price: number | null;
  price_change_percentage_24h: number | null;
  market_cap: number | null;
  total_volume: number | null;
  sparkline_7d: number[] | null;
  score: number;
}

export interface TrendingResponse {
  trending: TrendingCoin[];
  signal_trending: TrendingToken[];
  total_signals_24h: number;
  most_active_channels: string[];
  timestamp: string;
}

export async function getTrending(): Promise<TrendingResponse> {
  return fetchApi<TrendingResponse>("/api/v1/live/trending");
}

// ============== Analytics API ==============

export interface HistoricalParams {
  days?: number;
  token_symbol?: string;
  channel_name?: string;
}

export async function getHistoricalData(params: HistoricalParams = {}) {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined) {
      searchParams.append(key, String(value));
    }
  });

  const query = searchParams.toString();
  return fetchApi(`/api/v1/analytics/historical${query ? `?${query}` : ""}`);
}

export async function getChannelLeaderboard(): Promise<
  ChannelLeaderboardEntry[]
> {
  return fetchApi<ChannelLeaderboardEntry[]>(
    "/api/v1/analytics/channels/leaderboard",
  );
}

export async function getTokenStats(symbol: string): Promise<TokenStats> {
  return fetchApi<TokenStats>(`/api/v1/analytics/token/${symbol}/stats`);
}

export async function getPatterns(): Promise<PatternInfo[]> {
  return fetchApi<PatternInfo[]>("/api/v1/analytics/patterns");
}

// ============== System Benchmark API ==============

export interface BenchmarkResult {
  benchmark_results: {
    response_time: {
      uncached_ms: number;
      cache_hit_ms: number;
      improvement_factor: number;
    };
    stress_test: {
      concurrent_requests: number;
      total_time_ms: number;
      avg_time_per_request_ms: number;
      requests_per_second: number;
    };
  };
  system_status: {
    cache_connected: boolean;
    database_connected: boolean;
  };
}

export async function runBenchmark(): Promise<BenchmarkResult> {
  return fetchApi<BenchmarkResult>("/api/v1/analytics/benchmark");
}

// ============== Telegram API ==============

export async function getTelegramStatus(): Promise<
  TelegramStatus & { is_monitoring?: boolean }
> {
  return fetchApi<TelegramStatus & { is_monitoring?: boolean }>(
    "/api/v1/telegram/status",
  );
}

export async function connectTelegram(
  phoneNumber: string,
): Promise<TelegramAuthResponse> {
  return fetchApi<TelegramAuthResponse>("/api/v1/telegram/connect", {
    method: "POST",
    body: JSON.stringify({ phone_number: phoneNumber }),
  });
}

export async function verifyTelegramCode(
  code: string,
): Promise<TelegramAuthResponse> {
  return fetchApi<TelegramAuthResponse>("/api/v1/telegram/verify", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
}

export async function verifyTelegram2FA(
  password: string,
): Promise<TelegramAuthResponse> {
  return fetchApi<TelegramAuthResponse>("/api/v1/telegram/verify-2fa", {
    method: "POST",
    body: JSON.stringify({ password }),
  });
}

export async function disconnectTelegram(): Promise<{
  success: boolean;
  message?: string;
}> {
  return fetchApi("/api/v1/telegram/disconnect", { method: "POST" });
}

export async function getTelegramChannels(): Promise<{
  success: boolean;
  channels: Array<{
    id: number;
    title: string;
    username?: string;
    is_channel: boolean;
    is_group: boolean;
    participants_count?: number;
    unread_count?: number;
  }>;
  count: number;
  error?: string;
}> {
  return fetchApi("/api/v1/telegram/channels");
}

// ============== Background Monitoring API ==============

export interface MonitoringStatus {
  is_monitoring: boolean;
  started_at?: string;
  channels_count: number;
  messages_processed: number;
  signals_detected: number;
  last_message_at?: string;
  errors: string[];
}

export interface MonitoringResponse {
  success: boolean;
  message?: string;
  is_monitoring: boolean;
  channels_count: number;
  error?: string;
}

export async function getMonitoringStatus(): Promise<MonitoringStatus> {
  return fetchApi<MonitoringStatus>("/api/v1/telegram/monitoring/status");
}

export async function startMonitoring(): Promise<MonitoringResponse> {
  return fetchApi<MonitoringResponse>("/api/v1/telegram/monitoring/start", {
    method: "POST",
  });
}

export async function stopMonitoring(): Promise<MonitoringResponse> {
  return fetchApi<MonitoringResponse>("/api/v1/telegram/monitoring/stop", {
    method: "POST",
  });
}

export async function refreshMonitoring(): Promise<MonitoringResponse> {
  return fetchApi<MonitoringResponse>("/api/v1/telegram/monitoring/refresh", {
    method: "POST",
  });
}

// Keep legacy aliases
export const setupTelegram = connectTelegram;
export const logoutTelegram = disconnectTelegram;

// ============== Auth API ==============

export interface RegisterRequest {
  email: string;
  username: string;
  password: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface AuthUser {
  id: number;
  email: string;
  username: string;
  is_admin: boolean;
  is_active: boolean;
  created_at?: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_at: string;
  user: AuthUser;
}

export async function register(data: RegisterRequest): Promise<TokenResponse> {
  const response = await fetchApi<TokenResponse>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(data),
  });

  // Store token if registration successful
  if (response.access_token) {
    setAuthToken(response.access_token);
  }

  return response;
}

export async function login(credentials: LoginRequest): Promise<TokenResponse> {
  const response = await fetchApi<TokenResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(credentials),
  });

  // Store token if login successful
  if (response.access_token) {
    setAuthToken(response.access_token);
  }

  return response;
}

export async function logout(): Promise<void> {
  try {
    await fetchApi("/api/v1/auth/logout", { method: "POST" });
  } finally {
    setAuthToken(null);
  }
}

export async function getCurrentUser(): Promise<AuthUser> {
  return fetchApi<AuthUser>("/api/v1/auth/me");
}

// ============== User Telegram API ==============

export interface UserTelegramStatus {
  connected: boolean;
  auth_state: string;
  phone_number?: string;
  username?: string;
  first_name?: string;
  last_name?: string;
  has_saved_session?: boolean;
  error?: string;
}

export interface UserTelegramAuthResponse {
  success: boolean;
  message?: string;
  auth_state: string;
  requires_2fa?: boolean;
  error?: string;
}

export interface UserChannel {
  id: number;
  title: string;
  username?: string;
  is_channel: boolean;
  is_group: boolean;
  participants_count?: number;
  unread_count?: number;
}

export interface UserChannelsResponse {
  success: boolean;
  channels: UserChannel[];
  count: number;
  error?: string;
}

export async function getUserTelegramStatus(): Promise<UserTelegramStatus> {
  return fetchApi<UserTelegramStatus>("/api/v1/telegram/status");
}

export async function connectUserTelegram(
  phoneNumber: string,
): Promise<UserTelegramAuthResponse> {
  return fetchApi<UserTelegramAuthResponse>("/api/v1/telegram/connect", {
    method: "POST",
    body: JSON.stringify({ phone_number: phoneNumber }),
  });
}

export async function verifyUserTelegramCode(
  code: string,
): Promise<UserTelegramAuthResponse> {
  return fetchApi<UserTelegramAuthResponse>("/api/v1/telegram/verify", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
}

export async function verifyUserTelegram2FA(
  password: string,
): Promise<UserTelegramAuthResponse> {
  return fetchApi<UserTelegramAuthResponse>("/api/v1/telegram/verify-2fa", {
    method: "POST",
    body: JSON.stringify({ password }),
  });
}

export async function getUserTelegramChannels(): Promise<UserChannelsResponse> {
  return fetchApi<UserChannelsResponse>("/api/v1/telegram/channels");
}

export async function disconnectUserTelegram(): Promise<UserTelegramAuthResponse> {
  return fetchApi<UserTelegramAuthResponse>("/api/v1/telegram/disconnect", {
    method: "POST",
  });
}

// ============== Channel Subscriptions API ==============

export interface ChannelSubscription {
  id: number;
  channel_id: number;
  channel_name?: string;
  is_active: boolean;
  notify_email: boolean;
  notify_telegram: boolean;
  created_at: string;
}

export interface SubscribeRequest {
  channel_id: number;
  channel_title?: string;
  notify_email?: boolean;
  notify_telegram?: boolean;
}

export interface SubscriptionResponse {
  success: boolean;
  subscription?: ChannelSubscription;
  message?: string;
  error?: string;
}

export interface SubscriptionListResponse {
  success: boolean;
  subscriptions: ChannelSubscription[];
  count: number;
  error?: string;
}

export async function getSubscriptions(): Promise<SubscriptionListResponse> {
  return fetchApi<SubscriptionListResponse>("/api/v1/subscriptions/");
}

export async function subscribeToChannel(
  data: SubscribeRequest,
): Promise<SubscriptionResponse> {
  return fetchApi<SubscriptionResponse>("/api/v1/subscriptions/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateSubscription(
  id: number,
  data: {
    notify_email?: boolean;
    notify_telegram?: boolean;
    is_active?: boolean;
  },
): Promise<SubscriptionResponse> {
  return fetchApi<SubscriptionResponse>(`/api/v1/subscriptions/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function unsubscribeFromChannel(
  id: number,
): Promise<SubscriptionResponse> {
  return fetchApi<SubscriptionResponse>(`/api/v1/subscriptions/${id}`, {
    method: "DELETE",
  });
}

// ============== Tracking API ==============

export interface TrackedToken {
  id: number;
  symbol: string;
  chain: string;
  address: string | null;
  notes: string | null;
  created_at: string;
}

export async function getTrackedTokens(): Promise<TrackedToken[]> {
  return fetchApi<TrackedToken[]>("/api/v1/tracking/");
}

export async function trackToken(
  symbol: string,
  chain: string = "solana",
  address?: string,
  name?: string,
): Promise<TrackedToken> {
  return fetchApi<TrackedToken>("/api/v1/tracking/", {
    method: "POST",
    body: JSON.stringify({ symbol, chain, address, name }),
  });
}

export async function untrackToken(symbol: string): Promise<void> {
  return fetchApi<void>(`/api/v1/tracking/${symbol}`, {
    method: "DELETE",
  });
}

export interface TrackedTokenPriceData {
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

export async function getTrackedTokenPrices(): Promise<
  TrackedTokenPriceData[]
> {
  return fetchApi<TrackedTokenPriceData[]>("/api/v1/tracking/prices");
}

// ============== Price History ==============

/**
 * Backend may return two formats:
 *  - Simple tick:  { t, p }               (from in-memory CMC/CG polling)
 *  - OHLC candle:  { t, o, h, l, c }      (from CoinGecko OHLC endpoint)
 */
export interface PriceHistoryTick {
  t: string; // ISO timestamp
  p?: number; // price USD (simple tick)
  o?: number; // OHLC fields (CoinGecko)
  h?: number;
  l?: number;
  c?: number;
}

export interface PriceHistoryResponse {
  symbol: string;
  history: PriceHistoryTick[];
}

export async function getTokenPriceHistory(
  symbol: string,
): Promise<PriceHistoryResponse> {
  return fetchApi<PriceHistoryResponse>(
    `/api/v1/tracking/${encodeURIComponent(symbol)}/history`,
  );
}

// ============== Search API (Moralis) ==============

export interface TokenSearchResult {
  symbol: string;
  name: string;
  address: string;
  chain: string;
  price_usd: number | null;
  price_change_24h: number | null;
  logo: string | null;
  decimals: number | null;
  market_cap_rank?: number | null;
  market_cap?: number | null;
  volume_24h?: number | null;
}

export interface SearchResponse {
  query: string;
  results: TokenSearchResult[];
  count: number;
}

export async function searchTokens(
  query: string,
  limit: number = 20,
): Promise<SearchResponse> {
  return fetchApi<SearchResponse>(
    `/api/v1/search/tokens?q=${encodeURIComponent(query)}&limit=${limit}`,
  );
}

export async function getTokenByAddress(
  address: string,
  chain?: string,
): Promise<SearchResponse> {
  const url = `/api/v1/search/tokens/${encodeURIComponent(address)}${chain ? `?chain=${chain}` : ""}`;
  return fetchApi<SearchResponse>(url);
}

// ============== Market Data API ==============

export interface MarketCoin {
  id: string;
  symbol: string;
  name: string;
  image: string | null;
  current_price: number | null;
  market_cap: number | null;
  market_cap_rank: number | null;
  total_volume: number | null;
  high_24h: number | null;
  low_24h: number | null;
  price_change_24h: number | null;
  price_change_percentage_24h: number | null;
  price_change_percentage_1h: number | null;
  price_change_percentage_7d: number | null;
  circulating_supply: number | null;
  total_supply: number | null;
  ath: number | null;
  ath_change_percentage: number | null;
  sparkline_7d: number[] | null;
}

export interface GlobalMarketStats {
  total_market_cap_usd: number | null;
  total_volume_24h_usd: number | null;
  market_cap_change_24h_pct: number | null;
  active_cryptocurrencies: number | null;
  btc_dominance: number | null;
  eth_dominance: number | null;
}

export interface MarketDataResponse {
  coins: MarketCoin[];
  global: GlobalMarketStats;
  count: number;
  timestamp: string;
}

export async function getMarketData(
  limit: number = 50,
): Promise<MarketDataResponse> {
  return fetchApi<MarketDataResponse>(`/api/v1/live/market?limit=${limit}`);
}

// ============== OHLC Candlestick API (public, any token) ==============

export interface OhlcCandle {
  t: string; // ISO timestamp
  o: number; // open
  h: number; // high
  l: number; // low
  c: number; // close
}

export interface OhlcDataResponse {
  symbol: string;
  candles: OhlcCandle[];
  days: number;
  count: number;
  timestamp: string;
}

/**
 * Get OHLC candlestick data for any token symbol (public, no auth).
 * Works for any coin on CoinGecko, not just top 50.
 *
 * @param symbol - Token symbol (e.g. "BTC", "ETH", "PEPE")
 * @param days   - Timeframe: 1 (30-min candles), 7 (4h candles), 14 (4h), 30 (daily)
 */
export async function getOhlcData(
  symbol: string,
  days: number = 7,
): Promise<OhlcDataResponse> {
  return fetchApi<OhlcDataResponse>(
    `/api/v1/live/ohlc/${encodeURIComponent(symbol)}?days=${days}`,
  );
}

// ============== Notifications API ==============

export interface AppNotification {
  id: number;
  type: string;
  title: string;
  message: string;
  data: Record<string, any> | null;
  is_read: boolean;
  signal_id: number | null;
  token_symbol: string | null;
  contract_address: string | null;
  channel_name: string | null;
  created_at: string;
}

export interface NotificationListResponse {
  notifications: AppNotification[];
  total: number;
  unread_count: number;
}

export interface NotificationBadgeResponse {
  unread_count: number;
}

export async function getNotifications(
  params: {
    limit?: number;
    offset?: number;
    unread_only?: boolean;
    type?: string;
  } = {},
): Promise<NotificationListResponse> {
  const searchParams = new URLSearchParams();
  if (params.limit) searchParams.append("limit", String(params.limit));
  if (params.offset) searchParams.append("offset", String(params.offset));
  if (params.unread_only) searchParams.append("unread_only", "true");
  if (params.type) searchParams.append("type", params.type);
  const query = searchParams.toString();
  return fetchApi<NotificationListResponse>(
    `/api/v1/notifications${query ? `?${query}` : ""}`,
  );
}

export async function getNotificationBadge(): Promise<NotificationBadgeResponse> {
  return fetchApi<NotificationBadgeResponse>("/api/v1/notifications/badge");
}

export async function markNotificationsRead(ids: number[]): Promise<void> {
  await fetchApi("/api/v1/notifications/read", {
    method: "POST",
    body: JSON.stringify({ notification_ids: ids }),
  });
}

export async function markAllNotificationsRead(): Promise<void> {
  await fetchApi("/api/v1/notifications/read-all", { method: "POST" });
}

export async function deleteNotification(id: number): Promise<void> {
  await fetchApi(`/api/v1/notifications/${id}`, { method: "DELETE" });
}

export async function clearAllNotifications(): Promise<void> {
  await fetchApi("/api/v1/notifications/", { method: "DELETE" });
}

export { ApiError };
