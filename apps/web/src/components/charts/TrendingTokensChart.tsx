'use client';

import { useMemo } from 'react';
import { Bar } from 'react-chartjs-2';
import { useTrending } from '@/hooks/useApi';
import { useWebSocket } from '@/hooks/useWebSocket';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { chartColors } from '@/lib/chart-config';
import type { ChartOptions } from 'chart.js';

export function TrendingTokensChart() {
  const { data: apiTrending, isLoading } = useTrending();
  const { trending: wsTrending } = useWebSocket();

  const chartData = useMemo(() => {
    // Prefer WebSocket data, fall back to API data
    let tokens: Array<{ symbol: string; count: number; change?: number }> = [];
    
    if (wsTrending?.top_tokens && wsTrending.top_tokens.length > 0) {
      tokens = wsTrending.top_tokens.slice(0, 10);
    } else if (apiTrending?.trending && apiTrending.trending.length > 0) {
      tokens = apiTrending.trending.slice(0, 10).map((t: any) => ({
        symbol: t.symbol,
        count: t.signal_count_24h ?? t.total_volume ?? 0,
        change: t.signal_change_percent ?? t.price_change_percentage_24h ?? 0,
      }));
    }

    if (tokens.length === 0) {
      return {
        labels: ['BTC', 'ETH', 'SOL', 'DOGE', 'PEPE'],
        datasets: [
          {
            label: 'Signals',
            data: [0, 0, 0, 0, 0],
            backgroundColor: chartColors.primary.background,
            borderColor: chartColors.primary.border,
            borderWidth: 1,
          },
        ],
      };
    }

    return {
      labels: tokens.map((t) => t.symbol),
      datasets: [
        {
          label: 'Signals (24h)',
          data: tokens.map((t) => t.count),
          backgroundColor: tokens.map((t) => 
            (t.change || 0) >= 0 
              ? chartColors.bullish.background 
              : chartColors.bearish.background
          ),
          borderColor: tokens.map((t) => 
            (t.change || 0) >= 0 
              ? chartColors.bullish.border 
              : chartColors.bearish.border
          ),
          borderWidth: 1,
          borderRadius: 4,
        },
      ],
    };
  }, [apiTrending, wsTrending]);

  const options: ChartOptions<'bar'> = {
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: 'y' as const,
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        backgroundColor: 'rgb(31, 41, 55)',
        titleColor: 'rgb(255, 255, 255)',
        bodyColor: 'rgb(209, 213, 219)',
        borderColor: 'rgb(55, 65, 81)',
        borderWidth: 1,
      },
    },
    scales: {
      x: {
        grid: {
          color: 'rgba(75, 85, 99, 0.3)',
        },
        ticks: {
          color: 'rgb(156, 163, 175)',
        },
        beginAtZero: true,
      },
      y: {
        grid: {
          display: false,
        },
        ticks: {
          color: 'rgb(156, 163, 175)',
          font: {
            weight: 'bold',
          },
        },
      },
    },
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-medium">Trending Tokens</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-[250px] w-full" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-medium">Trending Tokens (24h)</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[250px]">
          <Bar data={chartData} options={options} />
        </div>
      </CardContent>
    </Card>
  );
}
