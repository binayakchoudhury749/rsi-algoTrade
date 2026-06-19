import yfinance as yf
import pandas as pd


ALLOWED_INTERVALS = {
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "60m",
    "1d": "1d"
}


def normalize_indian_symbol(symbol):
    """
    User can type:
    TATAMOTORS
    RELIANCE
    HDFCBANK

    Backend converts to:
    TATAMOTORS.NS
    RELIANCE.NS
    HDFCBANK.NS
    """

    symbol = symbol.upper().strip()

    symbol = symbol.replace(" ", "")
    symbol = symbol.replace(".NS", "")
    symbol = symbol.replace(".BO", "")

    return symbol + ".NS"


def get_period_by_interval(interval):
    if interval in ["5m", "15m", "30m"]:
        return "5d"
    if interval == "1h":
        return "1mo"
    if interval == "1d":
        return "6mo"
    return "5d"


def get_candles(symbol, interval="15m"):
    try:
        interval = ALLOWED_INTERVALS.get(interval, "15m")
        yf_symbol = normalize_indian_symbol(symbol)
        period = get_period_by_interval(interval)

        data = yf.download(
            tickers=yf_symbol,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=False,
            threads=True
        )

        if data.empty:
            return [], yf_symbol

        data = data.reset_index()

        time_col = "Datetime" if "Datetime" in data.columns else "Date"

        candles = []

        for _, row in data.iterrows():
            candles.append({
                "time": int(pd.Timestamp(row[time_col]).timestamp()),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": float(row["Volume"])
            })

        return candles, yf_symbol

    except Exception as e:
        print("Stock data error:", e)
        return [], symbol