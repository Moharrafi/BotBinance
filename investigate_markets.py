import ccxt
import json

exchange = ccxt.mexc()
markets = exchange.load_markets()

# Check DOGE symbols
doge_symbols = [s for s in markets.keys() if 'DOGE' in s]
print("DOGE Symbols:", doge_symbols)

# Check one swap symbol detail
if "DOGE/USDT:USDT" in markets:
    print("\nDOGE/USDT:USDT Detail:")
    # print(json.dumps(markets["DOGE/USDT:USDT"], indent=2))
    m = markets["DOGE/USDT:USDT"]
    print(f"ID: {m['id']}, Symbol: {m['symbol']}, Base: {m['base']}, Quote: {m['quote']}, Swap: {m['swap']}, Spot: {m['spot']}")

# Check one spot symbol detail
if "DOGE/USDT" in markets:
    print("\nDOGE/USDT Detail:")
    m = markets["DOGE/USDT"]
    print(f"ID: {m['id']}, Symbol: {m['symbol']}, Base: {m['base']}, Quote: {m['quote']}, Swap: {m['swap']}, Spot: {m['spot']}")

# Test symbol splitting
def get_spot_symbol(futures_symbol):
    if ":" in futures_symbol:
        return futures_symbol.split(":")[0]
    return futures_symbol

print(f"\nTransform 'DOGE/USDT:USDT' -> {get_spot_symbol('DOGE/USDT:USDT')}")
