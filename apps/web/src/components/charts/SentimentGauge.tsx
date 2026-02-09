'use client';

import { useMemo } from 'react';
import { Doughnut } from 'react-chartjs-2';
import { useSentiment } from '@/hooks/useApi';
import { useWebSocket } from '@/hooks/useWebSocket';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { chartColors } from '@/lib/chart-config';
import type { ChartOptions } from 'chart.js';

export function SentimentGauge() {
  const { data: apiSentiment, isLoading } = useSentiment();
  const { sentiment: wsSentiment } = useWebSocket();

  // Prefer real-time WebSocket data over REST API data
  const currentSentiment = wsSentiment || apiSentiment;

  const chartData = useMemo(() => {
    if (!currentSentiment) {
      return {
        labels: ['Bullish', 'Bearish', 'Neutral'],
        datasets: [
          {
            data: [33, 33, 34],
            backgroundColor: [
              chartColors.bullish.border,
              chartColors.bearish.border,
              chartColors.neutral.border,
            ],
            borderWidth: 0,
          },
        ],
      };
    }

    // Use sentiment score to create distribution
    const score = 'score' in currentSentiment ? currentSentiment.score : 0;
    
    // Convert score (-1 to 1) to percentages
    const bullishPercent = Math.max(0, score) * 50 + 25;
    const bearishPercent = Math.max(0, -score) * 50 + 25;
    const neutralPercent = 100 - bullishPercent - bearishPercent;

    return {
      labels: ['Bullish', 'Bearish', 'Neutral'],
      datasets: [
        {
          data: [bullishPercent, bearishPercent, neutralPercent],
          backgroundColor: [
            chartColors.bullish.border,
            chartColors.bearish.border,
            chartColors.neutral.border,
          ],
          borderWidth: 0,
          cutout: '70%',
        },
      ],
    };
  }, [currentSentiment]);

  const options: ChartOptions<'doughnut'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'bottom' as const,
        labels: {
          color: 'rgb(156, 163, 175)',
          usePointStyle: true,
          padding: 15,
        },
      },
      tooltip: {
        callbacks: {
          label: (context) => {
            return `${context.label}: ${context.parsed.toFixed(1)}%`;
          },
        },
      },
    },
  };

  const getSentimentLabel = () => {
    if (!currentSentiment) return 'Loading...';
    const overall = 'overall' in currentSentiment ? currentSentiment.overall : currentSentiment.overall_sentiment;
    return overall || 'NEUTRAL';
  };

  const getSentimentColor = () => {
    const label = getSentimentLabel();
    switch (label) {
      case 'BULLISH':
        return 'text-green-500';
      case 'BEARISH':
        return 'text-red-500';
      default:
        return 'text-yellow-500';
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-medium">Market Sentiment</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-[200px] w-full" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-medium">Market Sentiment</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="relative h-[200px]">
          <Doughnut data={chartData} options={options} />
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="text-center -mt-4">
              <span className={`text-2xl font-bold ${getSentimentColor()}`}>
                {getSentimentLabel()}
              </span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
