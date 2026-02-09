"""
API Integration Tests for Crypto Signal Aggregator
Tests API endpoints with database and cache integration
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_session
from app.cache import init_cache
from app.config import get_settings


# ============== Test Configuration ==============

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_engine():
    """Create test database engine"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine):
    """Create test database session"""
    async_session_maker = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session_maker() as session:
        yield session


@pytest.fixture
async def override_db(test_session):
    """Override database dependency"""
    async def _get_test_db():
        yield test_session
    
    app.dependency_overrides[get_session] = _get_test_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def client(override_db):
    """Create async test client"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ============== Health Check Tests ==============

class TestHealthEndpoints:
    """Tests for health check endpoints"""
    
    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """Test health check endpoint"""
        response = await client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        
    @pytest.mark.asyncio
    async def test_root_redirect(self, client):
        """Test root redirects to dashboard or returns info"""
        response = await client.get("/", follow_redirects=False)
        
        # Should either return 200 with info or redirect
        assert response.status_code in [200, 302, 307]


# ============== Signals API Tests ==============

class TestSignalsAPI:
    """Tests for signals endpoints"""
    
    @pytest.mark.asyncio
    async def test_get_signals_empty(self, client):
        """Test getting signals when database is empty"""
        response = await client.get("/api/v1/signals")
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == 0
        
    @pytest.mark.asyncio
    async def test_create_signal(self, client):
        """Test creating a new signal"""
        signal_data = {
            "channel_id": 1,
            "channel_name": "TestChannel",
            "token_symbol": "BTC",
            "token_name": "Bitcoin",
            "price_at_signal": 45000.00,
            "sentiment": "BULLISH",
            "message_text": "Buy BTC now!",
            "confidence_score": 0.85
        }
        
        response = await client.post("/api/v1/signals", json=signal_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["token_symbol"] == "BTC"
        assert data["sentiment"] == "BULLISH"
        assert data["id"] is not None
        
    @pytest.mark.asyncio
    async def test_get_signal_by_id(self, client):
        """Test getting a specific signal by ID"""
        # First create a signal
        signal_data = {
            "channel_id": 1,
            "channel_name": "TestChannel",
            "token_symbol": "ETH",
            "token_name": "Ethereum",
            "price_at_signal": 2500.00,
            "sentiment": "NEUTRAL",
            "message_text": "Watch ETH carefully",
            "confidence_score": 0.7
        }
        
        create_response = await client.post("/api/v1/signals", json=signal_data)
        created = create_response.json()
        signal_id = created["id"]
        
        # Now get it
        response = await client.get(f"/api/v1/signals/{signal_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == signal_id
        assert data["token_symbol"] == "ETH"
        
    @pytest.mark.asyncio
    async def test_get_signal_not_found(self, client):
        """Test getting non-existent signal"""
        response = await client.get("/api/v1/signals/99999")
        
        assert response.status_code == 404
        
    @pytest.mark.asyncio
    async def test_get_signals_with_filters(self, client):
        """Test getting signals with filters"""
        # Create multiple signals
        for token in ["BTC", "ETH", "SOL"]:
            signal_data = {
                "channel_id": 1,
                "channel_name": "TestChannel",
                "token_symbol": token,
                "token_name": f"{token} Token",
                "price_at_signal": 1000.00,
                "sentiment": "BULLISH",
                "message_text": f"Buy {token}!",
                "confidence_score": 0.8
            }
            await client.post("/api/v1/signals", json=signal_data)
        
        # Filter by token
        response = await client.get("/api/v1/signals?token_symbol=BTC")
        
        assert response.status_code == 200
        data = response.json()
        assert all(s["token_symbol"] == "BTC" for s in data["items"])
        
    @pytest.mark.asyncio
    async def test_get_signals_pagination(self, client):
        """Test signals pagination"""
        # Create 25 signals
        for i in range(25):
            signal_data = {
                "channel_id": 1,
                "channel_name": "TestChannel",
                "token_symbol": "BTC",
                "token_name": "Bitcoin",
                "price_at_signal": 45000.00 + i,
                "sentiment": "BULLISH",
                "message_text": f"Signal {i}",
                "confidence_score": 0.8
            }
            await client.post("/api/v1/signals", json=signal_data)
        
        # Get first page
        response = await client.get("/api/v1/signals?limit=10&offset=0")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 10
        assert data["total"] >= 25


# ============== Channels API Tests ==============

class TestChannelsAPI:
    """Tests for channels endpoints"""
    
    @pytest.mark.asyncio
    async def test_get_channels_empty(self, client):
        """Test getting channels when database is empty"""
        response = await client.get("/api/v1/channels")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
    @pytest.mark.asyncio
    async def test_create_channel(self, client):
        """Test creating a new channel"""
        channel_data = {
            "name": "CryptoAlpha",
            "telegram_id": "crypto_alpha_123",
            "description": "Premium crypto signals",
            "subscriber_count": 50000,
            "is_active": True
        }
        
        response = await client.post("/api/v1/channels", json=channel_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "CryptoAlpha"
        assert data["subscriber_count"] == 50000
        
    @pytest.mark.asyncio
    async def test_get_channel_by_id(self, client):
        """Test getting a specific channel"""
        # First create a channel
        channel_data = {
            "name": "SignalPro",
            "telegram_id": "signal_pro_456",
            "description": "Pro trading signals",
            "subscriber_count": 25000,
            "is_active": True
        }
        
        create_response = await client.post("/api/v1/channels", json=channel_data)
        created = create_response.json()
        channel_id = created["id"]
        
        # Get it
        response = await client.get(f"/api/v1/channels/{channel_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == channel_id
        assert data["name"] == "SignalPro"


# ============== Analytics API Tests ==============

class TestAnalyticsAPI:
    """Tests for analytics endpoints"""
    
    @pytest.mark.asyncio
    async def test_get_historical_data(self, client):
        """Test historical data endpoint"""
        response = await client.get("/api/v1/analytics/historical?days=30")
        
        assert response.status_code == 200
        data = response.json()
        assert "signals" in data
        assert "summary" in data
        assert "total_count" in data
        
    @pytest.mark.asyncio
    async def test_get_token_stats(self, client):
        """Test token stats endpoint"""
        # First create some signals for a token
        for i in range(5):
            signal_data = {
                "channel_id": 1,
                "channel_name": "TestChannel",
                "token_symbol": "DOGE",
                "token_name": "Dogecoin",
                "price_at_signal": 0.08 + i * 0.01,
                "sentiment": "BULLISH",
                "message_text": f"DOGE signal {i}",
                "confidence_score": 0.75
            }
            await client.post("/api/v1/signals", json=signal_data)
        
        response = await client.get("/api/v1/analytics/token/DOGE/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["token_symbol"] == "DOGE"
        assert data["total_signals"] >= 5
        
    @pytest.mark.asyncio
    async def test_get_channel_leaderboard(self, client):
        """Test channel leaderboard endpoint"""
        response = await client.get("/api/v1/analytics/channels/leaderboard")
        
        assert response.status_code == 200
        data = response.json()
        assert "leaderboard" in data
        
    @pytest.mark.asyncio
    async def test_get_market_patterns(self, client):
        """Test market patterns endpoint"""
        response = await client.get("/api/v1/analytics/patterns")
        
        assert response.status_code == 200
        data = response.json()
        assert "market_phase" in data
        assert "dominant_sentiment" in data
        
    @pytest.mark.asyncio
    async def test_get_benchmark(self, client):
        """Test cache benchmark endpoint"""
        response = await client.get("/api/v1/analytics/benchmark")
        
        assert response.status_code == 200
        data = response.json()
        assert "benchmark_results" in data


# ============== Error Handling Tests ==============

class TestErrorHandling:
    """Tests for error handling"""
    
    @pytest.mark.asyncio
    async def test_invalid_signal_data(self, client):
        """Test creating signal with invalid data"""
        signal_data = {
            "channel_id": "invalid",  # Should be int
            "token_symbol": "",  # Should not be empty
        }
        
        response = await client.post("/api/v1/signals", json=signal_data)
        
        assert response.status_code == 422  # Validation error
        
    @pytest.mark.asyncio
    async def test_invalid_pagination(self, client):
        """Test invalid pagination parameters"""
        response = await client.get("/api/v1/signals?limit=-1")
        
        # Should either reject or use default
        assert response.status_code in [200, 422]
        
    @pytest.mark.asyncio
    async def test_invalid_sentiment_filter(self, client):
        """Test invalid sentiment filter"""
        response = await client.get("/api/v1/signals?sentiment=INVALID")
        
        # Should either reject or ignore invalid filter
        assert response.status_code in [200, 400, 422]


# ============== WebSocket Tests ==============

class TestWebSocket:
    """Tests for WebSocket endpoints"""
    
    @pytest.mark.asyncio
    async def test_websocket_connect(self, client):
        """Test WebSocket connection"""
        # Note: Testing WebSocket requires special handling
        # This is a placeholder for WebSocket testing
        pass


# ============== Rate Limiting Tests ==============

class TestRateLimiting:
    """Tests for rate limiting (if implemented)"""
    
    @pytest.mark.asyncio
    async def test_rate_limit_not_exceeded(self, client):
        """Test requests within rate limit"""
        for _ in range(10):
            response = await client.get("/api/v1/signals")
            # Should all succeed
            assert response.status_code == 200


# ============== Run tests ==============

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
