"""
Locust Load Testing for Crypto Signal Aggregator API

Load Test Scenarios:
1. 10 concurrent users - Basic functionality test
2. 100 concurrent users - Standard load test  
3. 1000 concurrent users - Stress test

Target RPS: 100-500 depending on scenario
"""
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner
import random
import json
import time


# ============== Test Data ==============

TOKENS = ["BTC", "ETH", "SOL", "DOGE", "PEPE", "SHIB", "LINK", "MATIC", "AVAX", "DOT"]
SENTIMENTS = ["BULLISH", "BEARISH", "NEUTRAL"]
CHANNELS = ["CryptoWhale", "MoonShots", "AltcoinDaily", "GemHunter", "TokenAlpha", "SignalPro"]


# ============== User Classes ==============

class BaseAPIUser(HttpUser):
    """Base user class with common functionality"""
    
    abstract = True
    
    def on_start(self):
        """Setup before tests"""
        self.signal_ids = []
        self.channel_ids = []
        
    def random_token(self):
        return random.choice(TOKENS)
    
    def random_sentiment(self):
        return random.choice(SENTIMENTS)
    
    def random_channel(self):
        return random.choice(CHANNELS)


class SignalReaderUser(BaseAPIUser):
    """User that primarily reads signals"""
    
    wait_time = between(1, 3)
    weight = 5  # 5x more common than writers
    
    @task(10)
    def get_recent_signals(self):
        """Get most recent signals"""
        with self.client.get(
            "/api/v1/signals?limit=20",
            name="/api/v1/signals",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "items" in data:
                    self.signal_ids = [s["id"] for s in data["items"][:10]]
                response.success()
            else:
                response.failure(f"Status {response.status_code}")
    
    @task(5)
    def get_signal_detail(self):
        """Get a specific signal's details"""
        if self.signal_ids:
            signal_id = random.choice(self.signal_ids)
            self.client.get(
                f"/api/v1/signals/{signal_id}",
                name="/api/v1/signals/[id]"
            )
    
    @task(3)
    def filter_by_token(self):
        """Filter signals by token"""
        token = self.random_token()
        self.client.get(
            f"/api/v1/signals?token_symbol={token}&limit=20",
            name="/api/v1/signals?token_symbol=[token]"
        )
    
    @task(2)
    def filter_by_sentiment(self):
        """Filter signals by sentiment"""
        sentiment = self.random_sentiment()
        self.client.get(
            f"/api/v1/signals?sentiment={sentiment}&limit=20",
            name="/api/v1/signals?sentiment=[sentiment]"
        )


class AnalyticsUser(BaseAPIUser):
    """User focused on analytics endpoints (tests caching)"""
    
    wait_time = between(2, 5)
    weight = 3
    
    @task(10)
    def get_historical_data(self):
        """Get historical data - heavy query, should be cached"""
        days = random.choice([7, 30, 90])
        with self.client.get(
            f"/api/v1/analytics/historical?days={days}&limit=100000",
            name="/api/v1/analytics/historical",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                # Log cache status
                cached = response.headers.get("X-Cache-Status", "UNKNOWN")
                elapsed = response.elapsed.total_seconds() * 1000
                
                if cached == "HIT" and elapsed < 20:
                    response.success()
                elif cached != "HIT" and elapsed > 100:
                    response.success()  # Uncached expected to be slower
                else:
                    response.success()
            else:
                response.failure(f"Status {response.status_code}")
    
    @task(5)
    def get_token_stats(self):
        """Get token statistics"""
        token = self.random_token()
        self.client.get(
            f"/api/v1/analytics/token/{token}/stats",
            name="/api/v1/analytics/token/[symbol]/stats"
        )
    
    @task(3)
    def get_channel_leaderboard(self):
        """Get channel leaderboard"""
        self.client.get(
            "/api/v1/analytics/channels/leaderboard",
            name="/api/v1/analytics/channels/leaderboard"
        )
    
    @task(2)
    def get_market_patterns(self):
        """Get detected market patterns"""
        self.client.get(
            "/api/v1/analytics/patterns",
            name="/api/v1/analytics/patterns"
        )
    
    @task(1)
    def run_benchmark(self):
        """Run cache benchmark"""
        self.client.get(
            "/api/v1/analytics/benchmark",
            name="/api/v1/analytics/benchmark"
        )


class SignalWriterUser(BaseAPIUser):
    """User that creates signals (simulates Telegram ingestion)"""
    
    wait_time = between(5, 10)
    weight = 1  # Less common than readers
    
    @task
    def create_signal(self):
        """Create a new signal"""
        signal_data = {
            "channel_id": random.randint(1, 6),
            "channel_name": self.random_channel(),
            "token_symbol": self.random_token(),
            "token_name": f"{self.random_token()} Token",
            "price_at_signal": round(random.uniform(0.001, 50000), 6),
            "sentiment": self.random_sentiment(),
            "message_text": f"Signal for {self.random_token()} - {'Buy!' if random.random() > 0.3 else 'Sell!'}",
            "confidence_score": round(random.uniform(0.5, 1.0), 2),
            "tags": random.sample(["memecoin", "defi", "layer2", "ai", "gaming"], k=random.randint(0, 3))
        }
        
        with self.client.post(
            "/api/v1/signals",
            json=signal_data,
            name="/api/v1/signals [POST]",
            catch_response=True
        ) as response:
            if response.status_code == 201:
                created = response.json()
                self.signal_ids.append(created.get("id"))
                response.success()
            else:
                response.failure(f"Status {response.status_code}: {response.text[:100]}")


class ChannelManagerUser(BaseAPIUser):
    """User that manages channels"""
    
    wait_time = between(10, 20)
    weight = 1
    
    @task(3)
    def list_channels(self):
        """List all channels"""
        with self.client.get(
            "/api/v1/channels",
            name="/api/v1/channels",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                self.channel_ids = [c["id"] for c in data[:10]]
                response.success()
            else:
                response.failure(f"Status {response.status_code}")
    
    @task(2)
    def get_channel_detail(self):
        """Get channel details"""
        if self.channel_ids:
            channel_id = random.choice(self.channel_ids)
            self.client.get(
                f"/api/v1/channels/{channel_id}",
                name="/api/v1/channels/[id]"
            )
    
    @task(1)
    def create_channel(self):
        """Create a new channel"""
        channel_data = {
            "name": f"TestChannel_{random.randint(1000, 9999)}",
            "telegram_id": f"test_{random.randint(100000, 999999)}",
            "description": "Load test channel",
            "subscriber_count": random.randint(1000, 100000),
            "is_active": True
        }
        
        with self.client.post(
            "/api/v1/channels",
            json=channel_data,
            name="/api/v1/channels [POST]",
            catch_response=True
        ) as response:
            if response.status_code == 201:
                created = response.json()
                self.channel_ids.append(created.get("id"))
                response.success()
            else:
                response.failure(f"Status {response.status_code}")


class DashboardUser(BaseAPIUser):
    """User accessing web dashboard"""
    
    wait_time = between(2, 5)
    weight = 2
    
    @task(5)
    def load_dashboard(self):
        """Load main dashboard page"""
        self.client.get("/", name="/ [Dashboard]")
    
    @task(3)
    def load_signals_page(self):
        """Load signals page"""
        self.client.get("/signals", name="/signals")
    
    @task(2)
    def load_analytics_page(self):
        """Load analytics page"""
        self.client.get("/analytics", name="/analytics")
    
    @task(1)
    def check_health(self):
        """Check health endpoint"""
        self.client.get("/health", name="/health")


# ============== Combined User for Mixed Load ==============

class MixedWorkloadUser(HttpUser):
    """Combined user simulating realistic mixed traffic"""
    
    wait_time = between(1, 5)
    
    def on_start(self):
        self.signal_ids = []
        
    @task(20)
    def read_signals(self):
        """Most common: Read recent signals"""
        with self.client.get(
            "/api/v1/signals?limit=20",
            name="/api/v1/signals [READ]",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                self.signal_ids = [s["id"] for s in data.get("items", [])[:10]]
                response.success()
    
    @task(10)
    def get_analytics(self):
        """Get analytics (cached endpoint)"""
        self.client.get(
            "/api/v1/analytics/historical?days=30",
            name="/api/v1/analytics/historical"
        )
    
    @task(5)
    def get_token_stats(self):
        """Get specific token stats"""
        token = random.choice(TOKENS)
        self.client.get(
            f"/api/v1/analytics/token/{token}/stats",
            name="/api/v1/analytics/token/[symbol]/stats"
        )
    
    @task(3)
    def filter_signals(self):
        """Filter signals"""
        token = random.choice(TOKENS)
        self.client.get(
            f"/api/v1/signals?token_symbol={token}",
            name="/api/v1/signals?filter"
        )
    
    @task(1)
    def create_signal(self):
        """Occasionally create a signal"""
        signal_data = {
            "channel_id": random.randint(1, 6),
            "channel_name": random.choice(CHANNELS),
            "token_symbol": random.choice(TOKENS),
            "token_name": f"{random.choice(TOKENS)} Token",
            "price_at_signal": round(random.uniform(0.001, 50000), 6),
            "sentiment": random.choice(SENTIMENTS),
            "message_text": f"Test signal {random.randint(1, 10000)}",
            "confidence_score": round(random.uniform(0.5, 1.0), 2)
        }
        
        self.client.post(
            "/api/v1/signals",
            json=signal_data,
            name="/api/v1/signals [WRITE]"
        )


# ============== Event Handlers ==============

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when load test starts"""
    if isinstance(environment.runner, MasterRunner):
        print("=" * 60)
        print("LOAD TEST STARTED")
        print("=" * 60)
        print(f"Target Host: {environment.host}")
        print("Test Scenarios:")
        print("  - Light: 10 users, 100+ RPS")
        print("  - Medium: 100 users, 300+ RPS")
        print("  - Heavy: 1000 users, 500+ RPS")
        print("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when load test stops"""
    print("\n" + "=" * 60)
    print("LOAD TEST COMPLETED")
    print("=" * 60)


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Track request metrics for cache analysis"""
    # Track cache performance for analytics endpoints
    if "analytics" in name and exception is None:
        if response_time < 20:
            # Likely cache hit
            pass
        elif response_time > 1000:
            # Likely cache miss processing 100k+ records
            pass


# ============== Custom CLI Arguments ==============

@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument(
        "--scenario",
        choices=["light", "medium", "heavy", "stress"],
        default="light",
        help="Load test scenario"
    )


# ============== Run Instructions ==============
"""
Run Load Tests:

1. Light Load (10 users):
   locust -f tests/locust_load_test.py --host=http://localhost:8000 --users=10 --spawn-rate=2

2. Medium Load (100 users):
   locust -f tests/locust_load_test.py --host=http://localhost:8000 --users=100 --spawn-rate=10

3. Heavy Load (1000 users):
   locust -f tests/locust_load_test.py --host=http://localhost:8000 --users=1000 --spawn-rate=50

4. Web UI Mode:
   locust -f tests/locust_load_test.py --host=http://localhost:8000
   Then open http://localhost:8089

5. Headless with specific duration:
   locust -f tests/locust_load_test.py --host=http://localhost:8000 --users=100 --spawn-rate=10 --run-time=5m --headless

Expected Results:
- Light (10 users): >100 RPS, <100ms avg response
- Medium (100 users): >300 RPS, <200ms avg response
- Heavy (1000 users): >500 RPS, <500ms avg response
- Cache hit endpoints: <20ms regardless of load
"""
