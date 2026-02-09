"""
Signal parser for extracting crypto signals from Telegram messages.

Event-driven extraction pipeline:
  1. Every incoming message is scanned for contract addresses, token symbols,
     DEX URLs, price data, and sentiment keywords / emojis.
  2. If ANY of (contract address, token symbol, DEX URL) is found the message
     is considered "detected" and will be persisted + pushed in real-time.
  3. Messages that ALSO include price data are additionally classified as
     "full_signal" and carry higher confidence.
"""
import re
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime


class SignalParser:
    """Regex-based crypto message scanner."""

    # ── Contract address patterns ──────────────────────────────────

    # EVM: 0x + 40 hex chars
    EVM_ADDRESS_PATTERN = re.compile(r'\b(0x[a-fA-F0-9]{40})\b')

    # Solana base-58 (32-44 chars, no 0/O/I/l) — additional heuristic
    SOLANA_ADDRESS_PATTERN = re.compile(r'\b([1-9A-HJ-NP-Za-km-z]{32,44})\b')

    # DEX / scanner URLs that embed a contract address
    DEX_URL_PATTERN = re.compile(
        r'(?:dexscreener\.com|dextools\.io|birdeye\.so|geckoterminal\.com|'
        r'defined\.fi|pump\.fun|raydium\.io|solscan\.io|etherscan\.io|bscscan\.com|'
        r'basescan\.org|arbiscan\.io|polygonscan\.com)'
        r'[/\w\-]*?/?(0x[a-fA-F0-9]{40}|[1-9A-HJ-NP-Za-km-z]{32,44})',
        re.IGNORECASE,
    )

    # ── Token symbol patterns ──────────────────────────────────────

    # Explicit $SYMBOL or #SYMBOL
    CASHTAG_PATTERN = re.compile(r'[\$#]([A-Za-z]{2,12})\b')

    # Bare uppercase tickers (3-10 uppercase letters, word-bounded)
    BARE_TOKEN_PATTERN = re.compile(r'\b([A-Z]{2,10})\b')

    # ── Chain identifiers ─────────────────────────────────────────

    CHAIN_PATTERN = re.compile(
        r'\b(ethereum|eth\s+chain|bsc|bnb\s*chain|polygon|matic|arbitrum|arb|'
        r'optimism|op\s+chain|avalanche|avax|base\s+chain|base|solana|sol\s+chain|'
        r'fantom|ftm|cronos|cro|gnosis|linea|zksync|scroll|blast|mantle|'
        r'sui\s+chain|aptos|ton|tron)\b',
        re.IGNORECASE,
    )

    CHAIN_MAP = {
        'ethereum': 'eth', 'eth chain': 'eth', 'eth': 'eth',
        'bsc': 'bsc', 'bnb chain': 'bsc', 'bnbchain': 'bsc',
        'polygon': 'polygon', 'matic': 'polygon',
        'arbitrum': 'arbitrum', 'arb': 'arbitrum',
        'optimism': 'optimism', 'op chain': 'optimism',
        'avalanche': 'avalanche', 'avax': 'avalanche',
        'base chain': 'base', 'base': 'base',
        'solana': 'solana', 'sol chain': 'solana',
        'fantom': 'fantom', 'ftm': 'fantom',
        'cronos': 'cronos', 'cro': 'cronos',
        'gnosis': 'gnosis', 'linea': 'linea',
        'zksync': 'zksync', 'scroll': 'scroll',
        'blast': 'blast', 'mantle': 'mantle',
        'sui chain': 'sui', 'aptos': 'aptos',
        'ton': 'ton', 'tron': 'tron',
    }

    # ── Price patterns ────────────────────────────────────────────

    PRICE_PATTERN = re.compile(
        r'\$\s*([\d,]+\.?\d*)\b'                       # $0.0012
        r'|(?:[\d,]+\.?\d*)\s*(?:usd|usdt|busd)\b',    # 0.0012 USDT
        re.IGNORECASE,
    )
    TARGET_PATTERN = re.compile(
        r'(?:tp\d?|target\d?|take\s*profit)[:\s]*\$?([\d,]+\.?\d*)', re.IGNORECASE,
    )
    STOP_LOSS_PATTERN = re.compile(
        r'(?:sl|stop\s*loss|stop)[:\s]*\$?([\d,]+\.?\d*)', re.IGNORECASE,
    )
    ENTRY_PATTERN = re.compile(
        r'(?:entry|buy\s*(?:at|zone|price)?|enter\s*at|current\s*price|@)[:\s]*\$?([\d,]+\.?\d*)',
        re.IGNORECASE,
    )
    MC_PATTERN = re.compile(
        r'(?:mc|market\s*cap|mcap)[:\s]*\$?([\d,.]+)\s*([kmb])?', re.IGNORECASE,
    )

    # ── Sentiment ─────────────────────────────────────────────────

    BULLISH_KEYWORDS = [
        'buy', 'long', 'bullish', 'moon', 'pump', 'rocket', 'breakout',
        'accumulate', 'accumulation', 'gem', 'alpha', 'ape', 'send it',
        'dip', 'oversold', 'undervalued', 'strong', 'bullrun', 'bull run',
        'bag', 'load up', 'early', 'easy', '100x', '1000x', 'lowcap',
        'low cap', 'micro cap', 'next', 'call', 'launch', 'stealth',
        'aping', 'safu', 'moonshot', 'hidden gem',
    ]
    BEARISH_KEYWORDS = [
        'sell', 'short', 'bearish', 'dump', 'crash', 'distribution',
        'overbought', 'overvalued', 'weak', 'exit', 'take profit',
        'warning', 'caution', 'risk', 'bear', 'drop', 'falling',
        'rug', 'rugpull', 'scam', 'honeypot', 'avoid', 'stay away',
    ]
    BULLISH_EMOJIS = ['🚀', '📈', '💎', '🔥', '⚡', '💰', '🌙', '✨', '💪', '🎯', '🟢', '✅']
    BEARISH_EMOJIS = ['📉', '🔴', '⚠️', '🐻', '💀', '🆘', '❌', '⬇️', '🩸', '☠️']

    # ── Known tokens (used for validation / fuzzy match) ──────────

    KNOWN_TOKENS = {
        'BTC', 'ETH', 'SOL', 'DOGE', 'PEPE', 'SHIB', 'LINK', 'MATIC',
        'AVAX', 'DOT', 'ADA', 'XRP', 'BNB', 'ATOM', 'UNI', 'AAVE',
        'LTC', 'FTM', 'NEAR', 'APT', 'ARB', 'OP', 'INJ', 'SUI',
        'WIF', 'BONK', 'JUP', 'WLD', 'TIA', 'SEI', 'PYTH', 'JTO',
        'ONDO', 'STRK', 'DYM', 'MANTA', 'PIXEL', 'AI', 'RNDR',
        'FET', 'AGIX', 'OCEAN', 'TAO', 'RENDER', 'GRT', 'FIL',
        'IMX', 'BLUR', 'MEME', 'FLOKI', 'LUNC', 'ORDI', 'SATS',
        'RUNE', 'STX', 'PENDLE', 'GMX', 'RDNT', 'CAKE', 'DYDX',
        'TON', 'NOT', 'DOGS', 'HMSTR', 'CATI', 'BOME', 'MEW',
        'POPCAT', 'MYRO', 'SAMO', 'RAY', 'ORCA', 'DRIFT', 'TENSOR',
        'TRUMP', 'MELANIA', 'SPX', 'MOG', 'BRETT', 'TOSHI', 'DEGEN',
    }

    # Common English words that look like tickers — always filtered
    _NOISE_WORDS = {
        'THE', 'AND', 'FOR', 'WITH', 'THIS', 'THAT', 'FROM', 'ARE',
        'WAS', 'BUT', 'HAS', 'HAD', 'NOT', 'ALL', 'CAN', 'HER',
        'WHO', 'OIL', 'DID', 'GET', 'LET', 'SAY', 'SHE', 'TOO',
        'USE', 'WAY', 'MAY', 'DAY', 'ANY', 'NEW', 'NOW', 'OLD',
        'SEE', 'TIME', 'VERY', 'WHEN', 'COME', 'MAKE', 'LIKE',
        'JUST', 'KNOW', 'TAKE', 'TEAM', 'GOOD', 'BEEN', 'CALL',
        'FIRST', 'LONG', 'DOWN', 'FIND', 'HERE', 'THING', 'MANY',
        'WELL', 'ONLY', 'TELL', 'ONE', 'OUR', 'OUT', 'ALSO',
        'BACK', 'AFTER', 'YEAR', 'THAN', 'MOST', 'THEM', 'KEEP',
        'EVEN', 'LEFT', 'BEST', 'NEXT', 'WILL', 'STILL', 'OWN',
        'LOOK', 'SAME', 'BEING', 'WORLD', 'INTO', 'DOES', 'DONT',
        'PART', 'HEAD', 'LIVE', 'HIGH', 'MUST', 'HOME', 'BIG',
        'ABOUT', 'EACH', 'SOME', 'THEY', 'WHAT', 'YOUR', 'OVER',
        'MUCH', 'THEN', 'THEM', 'THESE', 'TWO', 'HOW', 'OUR',
        'PRICE', 'BUY', 'SELL', 'HOLD', 'UPDATE', 'JOIN', 'FREE',
        'NFT', 'DEX', 'CEX', 'APE', 'GEM', 'CHART', 'PUMP', 'DIP',
        'ENTRY', 'EXIT', 'STOP', 'LOSS', 'PROFIT', 'COIN',
        'TOKEN', 'TRADE', 'JUST', 'NOW', 'NEW', 'TOP', 'LOW',
        'USD', 'USDT', 'USDC', 'BUSD', 'DAI',  # Stables aren't signals
        'URL', 'COM', 'ORG', 'NET', 'HTTP', 'HTTPS', 'WWW',
        'PIN', 'BOT', 'VIA', 'MSG', 'DM', 'CHAT', 'ADMIN', 'MOD',
    }

    # ══════════════════════════════════════════════════════════════
    #  PUBLIC API
    # ══════════════════════════════════════════════════════════════

    def parse_message(
        self, message: str, channel_name: str = "Unknown"
    ) -> Optional[Dict[str, Any]]:
        """
        Scan a message for ANY crypto-relevant content.

        Returns a detection dict if contract addresses, token symbols, or
        DEX URLs are found — even without price data.  Returns ``None``
        only when nothing interesting is detected.
        """
        if not message or len(message) < 5:
            return None

        # ── Step 1: Extract structured data ──────────────────────
        contract_addresses = self._extract_contract_addresses(message)
        dex_urls = self._extract_dex_urls(message)
        chain = self._detect_chain(message)
        tokens = self._extract_tokens(message)

        # Merge addresses found in DEX URLs
        for addr in dex_urls:
            if addr not in contract_addresses:
                contract_addresses.append(addr)

        # Nothing found → skip
        if not tokens and not contract_addresses:
            return None

        # ── Step 2: Price extraction ─────────────────────────────
        entry_price = self._extract_entry_price(message)
        target_price = self._extract_target_price(message)
        stop_loss = self._extract_stop_loss(message)
        market_cap = self._extract_market_cap(message)

        if entry_price is None:
            prices = self._extract_all_prices(message)
            if prices:
                entry_price = prices[0]

        # ── Step 3: Sentiment analysis ───────────────────────────
        sentiment, confidence = self._analyze_sentiment(message)

        # Boost confidence if we have hard data
        if contract_addresses:
            confidence = min(0.99, confidence + 0.15)
        if entry_price is not None:
            confidence = min(0.99, confidence + 0.10)

        # ── Step 4: Determine detection quality ──────────────────
        has_price = entry_price is not None
        has_contract = len(contract_addresses) > 0
        has_token = len(tokens) > 0

        if has_price and (has_token or has_contract):
            signal_type = "full_signal"
        elif has_contract:
            signal_type = "contract_detection"
        else:
            signal_type = "token_mention"

        # ── Step 5: Primary symbol ───────────────────────────────
        primary_token = tokens[0] if tokens else None
        if not primary_token and contract_addresses:
            addr = contract_addresses[0]
            primary_token = f"CA:{addr[:6]}…{addr[-4:]}"

        # ── Step 6: Tags ─────────────────────────────────────────
        tags = self._extract_tags(message)
        tags.append(signal_type)

        return {
            "token_symbol": primary_token,
            "token_name": self._get_token_name(primary_token) if primary_token else "Unknown",
            "price_at_signal": entry_price,
            "target_price": target_price,
            "stop_loss": stop_loss,
            "market_cap": market_cap,
            "sentiment": sentiment,
            "confidence_score": confidence,
            "message_text": message,
            "channel_name": channel_name,
            "signal_type": signal_type,       # full_signal | contract_detection | token_mention
            "tags": tags,
            "all_tokens_mentioned": tokens,
            "contract_addresses": contract_addresses,
            "chain": chain,
            "parsed_at": datetime.utcnow().isoformat(),
        }
    
    # ══════════════════════════════════════════════════════════════
    #  VALIDATION  — relaxed: any detection is valid
    # ══════════════════════════════════════════════════════════════

    def validate_signal(self, parsed_signal: Optional[Dict[str, Any]]) -> bool:
        """
        Validate if the parsed content constitutes a valid signal.
        
        Checks for:
        1. Contract addresses (High priority)
        2. Token symbols with price/sentiment (Medium priority)
        3. Simple token mentions (Low priority, but valid)
        """
        if not parsed_signal:
            return False

        # Check for essential components
        has_contract = bool(parsed_signal.get("contract_addresses"))
        has_token = bool(parsed_signal.get("token_symbol"))
        
        # Valid if we have either a contract OR a token symbol
        return has_contract or has_token

    def is_full_signal(self, parsed_signal: Optional[Dict[str, Any]]) -> bool:
        """Return True only when the detection also carries price data."""
        if not self.validate_signal(parsed_signal):
            return False
        price = parsed_signal.get("price_at_signal")
        return price is not None and price > 0

    # ══════════════════════════════════════════════════════════════
    #  PRIVATE HELPERS
    # ══════════════════════════════════════════════════════════════

    def _extract_contract_addresses(self, message: str) -> List[str]:
        """Extract EVM and Solana contract addresses."""
        addresses: List[str] = []

        # EVM (0x…)
        for addr in self.EVM_ADDRESS_PATTERN.findall(message):
            low = addr.lower()
            if low not in addresses:
                addresses.append(low)

        # Solana (base-58, 32-44 chars)
        for addr in self.SOLANA_ADDRESS_PATTERN.findall(message):
            if (
                len(addr) >= 32
                and not addr.isalpha()
                and not any(c in addr for c in ['/', '\\', '.'])
                and addr not in addresses
            ):
                addresses.append(addr)

        return addresses[:5]

    def _extract_dex_urls(self, message: str) -> List[str]:
        """Return contract addresses embedded inside DEX / scanner URLs."""
        out: List[str] = []
        for addr in self.DEX_URL_PATTERN.findall(message):
            normalized = addr.lower() if addr.startswith("0x") else addr
            if normalized not in out:
                out.append(normalized)
        return out

    def _detect_chain(self, message: str) -> Optional[str]:
        """Detect blockchain from keywords or address format."""
        match = self.CHAIN_PATTERN.search(message)
        if match:
            raw = match.group(1).lower().strip()
            return self.CHAIN_MAP.get(raw, raw)

        # Infer chain from URL context
        msg_lower = message.lower()
        if 'solscan.io' in msg_lower or 'birdeye.so' in msg_lower or 'pump.fun' in msg_lower:
            return 'solana'
        if 'basescan.org' in msg_lower:
            return 'base'
        if 'arbiscan.io' in msg_lower:
            return 'arbitrum'
        if 'bscscan.com' in msg_lower:
            return 'bsc'
        if 'polygonscan.com' in msg_lower:
            return 'polygon'

        # Default EVM
        if self.EVM_ADDRESS_PATTERN.search(message):
            return 'eth'

        return None

    def _extract_tokens(self, message: str) -> List[str]:
        """
        Extract token symbols.  Priority: $CASHTAG/#TAG → known tickers
        → plausible bare uppercase tickers.
        """
        seen: set = set()
        tokens: List[str] = []

        def _add(sym: str):
            upper = sym.upper()
            if upper in self._NOISE_WORDS or upper in seen:
                return
            seen.add(upper)
            tokens.append(upper)

        # 1. Explicit $SYMBOL / #SYMBOL
        for m in self.CASHTAG_PATTERN.findall(message):
            _add(m)

        # 2. Known tickers in the message
        for m in self.BARE_TOKEN_PATTERN.findall(message):
            if m in self.KNOWN_TOKENS:
                _add(m)

        # 3. Plausible unknowns (3-6 chars uppercase, not noise)
        for m in self.BARE_TOKEN_PATTERN.findall(message):
            if 3 <= len(m) <= 6 and m not in self._NOISE_WORDS:
                _add(m)

        return tokens

    # ── Price helpers ─────────────────────────────────────────────

    def _extract_entry_price(self, message: str) -> Optional[float]:
        match = self.ENTRY_PATTERN.search(message)
        if match:
            try:
                return float(match.group(1).replace(',', ''))
            except (ValueError, IndexError):
                pass
        return None

    def _extract_target_price(self, message: str) -> Optional[float]:
        match = self.TARGET_PATTERN.search(message)
        if match:
            try:
                return float(match.group(1).replace(',', ''))
            except (ValueError, IndexError):
                pass
        return None

    def _extract_stop_loss(self, message: str) -> Optional[float]:
        match = self.STOP_LOSS_PATTERN.search(message)
        if match:
            try:
                return float(match.group(1).replace(',', ''))
            except (ValueError, IndexError):
                pass
        return None

    def _extract_market_cap(self, message: str) -> Optional[float]:
        match = self.MC_PATTERN.search(message)
        if match:
            try:
                val = float(match.group(1).replace(',', ''))
                suffix = (match.group(2) or '').lower()
                multiplier = {'k': 1_000, 'm': 1_000_000, 'b': 1_000_000_000}.get(suffix, 1)
                return val * multiplier
            except (ValueError, IndexError):
                pass
        return None

    def _extract_all_prices(self, message: str) -> List[float]:
        prices: List[float] = []
        for match in self.PRICE_PATTERN.finditer(message):
            raw = match.group(1) if match.group(1) else match.group(0)
            try:
                val = float(raw.replace(',', ''))
                if 0.0000001 <= val <= 10_000_000:
                    prices.append(val)
            except ValueError:
                continue
        return prices

    # ── Sentiment ─────────────────────────────────────────────────

    def _analyze_sentiment(self, message: str) -> Tuple[str, float]:
        msg_lower = message.lower()
        bull = sum(1 for kw in self.BULLISH_KEYWORDS if kw in msg_lower)
        bear = sum(1 for kw in self.BEARISH_KEYWORDS if kw in msg_lower)
        bull += sum(0.5 for e in self.BULLISH_EMOJIS if e in message)
        bear += sum(0.5 for e in self.BEARISH_EMOJIS if e in message)

        if bull + bear == 0:
            return "NEUTRAL", 0.5
        if bull > bear:
            return "BULLISH", min(0.95, 0.5 + (bull - bear) / 10)
        if bear > bull:
            return "BEARISH", min(0.95, 0.5 + (bear - bull) / 10)
        return "NEUTRAL", 0.5

    # ── Tags ──────────────────────────────────────────────────────

    def _extract_tags(self, message: str) -> List[str]:
        tags: List[str] = []
        msg_lower = message.lower()
        tag_map = {
            "breakout": ["breakout", "breaking out", "broke out"],
            "accumulation": ["accumulate", "accumulation", "accumulating"],
            "whale_alert": ["whale", "whales", "big buy", "big order"],
            "technical": ["chart", "ta ", "technical", "pattern", "indicator"],
            "fundamental": ["news", "announcement", "partnership", "listing"],
            "high_risk": ["high risk", "risky", "degen", "yolo", "gamble"],
            "low_risk": ["safe", "low risk", "conservative"],
            "swing_trade": ["swing", "swing trade"],
            "scalp": ["scalp", "quick flip", "fast trade"],
            "dip_buy": ["dip", "buying the dip", "discount", "cheap"],
            "momentum": ["momentum", "strength"],
            "reversal": ["reversal", "reverse", "bounce"],
            "new_launch": ["launch", "stealth", "fair launch", "just launched"],
            "airdrop": ["airdrop", "drop", "claim"],
        }
        for tag, keywords in tag_map.items():
            if any(kw in msg_lower for kw in keywords):
                tags.append(tag)
        return tags[:6]

    # ── Token name lookup ─────────────────────────────────────────

    _TOKEN_NAMES = {
        'BTC': 'Bitcoin', 'ETH': 'Ethereum', 'SOL': 'Solana',
        'DOGE': 'Dogecoin', 'PEPE': 'Pepe', 'SHIB': 'Shiba Inu',
        'LINK': 'Chainlink', 'MATIC': 'Polygon', 'AVAX': 'Avalanche',
        'DOT': 'Polkadot', 'ADA': 'Cardano', 'XRP': 'Ripple',
        'BNB': 'Binance Coin', 'ATOM': 'Cosmos', 'UNI': 'Uniswap',
        'AAVE': 'Aave', 'LTC': 'Litecoin', 'FTM': 'Fantom',
        'NEAR': 'NEAR Protocol', 'APT': 'Aptos', 'ARB': 'Arbitrum',
        'OP': 'Optimism', 'INJ': 'Injective', 'SUI': 'Sui',
        'WIF': 'dogwifhat', 'BONK': 'Bonk', 'JUP': 'Jupiter',
        'WLD': 'Worldcoin', 'TIA': 'Celestia', 'SEI': 'Sei',
        'PYTH': 'Pyth Network', 'ONDO': 'Ondo Finance',
        'RNDR': 'Render', 'RENDER': 'Render', 'FET': 'Fetch.ai',
        'TAO': 'Bittensor', 'TON': 'Toncoin', 'TRUMP': 'TRUMP',
        'BRETT': 'Brett', 'MOG': 'Mog Coin', 'POPCAT': 'Popcat',
    }

    def _get_token_name(self, symbol: str) -> str:
        if not symbol:
            return "Unknown"
        return self._TOKEN_NAMES.get(symbol.upper(), symbol)
