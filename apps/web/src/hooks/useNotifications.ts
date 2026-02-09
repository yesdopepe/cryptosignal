'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/lib/auth-context';
import { useWebSocket } from '@/hooks/useWebSocket';
import {
  getNotifications,
  getNotificationBadge,
  markNotificationsRead,
  markAllNotificationsRead,
  deleteNotification,
  clearAllNotifications,
  AppNotification,
} from '@/lib/api';
import { useCallback, useEffect } from 'react';

export const notificationKeys = {
  all: ['notifications'] as const,
  list: (params?: Record<string, any>) => ['notifications', 'list', params] as const,
  badge: () => ['notifications', 'badge'] as const,
};

export function useNotifications(params?: {
  limit?: number;
  offset?: number;
  unread_only?: boolean;
  type?: string;
}) {
  const { isAuthenticated } = useAuth();

  return useQuery({
    queryKey: notificationKeys.list(params),
    queryFn: () => getNotifications(params),
    enabled: isAuthenticated,
    refetchInterval: 60_000, // Refetch every minute as heartbeat
  });
}

export function useNotificationBadge() {
  const { isAuthenticated } = useAuth();
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: notificationKeys.badge(),
    queryFn: getNotificationBadge,
    enabled: isAuthenticated,
    refetchInterval: 30_000,
  });

  // Listen for real-time notification pushes via WebSocket
  // and bump the badge count optimistically
  const invalidate = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: notificationKeys.badge() });
    queryClient.invalidateQueries({ queryKey: notificationKeys.list() });
  }, [queryClient]);

  return { ...query, invalidate };
}

export function useMarkNotificationsRead() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (ids: number[]) => markNotificationsRead(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: notificationKeys.all });
    },
  });
}

export function useMarkAllRead() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: notificationKeys.all });
    },
  });
}

export function useDeleteNotification() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteNotification,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: notificationKeys.all });
    },
  });
}

export function useClearAllNotifications() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: clearAllNotifications,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: notificationKeys.all });
    },
  });
}
