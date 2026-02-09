"""Analytics service for processing and analyzing signal data."""
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import select, func, desc, case, and_, Integer
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np

from app.models import Signal, Channel, Token


class AnalyticsService:
    """Service for computing analytics on signal data."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_historical_data(
        self,
        days: int = 30,
        limit: int = 100000,
    ) -> Dict[str, Any]:
        """
        Get historical signal data for analytics.
        This is a heavy operation on 100k+ records.
        """
        start_time = time.perf_counter()
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Query signals with all necessary data
        query = (
            select(Signal)
            .where(Signal.timestamp >= start_date)
            .order_by(desc(Signal.timestamp))
            .limit(limit)
        )
        
        result = await self.session.execute(query)
        signals = result.scalars().all()
        
        # Process signals into response format
        signal_data = []
        total_roi = 0
        success_count = 0
        sentiment_counts = {"BULLISH": 0, "BEARISH": 0, "NEUTRAL": 0}
        
        for signal in signals:
            signal_data.append({
                "id": signal.id,
                "channel_name": signal.channel_name,
                "token_symbol": signal.token_symbol,
                "sentiment": signal.sentiment,
                "price_at_signal": signal.price_at_signal,
                "roi_percent": signal.roi_percent,
                "success": signal.success,
                "timestamp": signal.timestamp.isoformat(),
                "confidence_score": signal.confidence_score,
            })
            
            if signal.roi_percent:
                total_roi += signal.roi_percent
            if signal.success:
                success_count += 1
            sentiment_counts[signal.sentiment] = sentiment_counts.get(signal.sentiment, 0) + 1
        
        query_time = (time.perf_counter() - start_time) * 1000
        
        total_count = len(signal_data)
        avg_roi = total_roi / total_count if total_count > 0 else 0
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0
        
        return {
            "signals": signal_data,
            "total_count": total_count,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "summary": {
                "avg_roi": round(avg_roi, 2),
                "success_rate": round(success_rate, 2),
                "sentiment_distribution": sentiment_counts,
                "total_bullish": sentiment_counts.get("BULLISH", 0),
                "total_bearish": sentiment_counts.get("BEARISH", 0),
                "total_neutral": sentiment_counts.get("NEUTRAL", 0),
            },
            "query_time_ms": round(query_time, 2),
            "cached": False,
        }
    
    async def get_token_stats(self, symbol: str) -> Dict[str, Any]:
        """
        Get comprehensive statistics for a specific token from 100k+ records.
        This is a heavy computation operation.
        """
        start_time = time.perf_counter()
        
        # Get token info
        token_result = await self.session.execute(
            select(Token).where(Token.symbol == symbol.upper())
        )
        token = token_result.scalar_one_or_none()
        
        if not token:
            return {"error": f"Token {symbol} not found"}
        
        # Get all signals for this token
        signals_result = await self.session.execute(
            select(Signal).where(Signal.token_symbol == symbol.upper())
        )
        signals = signals_result.scalars().all()
        
        if not signals:
            return {
                "symbol": symbol.upper(),
                "name": token.name,
                "total_signals": 0,
                "message": "No signals found for this token",
            }
        
        # Calculate comprehensive statistics
        roi_values = [s.roi_percent for s in signals if s.roi_percent is not None]
        success_signals = [s for s in signals if s.success]
        
        # Sentiment distribution
        sentiment_dist = {"BULLISH": 0, "BEARISH": 0, "NEUTRAL": 0}
        for s in signals:
            sentiment_dist[s.sentiment] = sentiment_dist.get(s.sentiment, 0) + 1
        
        # ROI distribution buckets
        roi_dist = {
            "< -50%": 0,
            "-50% to -20%": 0,
            "-20% to 0%": 0,
            "0% to 20%": 0,
            "20% to 50%": 0,
            "50% to 100%": 0,
            "> 100%": 0,
        }
        for roi in roi_values:
            if roi < -50:
                roi_dist["< -50%"] += 1
            elif roi < -20:
                roi_dist["-50% to -20%"] += 1
            elif roi < 0:
                roi_dist["-20% to 0%"] += 1
            elif roi < 20:
                roi_dist["0% to 20%"] += 1
            elif roi < 50:
                roi_dist["20% to 50%"] += 1
            elif roi < 100:
                roi_dist["50% to 100%"] += 1
            else:
                roi_dist["> 100%"] += 1
        
        # Signals by channel
        channel_counts = {}
        for s in signals:
            channel_counts[s.channel_name] = channel_counts.get(s.channel_name, 0) + 1
        
        # Performance trend (last 30 days, daily)
        now = datetime.utcnow()
        performance_trend = []
        for i in range(30):
            day_start = now - timedelta(days=i+1)
            day_end = now - timedelta(days=i)
            day_signals = [s for s in signals if day_start <= s.timestamp < day_end]
            if day_signals:
                day_roi = np.mean([s.roi_percent for s in day_signals if s.roi_percent])
                performance_trend.append({
                    "date": day_end.strftime("%Y-%m-%d"),
                    "signal_count": len(day_signals),
                    "avg_roi": round(day_roi, 2) if not np.isnan(day_roi) else 0,
                })
        
        query_time = (time.perf_counter() - start_time) * 1000
        
        return {
            "symbol": symbol.upper(),
            "name": token.name,
            "total_signals": len(signals),
            "success_rate": round(len(success_signals) / len(signals) * 100, 2),
            "avg_roi": round(np.mean(roi_values), 2) if roi_values else 0,
            "median_roi": round(np.median(roi_values), 2) if roi_values else 0,
            "volatility": round(np.std(roi_values), 2) if roi_values else 0,
            "sentiment_distribution": sentiment_dist,
            "roi_distribution": roi_dist,
            "signals_by_channel": channel_counts,
            "performance_trend": performance_trend[::-1],  # Chronological order
            "query_time_ms": round(query_time, 2),
            "cached": False,
        }
    
    async def get_channel_leaderboard(self) -> Dict[str, Any]:
        """
        Get channel performance leaderboard from 100k+ signals.
        This is a heavy aggregation operation.
        """
        start_time = time.perf_counter()
        
        # Get all channels with their signals
        channels_result = await self.session.execute(
            select(Channel).where(Channel.is_active == True)
        )
        channels = channels_result.scalars().all()
        
        leaderboard = []
        total_signals = 0
        
        for channel in channels:
            # Get channel signals
            signals_result = await self.session.execute(
                select(Signal).where(Signal.channel_id == channel.id)
            )
            signals = signals_result.scalars().all()
            
            if not signals:
                continue
            
            total_signals += len(signals)
            
            # Calculate metrics
            success_count = sum(1 for s in signals if s.success)
            roi_values = [s.roi_percent for s in signals if s.roi_percent is not None]
            avg_roi = np.mean(roi_values) if roi_values else 0
            success_rate = (success_count / len(signals) * 100) if signals else 0
            
            # Calculate composite score
            # Score = (success_rate * 0.4) + (avg_roi * 0.4) + (signal_count_normalized * 0.2)
            score = (success_rate * 0.4) + (avg_roi * 0.4) + (min(len(signals) / 1000, 100) * 0.2)
            
            # Calculate win streak (consecutive successful signals)
            sorted_signals = sorted(signals, key=lambda s: s.timestamp, reverse=True)
            win_streak = 0
            for s in sorted_signals:
                if s.success:
                    win_streak += 1
                else:
                    break
            
            # Find top token
            token_counts = {}
            for s in signals:
                token_counts[s.token_symbol] = token_counts.get(s.token_symbol, 0) + 1
            top_token = max(token_counts.items(), key=lambda x: x[1])[0] if token_counts else "N/A"
            
            leaderboard.append({
                "channel_id": channel.id,
                "channel_name": channel.name,
                "total_signals": len(signals),
                "success_rate": round(success_rate, 2),
                "avg_roi": round(avg_roi, 2),
                "score": round(score, 2),
                "win_streak": win_streak,
                "top_token": top_token,
            })
        
        # Sort by score and add ranks
        leaderboard.sort(key=lambda x: x["score"], reverse=True)
        for i, entry in enumerate(leaderboard):
            entry["rank"] = i + 1
        
        query_time = (time.perf_counter() - start_time) * 1000
        
        return {
            "leaderboard": leaderboard,
            "total_channels": len(leaderboard),
            "total_signals_analyzed": total_signals,
            "time_period": "all_time",
            "query_time_ms": round(query_time, 2),
            "cached": False,
        }
    
    async def get_pattern_analysis(self) -> Dict[str, Any]:
        """
        Detect market patterns from historical signal data.
        This is a heavy computation on 100k+ records.
        """
        start_time = time.perf_counter()
        
        # Get recent signals for pattern analysis
        now = datetime.utcnow()
        thirty_days_ago = now - timedelta(days=30)
        
        result = await self.session.execute(
            select(Signal)
            .where(Signal.timestamp >= thirty_days_ago)
            .order_by(Signal.timestamp)
        )
        signals = result.scalars().all()
        
        if not signals:
            return {"error": "No signals found for pattern analysis"}
        
        # Analyze sentiment trends
        sentiment_counts = {"BULLISH": 0, "BEARISH": 0, "NEUTRAL": 0}
        for s in signals:
            sentiment_counts[s.sentiment] += 1
        
        total = len(signals)
        bullish_pct = sentiment_counts["BULLISH"] / total
        bearish_pct = sentiment_counts["BEARISH"] / total
        
        # Determine market phase
        if bullish_pct > 0.6:
            market_phase = "bull"
            dominant_sentiment = "BULLISH"
        elif bearish_pct > 0.4:
            market_phase = "bear"
            dominant_sentiment = "BEARISH"
        else:
            market_phase = "sideways"
            dominant_sentiment = "NEUTRAL"
        
        # Calculate sentiment strength (-1 to 1)
        sentiment_strength = (bullish_pct - bearish_pct)
        
        # Detect patterns by token
        patterns = []
        token_signals = {}
        for s in signals:
            if s.token_symbol not in token_signals:
                token_signals[s.token_symbol] = []
            token_signals[s.token_symbol].append(s)
        
        for token, t_signals in token_signals.items():
            if len(t_signals) < 10:
                continue
            
            # Check for bullish momentum (mostly bullish signals with positive ROI)
            recent_signals = sorted(t_signals, key=lambda x: x.timestamp)[-20:]
            bullish_count = sum(1 for s in recent_signals if s.sentiment == "BULLISH")
            avg_roi = np.mean([s.roi_percent for s in recent_signals if s.roi_percent])
            
            if bullish_count >= 15 and avg_roi > 20:
                patterns.append({
                    "pattern_type": "bullish_momentum",
                    "description": f"{token} showing strong bullish momentum with {bullish_count}/20 bullish signals and {avg_roi:.1f}% avg ROI",
                    "confidence": min(0.95, (bullish_count / 20) * 0.8 + (avg_roi / 100) * 0.2),
                    "tokens_affected": [token],
                    "start_date": recent_signals[0].timestamp.isoformat(),
                    "detected_at": now.isoformat(),
                    "supporting_signals": len(recent_signals),
                })
            
            # Check for accumulation pattern (signals clustering with increasing confidence)
            if len(t_signals) >= 30:
                recent = t_signals[-15:]
                older = t_signals[-30:-15]
                recent_conf = np.mean([s.confidence_score for s in recent])
                older_conf = np.mean([s.confidence_score for s in older])
                
                if recent_conf > older_conf * 1.1:  # 10% increase in confidence
                    patterns.append({
                        "pattern_type": "accumulation",
                        "description": f"{token} showing accumulation pattern with increasing signal confidence",
                        "confidence": min(0.9, (recent_conf / older_conf) - 0.9),
                        "tokens_affected": [token],
                        "start_date": older[0].timestamp.isoformat(),
                        "detected_at": now.isoformat(),
                        "supporting_signals": 30,
                    })
        
        # Determine volume trend
        week_ago = now - timedelta(days=7)
        two_weeks_ago = now - timedelta(days=14)
        
        recent_week = [s for s in signals if s.timestamp >= week_ago]
        previous_week = [s for s in signals if two_weeks_ago <= s.timestamp < week_ago]
        
        if len(previous_week) > 0:
            volume_change = (len(recent_week) - len(previous_week)) / len(previous_week)
            if volume_change > 0.2:
                volume_trend = "increasing"
            elif volume_change < -0.2:
                volume_trend = "decreasing"
            else:
                volume_trend = "stable"
        else:
            volume_trend = "insufficient_data"
        
        query_time = (time.perf_counter() - start_time) * 1000
        
        return {
            "patterns": patterns[:10],  # Top 10 patterns
            "market_phase": market_phase,
            "dominant_sentiment": dominant_sentiment,
            "sentiment_strength": round(sentiment_strength, 3),
            "volume_trend": volume_trend,
            "signals_analyzed": len(signals),
            "time_period_days": 30,
            "query_time_ms": round(query_time, 2),
            "cached": False,
        }
    
    async def get_trending_tokens(self, hours: int = 24) -> Dict[str, Any]:
        """Get trending tokens from recent signals."""
        start_time = time.perf_counter()
        
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=hours)
        previous_cutoff = cutoff - timedelta(hours=hours)
        
        # Get recent signals
        result = await self.session.execute(
            select(Signal).where(Signal.timestamp >= cutoff)
        )
        recent_signals = result.scalars().all()
        
        # Get previous period signals for comparison
        result = await self.session.execute(
            select(Signal).where(
                and_(Signal.timestamp >= previous_cutoff, Signal.timestamp < cutoff)
            )
        )
        previous_signals = result.scalars().all()
        
        # Count signals per token
        recent_counts = {}
        recent_roi = {}
        recent_sentiment = {}
        
        for s in recent_signals:
            token = s.token_symbol
            recent_counts[token] = recent_counts.get(token, 0) + 1
            if token not in recent_roi:
                recent_roi[token] = []
            if s.roi_percent:
                recent_roi[token].append(s.roi_percent)
            if token not in recent_sentiment:
                recent_sentiment[token] = {"BULLISH": 0, "BEARISH": 0, "NEUTRAL": 0}
            recent_sentiment[token][s.sentiment] += 1
        
        previous_counts = {}
        for s in previous_signals:
            previous_counts[s.token_symbol] = previous_counts.get(s.token_symbol, 0) + 1
        
        # Get token price data
        token_symbols = list(recent_counts.keys())
        token_data_map = {}
        if token_symbols:
            token_result = await self.session.execute(
                select(Token).where(Token.symbol.in_(token_symbols))
            )
            tokens = token_result.scalars().all()
            for t in tokens:
                token_data_map[t.symbol] = {
                    "price": t.current_price,
                    "change": t.price_change_24h
                }

        # Build trending list
        trending = []
        for token, count in recent_counts.items():
            prev_count = previous_counts.get(token, 1)
            change_pct = ((count - prev_count) / prev_count) * 100
            
            roi_list = recent_roi.get(token, [])
            avg_roi = np.mean(roi_list) if roi_list else 0
            
            sent = recent_sentiment.get(token, {})
            dominant = max(sent.items(), key=lambda x: x[1])[0] if sent else "NEUTRAL"
            
            # Momentum score based on count, change, and sentiment
            momentum = (count * 0.3) + (change_pct * 0.4) + (avg_roi * 0.3)
            
            token_price_data = token_data_map.get(token, {})
            
            trending.append({
                "symbol": token,
                "name": self._get_token_name(token),
                "signal_count_24h": count,
                "signal_change_percent": round(change_pct, 2),
                "dominant_sentiment": dominant,
                "avg_roi_24h": round(avg_roi, 2),
                "momentum_score": round(momentum, 2),
                "price": token_price_data.get("price"),
                "price_change_24h": token_price_data.get("change"),
            })
        
        # Sort by momentum and add ranks
        trending.sort(key=lambda x: x["momentum_score"], reverse=True)
        for i, t in enumerate(trending[:10]):
            t["rank"] = i + 1
        
        # Get most active channels
        channel_counts = {}
        for s in recent_signals:
            channel_counts[s.channel_name] = channel_counts.get(s.channel_name, 0) + 1
        most_active = sorted(channel_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "trending": trending[:10],
            "total_signals_24h": len(recent_signals),
            "most_active_channels": [c[0] for c in most_active],
            "timestamp": now.isoformat(),
        }
    
    async def get_market_sentiment(self, hours: int = 24) -> Dict[str, Any]:
        """Get overall market sentiment analysis."""
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=hours)
        
        result = await self.session.execute(
            select(Signal).where(Signal.timestamp >= cutoff)
        )
        signals = result.scalars().all()
        
        if not signals:
            return {
                "overall_sentiment": "NEUTRAL",
                "sentiment_score": 0,
                "signals_analyzed": 0,
            }
        
        total = len(signals)
        bullish = sum(1 for s in signals if s.sentiment == "BULLISH")
        bearish = sum(1 for s in signals if s.sentiment == "BEARISH")
        neutral = sum(1 for s in signals if s.sentiment == "NEUTRAL")
        
        bullish_pct = (bullish / total) * 100
        bearish_pct = (bearish / total) * 100
        neutral_pct = (neutral / total) * 100
        
        # Sentiment score: -1 (full bearish) to 1 (full bullish)
        sentiment_score = (bullish - bearish) / total
        
        # Determine overall sentiment
        if bullish_pct > 50:
            overall = "BULLISH"
        elif bearish_pct > 30:
            overall = "BEARISH"
        else:
            overall = "NEUTRAL"
        
        # Fear & Greed Index (0-100)
        # Based on sentiment distribution and success rates
        success_rate = sum(1 for s in signals if s.success) / total
        fear_greed = int(50 + (sentiment_score * 30) + ((success_rate - 0.5) * 40))
        fear_greed = max(0, min(100, fear_greed))
        
        # Top tokens by sentiment
        token_sentiment = {}
        for s in signals:
            if s.token_symbol not in token_sentiment:
                token_sentiment[s.token_symbol] = {"BULLISH": 0, "BEARISH": 0}
            token_sentiment[s.token_symbol][s.sentiment] = token_sentiment[s.token_symbol].get(s.sentiment, 0) + 1
        
        # Sort tokens by bullish/bearish counts
        bullish_tokens = sorted(
            [(t, s.get("BULLISH", 0)) for t, s in token_sentiment.items()],
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        bearish_tokens = sorted(
            [(t, s.get("BEARISH", 0)) for t, s in token_sentiment.items()],
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        return {
            "overall_sentiment": overall,
            "sentiment_score": round(sentiment_score, 3),
            "bullish_percent": round(bullish_pct, 2),
            "bearish_percent": round(bearish_pct, 2),
            "neutral_percent": round(neutral_pct, 2),
            "fear_greed_index": fear_greed,
            "signals_analyzed": total,
            "time_period_hours": hours,
            "top_bullish_tokens": [t[0] for t in bullish_tokens],
            "top_bearish_tokens": [t[0] for t in bearish_tokens],
            "timestamp": now.isoformat(),
        }
    
    def _get_token_name(self, symbol: str) -> str:
        """Get token name from symbol."""
        token_names = {
            "BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana",
            "DOGE": "Dogecoin", "PEPE": "Pepe", "SHIB": "Shiba Inu",
            "LINK": "Chainlink", "MATIC": "Polygon", "AVAX": "Avalanche",
            "DOT": "Polkadot",
        }
        return token_names.get(symbol, symbol)
