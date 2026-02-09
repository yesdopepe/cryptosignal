'use client';

import { useMemo } from 'react';
import { Line } from 'react-chartjs-2';
import { useWebSocket } from '@/hooks/useWebSocket';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { chartColors, defaultOptions } from '@/lib/chart-config';
import type { ChartOptions } from 'chart.js';

interface SignalStreamChartProps {
  maxPoints?: number;
}

export function SignalStreamChart({ maxPoints = 20 }: SignalStreamChartProps) {
  const { signals, isConnected } = useWebSocket();

  const chartData = useMemo(() => {
    // Group signals by minute
    const signalsByTime: Record<string, { bullish: number; bearish: number; neutral: number }> = {};
    
    const recentSignals = signals.slice(0, 50);
    
    recentSignals.forEach((signal) => {
      const date = new Date(signal.timestamp);
      const key = `${date.getHours()}:${date.getMinutes().toString().padStart(2, '0')}`;
      
      if (!signalsByTime[key]) {
        signalsByTime[key] = { bullish: 0, bearish: 0, neutral: 0 };
      }
      
      if (signal.sentiment === 'BULLISH') {
        signalsByTime[key].bullish++;
      } else if (signal.sentiment === 'BEARISH') {
        signalsByTime[key].bearish++;
      } else {
        signalsByTime[key].neutral++;
      }
    });

    const labels = Object.keys(signalsByTime).slice(-maxPoints);
    const data = labels.map((key) => signalsByTime[key]);

    return {
      labels,
      datasets: [
        {
          label: 'Bullish',
          data: data.map((d) => d?.bullish || 0),
          borderColor: chartColors.bullish.border,
          backgroundColor: chartColors.bullish.background,
          fill: true,
          tension: 0.4,
        },
        {
          label: 'Bearish',
          data: data.map((d) => d?.bearish || 0),
          borderColor: chartColors.bearish.border,
          backgroundColor: chartColors.bearish.background,
          fill: true,
          tension: 0.4,
        },
        {
          label: 'Neutral',
          data: data.map((d) => d?.neutral || 0),
          borderColor: chartColors.neutral.border,
          backgroundColor: chartColors.neutral.background,
          fill: true,
          tension: 0.4,
        },
      ],
    };
  }, [signals, maxPoints]);

  const options: ChartOptions<'line'> = {
    ...defaultOptions,
    plugins: {
      ...defaultOptions.plugins,
      legend: {
        position: 'top' as const,
        labels: {
          color: 'rgb(156, 163, 175)',
          usePointStyle: true,
        },
      },
      title: {
        display: false,
      },
    },
    scales: {
      ...defaultOptions.scales,
      y: {
        ...defaultOptions.scales?.y,
        beginAtZero: true,
        ticks: {
          ...defaultOptions.scales?.y?.ticks,
          stepSize: 1,
        },
      },
    },
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-base font-medium">Signal Stream</CardTitle>
        <div className="flex items-center gap-2">
          {isConnected ? (
            <Badge variant="success" className="flex items-center gap-1">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
              </span>
              Live
            </Badge>
          ) : (
            <Badge variant="secondary">Connecting...</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-[250px]">
          <Line data={chartData} options={options} />
        </div>
      </CardContent>
    </Card>
  );
}
