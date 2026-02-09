'use client';

import React, { createContext, useContext, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/lib/auth-context';
import { 
  getTrackedTokens, 
  trackToken as apiTrackToken, 
  untrackToken as apiUntrackToken, 
  TrackedToken 
} from '@/lib/api';
import { toast } from '@/components/ui/use-toast';

interface TrackedTokensContextValue {
  trackedTokens: TrackedToken[];
  isTracked: (symbol: string) => boolean;
  trackToken: (symbol: string, name?: string, chain?: string, address?: string) => void;
  untrackToken: (symbol: string) => void;
  clearTracked: () => void;
  isLoading: boolean;
}

const TrackedTokensContext = createContext<TrackedTokensContextValue | null>(null);

export function TrackedTokensProvider({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  const queryClient = useQueryClient();

  const { data: trackedTokens = [], isLoading } = useQuery({
    queryKey: ['tracked-tokens'],
    queryFn: getTrackedTokens,
    enabled: isAuthenticated,
  });

  const trackMutation = useMutation({
    mutationFn: async ({ symbol, name, chain, address }: { symbol: string; name?: string; chain?: string; address?: string }) => {
      // Name is optional but key for better UX
      // @ts-ignore - The API client might not have strict types for name yet if generated
      return apiTrackToken(symbol, chain || 'eth', address, name); 
    },
    onSuccess: (_, { symbol }) => {
      queryClient.invalidateQueries({ queryKey: ['tracked-tokens'] });
      toast({
        title: 'Token tracked',
        description: `Now tracking ${symbol}`,
      });
    },
    onError: (error) => {
      toast({
        title: 'Failed to track token',
        description: error instanceof Error ? error.message : 'Unknown error',
        variant: 'destructive',
      });
    }
  });

  const untrackMutation = useMutation({
    mutationFn: (symbol: string) => apiUntrackToken(symbol),
    onSuccess: (_, symbol) => {
      queryClient.invalidateQueries({ queryKey: ['tracked-tokens'] });
      toast({
        title: 'Token untracked',
        description: `Stopped tracking ${symbol}`,
      });
    },
    onError: (error) => {
      toast({
        title: 'Failed to untrack token',
        description: error instanceof Error ? error.message : 'Unknown error',
        variant: 'destructive',
      });
    }
  });

  const isTracked = useCallback((symbol: string) => {
    return trackedTokens.some(t => t.symbol.toUpperCase() === symbol.toUpperCase());
  }, [trackedTokens]);

  const trackToken = useCallback((symbol: string, name?: string, chain?: string, address?: string) => {
    if (!isAuthenticated) {
      toast({
        title: 'Authentication required',
        description: 'Please login to track tokens',
        variant: 'destructive',
      });
      return;
    }
    trackMutation.mutate({ symbol, name, chain, address });
  }, [trackMutation, isAuthenticated]);

  const untrackToken = useCallback((symbol: string) => {
    if (!isAuthenticated) return;
    untrackMutation.mutate(symbol);
  }, [untrackMutation, isAuthenticated]);

  const clearTracked = useCallback(() => {
    // No-op for API
  }, []);

  return (
    <TrackedTokensContext.Provider
      value={{
        trackedTokens,
        isTracked,
        trackToken,
        untrackToken,
        clearTracked,
        isLoading
      }}
    >
      {children}
    </TrackedTokensContext.Provider>
  );
}

export function useTrackedTokens() {
  const context = useContext(TrackedTokensContext);
  if (!context) {
    throw new Error('useTrackedTokens must be used within a TrackedTokensProvider');
  }
  return context;
}
