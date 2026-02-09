"""Synthetic data generator for creating 100k+ realistic signal records."""
import asyncio
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import numpy as np
from faker import Faker

from app.database import async_session_maker, create_tables
from app.models import Signal, Channel, Token
from app.config import settings

# Initialize Faker with disabled weighting for performance
fake = Faker()
Faker.seed(42)
random.seed(42)
np.random.seed(42)


class SyntheticDataGenerator:
    """Generator for creating realistic synthetic crypto signal data."""
    
    # Channel configurations
    CHANNELS = [
        {"name": "CryptoWhales", "telegram_id": "@cryptowhales", "subscribers": 125000, "description": "Premium whale watching signals"},
        {"name": "MoonShots", "telegram_id": "@moonshots_official", "subscribers": 89000, "description": "High risk, high reward altcoin plays"},
        {"name": "GemHunters", "telegram_id": "@gemhunters", "subscribers": 67000, "description": "Early gem discovery signals"},
        {"name": "DeFiSignals", "telegram_id": "@defisignals", "subscribers": 45000, "description": "DeFi protocol analysis and signals"},
        {"name": "AltcoinDaily", "telegram_id": "@altcoindaily", "subscribers": 156000, "description": "Daily altcoin analysis and picks"},
        {"name": "PumpAlerts", "telegram_id": "@pumpalerts", "subscribers": 78000, "description": "Real-time pump detection alerts"},
    ]
    
    # Token configurations with price ranges
    TOKENS = [
        {"symbol": "BTC", "name": "Bitcoin", "price_range": (20000, 70000)},
        {"symbol": "ETH", "name": "Ethereum", "price_range": (1000, 4000)},
        {"symbol": "SOL", "name": "Solana", "price_range": (10, 250)},
        {"symbol": "DOGE", "name": "Dogecoin", "price_range": (0.05, 0.5)},
        {"symbol": "PEPE", "name": "Pepe", "price_range": (0.000001, 0.00005)},
        {"symbol": "SHIB", "name": "Shiba Inu", "price_range": (0.000005, 0.0001)},
        {"symbol": "LINK", "name": "Chainlink", "price_range": (5, 50)},
        {"symbol": "MATIC", "name": "Polygon", "price_range": (0.3, 2.5)},
        {"symbol": "AVAX", "name": "Avalanche", "price_range": (10, 150)},
        {"symbol": "DOT", "name": "Polkadot", "price_range": (3, 50)},
    ]
    
    # Sentiment distribution: 60% BULLISH, 30% NEUTRAL, 10% BEARISH
    SENTIMENT_WEIGHTS = {
        "BULLISH": 0.60,
        "NEUTRAL": 0.30,
        "BEARISH": 0.10,
    }
    
    # Message templates for realistic signals
    BULLISH_TEMPLATES = [
        "🚀 {token} looking extremely bullish! Entry at ${price:.6f}. Target: {target}% gains. DYOR!",
        "📈 Strong buy signal on {token}. Price: ${price:.6f}. Accumulation zone detected.",
        "💎 {token} gem alert! Current: ${price:.6f}. Whale activity spotted. Moon soon! 🌙",
        "🔥 {token} breaking out! Entry: ${price:.6f}. Multiple bullish indicators aligned.",
        "⚡ Quick {token} alpha: ${price:.6f} entry. Chart looking prime for a pump!",
    ]
    
    BEARISH_TEMPLATES = [
        "⚠️ {token} showing weakness at ${price:.6f}. Consider taking profits or setting stops.",
        "📉 Bearish divergence on {token}. Current: ${price:.6f}. Caution advised.",
        "🔴 {token} sell signal. Price: ${price:.6f}. Distribution pattern forming.",
        "Warning: {token} at ${price:.6f} showing heavy selling pressure. Risk off!",
    ]
    
    NEUTRAL_TEMPLATES = [
        "👀 Watching {token} at ${price:.6f}. Waiting for confirmation before entry.",
        "📊 {token} consolidating at ${price:.6f}. Breakout direction uncertain.",
        "ℹ️ {token} update: ${price:.6f}. Range-bound trading expected.",
        "🔄 {token} at ${price:.6f}. Market indecision - wait for clearer signal.",
    ]
    
    TAGS_POOL = [
        "breakout", "accumulation", "whale_alert", "technical", "fundamental",
        "high_risk", "low_risk", "swing_trade", "scalp", "hodl", "dip_buy",
        "resistance_break", "support_test", "volume_surge", "momentum"
    ]
    
    def __init__(self, count: int = 100000):
        """Initialize generator with target signal count."""
        self.count = count
        self.channels: List[Channel] = []
        self.tokens: List[Token] = []
        self.channel_map: Dict[int, Dict[str, Any]] = {}
        self.token_map: Dict[str, Dict[str, Any]] = {}
    
    async def generate_all(self) -> Dict[str, int]:
        """Generate all synthetic data."""
        print(f"🚀 Starting synthetic data generation for {self.count:,} signals...")
        
        # Create tables
        await create_tables()
        print("✅ Database tables created")
        
        async with async_session_maker() as session:
            # Generate channels
            channel_count = await self._generate_channels(session)
            print(f"✅ Generated {channel_count} channels")
            
            # Generate tokens
            token_count = await self._generate_tokens(session)
            print(f"✅ Generated {token_count} tokens")
            
            # Generate signals in batches
            signal_count = await self._generate_signals(session)
            print(f"✅ Generated {signal_count:,} signals")
            
            # Update channel and token statistics
            await self._update_statistics(session)
            print("✅ Updated channel and token statistics")
            
            await session.commit()
        
        return {
            "channels": channel_count,
            "tokens": token_count,
            "signals": signal_count,
        }
    
    async def _generate_channels(self, session) -> int:
        """Generate channel records."""
        for i, ch_data in enumerate(self.CHANNELS):
            channel = Channel(
                name=ch_data["name"],
                telegram_id=ch_data["telegram_id"],
                description=ch_data["description"],
                subscriber_count=ch_data["subscribers"],
                is_active=True,
                created_at=datetime.utcnow() - timedelta(days=random.randint(180, 365)),
            )
            session.add(channel)
            await session.flush()
            
            self.channel_map[channel.id] = {
                "name": ch_data["name"],
                "id": channel.id,
            }
            self.channels.append(channel)
        
        return len(self.CHANNELS)
    
    async def _generate_tokens(self, session) -> int:
        """Generate token records."""
        for token_data in self.TOKENS:
            token = Token(
                symbol=token_data["symbol"],
                name=token_data["name"],
                current_price=random.uniform(*token_data["price_range"]),
                created_at=datetime.utcnow() - timedelta(days=365),
            )
            session.add(token)
            await session.flush()
            
            self.token_map[token_data["symbol"]] = {
                "name": token_data["name"],
                "price_range": token_data["price_range"],
            }
            self.tokens.append(token)
        
        return len(self.TOKENS)
    
    async def _generate_signals(self, session, batch_size: int = 5000) -> int:
        """Generate signal records in batches."""
        total_generated = 0
        base_date = datetime.utcnow()
        
        # Pre-calculate channel and token IDs
        channel_ids = [ch.id for ch in self.channels]
        channel_names = {ch.id: ch.name for ch in self.channels}
        token_symbols = list(self.token_map.keys())
        
        # Pre-calculate sentiment choices based on weights
        sentiments = list(self.SENTIMENT_WEIGHTS.keys())
        sentiment_weights = list(self.SENTIMENT_WEIGHTS.values())
        
        while total_generated < self.count:
            batch_count = min(batch_size, self.count - total_generated)
            signals_batch = []
            
            for _ in range(batch_count):
                # Random channel
                channel_id = random.choice(channel_ids)
                channel_name = channel_names[channel_id]
                
                # Random token
                token_symbol = random.choice(token_symbols)
                token_info = self.token_map[token_symbol]
                token_name = token_info["name"]
                price_range = token_info["price_range"]
                
                # Generate price
                price_at_signal = random.uniform(*price_range)
                
                # Sentiment based on distribution
                sentiment = random.choices(sentiments, weights=sentiment_weights)[0]
                
                # ROI: Normal distribution centered at 15%, std 50%, range -80% to 300%
                roi = np.clip(np.random.normal(15, 50), -80, 300)
                
                # Success: 60% of signals successful
                success = random.random() < 0.60
                
                # Current price based on ROI
                current_price = price_at_signal * (1 + roi / 100)
                
                # Timestamp: Random within last 365 days, clustered around market hours
                days_ago = random.randint(0, 364)
                # Market hours clustering (8am-8pm UTC more likely)
                if random.random() < 0.7:  # 70% during market hours
                    hour = random.randint(8, 20)
                else:
                    hour = random.randint(0, 23)
                
                timestamp = base_date - timedelta(
                    days=days_ago,
                    hours=random.randint(0, 23) if random.random() > 0.7 else hour,
                    minutes=random.randint(0, 59),
                    seconds=random.randint(0, 59),
                )
                
                # Generate message
                message = self._generate_message(token_symbol, price_at_signal, sentiment, roi)
                
                # Confidence score (higher for successful signals on average)
                if success:
                    confidence = min(1.0, max(0.3, random.gauss(0.7, 0.15)))
                else:
                    confidence = min(1.0, max(0.1, random.gauss(0.45, 0.2)))
                
                # Random tags
                num_tags = random.randint(1, 4)
                tags = random.sample(self.TAGS_POOL, num_tags)
                
                signal = Signal(
                    channel_id=channel_id,
                    channel_name=channel_name,
                    token_symbol=token_symbol,
                    token_name=token_name,
                    price_at_signal=price_at_signal,
                    current_price=current_price,
                    sentiment=sentiment,
                    message_text=message,
                    confidence_score=round(confidence, 3),
                    timestamp=timestamp,
                    success=success,
                    roi_percent=round(roi, 2),
                    tags=tags,
                )
                signals_batch.append(signal)
            
            # Bulk insert batch
            session.add_all(signals_batch)
            await session.flush()
            
            total_generated += batch_count
            progress = (total_generated / self.count) * 100
            print(f"  Progress: {total_generated:,}/{self.count:,} ({progress:.1f}%)")
        
        return total_generated
    
    def _generate_message(self, token: str, price: float, sentiment: str, roi: float) -> str:
        """Generate a realistic signal message."""
        if sentiment == "BULLISH":
            template = random.choice(self.BULLISH_TEMPLATES)
            target = abs(roi) if roi > 0 else random.randint(10, 50)
        elif sentiment == "BEARISH":
            template = random.choice(self.BEARISH_TEMPLATES)
            target = abs(roi)
        else:
            template = random.choice(self.NEUTRAL_TEMPLATES)
            target = 0
        
        return template.format(token=token, price=price, target=int(target))
    
    async def _update_statistics(self, session):
        """Update channel and token statistics based on generated signals."""
        from sqlalchemy import func, select
        
        # Update channel statistics
        for channel in self.channels:
            result = await session.execute(
                select(
                    func.count(Signal.id).label("total"),
                    func.avg(Signal.roi_percent).label("avg_roi"),
                    func.sum(func.cast(Signal.success, Integer)).label("success_count"),
                )
                .where(Signal.channel_id == channel.id)
            )
            stats = result.first()
            
            if stats and stats.total > 0:
                channel.total_signals = stats.total
                channel.avg_roi = round(stats.avg_roi or 0, 2)
                channel.success_rate = round((stats.success_count or 0) / stats.total * 100, 2)
        
        # Update token statistics
        for token in self.tokens:
            result = await session.execute(
                select(
                    func.count(Signal.id).label("total"),
                    func.avg(Signal.roi_percent).label("avg_roi"),
                    func.sum(func.cast(Signal.success, Integer)).label("success_count"),
                    func.max(Signal.timestamp).label("last_signal"),
                )
                .where(Signal.token_symbol == token.symbol)
            )
            stats = result.first()
            
            if stats and stats.total > 0:
                token.total_signals = stats.total
                token.avg_roi = round(stats.avg_roi or 0, 2)
                token.success_rate = round((stats.success_count or 0) / stats.total * 100, 2)
                token.last_signal_at = stats.last_signal


# Import Integer for cast
from sqlalchemy import Integer


async def main():
    """Run synthetic data generation."""
    generator = SyntheticDataGenerator(count=settings.synthetic_data_count)
    results = await generator.generate_all()
    
    print("\n" + "="*50)
    print("📊 SYNTHETIC DATA GENERATION COMPLETE")
    print("="*50)
    print(f"  Channels created: {results['channels']}")
    print(f"  Tokens created: {results['tokens']}")
    print(f"  Signals created: {results['signals']:,}")
    print("="*50)


if __name__ == "__main__":
    asyncio.run(main())
