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


# ─── DEXSCREENER & GECKOTERMINAL API (Pour les Memecoins) ───────────────

DEXSCREENER_API = "https://api.dexscreener.com/latest/dex/tokens"
GECKOTERMINAL_API = "https://api.geckoterminal.com/api/v2"

async def get_dexscreener_token(address: str) -> Optional[dict]:
    """Récupère les infos complètes d'un token via DexScreener."""
    session = get_session()
    try:
        async with session.get(f"{DEXSCREENER_API}/{address}") as resp:
            if resp.status == 200:
                data = await resp.json()
                pairs = data.get("pairs", [])
                if not pairs:
                    return None
                # Pour éviter le scam, on prend la pair la plus liquide
                best_pair = max(pairs, key=lambda x: float(x.get("liquidity", {}).get("usd", 0) or 0))
                
                chain_id = best_pair.get("chainId", "")
                token_address = best_pair.get("baseToken", {}).get("address", "")
                
                # Pattern d'URL d'icône DexScreener
                image_url = f"https://cdn.dexscreener.com/tokens/solana/{token_address}.png" if chain_id == "solana" else None
                # Alternative via pair info si dispo (parfois dans 'info')
                info = best_pair.get("info", {})
                if info and info.get("imageUrl"):
                    image_url = info.get("imageUrl")

                return {
                    "price": float(best_pair.get("priceUsd", 0) or 0),
                    "name": best_pair.get("baseToken", {}).get("name", "Unknown"),
                    "symbol": best_pair.get("baseToken", {}).get("symbol", "UKN"),
                    "liquidity": float(best_pair.get("liquidity", {}).get("usd", 0) or 0),
                    "network": chain_id,
                    "pool_address": best_pair.get("pairAddress", ""),
                    "image_url": image_url
                }
    except Exception as e:
        print(f"Error fetching DexScreener: {e}")
    return None

async def get_trending_memecoins() -> list[dict]:
    """Récupère les 10 meilleurs jetons boostés du moment."""
    session = get_session()
    url = "https://api.dexscreener.com/token-boosts/top/v1"
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                # On prend les 10 premiers
                return data[:10]
            return []
    except Exception:
        return []

async def get_dexscreener_tokens(addresses: list[str]) -> dict[str, dict]:
    """Récupère les infos (prix, nom, symbole, image) de plusieurs contrats."""
    if not addresses:
        return {}
    
    clean_addrs = [a.replace("meme:", "") for a in addresses]
    addr_string = ",".join(clean_addrs[:30])
    
    result = {}
    session = get_session()
    try:
        async with session.get(f"{DEXSCREENER_API}/{addr_string}") as resp:
            if resp.status == 200:
                data = await resp.json()
                for pair in data.get("pairs", []):
                    addr = pair.get("baseToken", {}).get("address", "")
                    # On garde la pair la plus liquide pour chaque token unique
                    if addr not in result or float(pair.get("liquidity", {}).get("usd", 0) or 0) > result[addr].get("liquidity", 0):
                        token_address = addr
                        chain_id = pair.get("chainId", "")
                        
                        image_url = f"https://cdn.dexscreener.com/tokens/solana/{token_address}.png" if chain_id == "solana" else None
                        info = pair.get("info", {})
                        if info and info.get("imageUrl"):
                            image_url = info.get("imageUrl")

                        result[addr] = {
                            "price": float(pair.get("priceUsd", 0) or 0),
                            "name": pair.get("baseToken", {}).get("name", "Unknown"),
                            "symbol": pair.get("baseToken", {}).get("symbol", "UKN"),
                            "liquidity": float(pair.get("liquidity", {}).get("usd", 0) or 0),
                            "image_url": image_url
                        }
    except Exception:
        pass
    
    # Mapper vers les clés meme:{adresse}
    final_dict = {}
    for a in clean_addrs:
        # Correspondance insensible à la casse
        match = next((v for k, v in result.items() if k.lower() == a.lower()), None)
        if match:
            final_dict[f"meme:{a}"] = match
            
    return final_dict


async def get_dexscreener_prices(addresses: list[str]) -> dict[str, float]:
    """Récupère le prix de plusieurs contrats en une seule requête."""
    if not addresses:
        return {}
    
    # On enlève le mot 'meme:'
    clean_addrs = [a.replace("meme:", "") for a in addresses]
    addr_string = ",".join(clean_addrs[:30])
    
    result = {a: 0.0 for a in clean_addrs}
    session = get_session()
    try:
        async with session.get(f"{DEXSCREENER_API}/{addr_string}") as resp:
            if resp.status == 200:
                data = await resp.json()
                for pair in data.get("pairs", []):
                    addr = pair.get("baseToken", {}).get("address", "").lower()
                    for req_addr in clean_addrs:
                        if req_addr.lower() == addr and result[req_addr] == 0.0:
                             result[req_addr] = float(pair.get("priceUsd", 0) or 0)
    except Exception:
        pass
    
    # On renvoie le dictionnaire sous forme meme:{adresse} pour compatibilité avec le portofolio
    return {f"meme:{a}": price for a, price in result.items() if price > 0}

async def get_geckoterminal_ohlc(network: str, pool_address: str, timeframe: str = "day") -> Optional[list[list[float]]]:
    """
    Récupère le graphique OHLC depuis GeckoTerminal pour un pool (Raydium, etc).
    timeframe = 'day', 'hour', ou 'minute'
    """
    session = get_session()
    url = f"{GECKOTERMINAL_API}/networks/{network}/pools/{pool_address}/ohlcv/{timeframe}?limit=200"
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                ohlcv = data.get("data", {}).get("attributes", {}).get("ohlcv_list", [])
                ohlcv.reverse()
                # On tronque à [timestamp, open, high, low, close]
                return [row[:5] for row in ohlcv]
            return None
    except Exception:
        return None
