'use client';

import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { TokenCandleChart } from '@/components/charts/TokenCandleChart';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ExternalLink } from 'lucide-react';

interface TokenDetailsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  symbol: string | null;
  name?: string | null;
}

export function TokenDetailsDialog({ 
  open, 
  onOpenChange, 
  symbol,
  name
}: TokenDetailsDialogProps) {
  // Default to fetching 90 days (max high-res data) to allow zooming out up to 3mo
  const [days, setDays] = useState<number | string>(90);
  const [viewDays, setViewDays] = useState<number | string>(7);

  // Strategy:
  // - 1D: Fetch 1 day (30min resolution)
  // - 7D-90D: Fetch 90 days (4h resolution). Allows smooth zoom/pan within 3 months.
  // - 1Y-Max: Fetch 'max' (4-day resolution). Allows full history but lower detail.
  const timeOptions = [
    { label: '1D', value: 1, fetch: 1 },           // High resolution (30m)
    { label: '7D', value: 7, fetch: 90 },          // 4h resolution, 3mo buffer
    { label: '14D', value: 14, fetch: 90 },        // 4h resolution, 3mo buffer
    { label: '30D', value: 30, fetch: 90 },        // 4h resolution, 3mo buffer
    { label: '90D', value: 90, fetch: 90 },        // 4h resolution, full view
    { label: '1Y', value: 365, fetch: 'max' },     // 4-day resolution, max 365d (Free Tier)
  ];

  if (!symbol) return null;

  const currentOption = timeOptions.find(o => o.value === viewDays) || timeOptions[1];

  const handleTimeChange = (opt: typeof timeOptions[0]) => {
     setViewDays(opt.value);
     setDays(opt.fetch);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[800px] max-w-[95vw]">
        <DialogHeader>
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex items-center gap-2">
                <DialogTitle className="text-xl">{name || symbol}</DialogTitle>
                <Badge variant="secondary">{symbol}</Badge>
            </div>
            <div className="flex gap-1 flex-wrap">
                 {timeOptions.map((opt) => (
                    <Button
                        key={opt.label}
                        variant={viewDays === opt.value ? "default" : "outline"}
                        size="sm"
                        className="h-7 px-2 text-xs"
                        onClick={() => handleTimeChange(opt)}
                    >
                        {opt.label}
                    </Button>
                 ))}
            </div>
          </div>
          <DialogDescription>
            Historical price candlestick chart.
          </DialogDescription>
        </DialogHeader>
        
        <div className="mt-4 border rounded-lg overflow-hidden bg-background">
            <TokenCandleChart 
                key={`${symbol}-${days}`} 
                symbol={symbol} 
                days={days} 
                initialVisibleDays={typeof viewDays === 'number' ? viewDays : undefined}
                height={400} 
            />
        </div>
      </DialogContent>
    </Dialog>
  );
}
