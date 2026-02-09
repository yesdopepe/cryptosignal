'use client';

import { useStats } from '@/hooks/useApi';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { formatNumber, formatPercent } from '@/lib/utils';
import { Radio, Users, Coins, TrendingUp, Clock, Target } from 'lucide-react';

export function StatsCards() {
  const { data: stats, isLoading } = useStats();

  const statItems = [
    {
      label: 'Total Signals',
      value: stats?.total_signals ?? 0,
      format: (v: number) => formatNumber(v),
      icon: Radio,
      color: 'text-blue-500',
      bgColor: 'bg-blue-500/10',
    },
    {
      label: 'Active Channels',
      value: stats?.active_channels ?? 0,
      format: (v: number) => v.toString(),
      icon: Users,
      color: 'text-purple-500',
      bgColor: 'bg-purple-500/10',
    },
    {
      label: 'Tokens Tracked',
      value: stats?.tokens_tracked ?? 0,
      format: (v: number) => v.toString(),
      icon: Coins,
      color: 'text-yellow-500',
      bgColor: 'bg-yellow-500/10',
    },
    {
      label: 'Success Rate',
      value: stats?.success_rate ?? 0,
      format: (v: number) => `${(v * 100).toFixed(1)}%`,
      icon: Target,
      color: 'text-green-500',
      bgColor: 'bg-green-500/10',
    },
    {
      label: 'Signals (24h)',
      value: stats?.signals_24h ?? 0,
      format: (v: number) => formatNumber(v),
      icon: Clock,
      color: 'text-cyan-500',
      bgColor: 'bg-cyan-500/10',
    },
    {
      label: 'Avg ROI (24h)',
      value: stats?.avg_roi_24h ?? 0,
      format: (v: number) => formatPercent(v),
      icon: TrendingUp,
      color: (stats?.avg_roi_24h ?? 0) >= 0 ? 'text-green-500' : 'text-red-500',
      bgColor: (stats?.avg_roi_24h ?? 0) >= 0 ? 'bg-green-500/10' : 'bg-red-500/10',
    },
  ];

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <Card key={i}>
            <CardContent className="p-4">
              <Skeleton className="h-4 w-20 mb-2" />
              <Skeleton className="h-8 w-16" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      {statItems.map((item) => {
        const Icon = item.icon;
        
        return (
          <Card key={item.label}>
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <div className={`p-1.5 rounded-md ${item.bgColor}`}>
                  <Icon className={`h-4 w-4 ${item.color}`} />
                </div>
                <span className="text-xs text-muted-foreground">{item.label}</span>
              </div>
              <p className={`text-2xl font-bold ${item.color}`}>
                {item.format(item.value)}
              </p>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
