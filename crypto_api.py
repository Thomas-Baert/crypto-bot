import aiohttp
import asyncio
from typing import Optional

# Cryptos disponibles : {symbole affiché: id CoinGecko}
AVAILABLE_CRYPTOS: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "XRP": "ripple",
    "ADA": "cardano",
    "AVAX": "avalanche-2",
    "DOGE": "dogecoin",
    "DOT": "polkadot",
    "LINK": "chainlink",
}

# Noms complets pour l'affichage
CRYPTO_NAMES: dict[str, str] = {
    "BTC": "Bitcoin",
    "ETH": "Ethereum",
    "SOL": "Solana",
    "BNB": "BNB",
    "XRP": "XRP",
    "ADA": "Cardano",
    "AVAX": "Avalanche",
    "DOGE": "Dogecoin",
    "DOT": "Polkadot",
    "LINK": "Chainlink",
}

# Emojis pour chaque crypto
CRYPTO_EMOJIS: dict[str, str] = {
    "BTC": "₿",
    "ETH": "⟠",
    "SOL": "◎",
    "BNB": "🔶",
    "XRP": "✕",
    "ADA": "₳",
    "AVAX": "🔺",
    "DOGE": "🐕",
    "DOT": "●",
    "LINK": "🔗",
}

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
_session: Optional[aiohttp.ClientSession] = None


def get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(
            headers={"Accept": "application/json"},
            timeout=aiohttp.ClientTimeout(total=10),
        )
    return _session


async def close_session():
    global _session
    if _session and not _session.closed:
        await _session.close()


def symbol_to_id(symbol: str) -> Optional[str]:
    """Convertit un symbole (BTC) en id CoinGecko (bitcoin)."""
    return AVAILABLE_CRYPTOS.get(symbol.upper())


def normalize_symbol(input_str: str) -> Optional[str]:
    """
    Accepte soit le symbole (BTC) soit le nom (bitcoin/Bitcoin) 
    et retourne le symbole standardisé.
    """
    upper = input_str.upper()
    if upper in AVAILABLE_CRYPTOS:
        return upper

    lower = input_str.lower()
    for sym, cg_id in AVAILABLE_CRYPTOS.items():
        if lower == cg_id or lower == CRYPTO_NAMES[sym].lower():
            return sym

    return None


async def get_price(symbol: str) -> Optional[float]:
    """Retourne le prix actuel en USD d'une crypto à partir de son symbole."""
    cg_id = symbol_to_id(symbol)
    if not cg_id:
        return None

    try:
        session = get_session()
        url = f"{COINGECKO_BASE}/simple/price"
        params = {"ids": cg_id, "vs_currencies": "usd"}
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            return data.get(cg_id, {}).get("usd")
    except Exception:
        return None


async def get_prices(symbols: list[str]) -> dict[str, Optional[float]]:
    """Retourne les prix USD de plusieurs cryptos en un seul appel API."""
    if not symbols:
        return {}

    valid = {s.upper(): symbol_to_id(s) for s in symbols if symbol_to_id(s)}
    if not valid:
        return {}

    ids_str = ",".join(valid.values())

    try:
        session = get_session()
        url = f"{COINGECKO_BASE}/simple/price"
        params = {"ids": ids_str, "vs_currencies": "usd"}
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                return {s: None for s in valid}
            data = await resp.json()

        result: dict[str, Optional[float]] = {}
        for sym, cg_id in valid.items():
            result[sym] = data.get(cg_id, {}).get("usd")
        return result
    except Exception:
        return {s: None for s in valid}


async def get_ohlc(symbol: str, days: str) -> Optional[list[list[float]]]:
    """
    Retourne l'historique OHLC (Open, High, Low, Close) d'une crypto.
    Valeurs valides pour days: '1', '7', '14', '30', '90', '365', 'max'.
    Format de retour : [[timestamp, open, high, low, close], ...]
    """
    cg_id = symbol_to_id(symbol)
    if not cg_id:
        return None

    try:
        session = get_session()
        url = f"{COINGECKO_BASE}/coins/{cg_id}/ohlc"
        params = {"vs_currency": "usd", "days": days}
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            return data
    except Exception:
        return None
