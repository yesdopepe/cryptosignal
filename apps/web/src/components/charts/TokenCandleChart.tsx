'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { Skeleton } from '@/components/ui/skeleton';
import { RefreshCw } from 'lucide-react';
import * as api from '@/lib/api';

export interface PriceTick {
  t: string;
  p?: number;
  o?: number;
  h?: number;
  l?: number;
  c?: number;
}

interface Props {
  symbol: string;
  liveTicks?: PriceTick[];
  /** OHLC timeframe in days (1, 7, 14, 30, 90, 365) or "max". Default: 7 */
  days?: number | string;
  /** Initial number of days to zoom into. If omitted, zooms to full extent. */
  initialVisibleDays?: number;
  height?: number;
}

// Global flag to ensure we only configure WASM once per session
let wasmConfigured = false;

// Cache the scichart module so we don't re-import every render
let scichartModule: any = null;

/**
 * High-performance candlestick chart powered by SciChart.js (WebGL + WASM).
 *
 * The chart div is **always mounted** so SciChart can attach to it reliably.
 * Loading / error / empty states are rendered as overlays on top.
 */
export function TokenCandleChart({ symbol, liveTicks = [], days = 7, height = 220, initialVisibleDays }: Props) {
  const chartId = useRef(`scichart-${symbol}-${Math.random().toString(36).substring(2, 9)}`);
  const surfaceRef = useRef<any>(null);
  const mountedRef = useRef(true);
  const fetchCountRef = useRef(0);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hasData, setHasData] = useState(false);

  const cleanupSurface = useCallback(() => {
    if (surfaceRef.current) {
      try {
        surfaceRef.current.delete();
      } catch {
        // surface may already be disposed
      }
      surfaceRef.current = null;
    }
  }, []);

  const fetchData = useCallback(async () => {
    const fetchId = ++fetchCountRef.current;

    try {
      setLoading(true);
      setError(null);

      // Minimum loading time to ensure UI feedback (prevents "no reaction" feel)
      const minDelay = new Promise(resolve => setTimeout(resolve, 600));

      // Load data and SciChart library in parallel
      const [ohlcRes, sc, _] = await Promise.all([
        // Allow error to propagate to main catch block
        api.getOhlcData(symbol, typeof days === 'number' ? days : 365),
        scichartModule
          ? Promise.resolve(scichartModule)
          : import('scichart').then(m => { scichartModule = m; return m; }),
        minDelay
      ]);

      // Bail out if component unmounted or a newer fetch started
      if (!mountedRef.current || fetchId !== fetchCountRef.current) return;

      if (!sc) throw new Error('Failed to load SciChart library');
      if (!ohlcRes) throw new Error('No data returned from API');

      // Configure WASM location once
      if (!wasmConfigured) {
        sc.SciChartSurface.loadWasmFromCDN();
        wasmConfigured = true;
      }

      // Ensure the chart div still exists in the DOM
      const chartElement = document.getElementById(chartId.current);
      if (!chartElement) return;

      // Clean up any previous surface before creating a new one
      cleanupSurface();

      // Create the Surface
      const { sciChartSurface, wasmContext } = await sc.SciChartSurface.create(
        chartId.current,
        { theme: new sc.SciChartJsNavyTheme() }
      );

      if (!mountedRef.current || fetchId !== fetchCountRef.current) {
        sciChartSurface.delete();
        return;
      }

      surfaceRef.current = sciChartSurface;
      sciChartSurface.background = 'transparent';

      // X-Axis
      const xAxis = new sc.DateTimeNumericAxis(wasmContext, {
        axisTitle: 'Time',
        textStyle: { fontSize: 10, color: '#94a3b8' },
        drawMajorGridLines: false,
        drawMinorGridLines: false,
        autoRange: sc.EAutoRange.Once,
      });
      sciChartSurface.xAxes.add(xAxis);

      // Y-Axis
      const yAxis = new sc.NumericAxis(wasmContext, {
        axisAlignment: sc.EAxisAlignment.Right,
        textStyle: { fontSize: 10, color: '#94a3b8' },
        labelPrefix: '$',
        labelPrecision: 2,
        autoRange: sc.EAutoRange.Always,
        growBy: new sc.NumberRange(0.1, 0.1),
      });
      sciChartSurface.yAxes.add(yAxis);

      const candles = ohlcRes.candles || [];

      if (candles.length > 0) {
        const xValues: number[] = [];
        const openValues: number[] = [];
        const highValues: number[] = [];
        const lowValues: number[] = [];
        const closeValues: number[] = [];

        candles.sort((a: any, b: any) => new Date(a.t).getTime() - new Date(b.t).getTime());

        for (const c of candles) {
          xValues.push(Math.floor(new Date(c.t).getTime() / 1000));
          openValues.push(c.o);
          highValues.push(c.h);
          lowValues.push(c.l);
          closeValues.push(c.c);
        }

        const ohlcSeries = new sc.OhlcDataSeries(wasmContext, {
          xValues, openValues, highValues, lowValues, closeValues,
          dataSeriesName: symbol,
        });

        sciChartSurface.renderableSeries.add(new sc.FastCandlestickRenderableSeries(wasmContext, {
          dataSeries: ohlcSeries,
          strokeThickness: 1,
          brushUp: '#22c55e', brushDown: '#ef4444',
          strokeUp: '#22c55e', strokeDown: '#ef4444',
          opacity: 0.9,
        }));

        if (candles.length >= 20) {
          sciChartSurface.renderableSeries.add(new sc.FastLineRenderableSeries(wasmContext, {
            dataSeries: new sc.XyMovingAverageFilter(ohlcSeries, { length: 20 }),
            stroke: '#38bdf8', strokeThickness: 2,
          }));
        }

        setHasData(true);
        setError(null);

        // Interactivity
        sciChartSurface.chartModifiers.add(
          new sc.ZoomPanModifier({ enableZoom: true, enablePan: true }),
          new sc.MouseWheelZoomModifier(),
          new sc.ZoomExtentsModifier(),
          new sc.CursorModifier({
            crosshairStroke: '#f59e0b', axisLabelFill: '#f59e0b', tooltipContainerBackground: '#1e293b',
          })
        );
        
        // Initial zoom will be handled by the effect below
        if (!initialVisibleDays) {
           sciChartSurface.zoomExtents();
        }
      } else {
        setHasData(false);
        // Surface was created but has no data — clean it up so
        // the overlay buttons aren't blocked by the empty canvas
        cleanupSurface();
      }
    } catch (err: any) {
      if (!mountedRef.current || fetchId !== fetchCountRef.current) return;
      console.error(`[${symbol}] SciChart Error:`, err);
      // Clean error message based on HTTP status
      const msg = err.status === 404 ? 'Token not listed on CoinGecko' 
                : err.status === 429 ? 'Rate limit exceeded — try again shortly'
                : err.status === 503 ? 'Data temporarily unavailable — try again shortly'
                : err.message || 'Error loading chart';
      setError(msg);
      cleanupSurface();
      setHasData(false);
    } finally {
      if (mountedRef.current && fetchId === fetchCountRef.current) {
        setLoading(false);
      }
    }
  }, [symbol, days, cleanupSurface]);

  // Handle dynamic zooming when initialVisibleDays changes
  useEffect(() => {
    if (loading || !hasData || !surfaceRef.current) return;

    const updateZoom = async () => {
      try {
        const _sc = scichartModule || (await import('scichart'));
        const surface = surfaceRef.current;
        if (!surface) return;
        
        // If max view (no specific days), zoom to fit all
        if (!initialVisibleDays) {
          surface.zoomExtents();
          return;
        }
        
        const xAxis = surface.xAxes.get(0);
        const renderableSeries = surface.renderableSeries.get(0);

        if (xAxis && renderableSeries) {
          const dataSeries = renderableSeries.dataSeries;
          const xRange = dataSeries.getXRange();
          const maxX = xRange.max;
          // Calculate visible range based on days
          const minVisible = maxX - (initialVisibleDays * 24 * 60 * 60);
          
          xAxis.animateVisibleRange(new _sc.NumberRange(minVisible, maxX), 500);
        }
      } catch (err) {
        console.error("Error updating chart zoom:", err);
      }
    };

    updateZoom();
  }, [initialVisibleDays, hasData, loading]);

  // Initial fetch and re-fetch when symbol/days change
  useEffect(() => {
    mountedRef.current = true;
    fetchData();

    return () => {
      mountedRef.current = false;
      cleanupSurface();
    };
  }, [fetchData, cleanupSurface]);

  return (
    <div style={{ height, position: 'relative' }} className="w-full overflow-hidden">
      {/* SciChart container — always mounted */}
      <div
        id={chartId.current}
        style={{ width: '100%', height: '100%' }}
      />

      {/* Loading overlay */}
      {loading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/60 backdrop-blur-[1px]">
          <Skeleton className="w-full h-full absolute inset-0" />
          <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground relative z-10" />
        </div>
      )}

      {/* Error overlay */}
      {!loading && error && (
        <div className="absolute inset-0 z-20 flex flex-col gap-2 items-center justify-center bg-secondary/20 backdrop-blur-[2px] rounded-lg text-xs p-4 text-center">
          <div className="text-red-500">
            <p className="font-bold">Chart Error</p>
            <p>{error}</p>
          </div>
          <button
            onClick={(e) => { e.stopPropagation(); fetchData(); }}
            className="px-3 py-1.5 bg-background hover:bg-accent rounded border border-border mt-2 flex items-center gap-1.5 cursor-pointer text-foreground"
          >
            <RefreshCw className="h-3 w-3" />
            Retry
          </button>
        </div>
      )}

      {/* No-data overlay */}
      {!loading && !error && !hasData && (
        <div className="absolute inset-0 z-20 flex flex-col gap-2 items-center justify-center bg-background/50 backdrop-blur-[1px]">
          <p className="text-muted-foreground text-sm bg-background/80 px-3 py-1 rounded border border-border/50 select-none">
            No Data Available
          </p>
          <button
            onClick={(e) => { e.stopPropagation(); fetchData(); }}
            className="text-xs px-3 py-1.5 bg-primary/10 hover:bg-primary/20 text-primary rounded transition-colors flex items-center gap-1.5 cursor-pointer"
          >
            <RefreshCw className="h-3 w-3" />
            Refresh Data
          </button>
        </div>
      )}
    </div>
  );
}
