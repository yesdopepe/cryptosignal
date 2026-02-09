'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from '@/lib/api';

// ============== Query Keys ==============

export const queryKeys = {
  signals: (params?: api.SignalsParams) => ['signals', params] as const,
  signal: (id: number) => ['signal', id] as const,
  channels: (params?: api.LimitOffsetParams) => ['channels', params] as const,
  channel: (id: number) => ['channel', id] as const,
  stats: () => ['stats'] as const,
  sentiment: () => ['sentiment'] as const,
  trending: () => ['trending'] as const,
  marketData: (limit?: number) => ['marketData', limit] as const,
  historical: (params?: api.HistoricalParams) => ['historical', params] as const,
  leaderboard: () => ['leaderboard'] as const,
  tokenStats: (symbol: string) => ['tokenStats', symbol] as const,
  patterns: () => ['patterns'] as const,
  telegramStatus: () => ['telegramStatus'] as const,
  currentUser: () => ['currentUser'] as const,
};

// ============== Signals Hooks ==============

export function useSignals(params?: api.SignalsParams) {
  return useQuery({
    queryKey: queryKeys.signals(params),
    queryFn: () => api.getSignals(params),
  });
}

export function useSignal(id: number) {
  return useQuery({
    queryKey: queryKeys.signal(id),
    queryFn: () => api.getSignal(id),
    enabled: !!id,
  });
}

export function useCreateSignal() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: api.createSignal,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['signals'] });
    },
  });
}

export function useDeleteSignal() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: api.deleteSignal,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['signals'] });
    },
  });
}

// ============== Channels Hooks ==============

export function useChannels(params?: api.LimitOffsetParams) {
  return useQuery({
    queryKey: queryKeys.channels(params),
    queryFn: () => api.getChannels(params),
  });
}

export function useChannel(id: number) {
  return useQuery({
    queryKey: queryKeys.channel(id),
    queryFn: () => api.getChannel(id),
    enabled: !!id,
  });
}

// ============== Live Data Hooks ==============

export function useStats() {
  return useQuery({
    queryKey: queryKeys.stats(),
    queryFn: api.getStats,
    refetchInterval: 30000, // Refresh every 30 seconds
  });
}

export function useSentiment() {
  return useQuery({
    queryKey: queryKeys.sentiment(),
    queryFn: api.getSentiment,
    refetchInterval: 30000,
  });
}

export function useTrending() {
  return useQuery({
    queryKey: queryKeys.trending(),
    queryFn: api.getTrending,
    refetchInterval: 60000, // Refresh every minute
  });
}

export function useMarketData(limit: number = 50) {
  return useQuery({
    queryKey: ['marketData', limit],
    queryFn: () => api.getMarketData(limit),
    refetchInterval: 30000, // Refresh every 30 seconds
    staleTime: 15000, // Consider stale after 15s
  });
}

// ============== Analytics Hooks ==============

export function useHistoricalData(params?: api.HistoricalParams) {
  return useQuery({
    queryKey: queryKeys.historical(params),
    queryFn: () => api.getHistoricalData(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useChannelLeaderboard() {
  return useQuery({
    queryKey: queryKeys.leaderboard(),
    queryFn: api.getChannelLeaderboard,
    staleTime: 60 * 60 * 1000, // 1 hour
  });
}

export function useTokenStats(symbol: string) {
  return useQuery({
    queryKey: queryKeys.tokenStats(symbol),
    queryFn: () => api.getTokenStats(symbol),
    enabled: !!symbol,
    staleTime: 60 * 1000, // 1 minute
  });
}

export function usePatterns() {
  return useQuery({
    queryKey: queryKeys.patterns(),
    queryFn: api.getPatterns,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

// ============== Telegram Hooks ==============

export function useTelegramStatus() {
  return useQuery({
    queryKey: queryKeys.telegramStatus(),
    queryFn: api.getTelegramStatus,
    refetchInterval: 10000, // Check status every 10 seconds
  });
}

export function useUserTelegramStatus() {
  return useQuery({
    queryKey: ['userTelegramStatus'],
    queryFn: api.getUserTelegramStatus,
    refetchInterval: 10000,
  });
}

export function useUserTelegramChannels() {
  return useQuery({
    queryKey: ['userTelegramChannels'],
    queryFn: api.getUserTelegramChannels,
  });
}

export function useSubscriptions() {
  return useQuery({
    queryKey: ['subscriptions'],
    queryFn: api.getSubscriptions,
  });
}

export function useSubscribe() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.subscribeToChannel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] });
    },
  });
}

export function useUnsubscribe() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.unsubscribeFromChannel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] });
    },
  });
}

export function useUpdateSubscription() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number, data: Parameters<typeof api.updateSubscription>[1] }) => 
      api.updateSubscription(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] });
    },
  });
}

export function useSetupTelegram() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: api.setupTelegram,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.telegramStatus() });
    },
  });
}

export function useVerifyTelegramCode() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: api.verifyTelegramCode,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.telegramStatus() });
    },
  });
}

export function useVerifyTelegram2FA() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: api.verifyTelegram2FA,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.telegramStatus() });
    },
  });
}

export function useLogoutTelegram() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: api.logoutTelegram,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.telegramStatus() });
    },
  });
}

// ============== Background Monitoring Hooks ==============

export function useMonitoringStatus() {
  return useQuery({
    queryKey: ['monitoringStatus'],
    queryFn: api.getMonitoringStatus,
    refetchInterval: 10000, // Poll every 10 seconds
  });
}

export function useStartMonitoring() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.startMonitoring,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['monitoringStatus'] });
      queryClient.invalidateQueries({ queryKey: ['userTelegramStatus'] });
    },
  });
}

export function useStopMonitoring() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.stopMonitoring,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['monitoringStatus'] });
      queryClient.invalidateQueries({ queryKey: ['userTelegramStatus'] });
    },
  });
}

export function useRefreshMonitoring() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.refreshMonitoring,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['monitoringStatus'] });
    },
  });
}

// ============== Auth Hooks ==============

export function useCurrentUser() {
  return useQuery({
    queryKey: queryKeys.currentUser(),
    queryFn: api.getCurrentUser,
    enabled: api.isAuthenticated(),
    retry: false,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: api.login,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.currentUser() });
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: api.logout,
    onSuccess: () => {
      queryClient.clear();
    },
  });
}

// Re-export auth utilities
export { isAuthenticated, getAuthToken, setAuthToken } from '@/lib/api';

// ============== Search Hooks ==============

export function useTokenSearch(query: string, enabled: boolean = true) {
  return useQuery({
    queryKey: ['tokenSearch', query],
    queryFn: () => api.searchTokens(query),
    enabled: enabled && query.length >= 2,
    staleTime: 30 * 1000, // 30 seconds
  });
}
