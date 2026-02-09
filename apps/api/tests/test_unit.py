"""
Unit Tests for the Crypto Signal Aggregator API
Target: 70%+ code coverage
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.database import Base
from app.models.signal import Signal
from app.models.channel import Channel
from app.models.token import Token
from app.schemas.signal import SignalCreate, SignalResponse, Sentiment
from app.schemas.channel import ChannelCreate
from app.schemas.analytics import HistoricalDataResponse
from app.services.signal_parser import SignalParser
from app.services.synthetic_data import SyntheticDataGenerator
from app.services.analytics_service import AnalyticsService
from app.utils.validators import validate_token_symbol, validate_channel_name, validate_price
from app.utils.helpers import (
    calculate_roi, 
    calculate_success_rate, 
    calculate_average_roi,
    format_price,
    truncate_text
)


# ============== Fixtures ==============

@pytest.fixture
def settings():
    """Test settings with SQLite"""
    return Settings(
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        REDIS_URL="redis://localhost:6379/1",
        TELEGRAM_MOCK_MODE=True,
        SECRET_KEY="test-secret-key"
    )


@pytest.fixture
async def db_engine(settings):
    """Create test database engine"""
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    """Create test database session"""
    async_session_maker = sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session_maker() as session:
        yield session


@pytest.fixture
def signal_parser():
    """Create signal parser instance"""
    return SignalParser()


@pytest.fixture
def synthetic_generator():
    """Create synthetic data generator instance"""
    return SyntheticDataGenerator()


# ============== Signal Parser Tests ==============

class TestSignalParser:
    """Tests for signal parsing functionality"""
    
    def test_parse_bullish_message(self, signal_parser):
        """Test parsing a bullish signal message"""
        message = "🚀 BTC to the moon! Buy now at $45,000. Strong support!"
        result = signal_parser.parse_message(message)
        
        assert result.sentiment == Sentiment.BULLISH
        assert "BTC" in result.tokens
        
    def test_parse_bearish_message(self, signal_parser):
        """Test parsing a bearish signal message"""
        message = "⚠️ ETH looking weak. Sell positions. Price dropping to $2,000."
        result = signal_parser.parse_message(message)
        
        assert result.sentiment == Sentiment.BEARISH
        
    def test_parse_neutral_message(self, signal_parser):
        """Test parsing a neutral signal message"""
        message = "SOL trading sideways. Watch for breakout."
        result = signal_parser.parse_message(message)
        
        assert result.sentiment == Sentiment.NEUTRAL
        
    def test_extract_token_symbols(self, signal_parser):
        """Test token symbol extraction"""
        message = "Buy $BTC and $ETH. Also looking at DOGE and PEPE."
        tokens = signal_parser.extract_tokens(message)
        
        assert "BTC" in tokens
        assert "ETH" in tokens
        
    def test_extract_price(self, signal_parser):
        """Test price extraction"""
        message = "BTC at $45,123.45 is a great entry."
        price = signal_parser.extract_price(message)
        
        assert price is not None
        assert price == pytest.approx(45123.45, rel=0.01)
        
    def test_extract_price_with_K_suffix(self, signal_parser):
        """Test price extraction with K suffix"""
        message = "Entry at 45K, target 50K"
        price = signal_parser.extract_price(message)
        
        assert price is not None
        assert price == pytest.approx(45000, rel=0.01)
        
    def test_calculate_confidence(self, signal_parser):
        """Test confidence score calculation"""
        # High confidence message with multiple indicators
        message = "🚀🚀🚀 BTC MASSIVE PUMP incoming! Buy NOW! To the MOON! 100x potential!"
        result = signal_parser.parse_message(message)
        
        assert result.confidence >= 0.5
        
    def test_extract_tags(self, signal_parser):
        """Test tag extraction"""
        message = "#crypto #memecoin Buy PEPE now! #100x"
        tags = signal_parser.extract_tags(message)
        
        assert "crypto" in tags or len(tags) > 0


# ============== Validators Tests ==============

class TestValidators:
    """Tests for validation functions"""
    
    def test_validate_token_symbol_valid(self):
        """Test valid token symbols"""
        assert validate_token_symbol("BTC") == "BTC"
        assert validate_token_symbol("eth") == "ETH"
        assert validate_token_symbol("PEPE") == "PEPE"
        
    def test_validate_token_symbol_invalid(self):
        """Test invalid token symbols"""
        with pytest.raises(ValueError):
            validate_token_symbol("")
        with pytest.raises(ValueError):
            validate_token_symbol("A" * 20)
        with pytest.raises(ValueError):
            validate_token_symbol("123")
            
    def test_validate_channel_name_valid(self):
        """Test valid channel names"""
        assert validate_channel_name("CryptoWhale") is not None
        assert validate_channel_name("Trading_Signals_123") is not None
        
    def test_validate_channel_name_invalid(self):
        """Test invalid channel names"""
        with pytest.raises(ValueError):
            validate_channel_name("")
        with pytest.raises(ValueError):
            validate_channel_name("ab")  # Too short
            
    def test_validate_price_valid(self):
        """Test valid prices"""
        assert validate_price(100.00) == 100.00
        assert validate_price(0.000001) == 0.000001
        
    def test_validate_price_invalid(self):
        """Test invalid prices"""
        with pytest.raises(ValueError):
            validate_price(-100)
        with pytest.raises(ValueError):
            validate_price(0)


# ============== Helpers Tests ==============

class TestHelpers:
    """Tests for helper functions"""
    
    def test_calculate_roi_positive(self):
        """Test positive ROI calculation"""
        roi = calculate_roi(100, 150)
        assert roi == 50.0
        
    def test_calculate_roi_negative(self):
        """Test negative ROI calculation"""
        roi = calculate_roi(100, 75)
        assert roi == -25.0
        
    def test_calculate_roi_zero_entry(self):
        """Test ROI with zero entry price"""
        roi = calculate_roi(0, 100)
        assert roi == 0.0
        
    def test_calculate_success_rate(self):
        """Test success rate calculation"""
        rate = calculate_success_rate(70, 100)
        assert rate == 70.0
        
    def test_calculate_success_rate_zero_total(self):
        """Test success rate with zero total"""
        rate = calculate_success_rate(0, 0)
        assert rate == 0.0
        
    def test_calculate_average_roi(self):
        """Test average ROI calculation"""
        rois = [10.0, 20.0, -5.0, 15.0]
        avg = calculate_average_roi(rois)
        assert avg == 10.0
        
    def test_calculate_average_roi_empty(self):
        """Test average ROI with empty list"""
        avg = calculate_average_roi([])
        assert avg == 0.0
        
    def test_format_price_large(self):
        """Test formatting large prices"""
        formatted = format_price(45000.50)
        assert "$" in formatted
        assert "45" in formatted
        
    def test_format_price_small(self):
        """Test formatting small prices"""
        formatted = format_price(0.00001234)
        assert "$" in formatted
        
    def test_truncate_text(self):
        """Test text truncation"""
        text = "This is a very long message that should be truncated"
        truncated = truncate_text(text, 20)
        assert len(truncated) <= 23  # 20 + "..."
        assert truncated.endswith("...")
        
    def test_truncate_text_short(self):
        """Test truncation of short text"""
        text = "Short"
        truncated = truncate_text(text, 20)
        assert truncated == text


# ============== Synthetic Data Generator Tests ==============

class TestSyntheticDataGenerator:
    """Tests for synthetic data generation"""
    
    def test_generate_signals_count(self, synthetic_generator):
        """Test generating specific number of signals"""
        signals = synthetic_generator.generate_signals(count=100)
        assert len(signals) == 100
        
    def test_generate_signals_sentiment_distribution(self, synthetic_generator):
        """Test sentiment distribution in generated signals"""
        signals = synthetic_generator.generate_signals(count=1000)
        
        bullish = sum(1 for s in signals if s["sentiment"] == "BULLISH")
        bearish = sum(1 for s in signals if s["sentiment"] == "BEARISH")
        neutral = sum(1 for s in signals if s["sentiment"] == "NEUTRAL")
        
        # Should roughly match 60/10/30 distribution
        assert bullish > bearish
        assert bullish > neutral
        
    def test_generate_signals_roi_range(self, synthetic_generator):
        """Test ROI values are within reasonable range"""
        signals = synthetic_generator.generate_signals(count=100)
        
        for signal in signals:
            if signal["roi_percent"] is not None:
                assert -100 <= signal["roi_percent"] <= 1000
                
    def test_generate_channels(self, synthetic_generator):
        """Test channel generation"""
        channels = synthetic_generator.generate_channels()
        assert len(channels) == 6  # Default 6 channels
        
        for channel in channels:
            assert "name" in channel
            assert "description" in channel
            
    def test_generate_tokens(self, synthetic_generator):
        """Test token generation"""
        tokens = synthetic_generator.generate_tokens()
        assert len(tokens) == 10  # Default 10 tokens
        
        for token in tokens:
            assert "symbol" in token
            assert "name" in token
            
    def test_generate_large_dataset(self, synthetic_generator):
        """Test generating large dataset (100k+)"""
        # Generate fewer for test speed, but verify structure
        signals = synthetic_generator.generate_signals(count=1000)
        
        assert len(signals) == 1000
        assert all("token_symbol" in s for s in signals)
        assert all("channel_name" in s for s in signals)
        assert all("timestamp" in s for s in signals)


# ============== Model Tests ==============

class TestModels:
    """Tests for SQLAlchemy models"""
    
    @pytest.mark.asyncio
    async def test_create_channel(self, db_session):
        """Test creating a channel"""
        channel = Channel(
            name="TestChannel",
            telegram_id="test_123",
            description="Test description",
            subscriber_count=1000,
            is_active=True
        )
        
        db_session.add(channel)
        await db_session.commit()
        await db_session.refresh(channel)
        
        assert channel.id is not None
        assert channel.name == "TestChannel"
        
    @pytest.mark.asyncio
    async def test_create_signal(self, db_session):
        """Test creating a signal"""
        # First create a channel
        channel = Channel(
            name="SignalChannel",
            telegram_id="signal_123",
            is_active=True
        )
        db_session.add(channel)
        await db_session.commit()
        
        # Now create signal
        signal = Signal(
            channel_id=channel.id,
            channel_name=channel.name,
            token_symbol="BTC",
            token_name="Bitcoin",
            price_at_signal=45000.00,
            sentiment="BULLISH",
            message_text="Buy BTC now!",
            confidence_score=0.85
        )
        
        db_session.add(signal)
        await db_session.commit()
        await db_session.refresh(signal)
        
        assert signal.id is not None
        assert signal.token_symbol == "BTC"
        assert signal.sentiment == "BULLISH"
        
    @pytest.mark.asyncio
    async def test_signal_channel_relationship(self, db_session):
        """Test signal-channel relationship"""
        channel = Channel(
            name="RelChannel",
            telegram_id="rel_123",
            is_active=True
        )
        db_session.add(channel)
        await db_session.commit()
        
        signal = Signal(
            channel_id=channel.id,
            channel_name=channel.name,
            token_symbol="ETH",
            token_name="Ethereum",
            price_at_signal=2500.00,
            sentiment="NEUTRAL"
        )
        
        db_session.add(signal)
        await db_session.commit()
        
        # Verify relationship
        assert signal.channel_id == channel.id


# ============== Schema Tests ==============

class TestSchemas:
    """Tests for Pydantic schemas"""
    
    def test_signal_create_valid(self):
        """Test creating a valid signal"""
        signal = SignalCreate(
            channel_id=1,
            channel_name="TestChannel",
            token_symbol="BTC",
            token_name="Bitcoin",
            price_at_signal=45000.00,
            sentiment=Sentiment.BULLISH,
            message_text="Buy BTC!",
            confidence_score=0.8
        )
        
        assert signal.token_symbol == "BTC"
        assert signal.sentiment == Sentiment.BULLISH
        
    def test_signal_create_invalid_confidence(self):
        """Test signal with invalid confidence score"""
        with pytest.raises(ValueError):
            SignalCreate(
                channel_id=1,
                channel_name="TestChannel",
                token_symbol="BTC",
                token_name="Bitcoin",
                price_at_signal=45000.00,
                sentiment=Sentiment.BULLISH,
                message_text="Buy BTC!",
                confidence_score=1.5  # Invalid: > 1.0
            )
            
    def test_channel_create_valid(self):
        """Test creating a valid channel"""
        channel = ChannelCreate(
            name="NewChannel",
            telegram_id="new_123",
            description="A new trading channel",
            subscriber_count=5000,
            is_active=True
        )
        
        assert channel.name == "NewChannel"
        assert channel.subscriber_count == 5000


# ============== Analytics Service Tests ==============

class TestAnalyticsService:
    """Tests for analytics service"""
    
    @pytest.mark.asyncio
    async def test_get_historical_summary(self, db_session):
        """Test historical data summary calculation"""
        # Add test signals
        for i in range(10):
            signal = Signal(
                channel_id=1,
                channel_name="TestChannel",
                token_symbol="BTC",
                token_name="Bitcoin",
                price_at_signal=45000.00 + i * 100,
                sentiment="BULLISH" if i % 2 == 0 else "BEARISH",
                message_text=f"Signal {i}",
                confidence_score=0.8,
                roi_percent=10.0 if i % 2 == 0 else -5.0,
                success=i % 2 == 0
            )
            db_session.add(signal)
        
        await db_session.commit()
        
        service = AnalyticsService(db_session)
        summary = await service.get_historical_summary(days=30)
        
        assert summary["total_count"] == 10
        assert "sentiment_distribution" in summary
        
    @pytest.mark.asyncio
    async def test_get_token_stats(self, db_session):
        """Test token statistics calculation"""
        # Add test signals for a specific token
        for i in range(5):
            signal = Signal(
                channel_id=1,
                channel_name="TestChannel",
                token_symbol="ETH",
                token_name="Ethereum",
                price_at_signal=2500.00,
                sentiment="BULLISH",
                message_text=f"ETH signal {i}",
                confidence_score=0.75,
                roi_percent=15.0,
                success=True
            )
            db_session.add(signal)
        
        await db_session.commit()
        
        service = AnalyticsService(db_session)
        stats = await service.get_token_stats("ETH")
        
        assert stats["total_signals"] == 5
        assert stats["token_symbol"] == "ETH"


# ============== Run tests ==============

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=app", "--cov-report=html"])
