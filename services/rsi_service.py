import pandas as pd


def calculate_rsi(candles, period=14):
    if not candles or len(candles) < period + 2:
        return candles, None

    df = pd.DataFrame(candles)

    delta = df["close"].diff()

    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    df["rsi"] = rsi

    df = df.fillna(0)

    updated_candles = df.to_dict(orient="records")
    latest_rsi = round(float(df["rsi"].iloc[-1]), 2)

    return updated_candles, latest_rsi