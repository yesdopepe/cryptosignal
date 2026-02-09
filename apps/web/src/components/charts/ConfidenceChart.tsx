'use client';

import { useMemo } from 'react';
import { Line } from 'react-chartjs-2';
import { useWebSocket } from '@/hooks/useWebSocket';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { chartColors, defaultOptions } from '@/lib/chart-config';
import type { ChartOptions } from 'chart.js';

interface ConfidenceChartProps {
  maxPoints?: number;
}

export function ConfidenceChart({ maxPoints = 30 }: ConfidenceChartProps) {
  const { signals } = useWebSocket();

  const chartData = useMemo(() => {
    const recentSignals = signals.slice(0, maxPoints).reverse();
    
    if (recentSignals.length === 0) {
      return {
        labels: Array(10).fill(''),
        datasets: [
          {
            label: 'Confidence Score',
            data: Array(10).fill(0.5),
            borderColor: chartColors.primary.border,
            backgroundColor: chartColors.primary.background,
            fill: true,
            tension: 0.4,
            pointRadius: 0,
          },
        ],
      };
    }

    return {
      labels: recentSignals.map((s, i) => `#${i + 1}`),
      datasets: [
        {
          label: 'Confidence Score',
          data: recentSignals.map((s) => s.confidence_score),
          borderColor: chartColors.primary.border,
          backgroundColor: chartColors.primary.background,
          fill: true,
          tension: 0.4,
          pointRadius: 3,
          pointBackgroundColor: recentSignals.map((s) => {
            if (s.sentiment === 'BULLISH') return chartColors.bullish.border;
            if (s.sentiment === 'BEARISH') return chartColors.bearish.border;
            return chartColors.neutral.border;
          }),
        },
      ],
    };
  }, [signals, maxPoints]);

  const options: ChartOptions<'line'> = {
    ...defaultOptions,
    plugins: {
      ...defaultOptions.plugins,
      legend: {
        display: false,
      },
      tooltip: {
        ...defaultOptions.plugins?.tooltip,
        callbacks: {
          label: (context) => {
            const yVal = context.parsed.y ?? 0;
            const signal = signals[signals.length - 1 - context.dataIndex];
            if (signal) {
              return [
                `Confidence: ${(yVal * 100).toFixed(0)}%`,
                `Token: ${signal.token_symbol}`,
                `Sentiment: ${signal.sentiment}`,
              ];
            }
            return `Confidence: ${(yVal * 100).toFixed(0)}%`;
          },
        },
      },
    },
    scales: {
      ...defaultOptions.scales,
      y: {
        ...defaultOptions.scales?.y,
        min: 0,
        max: 1,
        ticks: {
          ...defaultOptions.scales?.y?.ticks,
          callback: (value) => `${(Number(value) * 100).toFixed(0)}%`,
        },
      },
      x: {
        ...defaultOptions.scales?.x,
        display: false,
      },
    },
  };

  // Calculate average confidence
  const avgConfidence = useMemo(() => {
    if (signals.length === 0) return 0;
    const sum = signals.slice(0, 20).reduce((acc, s) => acc + s.confidence_score, 0);
    return sum / Math.min(signals.length, 20);
  }, [signals]);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-base font-medium">Signal Confidence</CardTitle>
        <span className="text-sm text-muted-foreground">
          Avg: <span className="font-semibold text-foreground">{(avgConfidence * 100).toFixed(0)}%</span>
        </span>
      </CardHeader>
      <CardContent>
        <div className="h-[150px]">
          <Line data={chartData} options={options} />
        </div>
      </CardContent>
    </Card>
  );
}
