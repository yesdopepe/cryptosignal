'use client';

import { QueryClient, QueryClientProvider, QueryCache, MutationCache } from '@tanstack/react-query';
import { useState } from 'react';
import { WebSocketProvider } from '@/hooks/useWebSocket';
import { AuthProvider } from '@/lib/auth-context';
import { TrackedTokensProvider } from '@/hooks/useTrackedTokens';
import { toast } from '@/components/ui/use-toast';
import { ExplorerDialog } from './explorer/explorer-dialog';

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30 * 1000, // 30 seconds
            refetchOnWindowFocus: false,
          },
        },
        queryCache: new QueryCache({
          onError: (error) => {
            // Only show toast for 5xx errors or unknown errors
            // We usually want to handle 4xx errors in the UI components
            const msg = error instanceof Error ? error.message : 'An error occurred';
            console.error('Query error:', error);
          },
        }),
        mutationCache: new MutationCache({
          onError: (error) => {
            const msg = error instanceof Error ? error.message : 'Action failed';
            toast({
              title: 'Error',
              description: msg,
              variant: 'destructive',
            });
          },
        }),
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <TrackedTokensProvider>
          <WebSocketProvider>
            {children}
            <ExplorerDialog />
          </WebSocketProvider>
        </TrackedTokensProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
