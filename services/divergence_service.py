def find_swing_lows(candles, lookback=3):
    lows = []

    for i in range(lookback, len(candles) - lookback):
        current_low = candles[i]["low"]

        left = [candles[j]["low"] for j in range(i - lookback, i)]
        right = [candles[j]["low"] for j in range(i + 1, i + lookback + 1)]

        if current_low < min(left) and current_low < min(right):
            lows.append({
                "index": i,
                "time": candles[i]["time"],
                "price": candles[i]["low"],
                "rsi": candles[i].get("rsi", 0)
            })

    return lows


def find_swing_highs(candles, lookback=3):
    highs = []

    for i in range(lookback, len(candles) - lookback):
        current_high = candles[i]["high"]

        left = [candles[j]["high"] for j in range(i - lookback, i)]
        right = [candles[j]["high"] for j in range(i + 1, i + lookback + 1)]

        if current_high > max(left) and current_high > max(right):
            highs.append({
                "index": i,
                "time": candles[i]["time"],
                "price": candles[i]["high"],
                "rsi": candles[i].get("rsi", 0)
            })

    return highs


def detect_rsi_divergence(candles):
    if not candles or len(candles) < 30:
        return {
            "type": "none",
            "signal": "WAIT",
            "message": "Not enough candle data"
        }

    lows = find_swing_lows(candles)
    highs = find_swing_highs(candles)

    # Bullish divergence
    if len(lows) >= 2:
        low1 = lows[-2]
        low2 = lows[-1]

        if low2["price"] < low1["price"] and low2["rsi"] > low1["rsi"]:
            return {
                "type": "bullish",
                "signal": "BUY WATCH",
                "message": "Bullish RSI divergence found",
                "point1": low1,
                "point2": low2
            }

    # Bearish divergence
    if len(highs) >= 2:
        high1 = highs[-2]
        high2 = highs[-1]

        if high2["price"] > high1["price"] and high2["rsi"] < high1["rsi"]:
            return {
                "type": "bearish",
                "signal": "SELL WATCH",
                "message": "Bearish RSI divergence found",
                "point1": high1,
                "point2": high2
            }

    return {
        "type": "none",
        "signal": "WAIT",
        "message": "No strong RSI divergence found"
    }