import os
import time
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, request, session, jsonify
import json
import sqlite3
import csv
import io
from flask import Response
from services.supabase_client import supabase
from flask import request, jsonify, render_template, redirect, url_for, session
from datetime import datetime


def now_text():
    return datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")


def to_float(value, default=0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def to_int(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def clean_symbol_text(symbol):
    return str(symbol or "").upper().replace(".NS", "").replace(".BO", "").strip()


try:
    from openai import OpenAI
except Exception:
    OpenAI = None

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("APP_SECRET_KEY", "rsi-divergence-pro-secret")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "1234")

CACHE_SECONDS = 1
LIVE_PRICE_CACHE_SECONDS = 1
LIVE_PRICE_CACHE = {}
CACHE = {}

NSE_STOCKS = [
    {"symbol": "RELIANCE", "name": "Reliance Industries Ltd"},
    {"symbol": "TCS", "name": "Tata Consultancy Services Ltd"},
    {"symbol": "INFY", "name": "Infosys Ltd"},
    {"symbol": "HDFCBANK", "name": "HDFC Bank Ltd"},
    {"symbol": "ICICIBANK", "name": "ICICI Bank Ltd"},
    {"symbol": "SBIN", "name": "State Bank of India"},
    {"symbol": "AXISBANK", "name": "Axis Bank Ltd"},
    {"symbol": "KOTAKBANK", "name": "Kotak Mahindra Bank Ltd"},
    {"symbol": "LT", "name": "Larsen & Toubro Ltd"},
    {"symbol": "ITC", "name": "ITC Ltd"},
    {"symbol": "BHARTIARTL", "name": "Bharti Airtel Ltd"},
    {"symbol": "BAJFINANCE", "name": "Bajaj Finance Ltd"},
    {"symbol": "TATAMOTORS", "name": "Tata Motors Ltd"},
    {"symbol": "TATASTEEL", "name": "Tata Steel Ltd"},
    {"symbol": "TATAPOWER", "name": "Tata Power Company Ltd"},
    {"symbol": "MARUTI", "name": "Maruti Suzuki India Ltd"},
    {"symbol": "M&M", "name": "Mahindra & Mahindra Ltd"},
    {"symbol": "SUNPHARMA", "name": "Sun Pharmaceutical Industries Ltd"},
    {"symbol": "CIPLA", "name": "Cipla Ltd"},
    {"symbol": "WIPRO", "name": "Wipro Ltd"},
    {"symbol": "HCLTECH", "name": "HCL Technologies Ltd"},
    {"symbol": "TECHM", "name": "Tech Mahindra Ltd"},
    {"symbol": "ADANIENT", "name": "Adani Enterprises Ltd"},
    {"symbol": "ADANIPORTS", "name": "Adani Ports and SEZ Ltd"},
    {"symbol": "POWERGRID", "name": "Power Grid Corporation of India Ltd"},
    {"symbol": "NTPC", "name": "NTPC Ltd"},
    {"symbol": "ONGC", "name": "Oil and Natural Gas Corporation Ltd"},
    {"symbol": "COALINDIA", "name": "Coal India Ltd"},
    {"symbol": "JSWSTEEL", "name": "JSW Steel Ltd"},
    {"symbol": "HINDALCO", "name": "Hindalco Industries Ltd"},
    {"symbol": "ULTRACEMCO", "name": "UltraTech Cement Ltd"},
    {"symbol": "GRASIM", "name": "Grasim Industries Ltd"},
    {"symbol": "TITAN", "name": "Titan Company Ltd"},
    {"symbol": "ASIANPAINT", "name": "Asian Paints Ltd"},
    {"symbol": "BRITANNIA", "name": "Britannia Industries Ltd"},
    {"symbol": "ZOMATO", "name": "Zomato Ltd"},
    {"symbol": "PAYTM", "name": "One 97 Communications Ltd"},
    {"symbol": "IRCTC", "name": "Indian Railway Catering and Tourism Corporation Ltd"},
    {"symbol": "IREDA", "name": "Indian Renewable Energy Development Agency Ltd"},
    {"symbol": "HAL", "name": "Hindustan Aeronautics Ltd"},
    {"symbol": "BEL", "name": "Bharat Electronics Ltd"},
    {"symbol": "RVNL", "name": "Rail Vikas Nigam Ltd"},
    {"symbol": "IRFC", "name": "Indian Railway Finance Corporation Ltd"},
    {"symbol": "SUZLON", "name": "Suzlon Energy Ltd"},
    {"symbol": "YESBANK", "name": "Yes Bank Ltd"},
    {"symbol": "PNB", "name": "Punjab National Bank"},
    {"symbol": "BANKBARODA", "name": "Bank of Baroda"},
    {"symbol": "CANBK", "name": "Canara Bank"},
    {"symbol": "JIOFIN", "name": "Jio Financial Services Ltd"},
    {"symbol": "NHPC", "name": "NHPC Ltd"},
    {"symbol": "SJVN", "name": "SJVN Ltd"},
    {"symbol": "HUDCO", "name": "HUDCO Ltd"},
    {"symbol": "MAZDOCK", "name": "Mazagon Dock Shipbuilders Ltd"},
    {"symbol": "COCHINSHIP", "name": "Cochin Shipyard Ltd"},
    {"symbol": "BSE", "name": "BSE Ltd"},
    {"symbol": "CDSL", "name": "Central Depository Services India Ltd"},
    {"symbol": "ANGELONE", "name": "Angel One Ltd"},
]

DEFAULT_SCAN_SYMBOLS = [
    "RELIANCE", "TATAMOTORS", "ZOMATO", "SBIN", "HDFCBANK",
    "INFY", "IREDA", "IRFC", "RVNL", "HAL", "BEL", "SUZLON",
    "JIOFIN", "TATAPOWER", "ADANIENT"
]

SYMBOL_ALIASES = {
    "NIFTY": "^NSEI",
    "NIFTY50": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "NIFTYBANK": "^NSEBANK",
    "SENSEX": "^BSESN",
}


@app.route("/")
def home():
    if session.get("logged_in"):
        return redirect(url_for("chart_view"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("chart_view"))

        return "<h2>Invalid login</h2><a href='/login'>Try again</a>"

    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Login - RSI Divergence Pro</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body{margin:0;font-family:Arial;background:#f5f7fb;height:100vh;display:flex;align-items:center;justify-content:center;color:#172033}
            .card{width:90%;max-width:380px;background:white;border:1px solid #e5e7eb;border-radius:18px;padding:28px;box-shadow:0 20px 40px rgba(15,23,42,.08)}
            h2{text-align:center;margin:0}p{text-align:center;color:#6b7280;font-size:13px}
            input{width:100%;height:48px;margin-top:12px;border:1px solid #e5e7eb;border-radius:12px;padding:0 14px;box-sizing:border-box}
            button{width:100%;height:48px;margin-top:16px;border:none;border-radius:12px;background:#2563eb;color:white;font-weight:800;font-size:15px;cursor:pointer}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>RSI Divergence Pro</h2>
            <p>Advanced RSI Scanner</p>
            <form method="POST">
                <input name="username" placeholder="Username" required>
                <input name="password" type="password" placeholder="Password" required>
                <button type="submit">Login</button>
            </form>
            <p>Default: admin / 1234</p>
        </div>
    </body>
    </html>
    """


@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return redirect(url_for("chart_view"))


@app.route("/chart-view")
def chart_view():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template("chart_view.html")


@app.route("/divergence-scanner")
def divergence_scanner():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template("divergence_scanner.html")



@app.route("/settings")
def settings():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return "<h2>Settings page next.</h2><a href='/chart-view'>Back</a>"


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


def clean_symbol(value):
    value = str(value or "").upper().strip()
    value = value.replace(".NS", "").replace(".BO", "")
    value = value.replace("NSE:", "").replace("BSE:", "")
    return value.strip()


def resolve_input_to_symbol(user_input):
    text = str(user_input or "").strip()
    clean = clean_symbol(text)

    if not clean:
        return ""

    for stock in NSE_STOCKS:
        if stock["symbol"].upper() == clean:
            return stock["symbol"]

    text_lower = text.lower()

    for stock in NSE_STOCKS:
        if text_lower in stock["name"].lower():
            return stock["symbol"]

    compact = text_lower.replace(" ", "")

    for stock in NSE_STOCKS:
        if compact in stock["name"].lower().replace(" ", ""):
            return stock["symbol"]

    return clean


def get_stock_name(symbol):
    clean = clean_symbol(symbol)

    for stock in NSE_STOCKS:
        if stock["symbol"] == clean:
            return stock["name"]

    return clean


def build_yahoo_candidates(symbol):
    clean = clean_symbol(symbol)

    if clean in SYMBOL_ALIASES:
        return [SYMBOL_ALIASES[clean]]

    if clean.startswith("^"):
        return [clean]

    return [f"{clean}.NS", f"{clean}.BO"]


def get_period_for_interval(interval):
    return "5d"


def normalize_dataframe(data):
    if data is None or data.empty:
        return data

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    return data


def safe_float(value, default=None):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def fetch_from_yfinance(yahoo_symbol, timeframe):
    try:
        data = yf.download(
            tickers=yahoo_symbol,
            period=get_period_for_interval(timeframe),
            interval=timeframe,
            progress=False,
            auto_adjust=False,
            threads=True
        )

        data = normalize_dataframe(data)

        if data is None or data.empty:
            return []

        data = data.reset_index()
        time_col = "Datetime" if "Datetime" in data.columns else "Date"

        candles = []

        for _, row in data.iterrows():
            open_price = safe_float(row.get("Open"))
            high_price = safe_float(row.get("High"))
            low_price = safe_float(row.get("Low"))
            close_price = safe_float(row.get("Close"))
            volume = safe_float(row.get("Volume"), 0)

            if open_price is None or high_price is None or low_price is None or close_price is None:
                continue

            candle_time = pd.Timestamp(row[time_col])

            candles.append({
                "time": int(candle_time.timestamp()),
                "open": round(open_price, 2),
                "high": round(high_price, 2),
                "low": round(low_price, 2),
                "close": round(close_price, 2),
                "volume": round(volume or 0, 2),
            })

        return candles

    except Exception as e:
        print(f"YFinance error for {yahoo_symbol}: {e}")
        return []


def get_candles(user_symbol, timeframe="15m"):
    if timeframe not in ["5m", "15m", "30m"]:
        timeframe = "15m"

    resolved_symbol = resolve_input_to_symbol(user_symbol)
    candidates = build_yahoo_candidates(resolved_symbol)

    for yahoo_symbol in candidates:
        cache_key = f"{yahoo_symbol}_{timeframe}"
        now = time.time()

        if cache_key in CACHE:
            cached = CACHE[cache_key]
            if now - cached["created_at"] <= CACHE_SECONDS:
                return cached["candles"], yahoo_symbol, resolved_symbol

        candles = fetch_from_yfinance(yahoo_symbol, timeframe)

        if candles:
            CACHE[cache_key] = {
                "created_at": now,
                "candles": candles,
            }
            return candles, yahoo_symbol, resolved_symbol

    return [], candidates[0] if candidates else "", resolved_symbol


def calculate_rsi(candles, period=14):
    if not candles or len(candles) < period + 5:
        return candles, None

    df = pd.DataFrame(candles)

    delta = df["close"].diff()

    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    df["rsi"] = rsi
    df.loc[(avg_loss == 0) & (avg_gain > 0), "rsi"] = 100
    df.loc[(avg_gain == 0) & (avg_loss > 0), "rsi"] = 0
    df["rsi"] = df["rsi"].fillna(0).round(2)

    latest_rsi = safe_float(df["rsi"].iloc[-1], None)
    latest_rsi = round(latest_rsi, 2) if latest_rsi is not None else None

    return df.to_dict(orient="records"), latest_rsi


def find_swing_lows(candles, lookback=3):
    lows = []

    if len(candles) < lookback * 2 + 5:
        return lows

    for i in range(lookback, len(candles) - lookback):
        current = candles[i]["low"]
        left = [candles[j]["low"] for j in range(i - lookback, i)]
        right = [candles[j]["low"] for j in range(i + 1, i + lookback + 1)]
        rsi_value = candles[i].get("rsi", 0)

        if current <= min(left) and current <= min(right) and rsi_value > 0:
            lows.append({
                "index": i,
                "time": int(candles[i]["time"]),
                "price": round(float(current), 2),
                "rsi": round(float(rsi_value), 2),
            })

    return lows


def find_swing_highs(candles, lookback=3):
    highs = []

    if len(candles) < lookback * 2 + 5:
        return highs

    for i in range(lookback, len(candles) - lookback):
        current = candles[i]["high"]
        left = [candles[j]["high"] for j in range(i - lookback, i)]
        right = [candles[j]["high"] for j in range(i + 1, i + lookback + 1)]
        rsi_value = candles[i].get("rsi", 0)

        if current >= max(left) and current >= max(right) and rsi_value > 0:
            highs.append({
                "index": i,
                "time": int(candles[i]["time"]),
                "price": round(float(current), 2),
                "rsi": round(float(rsi_value), 2),
            })

    return highs


def detect_advanced_divergence(candles):
    if not candles or len(candles) < 35:
        return {
            "type": "none",
            "kind": "No Divergence",
            "direction": "neutral",
            "signal": "WAIT",
            "message": "Not enough candles.",
            "point1": None,
            "point2": None,
        }

    lows = find_swing_lows(candles)[-12:]
    highs = find_swing_highs(candles)[-12:]
    signals = []

    for i in range(1, len(lows)):
        low1 = lows[i - 1]
        low2 = lows[i]

        if low2["price"] < low1["price"] and low2["rsi"] > low1["rsi"]:
            signals.append({
                "type": "regular_bullish",
                "kind": "Regular Bullish Divergence",
                "direction": "bullish",
                "signal": "BUY WATCH",
                "message": "Regular bullish RSI divergence found.",
                "point1": low1,
                "point2": low2,
            })

        if low2["price"] > low1["price"] and low2["rsi"] < low1["rsi"]:
            signals.append({
                "type": "hidden_bullish",
                "kind": "Hidden Bullish Divergence",
                "direction": "bullish",
                "signal": "TREND BUY WATCH",
                "message": "Hidden bullish RSI divergence found.",
                "point1": low1,
                "point2": low2,
            })

    for i in range(1, len(highs)):
        high1 = highs[i - 1]
        high2 = highs[i]

        if high2["price"] > high1["price"] and high2["rsi"] < high1["rsi"]:
            signals.append({
                "type": "regular_bearish",
                "kind": "Regular Bearish Divergence",
                "direction": "bearish",
                "signal": "SELL / EXIT WATCH",
                "message": "Regular bearish RSI divergence found.",
                "point1": high1,
                "point2": high2,
            })

        if high2["price"] < high1["price"] and high2["rsi"] > high1["rsi"]:
            signals.append({
                "type": "hidden_bearish",
                "kind": "Hidden Bearish Divergence",
                "direction": "bearish",
                "signal": "TREND SELL WATCH",
                "message": "Hidden bearish RSI divergence found.",
                "point1": high1,
                "point2": high2,
            })

    if not signals:
        return {
            "type": "none",
            "kind": "No Divergence",
            "direction": "neutral",
            "signal": "WAIT",
            "message": "No clean divergence found.",
            "point1": None,
            "point2": None,
        }

    signals.sort(key=lambda x: x["point2"]["index"], reverse=True)
    return signals[0]


def get_rsi_zone(rsi):
    if rsi is None:
        return "No RSI"

    if rsi < 20:
        return "Extreme Oversold"
    if rsi < 30:
        return "Oversold"
    if rsi < 45:
        return "Weak Zone"
    if rsi <= 55:
        return "Neutral Zone"
    if rsi <= 70:
        return "Strong Zone"
    if rsi <= 80:
        return "Overbought"
    return "Extreme Overbought"


def get_rsi_slope(candles, lookback=5):
    valid = [c for c in candles if c.get("rsi", 0) > 0]

    if len(valid) < lookback + 2:
        return {"label": "Not enough RSI data", "value": 0, "direction": "flat"}

    current = valid[-1]["rsi"]
    previous = valid[-lookback]["rsi"]
    slope = round(current - previous, 2)

    if slope > 2:
        return {"label": "Positive RSI Slope", "value": slope, "direction": "positive"}

    if slope < -2:
        return {"label": "Negative RSI Slope", "value": slope, "direction": "negative"}

    return {"label": "Flat RSI Slope", "value": slope, "direction": "flat"}


def get_rsi_50_status(candles):
    valid = [c for c in candles if c.get("rsi", 0) > 0]

    if len(valid) < 3:
        return "No 50-line data"

    prev = valid[-2]["rsi"]
    current = valid[-1]["rsi"]

    if prev <= 50 and current > 50:
        return "Fresh Cross Above 50"
    if prev >= 50 and current < 50:
        return "Fresh Cross Below 50"
    if current > 50:
        return "Above 50"
    if current < 50:
        return "Below 50"

    return "At 50"


def detect_failure_swing(candles):
    valid = [c["rsi"] for c in candles if c.get("rsi", 0) > 0][-40:]

    if len(valid) < 15:
        return {"type": "none", "label": "No failure swing"}

    current = valid[-1]
    prev_5 = valid[-5]

    if min(valid[-25:]) < 30 and current > 45 and current > prev_5 + 2:
        return {"type": "bullish", "label": "Bullish Failure Swing Watch"}

    if max(valid[-25:]) > 70 and current < 55 and current < prev_5 - 2:
        return {"type": "bearish", "label": "Bearish Failure Swing Watch"}

    return {"type": "none", "label": "No failure swing"}


def candle_confirmation(candles, direction):
    if not candles or len(candles) < 2:
        return {"confirmed": False, "label": "No candle confirmation", "entry_price": None}

    prev = candles[-2]
    last = candles[-1]

    if direction == "bullish":
        entry_price = round(float(last["high"]), 2)

        if last["close"] > last["open"] and last["close"] > prev["high"]:
            return {
                "confirmed": True,
                "label": "Bullish candle confirmation active",
                "entry_price": entry_price,
            }

        return {
            "confirmed": False,
            "label": f"Wait for candle close above ₹{entry_price}",
            "entry_price": entry_price,
        }

    if direction == "bearish":
        entry_price = round(float(last["low"]), 2)

        if last["close"] < last["open"] and last["close"] < prev["low"]:
            return {
                "confirmed": True,
                "label": "Bearish candle confirmation active",
                "entry_price": entry_price,
            }

        return {
            "confirmed": False,
            "label": f"Wait for candle close below ₹{entry_price}",
            "entry_price": entry_price,
        }

    return {"confirmed": False, "label": "No direction", "entry_price": None}


def calculate_buy_targets(entry, stop_loss):
    risk = entry - stop_loss

    if risk <= 0:
        return None

    return {
        "risk": round(risk, 2),
        "target_1": round(entry + risk * 3, 2),
        "target_2": round(entry + risk * 5, 2),
    }


def calculate_sell_targets(entry, stop_loss):
    risk = stop_loss - entry

    if risk <= 0:
        return None

    return {
        "risk": round(risk, 2),
        "target_1": round(entry - risk * 3, 2),
        "target_2": round(entry - risk * 5, 2),
    }


def build_mtf_context(candles_5m, candles_15m, candles_30m, main_direction):
    rsi_5 = candles_5m[-1]["rsi"] if candles_5m and candles_5m[-1].get("rsi") else None
    rsi_15 = candles_15m[-1]["rsi"] if candles_15m and candles_15m[-1].get("rsi") else None
    rsi_30 = candles_30m[-1]["rsi"] if candles_30m and candles_30m[-1].get("rsi") else None

    slope_5 = get_rsi_slope(candles_5m)
    slope_15 = get_rsi_slope(candles_15m)
    slope_30 = get_rsi_slope(candles_30m)

    if main_direction == "bullish":
        trend_30 = "30m Trend Supportive" if rsi_30 is not None and rsi_30 >= 45 else "30m Trend Not Supportive"

        if rsi_5 is not None and rsi_5 > 50 and slope_5["direction"] == "positive":
            entry_5 = "5m Entry Momentum Confirmed"
        elif slope_5["direction"] == "positive":
            entry_5 = "5m Improving, wait for RSI 50"
        else:
            entry_5 = "5m Entry Not Confirmed"

    elif main_direction == "bearish":
        trend_30 = "30m Weakness Supportive" if rsi_30 is not None and rsi_30 <= 55 else "30m Weakness Not Confirmed"

        if rsi_5 is not None and rsi_5 < 50 and slope_5["direction"] == "negative":
            entry_5 = "5m Exit/Sell Momentum Confirmed"
        elif slope_5["direction"] == "negative":
            entry_5 = "5m Weakening, wait for RSI 50 break"
        else:
            entry_5 = "5m Exit/Sell Not Confirmed"

    else:
        trend_30 = "No 30m confirmation"
        entry_5 = "No 5m confirmation"

    return {
        "rsi_5m": rsi_5,
        "rsi_15m": rsi_15,
        "rsi_30m": rsi_30,
        "slope_5m": slope_5,
        "slope_15m": slope_15,
        "slope_30m": slope_30,
        "trend_30m": trend_30,
        "entry_5m": entry_5,
    }


def build_advanced_rsi_engine(candles_5m, candles_15m, candles_30m):
    main_divergence = detect_advanced_divergence(candles_15m)
    direction = main_divergence["direction"]

    latest_rsi = candles_15m[-1]["rsi"] if candles_15m and candles_15m[-1].get("rsi") else None
    zone = get_rsi_zone(latest_rsi)
    slope = get_rsi_slope(candles_15m)
    rsi_50 = get_rsi_50_status(candles_15m)
    failure = detect_failure_swing(candles_15m)
    confirmation = candle_confirmation(candles_15m, direction)
    mtf = build_mtf_context(candles_5m, candles_15m, candles_30m, direction)

    score = 0
    reasons = []

    if main_divergence["type"] in ["regular_bullish", "regular_bearish"]:
        score += 25
        reasons.append("Regular RSI divergence on 15m")

    elif main_divergence["type"] in ["hidden_bullish", "hidden_bearish"]:
        score += 20
        reasons.append("Hidden RSI divergence on 15m")

    if direction != "neutral":
        score += 15
        reasons.append("15m main signal active")

    if "Supportive" in mtf["trend_30m"]:
        score += 15
        reasons.append(mtf["trend_30m"])

    if "Confirmed" in mtf["entry_5m"]:
        score += 10
        reasons.append(mtf["entry_5m"])

    if direction == "bullish" and slope["direction"] == "positive":
        score += 10
        reasons.append("15m RSI slope positive")

    if direction == "bearish" and slope["direction"] == "negative":
        score += 10
        reasons.append("15m RSI slope negative")

    if direction == "bullish" and "Above 50" in rsi_50:
        score += 10
        reasons.append("RSI above 50")

    if direction == "bearish" and "Below 50" in rsi_50:
        score += 10
        reasons.append("RSI below 50")

    if failure["type"] == direction:
        score += 10
        reasons.append(failure["label"])

    if confirmation["confirmed"]:
        score += 5
        reasons.append(confirmation["label"])

    score = min(score, 100)

    if score >= 80:
        grade = "STRONG SETUP"
    elif score >= 65:
        grade = "GOOD SETUP"
    elif score >= 50:
        grade = "RISKY SETUP"
    else:
        grade = "AVOID / WAIT"

    if direction == "bullish":
        action = "BUY WATCH" if not confirmation["confirmed"] else "BUY CONFIRMED"
        entry_status = confirmation["label"]
        exit_status = "Book 50% at T1, trail remaining."

    elif direction == "bearish":
        action = "SELL / EXIT WATCH" if not confirmation["confirmed"] else "SELL / EXIT CONFIRMED"
        entry_status = confirmation["label"]
        exit_status = "Book profit / avoid fresh buy."

    else:
        action = "WAIT"
        entry_status = "No trade. Wait for clean RSI setup."
        exit_status = "No exit signal."

    return {
        "main_signal": action,
        "divergence_type": main_divergence["kind"],
        "direction": direction,
        "rsi_zone": zone,
        "rsi_slope": slope["label"],
        "rsi_slope_value": slope["value"],
        "rsi_50_status": rsi_50,
        "failure_swing": failure["label"],
        "confirmation_5m": mtf["entry_5m"],
        "main_15m": main_divergence["signal"],
        "trend_30m": mtf["trend_30m"],
        "signal_grade": grade,
        "entry_status": entry_status,
        "exit_status": exit_status,
        "score": score,
        "reasons": reasons,
        "main_divergence": main_divergence,
        "mtf": mtf,
        "candle_confirmation": confirmation,
    }


def build_exit_advice(direction, targets):
    if direction == "bullish" and targets:
        return "Book 50% at Target 1, move SL to entry, hold balance for Target 2."

    if direction == "bearish" and targets:
        return "For holding, book partial profit at Target 1 and remaining near Target 2."

    return "No active trade. Wait for clean RSI setup."

def calculate_pro_market_context(candles):
    if not candles or len(candles) < 30:
        return {
            "trend_bias": "Not enough data",
            "ema20": None,
            "ema50": None,
            "atr": None,
            "atr_percent": None,
            "volatility": "Unknown",
            "avg_volume_20": None,
            "current_volume": None,
            "relative_volume": None,
            "volume_signal": "Unknown",
            "liquidity": "Unknown",
            "support": None,
            "resistance": None,
            "range_position": None,
            "range_status": "Unknown",
        }

    df = pd.DataFrame(candles)

    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()

    df["prev_close"] = df["close"].shift(1)

    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - df["prev_close"]).abs()
    tr3 = (df["low"] - df["prev_close"]).abs()

    df["tr"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["atr"] = df["tr"].rolling(14).mean()

    latest = df.iloc[-1]
    current_price = float(latest["close"])

    ema20 = round(float(latest["ema20"]), 2)
    ema50 = round(float(latest["ema50"]), 2)

    ema20_prev = float(df["ema20"].iloc[-5]) if len(df) >= 5 else ema20

    if current_price > ema20 > ema50 and ema20 > ema20_prev:
        trend_bias = "Bullish Trend"
    elif current_price < ema20 < ema50 and ema20 < ema20_prev:
        trend_bias = "Bearish Trend"
    else:
        trend_bias = "Sideways / Mixed Trend"

    atr = safe_float(latest["atr"], 0)
    atr = round(atr, 2) if atr else 0
    atr_percent = round((atr / current_price) * 100, 2) if current_price and atr else 0

    if atr_percent < 0.5:
        volatility = "Low Volatility"
    elif atr_percent <= 3:
        volatility = "Healthy Volatility"
    elif atr_percent <= 5:
        volatility = "High Volatility"
    else:
        volatility = "Very High Risk Volatility"

    current_volume = safe_float(latest.get("volume"), 0) or 0
    avg_volume_20 = float(df["volume"].tail(20).mean()) if "volume" in df.columns else 0

    relative_volume = round(current_volume / avg_volume_20, 2) if avg_volume_20 else 0

    if relative_volume >= 2:
        volume_signal = "Strong Volume Spike"
    elif relative_volume >= 1.2:
        volume_signal = "Above Average Volume"
    elif relative_volume >= 0.7:
        volume_signal = "Normal Volume"
    else:
        volume_signal = "Low Volume"

    if avg_volume_20 >= 1000000:
        liquidity = "High Liquidity"
    elif avg_volume_20 >= 300000:
        liquidity = "Good Liquidity"
    elif avg_volume_20 >= 100000:
        liquidity = "Average Liquidity"
    else:
        liquidity = "Low Liquidity"

    recent_high = round(float(df["high"].tail(30).max()), 2)
    recent_low = round(float(df["low"].tail(30).min()), 2)

    if recent_high != recent_low:
        range_position = round(((current_price - recent_low) / (recent_high - recent_low)) * 100, 2)
    else:
        range_position = 50

    if range_position <= 25:
        range_status = "Near Support Zone"
    elif range_position >= 75:
        range_status = "Near Resistance Zone"
    else:
        range_status = "Middle Range"

    return {
        "trend_bias": trend_bias,
        "ema20": ema20,
        "ema50": ema50,
        "atr": atr,
        "atr_percent": atr_percent,
        "volatility": volatility,
        "avg_volume_20": round(avg_volume_20, 2),
        "current_volume": round(current_volume, 2),
        "relative_volume": relative_volume,
        "volume_signal": volume_signal,
        "liquidity": liquidity,
        "support": recent_low,
        "resistance": recent_high,
        "range_position": range_position,
        "range_status": range_status,
    }


def calculate_pro_score(advanced, market_context, targets, current_price):
    score = advanced.get("score", 0)

    direction = advanced.get("direction", "neutral")
    trend_bias = market_context.get("trend_bias", "")
    relative_volume = market_context.get("relative_volume") or 0
    liquidity = market_context.get("liquidity", "")
    atr_percent = market_context.get("atr_percent") or 0
    range_position = market_context.get("range_position") or 50

    if direction == "bullish" and trend_bias == "Bullish Trend":
        score += 10

    if direction == "bearish" and trend_bias == "Bearish Trend":
        score += 10

    if relative_volume >= 2:
        score += 10
    elif relative_volume >= 1.2:
        score += 7
    elif relative_volume < 0.7:
        score -= 5

    if liquidity in ["High Liquidity", "Good Liquidity"]:
        score += 7
    elif liquidity == "Low Liquidity":
        score -= 8

    if 0.5 <= atr_percent <= 3:
        score += 7
    elif atr_percent > 5:
        score -= 10

    if direction == "bullish" and range_position <= 40:
        score += 6

    if direction == "bearish" and range_position >= 60:
        score += 6

    if targets and current_price:
        risk = targets.get("risk", 0)
        risk_percent = round((risk / current_price) * 100, 2) if current_price else 0

        if risk_percent <= 2.5:
            score += 7
        elif risk_percent > 5:
            score -= 7

    return max(0, min(100, int(score)))


def get_pro_grade(score):
    if score >= 85:
        return "A+ INSTITUTIONAL SETUP"
    if score >= 75:
        return "A HIGH QUALITY"
    if score >= 65:
        return "B GOOD SETUP"
    if score >= 50:
        return "C RISKY SETUP"
    return "D AVOID"


def get_tradability(pro_score, market_context, direction):
    liquidity = market_context.get("liquidity", "")
    volatility = market_context.get("volatility", "")

    if direction == "neutral":
        return "No Trade"

    if liquidity == "Low Liquidity":
        return "Avoid - Low Liquidity"

    if volatility == "Very High Risk Volatility":
        return "Avoid - High Volatility"

    if pro_score >= 85:
        return "High Quality Tradable"

    if pro_score >= 75:
        return "Tradable"

    if pro_score >= 65:
        return "Watchlist Only"

    return "Avoid / Wait"

def analyze_symbol_engine(symbol, chart_timeframe="15m"):
    selected_candles, backend_symbol, resolved_symbol = get_candles(symbol, chart_timeframe)
    candles_5m, _, _ = get_candles(symbol, "5m")
    candles_15m, _, _ = get_candles(symbol, "15m")
    candles_30m, _, _ = get_candles(symbol, "30m")

    if not selected_candles or not candles_15m:
        return None

    selected_candles, selected_rsi = calculate_rsi(selected_candles)
    candles_5m, _ = calculate_rsi(candles_5m)
    candles_15m, latest_rsi = calculate_rsi(candles_15m)
    candles_30m, _ = calculate_rsi(candles_30m)

    if not candles_15m:
        return None

    chart_divergence = detect_advanced_divergence(selected_candles)
    advanced = build_advanced_rsi_engine(candles_5m, candles_15m, candles_30m)

    latest_candle = selected_candles[-1]
    current_price = round(float(latest_candle["close"]), 2)

    direction = advanced["direction"]
    main_divergence = advanced["main_divergence"]

    entry = None
    stop_loss = None
    targets = None

    if direction == "bullish" and main_divergence.get("point2"):
        confirmation = advanced["candle_confirmation"]
        entry = confirmation["entry_price"] or current_price
        stop_loss = round(float(main_divergence["point2"]["price"]), 2)
        targets = calculate_buy_targets(entry, stop_loss)

    elif direction == "bearish" and main_divergence.get("point2"):
        confirmation = advanced["candle_confirmation"]
        entry = confirmation["entry_price"] or current_price
        stop_loss = round(float(main_divergence["point2"]["price"]), 2)
        targets = calculate_sell_targets(entry, stop_loss)

    market_context = calculate_pro_market_context(candles_15m)

    pro_score = calculate_pro_score(
        advanced=advanced,
        market_context=market_context,
        targets=targets,
        current_price=current_price
    )

    pro_grade = get_pro_grade(pro_score)
    tradability = get_tradability(pro_score, market_context, direction)

    advanced["pro_score"] = pro_score
    advanced["pro_grade"] = pro_grade
    advanced["market_context"] = market_context
    advanced["tradability"] = tradability

    exit_advice = build_exit_advice(direction, targets)

    return {
        "symbol": clean_symbol(resolved_symbol),
        "stock_name": get_stock_name(resolved_symbol),
        "backend_symbol": backend_symbol,
        "timeframe": chart_timeframe,
        "current_price": current_price,
        "latest_rsi": selected_rsi,
        "candles": selected_candles,
        "divergence": chart_divergence,
        "advanced": advanced,
        "market_context": market_context,
        "entry": entry,
        "stop_loss": stop_loss,
        "targets": targets,
        "signal_score": advanced["score"],
        "pro_score": pro_score,
        "pro_grade": pro_grade,
        "tradability": tradability,
        "exit_advice": exit_advice,
    }

@app.route("/api/stocks")
def api_stocks():
    query = request.args.get("q", "").strip().lower()

    if not query:
        return jsonify({"status": "success", "stocks": NSE_STOCKS[:50]})

    results = []

    for stock in NSE_STOCKS:
        if query in stock["symbol"].lower() or query in stock["name"].lower():
            results.append(stock)

    return jsonify({"status": "success", "stocks": results[:30]})



@app.route("/api/scanner")
def api_scanner():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Not logged in."})

    symbols_text = request.args.get("symbols", "").strip()
    grade_filter = request.args.get("grade", "ALL").strip().upper()
    direction_filter = request.args.get("direction", "ALL").strip().lower()
    only_tradable = request.args.get("tradable", "0").strip() == "1"

    if symbols_text:
        symbols = [clean_symbol(x) for x in symbols_text.split(",") if clean_symbol(x)]
    else:
        symbols = DEFAULT_SCAN_SYMBOLS

    symbols = symbols[:25]

    results = []
    failed = []

    for symbol in symbols:
        try:
            result = analyze_symbol_engine(symbol, "15m")

            if not result:
                failed.append(symbol)
                continue

            advanced = result["advanced"]
            market = result["market_context"]

            row = {
                "symbol": result["symbol"],
                "stock_name": result["stock_name"],
                "price": result["current_price"],
                "rsi": result["latest_rsi"],

                "direction": advanced["direction"],
                "main_signal": advanced["main_signal"],
                "divergence_type": advanced["divergence_type"],
                "rsi_zone": advanced["rsi_zone"],
                "rsi_slope": advanced["rsi_slope"],
                "rsi_50_status": advanced["rsi_50_status"],
                "confirmation_5m": advanced["confirmation_5m"],
                "trend_30m": advanced["trend_30m"],

                "signal_grade": advanced["signal_grade"],
                "score": advanced["score"],

                "pro_score": result["pro_score"],
                "pro_grade": result["pro_grade"],
                "tradability": result["tradability"],

                "trend_bias": market["trend_bias"],
                "ema20": market["ema20"],
                "ema50": market["ema50"],
                "atr": market["atr"],
                "atr_percent": market["atr_percent"],
                "volatility": market["volatility"],
                "relative_volume": market["relative_volume"],
                "volume_signal": market["volume_signal"],
                "liquidity": market["liquidity"],
                "support": market["support"],
                "resistance": market["resistance"],
                "range_position": market["range_position"],
                "range_status": market["range_status"],

                "entry_status": advanced["entry_status"],
                "exit_status": advanced["exit_status"],

                "entry": result["entry"],
                "stop_loss": result["stop_loss"],
                "target_1": result["targets"]["target_1"] if result["targets"] else None,
                "target_2": result["targets"]["target_2"] if result["targets"] else None,
                "exit_advice": result["exit_advice"],
            }

            if grade_filter != "ALL" and row["signal_grade"] != grade_filter:
                continue

            if direction_filter != "all" and row["direction"] != direction_filter:
                continue

            if only_tradable and row["tradability"] not in ["High Quality Tradable", "Tradable"]:
                continue

            results.append(row)

        except Exception as e:
            print("Scanner error:", symbol, e)
            failed.append(symbol)

    results.sort(key=lambda x: x["pro_score"], reverse=True)

    strong_count = len([x for x in results if x["signal_grade"] == "STRONG SETUP"])
    good_count = len([x for x in results if x["signal_grade"] == "GOOD SETUP"])
    risky_count = len([x for x in results if x["signal_grade"] == "RISKY SETUP"])
    tradable_count = len([x for x in results if x["tradability"] in ["High Quality Tradable", "Tradable"]])

    return jsonify({
        "status": "success",
        "results": results,
        "failed": failed,
        "summary": {
            "total_scanned": len(symbols),
            "total_loaded": len(results),
            "strong": strong_count,
            "good": good_count,
            "risky": risky_count,
            "tradable": tradable_count,
        },
        "server_time": datetime.now().strftime("%d-%m-%Y %I:%M:%S %p"),
        "refresh_seconds": 60,
    })

FAST_SCANNER_SYMBOLS = [
    "RELIANCE", "TATAMOTORS", "ZOMATO", "SBIN", "HDFCBANK",
    "INFY", "IREDA", "IRFC", "RVNL", "HAL", "BEL", "SUZLON",
    "JIOFIN", "TATAPOWER", "ADANIENT"
]


def safe_get(data, key, default="-"):
    try:
        value = data.get(key, default)
        if value is None:
            return default
        return value
    except Exception:
        return default


def build_big_trader_flags(result):
    advanced = result.get("advanced", {})
    market = result.get("market_context", {})

    flags = []

    liquidity = market.get("liquidity", "")
    volatility = market.get("volatility", "")
    rel_vol = market.get("relative_volume") or 0
    pro_score = result.get("pro_score") or advanced.get("score", 0)
    direction = advanced.get("direction", "neutral")

    if liquidity in ["High Liquidity", "Good Liquidity"]:
        flags.append("Liquidity OK")
    else:
        flags.append("Low liquidity risk")

    if rel_vol >= 2:
        flags.append("Volume spike")
    elif rel_vol >= 1.2:
        flags.append("Good volume")
    else:
        flags.append("Weak volume")

    if volatility == "Healthy Volatility":
        flags.append("Clean volatility")
    elif volatility in ["High Volatility", "Very High Risk Volatility"]:
        flags.append("Volatility risk")

    if pro_score >= 85:
        flags.append("A+ watchlist")
    elif pro_score >= 75:
        flags.append("High quality watchlist")

    if direction == "bullish":
        flags.append("Bullish setup")
    elif direction == "bearish":
        flags.append("Bearish setup")
    else:
        flags.append("No direction")

    return flags


@app.route("/api/scanner-default-symbols")
def api_scanner_default_symbols():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Not logged in"})

    return jsonify({
        "status": "success",
        "symbols": FAST_SCANNER_SYMBOLS
    })

def build_ai_priority_engine(result):
    advanced = result.get("advanced", {})
    market = result.get("market_context", {})
    targets = result.get("targets") or {}

    direction = advanced.get("direction", "neutral")
    pro_score = result.get("pro_score") or advanced.get("score", 0)

    tradability = result.get("tradability", "No Trade")
    liquidity = market.get("liquidity", "")
    volatility = market.get("volatility", "")
    volume_signal = market.get("volume_signal", "")
    relative_volume = market.get("relative_volume") or 0
    range_status = market.get("range_status", "")
    trend_bias = market.get("trend_bias", "")
    rsi_zone = advanced.get("rsi_zone", "")
    rsi_50_status = advanced.get("rsi_50_status", "")
    divergence_type = advanced.get("divergence_type", "")
    entry_status = advanced.get("entry_status", "")

    tags = []
    warnings = []
    reasons = []

    if direction == "bullish":
        tags.append("Bullish")
    elif direction == "bearish":
        tags.append("Bearish")
    else:
        tags.append("No Direction")

    if "Divergence" in divergence_type and divergence_type != "No Divergence":
        tags.append("RSI Divergence")
        reasons.append(divergence_type)

    if "Hidden" in divergence_type:
        tags.append("Hidden Divergence")

    if "Regular" in divergence_type:
        tags.append("Regular Divergence")

    if "Confirmed" in entry_status:
        tags.append("Entry Confirmed")
        reasons.append("Entry confirmation is active")
    elif "Wait for candle" in entry_status:
        tags.append("Near Entry")
        reasons.append(entry_status)

    if relative_volume >= 2:
        tags.append("Volume Spike")
        reasons.append("Strong relative volume")
    elif relative_volume < 0.7:
        warnings.append("Weak volume")

    if liquidity in ["High Liquidity", "Good Liquidity"]:
        tags.append("Liquid Stock")
    else:
        warnings.append("Low liquidity risk")

    if volatility == "Healthy Volatility":
        tags.append("Healthy Volatility")
    elif volatility in ["High Volatility", "Very High Risk Volatility"]:
        warnings.append("High volatility risk")

    if "Near Support" in range_status:
        tags.append("Near Support")
        reasons.append("Price is near support zone")

    if "Near Resistance" in range_status:
        tags.append("Near Resistance")

    if direction == "bullish" and trend_bias == "Bullish Trend":
        tags.append("Trend Support")
        reasons.append("Bullish trend bias supports setup")

    if direction == "bearish" and trend_bias == "Bearish Trend":
        tags.append("Trend Support")
        reasons.append("Bearish trend bias supports setup")

    if direction == "bullish" and "Above 50" in rsi_50_status:
        tags.append("RSI Above 50")

    if direction == "bearish" and "Below 50" in rsi_50_status:
        tags.append("RSI Below 50")

    risk_quality = "No Risk Data"

    current_price = result.get("current_price") or 0

    if targets and current_price:
        risk = targets.get("risk") or 0
        risk_percent = round((risk / current_price) * 100, 2) if current_price else 0

        if risk_percent <= 2:
            risk_quality = "Excellent Risk"
            tags.append("Low Risk")
        elif risk_percent <= 3.5:
            risk_quality = "Good Risk"
        elif risk_percent <= 5:
            risk_quality = "High Risk"
            warnings.append("Risk is high")
        else:
            risk_quality = "Avoid Risk"
            warnings.append("Risk is too high")
    else:
        risk_percent = None

    if pro_score >= 85:
        priority = "VERY HIGH"
    elif pro_score >= 75:
        priority = "HIGH"
    elif pro_score >= 65:
        priority = "MEDIUM"
    elif pro_score >= 50:
        priority = "LOW"
    else:
        priority = "AVOID"

    if direction == "neutral":
        ai_action = "No Trade"
    elif tradability in ["High Quality Tradable", "Tradable"] and "Entry Confirmed" in tags:
        ai_action = "Paper Trade Ready"
    elif tradability in ["High Quality Tradable", "Tradable"]:
        ai_action = "Watch Closely"
    elif pro_score >= 65:
        ai_action = "Watchlist Only"
    else:
        ai_action = "Avoid / Wait"

    if "Entry Confirmed" in tags:
        urgency = "Immediate Check"
    elif "Near Entry" in tags:
        urgency = "Near Entry"
    elif pro_score >= 75:
        urgency = "High Priority Watch"
    else:
        urgency = "Normal Watch"

    if not reasons:
        reasons.append("No strong professional setup yet")

    if not warnings:
        warnings.append("No major warning")

    ai_reason = ". ".join(reasons)
    risk_warning = ". ".join(warnings)

    return {
        "ai_action": ai_action,
        "priority": priority,
        "urgency": urgency,
        "tags": tags,
        "warnings": warnings,
        "ai_reason": ai_reason,
        "risk_warning": risk_warning,
        "risk_quality": risk_quality,
        "risk_percent": risk_percent,
    }

@app.route("/api/paper-live-pnl")
def api_paper_live_pnl():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Not logged in."})

    conn = get_paper_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM paper_trades
        ORDER BY id DESC
    """)

    rows = cur.fetchall()

    trades = []

    for row in rows:
        trade = calculate_trade_metrics(dict(row), live=True)
        trades.append(trade)

        if trade.get("status") == "OPEN":
            cur.execute("""
                UPDATE paper_trades
                SET current_price=?,
                    unrealized_pnl=?,
                    updated_at=?
                WHERE id=?
            """, (
                trade.get("current_price"),
                trade.get("unrealized_pnl"),
                paper_now(),
                trade.get("id")
            ))

    conn.commit()
    conn.close()

    summary = build_paper_summary(trades)
    ai_insights = build_trade_ai_insights(trades)

    return jsonify({
        "status": "success",
        "summary": summary,
        "trades": trades,
        "ai_insights": ai_insights,
        "server_time": paper_now()
    })


@app.route("/api/update-paper-trade-notes", methods=["POST"])
def api_update_paper_trade_notes():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Not logged in."})

    data = request.get_json(silent=True) or {}
    trade_id = data.get("id")

    if not trade_id:
        return jsonify({"status": "error", "message": "Trade id required."})

    conn = get_paper_conn()
    cur = conn.cursor()

    cur.execute("""
        UPDATE paper_trades
        SET notes=?,
            mistake_tags=?,
            updated_at=?
        WHERE id=?
    """, (
        data.get("notes", ""),
        data.get("mistake_tags", ""),
        paper_now(),
        trade_id
    ))

    conn.commit()
    conn.close()

    return jsonify({"status": "success", "message": "Notes updated."})

def build_paper_trade_plan(result, capital=10000, risk_amount=500):
    entry = result.get("entry")
    stop_loss = result.get("stop_loss")
    targets = result.get("targets") or {}

    if not entry or not stop_loss:
        return {
            "capital": capital,
            "risk_amount": risk_amount,
            "quantity": 0,
            "max_loss": 0,
            "target_1_profit": 0,
            "target_2_profit": 0,
            "status": "No valid entry/SL"
        }

    risk_per_share = abs(entry - stop_loss)

    if risk_per_share <= 0:
        return {
            "capital": capital,
            "risk_amount": risk_amount,
            "quantity": 0,
            "max_loss": 0,
            "target_1_profit": 0,
            "target_2_profit": 0,
            "status": "Invalid risk"
        }

    quantity = int(risk_amount / risk_per_share)

    if quantity <= 0:
        quantity = 1

    target_1 = targets.get("target_1")
    target_2 = targets.get("target_2")

    target_1_profit = round((target_1 - entry) * quantity, 2) if target_1 else 0
    target_2_profit = round((target_2 - entry) * quantity, 2) if target_2 else 0

    if result.get("advanced", {}).get("direction") == "bearish":
        target_1_profit = round((entry - target_1) * quantity, 2) if target_1 else 0
        target_2_profit = round((entry - target_2) * quantity, 2) if target_2 else 0

    max_loss = round(risk_per_share * quantity, 2)

    return {
        "capital": capital,
        "risk_amount": risk_amount,
        "quantity": quantity,
        "max_loss": max_loss,
        "target_1_profit": target_1_profit,
        "target_2_profit": target_2_profit,
        "status": "Paper trade plan ready"
    }

def build_advanced_position_plan(result, capital=10000, risk_value=500, risk_mode="amount"):
    entry = result.get("entry")
    stop_loss = result.get("stop_loss")
    targets = result.get("targets") or {}
    advanced = result.get("advanced", {}) or {}

    direction = advanced.get("direction", "neutral")

    try:
        capital = float(capital)
    except Exception:
        capital = 10000

    try:
        risk_value = float(risk_value)
    except Exception:
        risk_value = 500

    if risk_mode == "percent":
        risk_amount = capital * (risk_value / 100)
    else:
        risk_amount = risk_value

    if not entry or not stop_loss or direction == "neutral":
        return {
            "capital": round(capital, 2),
            "risk_mode": risk_mode,
            "risk_amount": round(risk_amount, 2),
            "quantity": 0,
            "capital_used": 0,
            "max_loss": 0,
            "risk_per_share": 0,
            "risk_percent_on_capital": 0,
            "target_1_profit": 0,
            "target_2_profit": 0,
            "target_1_rr": None,
            "target_2_rr": None,
            "position_quality": "No Trade",
            "exit_plan": "No valid entry and stop-loss found. Wait for confirmed setup.",
            "entry_plan": "Wait for confirmation.",
            "affordable": False,
        }

    entry = float(entry)
    stop_loss = float(stop_loss)

    target_1 = targets.get("target_1")
    target_2 = targets.get("target_2")

    risk_per_share = abs(entry - stop_loss)

    if risk_per_share <= 0:
        return {
            "capital": round(capital, 2),
            "risk_mode": risk_mode,
            "risk_amount": round(risk_amount, 2),
            "quantity": 0,
            "capital_used": 0,
            "max_loss": 0,
            "risk_per_share": 0,
            "risk_percent_on_capital": 0,
            "target_1_profit": 0,
            "target_2_profit": 0,
            "target_1_rr": None,
            "target_2_rr": None,
            "position_quality": "Invalid Risk",
            "exit_plan": "Invalid stop-loss distance.",
            "entry_plan": "Do not enter.",
            "affordable": False,
        }

    qty_by_risk = int(risk_amount / risk_per_share)
    qty_by_capital = int(capital / entry)

    quantity = min(qty_by_risk, qty_by_capital)

    if quantity < 1:
        quantity = 0

    capital_used = round(quantity * entry, 2)
    max_loss = round(quantity * risk_per_share, 2)
    risk_percent_on_capital = round((max_loss / capital) * 100, 2) if capital else 0

    if direction == "bullish":
        target_1_profit = round((float(target_1) - entry) * quantity, 2) if target_1 else 0
        target_2_profit = round((float(target_2) - entry) * quantity, 2) if target_2 else 0

        target_1_rr = round((float(target_1) - entry) / risk_per_share, 2) if target_1 else None
        target_2_rr = round((float(target_2) - entry) / risk_per_share, 2) if target_2 else None

        entry_plan = f"Buy only if price sustains above ₹{round(entry, 2)}."
        exit_plan = (
            f"Exit immediately if price closes below SL ₹{round(stop_loss, 2)}. "
            f"Book 50% near Target 1 ₹{target_1 if target_1 else '-'}, move SL to entry, "
            f"then trail remaining quantity for Target 2 ₹{target_2 if target_2 else '-'}."
        )

    elif direction == "bearish":
        target_1_profit = round((entry - float(target_1)) * quantity, 2) if target_1 else 0
        target_2_profit = round((entry - float(target_2)) * quantity, 2) if target_2 else 0

        target_1_rr = round((entry - float(target_1)) / risk_per_share, 2) if target_1 else None
        target_2_rr = round((entry - float(target_2)) / risk_per_share, 2) if target_2 else None

        entry_plan = f"Sell/Exit watch only if price breaks below ₹{round(entry, 2)}."
        exit_plan = (
            f"Exit bearish view if price moves above SL ₹{round(stop_loss, 2)}. "
            f"Book partial near Target 1 ₹{target_1 if target_1 else '-'} and remaining near Target 2 ₹{target_2 if target_2 else '-'}."
        )

    else:
        target_1_profit = 0
        target_2_profit = 0
        target_1_rr = None
        target_2_rr = None
        entry_plan = "No clean direction."
        exit_plan = "No trade."

    if quantity == 0:
        position_quality = "Capital Too Small"
        affordable = False
    elif risk_percent_on_capital <= 1:
        position_quality = "Very Safe Risk"
        affordable = True
    elif risk_percent_on_capital <= 2:
        position_quality = "Good Risk"
        affordable = True
    elif risk_percent_on_capital <= 3:
        position_quality = "Medium Risk"
        affordable = True
    else:
        position_quality = "High Risk"
        affordable = True

    return {
        "capital": round(capital, 2),
        "risk_mode": risk_mode,
        "risk_amount": round(risk_amount, 2),
        "quantity": quantity,
        "capital_used": capital_used,
        "max_loss": max_loss,
        "risk_per_share": round(risk_per_share, 2),
        "risk_percent_on_capital": risk_percent_on_capital,
        "target_1_profit": target_1_profit,
        "target_2_profit": target_2_profit,
        "target_1_rr": target_1_rr,
        "target_2_rr": target_2_rr,
        "position_quality": position_quality,
        "exit_plan": exit_plan,
        "entry_plan": entry_plan,
        "affordable": affordable,
    }

LOT_SIZE_MASTER = {
    # Cash equity default lot is 1 share.
    # F&O lot sizes change, so update here if you trade by lot.
    "RELIANCE": 1,
    "TATAMOTORS": 1,
    "ZOMATO": 1,
    "SBIN": 1,
    "HDFCBANK": 1,
    "INFY": 1,
    "IREDA": 1,
    "IRFC": 1,
    "RVNL": 1,
    "HAL": 1,
    "BEL": 1,
    "SUZLON": 1,
    "JIOFIN": 1,
    "TATAPOWER": 1,
    "ADANIENT": 1
}


def clean_for_lot(symbol):
    return str(symbol or "").upper().replace(".NS", "").replace(".BO", "").strip()


def get_lot_size(symbol):
    symbol = clean_for_lot(symbol)
    return int(LOT_SIZE_MASTER.get(symbol, 1))


def num(value, default=0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def text_is_bullish(text):
    text = str(text or "").lower()
    bullish_words = ["bullish", "buy", "positive", "above 50", "support", "uptrend", "long"]
    return any(w in text for w in bullish_words)


def text_is_bearish(text):
    text = str(text or "").lower()
    bearish_words = ["bearish", "sell", "exit", "negative", "below 50", "resistance", "downtrend", "short"]
    return any(w in text for w in bearish_words)


def get_recent_structure(candles, lookback=14):
    if not candles:
        return {
            "recent_high": 0,
            "recent_low": 0,
            "last_close": 0
        }

    recent = candles[-lookback:] if len(candles) >= lookback else candles

    highs = [num(x.get("high")) for x in recent if num(x.get("high")) > 0]
    lows = [num(x.get("low")) for x in recent if num(x.get("low")) > 0]
    closes = [num(x.get("close")) for x in recent if num(x.get("close")) > 0]

    return {
        "recent_high": round(max(highs), 2) if highs else 0,
        "recent_low": round(min(lows), 2) if lows else 0,
        "last_close": round(closes[-1], 2) if closes else 0
    }


def build_clean_trade_decision(
    result,
    qty_mode="auto",
    manual_qty=0,
    lots=1,
    capital=10000,
    risk_value=500,
    risk_mode="amount"
):
    advanced = result.get("advanced", {}) or {}
    market = result.get("market_context", {}) or advanced.get("market_context", {}) or {}

    symbol = clean_for_lot(result.get("symbol") or result.get("input_symbol") or "")
    candles = result.get("candles") or []

    current_price = (
        num(result.get("current_price")) or
        num(result.get("price")) or
        num(result.get("last_price"))
    )

    if not current_price:
        structure = get_recent_structure(candles)
        current_price = structure["last_close"]

    atr = num(market.get("atr"))
    atr_percent = num(market.get("atr_percent"))

    if not atr and current_price:
        atr = current_price * 0.008

    buffer = max(atr * 0.15, current_price * 0.001) if current_price else 0

    support = num(market.get("support"))
    resistance = num(market.get("resistance"))

    structure = get_recent_structure(candles)
    recent_high = structure["recent_high"]
    recent_low = structure["recent_low"]

    raw_direction = str(advanced.get("direction") or result.get("direction") or "neutral").lower()

    signal_texts = [
        advanced.get("main_signal"),
        advanced.get("confirmation_5m"),
        advanced.get("main_15m"),
        advanced.get("trend_30m"),
        advanced.get("rsi_50_status"),
        market.get("trend_bias"),
        advanced.get("divergence_type")
    ]

    bullish_votes = 0
    bearish_votes = 0

    if raw_direction == "bullish":
        bullish_votes += 2
    elif raw_direction == "bearish":
        bearish_votes += 2

    for text in signal_texts:
        if text_is_bullish(text):
            bullish_votes += 1
        if text_is_bearish(text):
            bearish_votes += 1

    conflict = False
    conflict_reason = ""

    if bullish_votes >= 2 and bearish_votes >= 2:
        conflict = True
        final_direction = "neutral"
        conflict_reason = "Mixed setup: bullish and bearish signals both found. No trade."
    elif bullish_votes > bearish_votes:
        final_direction = "bullish"
    elif bearish_votes > bullish_votes:
        final_direction = "bearish"
    else:
        final_direction = "neutral"
        conflict_reason = "No clean one-side setup."

    if final_direction == "bullish":
        trigger_price = recent_high + buffer if recent_high else current_price
        stop_base = support if support else recent_low
        stop_loss = stop_base - buffer if stop_base else trigger_price - atr

        if stop_loss >= trigger_price:
            stop_loss = trigger_price - max(atr, trigger_price * 0.01)

        risk_per_share = abs(trigger_price - stop_loss)

        target_1 = trigger_price + (risk_per_share * 1.5)
        target_2 = trigger_price + (risk_per_share * 2.5)

        if current_price >= trigger_price:
            trade_call = "BUY NOW / ENTRY ACTIVE"
            trigger_action = f"Buy active above ₹{round(trigger_price, 2)}"
        else:
            trade_call = "WAIT FOR BUY TRIGGER"
            trigger_action = f"Buy only above ₹{round(trigger_price, 2)}"

        exit_action = f"Exit if price closes below SL ₹{round(stop_loss, 2)}"

    elif final_direction == "bearish":
        trigger_price = recent_low - buffer if recent_low else current_price
        stop_base = resistance if resistance else recent_high
        stop_loss = stop_base + buffer if stop_base else trigger_price + atr

        if stop_loss <= trigger_price:
            stop_loss = trigger_price + max(atr, trigger_price * 0.01)

        risk_per_share = abs(stop_loss - trigger_price)

        target_1 = trigger_price - (risk_per_share * 1.5)
        target_2 = trigger_price - (risk_per_share * 2.5)

        if current_price <= trigger_price:
            trade_call = "SELL / EXIT NOW"
            trigger_action = f"Sell or exit active below ₹{round(trigger_price, 2)}"
        else:
            trade_call = "WAIT FOR SELL TRIGGER"
            trigger_action = f"Sell/exit only below ₹{round(trigger_price, 2)}"

        exit_action = f"Exit bearish view if price goes above SL ₹{round(stop_loss, 2)}"

    else:
        trigger_price = 0
        stop_loss = 0
        target_1 = 0
        target_2 = 0
        risk_per_share = 0
        trade_call = "NO TRADE"
        trigger_action = conflict_reason or "No clean trigger."
        exit_action = "No exit price because setup is not valid."

    try:
        capital = float(capital)
    except Exception:
        capital = 10000

    try:
        risk_value = float(risk_value)
    except Exception:
        risk_value = 500

    risk_amount = capital * (risk_value / 100) if risk_mode == "percent" else risk_value

    lot_size = get_lot_size(symbol)

    try:
        lots = int(float(lots))
    except Exception:
        lots = 1

    try:
        manual_qty = int(float(manual_qty))
    except Exception:
        manual_qty = 0

    if final_direction == "neutral" or not trigger_price or not risk_per_share:
        final_qty = 0
        qty_source = "No Trade"
    elif qty_mode == "lots":
        final_qty = max(0, lots * lot_size)
        qty_source = f"{lots} lot x {lot_size} shares"
    elif qty_mode == "manual":
        final_qty = max(0, manual_qty)
        qty_source = "Manual Qty"
    else:
        qty_by_risk = int(risk_amount / risk_per_share)
        qty_by_capital = int(capital / trigger_price) if trigger_price else 0
        final_qty = max(0, min(qty_by_risk, qty_by_capital))
        qty_source = "Auto Risk Based"

    capital_used = round(final_qty * trigger_price, 2) if final_qty and trigger_price else 0
    max_loss = round(final_qty * risk_per_share, 2) if final_qty and risk_per_share else 0

    if final_direction == "bullish":
        t1_profit = round((target_1 - trigger_price) * final_qty, 2)
        t2_profit = round((target_2 - trigger_price) * final_qty, 2)
    elif final_direction == "bearish":
        t1_profit = round((trigger_price - target_1) * final_qty, 2)
        t2_profit = round((trigger_price - target_2) * final_qty, 2)
    else:
        t1_profit = 0
        t2_profit = 0

    risk_percent = round((max_loss / capital) * 100, 2) if capital and max_loss else 0

    if final_direction == "neutral":
        ai_guidance = "Avoid this setup because signal direction is not clean."
        setup_focus = "NO TRADE"
    elif conflict:
        ai_guidance = "Avoid. Bullish and bearish signals are conflicting."
        setup_focus = "CONFLICT"
    elif final_direction == "bullish":
        ai_guidance = (
            f"Focus only on BUY side. Trigger is ₹{round(trigger_price, 2)}. "
            f"SL is ₹{round(stop_loss, 2)}. T1 ₹{round(target_1, 2)}, T2 ₹{round(target_2, 2)}."
        )
        setup_focus = "CLEAR BUY SETUP"
    else:
        ai_guidance = (
            f"Focus only on SELL/EXIT side. Trigger is ₹{round(trigger_price, 2)}. "
            f"SL is ₹{round(stop_loss, 2)}. T1 ₹{round(target_1, 2)}, T2 ₹{round(target_2, 2)}."
        )
        setup_focus = "CLEAR SELL SETUP"

    return {
        "setup_focus": setup_focus,
        "setup_valid": final_direction != "neutral" and not conflict,
        "final_direction": final_direction,
        "conflict": conflict,
        "conflict_reason": conflict_reason,

        "trade_call": trade_call,
        "trigger_action": trigger_action,
        "exit_action": exit_action,

        "final_entry": round(trigger_price, 2) if trigger_price else 0,
        "final_stop_loss": round(stop_loss, 2) if stop_loss else 0,
        "final_target_1": round(target_1, 2) if target_1 else 0,
        "final_target_2": round(target_2, 2) if target_2 else 0,

        "exit_price": round(stop_loss, 2) if stop_loss else 0,
        "risk_per_share": round(risk_per_share, 2) if risk_per_share else 0,

        "lot_size": lot_size,
        "qty_mode": qty_mode,
        "lots": lots,
        "qty_source": qty_source,
        "final_quantity": final_qty,

        "capital": round(capital, 2),
        "risk_amount": round(risk_amount, 2),
        "capital_used": capital_used,
        "max_loss": max_loss,
        "risk_percent": risk_percent,

        "target_1_profit": t1_profit,
        "target_2_profit": t2_profit,

        "ai_guidance": ai_guidance
    }

@app.route("/api/scanner-stock")
def api_scanner_stock():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Not logged in"})

    symbol = request.args.get("symbol", "").strip().upper()
    capital = request.args.get("capital", "10000")
    risk_value = request.args.get("risk_value", "500")
    risk_mode = request.args.get("risk_mode", "amount")

    if not symbol:
        return jsonify({
            "status": "error",
            "symbol": symbol,
            "message": "Symbol missing"
        })

    try:
        result = analyze_symbol_engine(symbol, "15m")
        capital = request.args.get("capital", "10000")
        risk_value = request.args.get("risk_value", "500")
        risk_mode = request.args.get("risk_mode", "amount")

        qty_mode = request.args.get("qty_mode", "auto")
        manual_qty = request.args.get("manual_qty", "0")
        lots = request.args.get("lots", "1")

        clean_decision = build_clean_trade_decision(
    result=result,
    qty_mode=qty_mode,
    manual_qty=manual_qty,
    lots=lots,
    capital=capital,
    risk_value=risk_value,
    risk_mode=risk_mode
)
        position_plan = build_advanced_position_plan(
    result=result,
    capital=capital,
    risk_value=risk_value,
    risk_mode=risk_mode
)

        if not result:
            return jsonify({
                "status": "error",
                "symbol": symbol,
                "message": "No data found"
            })

        advanced = result.get("advanced", {})
        market = result.get("market_context", {})
        targets = result.get("targets") or {}

        current_price = result.get("current_price") or 0
        risk = targets.get("risk") if targets else None

        risk_percent = None
        if risk and current_price:
            risk_percent = round((risk / current_price) * 100, 2)

        if risk_percent is None:
            risk_quality = "No RR"
        elif risk_percent <= 2:
            risk_quality = "Excellent risk"
        elif risk_percent <= 3.5:
            risk_quality = "Good risk"
        elif risk_percent <= 5:
            risk_quality = "High risk"
        else:
            risk_quality = "Avoid risk"

        pro_score = result.get("pro_score") or advanced.get("score", 0)
        pro_grade = result.get("pro_grade") or advanced.get("signal_grade", "AVOID / WAIT")
        tradability = result.get("tradability") or "Watch only"

        big_trader_flags = build_big_trader_flags(result)
        ai_engine = build_ai_priority_engine(result)
        paper_plan = build_paper_trade_plan(result)

        return jsonify({
            "status": "success",

            "symbol": result.get("symbol"),
            "stock_name": result.get("stock_name"),
            "price": result.get("current_price"),
            "rsi": result.get("latest_rsi"),

            "direction": advanced.get("direction", "neutral"),
            "main_signal": advanced.get("main_signal", "WAIT"),
            "divergence_type": advanced.get("divergence_type", "No Divergence"),
            "rsi_zone": advanced.get("rsi_zone", "-"),
            "rsi_slope": advanced.get("rsi_slope", "-"),
            "rsi_slope_value": advanced.get("rsi_slope_value", 0),
            "rsi_50_status": advanced.get("rsi_50_status", "-"),
            "failure_swing": advanced.get("failure_swing", "-"),
            "confirmation_5m": advanced.get("confirmation_5m", "-"),
            "main_15m": advanced.get("main_15m", "-"),
            "trend_30m": advanced.get("trend_30m", "-"),

            "signal_grade": advanced.get("signal_grade", "AVOID / WAIT"),
            "score": advanced.get("score", 0),

            "pro_score": pro_score,
            "pro_grade": pro_grade,
            "tradability": tradability,

            "trend_bias": market.get("trend_bias", "-"),
            "ema20": market.get("ema20"),
            "ema50": market.get("ema50"),
            "atr": market.get("atr"),
            "atr_percent": market.get("atr_percent"),
            "volatility": market.get("volatility", "-"),
            "relative_volume": market.get("relative_volume"),
            "volume_signal": market.get("volume_signal", "-"),
            "liquidity": market.get("liquidity", "-"),
            "support": market.get("support"),
            "resistance": market.get("resistance"),
            "range_position": market.get("range_position"),
            "range_status": market.get("range_status", "-"),

            "entry": result.get("entry"),
            "stop_loss": result.get("stop_loss"),
            "target_1": targets.get("target_1") if targets else None,
            "target_2": targets.get("target_2") if targets else None,
            "risk_percent": risk_percent,
            "risk_quality": risk_quality,

            "entry_status": advanced.get("entry_status", "-"),
            "exit_status": advanced.get("exit_status", "-"),
            "exit_advice": result.get("exit_advice", "-"),

            "big_trader_flags": big_trader_flags,
            "server_time": datetime.now().strftime("%d-%m-%Y %I:%M:%S %p"),
            "ai_action": ai_engine["ai_action"],
            "ai_priority": ai_engine["priority"],
            "ai_urgency": ai_engine["urgency"],
            "ai_tags": ai_engine["tags"],
            "ai_warnings": ai_engine["warnings"],
            "ai_reason": ai_engine["ai_reason"],
            "risk_warning": ai_engine["risk_warning"],
            "risk_quality": ai_engine["risk_quality"],
            "risk_percent": ai_engine["risk_percent"],

            "paper_capital": paper_plan["capital"],
            "paper_risk_amount": paper_plan["risk_amount"],
            "paper_quantity": paper_plan["quantity"],
            "paper_max_loss": paper_plan["max_loss"],
            "paper_target_1_profit": paper_plan["target_1_profit"],
            "paper_target_2_profit": paper_plan["target_2_profit"],
            "paper_status": paper_plan["status"],
            "position_capital": position_plan["capital"],
"position_risk_mode": position_plan["risk_mode"],
"position_risk_amount": position_plan["risk_amount"],
"position_quantity": position_plan["quantity"],
"position_capital_used": position_plan["capital_used"],
"position_max_loss": position_plan["max_loss"],
"position_risk_per_share": position_plan["risk_per_share"],
"position_risk_percent": position_plan["risk_percent_on_capital"],
"position_target_1_profit": position_plan["target_1_profit"],
"position_target_2_profit": position_plan["target_2_profit"],
"position_target_1_rr": position_plan["target_1_rr"],
"position_target_2_rr": position_plan["target_2_rr"],
"position_quality": position_plan["position_quality"],
"position_entry_plan": position_plan["entry_plan"],
"position_exit_plan": position_plan["exit_plan"],
"position_affordable": position_plan["affordable"],
"setup_focus": clean_decision["setup_focus"],
"setup_valid": clean_decision["setup_valid"],
"final_direction": clean_decision["final_direction"],
"conflict": clean_decision["conflict"],
"conflict_reason": clean_decision["conflict_reason"],

"trade_call": clean_decision["trade_call"],
"trigger_action": clean_decision["trigger_action"],
"exit_action": clean_decision["exit_action"],

"final_entry": clean_decision["final_entry"],
"final_stop_loss": clean_decision["final_stop_loss"],
"final_target_1": clean_decision["final_target_1"],
"final_target_2": clean_decision["final_target_2"],
"exit_price": clean_decision["exit_price"],

"lot_size": clean_decision["lot_size"],
"qty_mode": clean_decision["qty_mode"],
"lots": clean_decision["lots"],
"qty_source": clean_decision["qty_source"],
"final_quantity": clean_decision["final_quantity"],

"final_capital": clean_decision["capital"],
"final_risk_amount": clean_decision["risk_amount"],
"final_capital_used": clean_decision["capital_used"],
"final_max_loss": clean_decision["max_loss"],
"final_risk_percent": clean_decision["risk_percent"],
"final_risk_per_share": clean_decision["risk_per_share"],

"final_t1_profit": clean_decision["target_1_profit"],
"final_t2_profit": clean_decision["target_2_profit"],
"final_ai_guidance": clean_decision["ai_guidance"]
        })

    except Exception as e:
        print("Scanner stock error:", symbol, e)

        return jsonify({
            "status": "error",
            "symbol": symbol,
            "message": "Scanner failed for this stock"
        })

def build_local_chart_ai(payload):
    advanced = payload.get("advanced", {}) or {}
    market = payload.get("market_context", {}) or advanced.get("market_context", {}) or {}
    targets = payload.get("targets", {}) or {}

    symbol = payload.get("symbol", "-")
    price = payload.get("current_price", "-")
    rsi = payload.get("latest_rsi", "-")

    direction = advanced.get("direction", "neutral")
    signal = advanced.get("main_signal", "WAIT")
    score = advanced.get("pro_score") or advanced.get("score") or payload.get("pro_score") or payload.get("signal_score") or 0
    divergence = advanced.get("divergence_type", "No Divergence")
    rsi_zone = advanced.get("rsi_zone", "-")
    trend = market.get("trend_bias", "-")
    volume = market.get("volume_signal", "-")
    liquidity = market.get("liquidity", "-")
    volatility = market.get("volatility", "-")
    range_status = market.get("range_status", "-")

    entry = payload.get("entry")
    stop_loss = payload.get("stop_loss")
    t1 = targets.get("target_1")
    t2 = targets.get("target_2")

    if score >= 85:
        priority = "Very High Priority"
    elif score >= 75:
        priority = "High Priority"
    elif score >= 65:
        priority = "Medium Priority"
    elif score >= 50:
        priority = "Low Priority"
    else:
        priority = "Avoid / Wait"

    if direction == "bullish":
        bias = "Bullish watch"
    elif direction == "bearish":
        bias = "Bearish / exit watch"
    else:
        bias = "No clean trade direction"

    warnings = []

    if "Low" in str(liquidity):
        warnings.append("Liquidity is weak, avoid large quantity.")
    if "High" in str(volatility) or "Risk" in str(volatility):
        warnings.append("Volatility is high, use smaller risk.")
    if not entry or not stop_loss:
        warnings.append("Entry and stop-loss are not fully confirmed.")
    if score < 65:
        warnings.append("Setup score is not strong enough for aggressive action.")

    if not warnings:
        warnings.append("No major warning, but paper test first.")

    checklist = [
        "Check if candle closes beyond entry level.",
        "Confirm volume is not weak.",
        "Avoid chasing if price is already near target.",
        "Use stop-loss strictly in paper trading.",
        "Re-check 30m trend before final action."
    ]

    text = f"""
AI CHART SUMMARY

Stock: {symbol}
Current Price: ₹{price}
RSI: {rsi}
Bias: {bias}
Signal: {signal}
Priority: {priority}
Score: {score}/100

WHY THIS MATTERS
{symbol} is showing {divergence}. RSI zone is {rsi_zone}. Market trend is {trend}. Volume condition is {volume}. Liquidity is {liquidity}. Volatility condition is {volatility}. Price range status is {range_status}.

TRADE PLAN FOR PAPER TRADING
Entry: {entry if entry else "Wait for confirmation"}
Stop Loss: {stop_loss if stop_loss else "Not available"}
Target 1: {t1 if t1 else "Not available"}
Target 2: {t2 if t2 else "Not available"}

RISK WARNING
- {warnings[0]}

CHECKLIST
- {checklist[0]}
- {checklist[1]}
- {checklist[2]}
- {checklist[3]}
- {checklist[4]}
"""

    return text.strip()


@app.route("/api/ai-chart-analysis", methods=["POST"])
def api_ai_chart_analysis():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Not logged in."})

    payload = request.get_json(silent=True) or {}

    local_text = build_local_chart_ai(payload)

    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-5.5")

    if not api_key or OpenAI is None:
        return jsonify({
            "status": "success",
            "provider": "local_ai",
            "ai_text": local_text
        })

    try:
        compact_payload = {
            "symbol": payload.get("symbol"),
            "price": payload.get("current_price"),
            "rsi": payload.get("latest_rsi"),
            "advanced": payload.get("advanced"),
            "market_context": payload.get("market_context"),
            "entry": payload.get("entry"),
            "stop_loss": payload.get("stop_loss"),
            "targets": payload.get("targets"),
            "timeframe": payload.get("timeframe"),
        }

        client = OpenAI(api_key=api_key)

        response = client.responses.create(
            model=model,
            instructions=(
                "You are an AI chart analyst for educational paper trading only. "
                "Do not give guaranteed profit claims. Be fast, practical and concise. "
                "Analyze RSI divergence, trend, volume, liquidity, volatility, entry, stop loss and targets. "
                "Return a trader-friendly analysis with headings: AI Summary, Setup Quality, Entry Plan, Risk Warning, Checklist."
            ),
            input=json.dumps(compact_payload, default=str)
        )

        return jsonify({
            "status": "success",
            "provider": "openai",
            "ai_text": response.output_text
        })

    except Exception as e:
        print("AI chart error:", e)

        return jsonify({
            "status": "success",
            "provider": "local_ai_fallback",
            "ai_text": local_text
        })

def fetch_live_price(symbol):
    resolved_symbol = resolve_input_to_symbol(symbol)
    candidates = build_yahoo_candidates(resolved_symbol)

    for yahoo_symbol in candidates:
        cache_key = f"live_{yahoo_symbol}"
        now = time.time()

        if cache_key in LIVE_PRICE_CACHE:
            cached = LIVE_PRICE_CACHE[cache_key]
            if now - cached["created_at"] <= LIVE_PRICE_CACHE_SECONDS:
                return cached["data"]

        try:
            ticker = yf.Ticker(yahoo_symbol)

            price = None

            try:
                fast_info = ticker.fast_info
                if isinstance(fast_info, dict):
                    price = fast_info.get("last_price") or fast_info.get("regular_market_price")
                else:
                    price = getattr(fast_info, "last_price", None)
            except Exception:
                price = None

            if not price:
                hist = ticker.history(period="1d", interval="1m")

                if hist is not None and not hist.empty:
                    price = float(hist["Close"].dropna().iloc[-1])

            if price and price > 0:
                live_data = {
                    "symbol": clean_symbol(resolved_symbol),
                    "backend_symbol": yahoo_symbol,
                    "price": round(float(price), 2),
                    "server_time": datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
                }

                LIVE_PRICE_CACHE[cache_key] = {
                    "created_at": now,
                    "data": live_data
                }

                return live_data

        except Exception as e:
            print("Live price error:", yahoo_symbol, e)

    return None


@app.route("/api/live-price")
def api_live_price():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Not logged in."})

    symbol = request.args.get("symbol", "").strip()

    if not symbol:
        return jsonify({"status": "error", "message": "Symbol required."})

    live_data = fetch_live_price(symbol)

    if not live_data:
        return jsonify({
            "status": "error",
            "message": "Live price not available."
        })

    live_data["status"] = "success"
    return jsonify(live_data)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PAPER_DB_PATH = os.path.join(BASE_DIR, "paper_trading_pro.db")


def get_paper_conn():
    conn = sqlite3.connect(PAPER_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_paper_db():
    conn = get_paper_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS paper_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            updated_at TEXT,

            symbol TEXT,
            stock_name TEXT,
            timeframe TEXT,
            direction TEXT,
            signal TEXT,
            setup_type TEXT,

            entry REAL,
            stop_loss REAL,
            target_1 REAL,
            target_2 REAL,
            quantity INTEGER,

            capital REAL,
            capital_used REAL,
            risk_amount REAL,
            risk_per_share REAL,
            max_loss REAL,

            t1_profit REAL,
            t2_profit REAL,
            t1_rr REAL,
            t2_rr REAL,

            pro_score REAL,
            ai_priority TEXT,
            ai_reason TEXT,
            entry_plan TEXT,
            exit_plan TEXT,

            status TEXT DEFAULT 'OPEN',
            current_price REAL,
            unrealized_pnl REAL,
            realized_pnl REAL,

            exit_price REAL,
            exit_reason TEXT,
            result TEXT,

            notes TEXT,
            mistake_tags TEXT
        )
    """)

    conn.commit()
    conn.close()


def paper_now():
    return datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")


def paper_float(value, default=0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def paper_int(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def get_safe_live_price(symbol):
    try:
        if "fetch_live_price" in globals():
            live = fetch_live_price(symbol)
            if live and live.get("price"):
                return paper_float(live.get("price"))
    except Exception as e:
        print("paper live price error:", e)

    return None


def calculate_trade_metrics(trade, live=True):
    t = dict(trade)

    direction = (t.get("direction") or "neutral").lower()
    entry = paper_float(t.get("entry"))
    stop_loss = paper_float(t.get("stop_loss"))
    target_1 = paper_float(t.get("target_1"))
    target_2 = paper_float(t.get("target_2"))
    qty = paper_int(t.get("quantity"))

    current_price = paper_float(t.get("current_price"))

    if live and t.get("status") == "OPEN":
        live_price = get_safe_live_price(t.get("symbol"))
        if live_price:
            current_price = live_price

    if not current_price:
        current_price = entry

    if direction == "bullish":
        unrealized = round((current_price - entry) * qty, 2)
    elif direction == "bearish":
        unrealized = round((entry - current_price) * qty, 2)
    else:
        unrealized = 0

    live_alert = "Tracking"

    if t.get("status") == "OPEN":
        if direction == "bullish":
            if stop_loss and current_price <= stop_loss:
                live_alert = "SL TOUCHED"
            elif target_2 and current_price >= target_2:
                live_alert = "TARGET 2 TOUCHED"
            elif target_1 and current_price >= target_1:
                live_alert = "TARGET 1 TOUCHED"
            elif entry and current_price >= entry:
                live_alert = "ENTRY ACTIVE"
            else:
                live_alert = "WAITING"

        elif direction == "bearish":
            if stop_loss and current_price >= stop_loss:
                live_alert = "SL TOUCHED"
            elif target_2 and current_price <= target_2:
                live_alert = "TARGET 2 TOUCHED"
            elif target_1 and current_price <= target_1:
                live_alert = "TARGET 1 TOUCHED"
            elif entry and current_price <= entry:
                live_alert = "ENTRY ACTIVE"
            else:
                live_alert = "WAITING"

    risk_per_share = abs(entry - stop_loss) if entry and stop_loss else 0
    capital_used = round(entry * qty, 2) if entry and qty else 0
    max_loss = round(risk_per_share * qty, 2) if risk_per_share and qty else 0

    t["current_price"] = round(current_price, 2)
    t["unrealized_pnl"] = unrealized
    t["live_alert"] = live_alert
    t["capital_used"] = round(paper_float(t.get("capital_used"), capital_used), 2)
    t["max_loss"] = round(paper_float(t.get("max_loss"), max_loss), 2)

    return t


def build_paper_summary(trades):
    open_trades = [x for x in trades if x.get("status") == "OPEN"]
    closed_trades = [x for x in trades if x.get("status") == "CLOSED"]

    realized = round(sum(paper_float(x.get("realized_pnl")) for x in closed_trades), 2)
    unrealized = round(sum(paper_float(x.get("unrealized_pnl")) for x in open_trades), 2)

    wins = [x for x in closed_trades if paper_float(x.get("realized_pnl")) > 0]
    losses = [x for x in closed_trades if paper_float(x.get("realized_pnl")) < 0]

    win_rate = round((len(wins) / len(closed_trades)) * 100, 2) if closed_trades else 0

    avg_win = round(sum(paper_float(x.get("realized_pnl")) for x in wins) / len(wins), 2) if wins else 0
    avg_loss = round(sum(paper_float(x.get("realized_pnl")) for x in losses) / len(losses), 2) if losses else 0

    return {
        "open_count": len(open_trades),
        "closed_count": len(closed_trades),
        "total_count": len(trades),
        "realized_pnl": realized,
        "unrealized_pnl": unrealized,
        "net_pnl": round(realized + unrealized, 2),
        "win_rate": win_rate,
        "wins": len(wins),
        "losses": len(losses),
        "avg_win": avg_win,
        "avg_loss": avg_loss
    }


def build_trade_ai_insights(trades):
    if not trades:
        return "No trades saved yet. Save scanner signals to start AI performance tracking."

    summary = build_paper_summary(trades)

    open_count = summary["open_count"]
    closed_count = summary["closed_count"]
    win_rate = summary["win_rate"]
    net_pnl = summary["net_pnl"]

    best = None
    worst = None

    closed = [x for x in trades if x.get("status") == "CLOSED"]

    if closed:
        best = max(closed, key=lambda x: paper_float(x.get("realized_pnl")))
        worst = min(closed, key=lambda x: paper_float(x.get("realized_pnl")))

    lines = []

    lines.append(f"AI Performance Summary: You have {open_count} open trades and {closed_count} closed trades.")
    lines.append(f"Current paper net P&L is ₹{net_pnl}. Win rate is {win_rate}%.")

    if best:
        lines.append(f"Best trade: {best.get('symbol')} with ₹{best.get('realized_pnl')} profit.")

    if worst:
        lines.append(f"Weakest trade: {worst.get('symbol')} with ₹{worst.get('realized_pnl')} result.")

    if win_rate >= 60 and closed_count >= 5:
        lines.append("Your setup selection is performing well. Continue tracking the same rules.")
    elif closed_count >= 5:
        lines.append("Win rate is still weak. Avoid low-score setups and focus only on high-priority scanner signals.")
    else:
        lines.append("Need more closed trades before judging strategy quality.")

    return " ".join(lines)


init_paper_db()


@app.route("/paper-trading")
def paper_trading():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    return render_template("paper_trading.html")


@app.route("/api/analyze-stock")
def api_analyze_stock():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Not logged in."})

    symbol = request.args.get("symbol", "").strip().upper()
    tf = request.args.get("tf", "15m").strip()

    if not symbol:
        return jsonify({"status": "error", "message": "Symbol required."})

    if tf not in ["5m", "15m", "30m"]:
        tf = "15m"

    try:
        result = analyze_symbol_engine(symbol, tf)

        if not result:
            return jsonify({
                "status": "error",
                "message": "No data found for this stock."
            })

        if result.get("status") == "error":
            return jsonify(result)

        clean_decision = build_clean_trade_decision(
            result=result,
            qty_mode=request.args.get("qty_mode", "auto"),
            manual_qty=request.args.get("manual_qty", "0"),
            lots=request.args.get("lots", "1"),
            capital=request.args.get("capital", "10000"),
            risk_value=request.args.get("risk_value", "500"),
            risk_mode=request.args.get("risk_mode", "amount")
        )

        result["clean_decision"] = clean_decision

        # Also expose clean decision at top level so Chart View and Scanner can use same engine.
        result.update({
            "setup_focus": clean_decision["setup_focus"],
            "setup_valid": clean_decision["setup_valid"],
            "final_direction": clean_decision["final_direction"],
            "conflict": clean_decision["conflict"],
            "conflict_reason": clean_decision["conflict_reason"],

            "trade_call": clean_decision["trade_call"],
            "trigger_action": clean_decision["trigger_action"],
            "exit_action": clean_decision["exit_action"],

            "final_entry": clean_decision["final_entry"],
            "final_stop_loss": clean_decision["final_stop_loss"],
            "final_target_1": clean_decision["final_target_1"],
            "final_target_2": clean_decision["final_target_2"],
            "exit_price": clean_decision["exit_price"],

            "lot_size": clean_decision["lot_size"],
            "qty_mode": clean_decision["qty_mode"],
            "lots": clean_decision["lots"],
            "qty_source": clean_decision["qty_source"],
            "final_quantity": clean_decision["final_quantity"],

            "final_capital": clean_decision["capital"],
            "final_risk_amount": clean_decision["risk_amount"],
            "final_capital_used": clean_decision["capital_used"],
            "final_max_loss": clean_decision["max_loss"],
            "final_risk_percent": clean_decision["risk_percent"],
            "final_risk_per_share": clean_decision["risk_per_share"],

            "final_t1_profit": clean_decision["target_1_profit"],
            "final_t2_profit": clean_decision["target_2_profit"],
            "final_ai_guidance": clean_decision["ai_guidance"],
            "status": "success"
        })

        return jsonify(result)

    except Exception as e:
        print("Analyze stock error:", e)
        return jsonify({
            "status": "error",
            "message": str(e)
        })


@app.route("/api/save-paper-trade", methods=["POST"])
def api_save_paper_trade():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Not logged in."})

    data = request.get_json(silent=True) or {}

    symbol = str(data.get("symbol", "")).upper().replace(".NS", "").replace(".BO", "").strip()

    if not symbol:
        return jsonify({"status": "error", "message": "Symbol required."})

    direction = str(
        data.get("final_direction") or
        data.get("direction") or
        data.get("signal_direction") or
        "neutral"
    ).lower()

    entry = paper_float(
        data.get("final_entry") or
        data.get("trigger_price") or
        data.get("entry")
    )

    stop_loss = paper_float(
        data.get("final_stop_loss") or
        data.get("stop_loss")
    )

    target_1 = paper_float(
        data.get("final_target_1") or
        data.get("target_1")
    )

    target_2 = paper_float(
        data.get("final_target_2") or
        data.get("target_2")
    )

    quantity = paper_int(
        data.get("final_quantity") or
        data.get("position_quantity") or
        data.get("quantity")
    )

    capital = paper_float(
        data.get("final_capital") or
        data.get("position_capital") or
        data.get("capital"),
        10000
    )

    capital_used = paper_float(
        data.get("final_capital_used") or
        data.get("position_capital_used") or
        data.get("capital_used")
    )

    risk_amount = paper_float(
        data.get("final_risk_amount") or
        data.get("position_risk_amount") or
        data.get("risk_amount")
    )

    risk_per_share = paper_float(
        data.get("final_risk_per_share") or
        data.get("position_risk_per_share") or
        abs(entry - stop_loss)
    )

    max_loss = paper_float(
        data.get("final_max_loss") or
        data.get("position_max_loss") or
        data.get("max_loss")
    )

    if not capital_used and entry and quantity:
        capital_used = round(entry * quantity, 2)

    if not max_loss and risk_per_share and quantity:
        max_loss = round(risk_per_share * quantity, 2)

    if not entry or not stop_loss or not quantity:
        return jsonify({
            "status": "error",
            "message": "Trade not saved. Entry, Stop Loss and Quantity are required."
        })

    conn = get_paper_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO paper_trades (
            created_at, updated_at,
            symbol, stock_name, timeframe, direction, signal, setup_type,
            entry, stop_loss, target_1, target_2, quantity,
            capital, capital_used, risk_amount, risk_per_share, max_loss,
            t1_profit, t2_profit, t1_rr, t2_rr,
            pro_score, ai_priority, ai_reason, entry_plan, exit_plan,
            status, current_price, unrealized_pnl, realized_pnl,
            exit_price, exit_reason, result, notes, mistake_tags
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        paper_now(), paper_now(),
        symbol,
        data.get("stock_name", ""),
        data.get("timeframe", "15m"),
        direction,
        data.get("main_signal") or data.get("signal") or data.get("trade_call") or "",
        data.get("divergence_type") or data.get("setup_type") or data.get("setup_focus") or "",
        entry,
        stop_loss,
        target_1,
        target_2,
        quantity,
        capital,
        capital_used,
        risk_amount,
        risk_per_share,
        max_loss,
        paper_float(data.get("final_t1_profit") or data.get("position_target_1_profit") or data.get("t1_profit")),
        paper_float(data.get("final_t2_profit") or data.get("position_target_2_profit") or data.get("t2_profit")),
        paper_float(data.get("position_target_1_rr") or data.get("t1_rr")),
        paper_float(data.get("position_target_2_rr") or data.get("t2_rr")),
        paper_float(data.get("pro_score")),
        data.get("ai_priority", ""),
        data.get("final_ai_guidance") or data.get("ai_reason", ""),
        data.get("trigger_action") or data.get("position_entry_plan") or data.get("entry_plan") or "",
        data.get("exit_action") or data.get("position_exit_plan") or data.get("exit_plan") or "",
        "OPEN",
        paper_float(data.get("price") or data.get("current_price") or entry),
        0,
        0,
        0,
        "",
        "",
        data.get("notes", ""),
        data.get("mistake_tags", "")
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "status": "success",
        "message": "Clean decision trade saved to Paper Trading Pro."
    })


@app.route("/api/paper-trades")
def api_paper_trades():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Not logged in."})

    live = request.args.get("live", "1") == "1"

    conn = get_paper_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM paper_trades
        ORDER BY id DESC
    """)

    rows = cur.fetchall()
    conn.close()

    trades = []

    for row in rows:
        trade = calculate_trade_metrics(dict(row), live=live)
        trades.append(trade)

    summary = build_paper_summary(trades)
    ai_insights = build_trade_ai_insights(trades)

    return jsonify({
        "status": "success",
        "trades": trades,
        "summary": summary,
        "ai_insights": ai_insights
    })


@app.route("/api/close-paper-trade", methods=["POST"])
def api_close_paper_trade():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Not logged in."})

    data = request.get_json(silent=True) or {}

    trade_id = data.get("id")

    if not trade_id:
        return jsonify({"status": "error", "message": "Trade id required."})

    conn = get_paper_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM paper_trades WHERE id=?", (trade_id,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return jsonify({"status": "error", "message": "Trade not found."})

    trade = dict(row)

    exit_price = paper_float(data.get("exit_price"))

    if not exit_price:
        exit_price = get_safe_live_price(trade.get("symbol"))

        if not exit_price:
            conn.close()
            return jsonify({
                "status": "error",
                "message": "Live exit price not available. Enter exit price manually. No hypothetical exit used."
        })
    direction = (trade.get("direction") or "neutral").lower()
    entry = paper_float(trade.get("entry"))
    qty = paper_int(trade.get("quantity"))

    if direction == "bullish":
        realized = round((exit_price - entry) * qty, 2)
    elif direction == "bearish":
        realized = round((entry - exit_price) * qty, 2)
    else:
        realized = 0

    if realized > 0:
        result = "WIN"
    elif realized < 0:
        result = "LOSS"
    else:
        result = "BREAKEVEN"

    cur.execute("""
        UPDATE paper_trades
        SET updated_at=?,
            status='CLOSED',
            exit_price=?,
            realized_pnl=?,
            unrealized_pnl=0,
            exit_reason=?,
            result=?,
            notes=?,
            mistake_tags=?
        WHERE id=?
    """, (
        paper_now(),
        exit_price,
        realized,
        data.get("exit_reason", "Manual Exit"),
        result,
        data.get("notes", trade.get("notes", "")),
        data.get("mistake_tags", trade.get("mistake_tags", "")),
        trade_id
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "status": "success",
        "message": "Trade closed.",
        "realized_pnl": realized,
        "result": result
    })


@app.route("/api/delete-paper-trade", methods=["POST"])
def api_delete_paper_trade():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Not logged in."})

    data = request.get_json(silent=True) or {}
    trade_id = data.get("id")

    if not trade_id:
        return jsonify({"status": "error", "message": "Trade id required."})

    conn = get_paper_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM paper_trades WHERE id=?", (trade_id,))
    conn.commit()
    conn.close()

    return jsonify({"status": "success", "message": "Trade deleted."})


@app.route("/api/export-paper-trades")
def api_export_paper_trades():
    if not session.get("logged_in"):
        return "Not logged in", 401

    conn = get_paper_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM paper_trades ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)

    headers = [
        "id", "created_at", "symbol", "direction", "signal", "setup_type",
        "entry", "stop_loss", "target_1", "target_2", "quantity",
        "capital_used", "max_loss", "status", "exit_price",
        "realized_pnl", "result", "notes", "mistake_tags"
    ]

    writer.writerow(headers)

    for row in rows:
        writer.writerow([row[h] for h in headers])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=paper_trades.csv"}
    )

ALERT_DB_PATH = os.path.join(BASE_DIR, "alerts_pro.db")


def get_alert_conn():
    conn = sqlite3.connect(ALERT_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_alert_db():
    conn = get_alert_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS alert_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            updated_at TEXT,
            symbol TEXT,
            alert_type TEXT,
            condition_type TEXT,
            trigger_value REAL,
            message TEXT,
            is_active INTEGER DEFAULT 1,
            last_price REAL,
            last_rsi REAL,
            last_status TEXT,
            triggered_count INTEGER DEFAULT 0,
            last_triggered_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def alert_now():
    return datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")


def alert_float(value, default=0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def get_alert_market_data(symbol):
    price = None
    rsi = None
    pro_score = None

    try:
        if "fetch_live_price" in globals():
            live = fetch_live_price(symbol)
            if live and live.get("price"):
                price = float(live.get("price"))
    except Exception:
        price = None

    try:
        result = analyze_symbol_engine(symbol, "15m")
        if result:
            price = price or result.get("current_price")
            rsi = result.get("latest_rsi")

            adv = result.get("advanced", {}) or {}
            pro_score = adv.get("pro_score") or result.get("pro_score") or adv.get("score")
    except Exception as e:
        print("alert market data error:", e)

    return {
        "price": alert_float(price),
        "rsi": alert_float(rsi),
        "pro_score": alert_float(pro_score)
    }


def check_single_alert(alert):
    symbol = alert["symbol"]
    alert_type = alert["alert_type"]
    condition_type = alert["condition_type"]
    trigger_value = alert_float(alert["trigger_value"])

    market = get_alert_market_data(symbol)

    price = market["price"]
    rsi = market["rsi"]
    pro_score = market["pro_score"]

    triggered = False
    reason = "Waiting"

    if alert_type == "price":
        if condition_type == "above" and price >= trigger_value:
            triggered = True
            reason = f"Price above ₹{trigger_value}"

        elif condition_type == "below" and price <= trigger_value:
            triggered = True
            reason = f"Price below ₹{trigger_value}"

        else:
            reason = f"Price ₹{price}, waiting for {condition_type} ₹{trigger_value}"

    elif alert_type == "rsi":
        if condition_type == "above" and rsi >= trigger_value:
            triggered = True
            reason = f"RSI above {trigger_value}"

        elif condition_type == "below" and rsi <= trigger_value:
            triggered = True
            reason = f"RSI below {trigger_value}"

        else:
            reason = f"RSI {rsi}, waiting for {condition_type} {trigger_value}"

    elif alert_type == "score":
        if pro_score >= trigger_value:
            triggered = True
            reason = f"Pro score above {trigger_value}"

        else:
            reason = f"Pro score {pro_score}, waiting for {trigger_value}+"

    return {
        "triggered": triggered,
        "reason": reason,
        "price": price,
        "rsi": rsi,
        "pro_score": pro_score
    }


init_alert_db()


@app.route("/alerts")
def alerts_page():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    return render_template("alerts.html")


@app.route("/api/create-alert", methods=["POST"])
def api_create_alert():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Not logged in."})

    data = request.get_json(silent=True) or {}

    symbol = str(data.get("symbol", "")).upper().replace(".NS", "").replace(".BO", "").strip()

    if not symbol:
        return jsonify({"status": "error", "message": "Symbol required."})

    conn = get_alert_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO alert_rules (
            created_at, updated_at, symbol, alert_type, condition_type,
            trigger_value, message, is_active, last_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
    """, (
        alert_now(),
        alert_now(),
        symbol,
        data.get("alert_type", "price"),
        data.get("condition_type", "above"),
        alert_float(data.get("trigger_value")),
        data.get("message", ""),
        "Created"
    ))

    conn.commit()
    conn.close()

    return jsonify({"status": "success", "message": "Alert created."})


@app.route("/api/alerts")
def api_alerts():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Not logged in."})

    conn = get_alert_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM alert_rules
        ORDER BY id DESC
    """)

    rows = [dict(x) for x in cur.fetchall()]
    conn.close()

    return jsonify({"status": "success", "alerts": rows})


@app.route("/api/check-alerts")
def api_check_alerts():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Not logged in."})

    conn = get_alert_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM alert_rules
        WHERE is_active=1
        ORDER BY id DESC
    """)

    rows = cur.fetchall()

    checked = []
    triggered_list = []

    for row in rows:
        alert = dict(row)

        result = check_single_alert(alert)

        triggered_count = int(alert.get("triggered_count") or 0)

        if result["triggered"]:
            triggered_count += 1
            triggered_list.append({
                "id": alert["id"],
                "symbol": alert["symbol"],
                "message": alert["message"],
                "reason": result["reason"],
                "price": result["price"],
                "rsi": result["rsi"],
                "pro_score": result["pro_score"]
            })

        cur.execute("""
            UPDATE alert_rules
            SET updated_at=?,
                last_price=?,
                last_rsi=?,
                last_status=?,
                triggered_count=?,
                last_triggered_at=?
            WHERE id=?
        """, (
            alert_now(),
            result["price"],
            result["rsi"],
            result["reason"],
            triggered_count,
            alert_now() if result["triggered"] else alert.get("last_triggered_at"),
            alert["id"]
        ))

        alert["last_price"] = result["price"]
        alert["last_rsi"] = result["rsi"]
        alert["last_status"] = result["reason"]
        alert["triggered_count"] = triggered_count
        alert["triggered"] = result["triggered"]
        alert["pro_score"] = result["pro_score"]

        checked.append(alert)

    conn.commit()
    conn.close()

    return jsonify({
        "status": "success",
        "alerts": checked,
        "triggered": triggered_list,
        "server_time": alert_now()
    })


@app.route("/api/toggle-alert", methods=["POST"])
def api_toggle_alert():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Not logged in."})

    data = request.get_json(silent=True) or {}
    alert_id = data.get("id")

    conn = get_alert_conn()
    cur = conn.cursor()

    cur.execute("SELECT is_active FROM alert_rules WHERE id=?", (alert_id,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return jsonify({"status": "error", "message": "Alert not found."})

    new_status = 0 if row["is_active"] else 1

    cur.execute("""
        UPDATE alert_rules
        SET is_active=?, updated_at=?
        WHERE id=?
    """, (new_status, alert_now(), alert_id))

    conn.commit()
    conn.close()

    return jsonify({"status": "success", "message": "Alert updated."})


@app.route("/api/delete-alert", methods=["POST"])
def api_delete_alert():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Not logged in."})

    data = request.get_json(silent=True) or {}
    alert_id = data.get("id")

    conn = get_alert_conn()
    cur = conn.cursor()

    cur.execute("DELETE FROM alert_rules WHERE id=?", (alert_id,))

    conn.commit()
    conn.close()

    return jsonify({"status": "success", "message": "Alert deleted."})

@app.route("/trade-history")
def trade_history_page():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template("trade_history.html")


@app.route("/watchlist")
def watchlist_page():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template("watchlist.html")


@app.route("/signal-details")
def signal_details_page():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template("signal_details.html")


@app.route("/exit-guide")
def exit_guide_page():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template("exit_guide.html")


@app.route("/profit-calculator")
def profit_calculator_page():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template("profit_calculator.html")

@app.route("/api/watchlist", methods=["GET", "POST"])
def api_watchlist():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Not logged in"})

    if request.method == "GET":
        data = supabase.table("watchlist").select("*").order("created_at", desc=True).execute()
        return jsonify({"status": "success", "watchlist": data.data})

    payload = request.get_json(silent=True) or {}

    symbol = clean_symbol_text(payload.get("symbol"))

    if not symbol:
        return jsonify({"status": "error", "message": "Symbol required"})

    row = {
        "symbol": symbol,
        "stock_name": payload.get("stock_name", ""),
        "category": payload.get("category", "General"),
        "notes": payload.get("notes", "")
    }

    supabase.table("watchlist").insert(row).execute()

    return jsonify({"status": "success", "message": "Added to watchlist"})


@app.route("/api/delete-watchlist", methods=["POST"])
def api_delete_watchlist():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Not logged in"})

    payload = request.get_json(silent=True) or {}
    row_id = payload.get("id")

    if not row_id:
        return jsonify({"status": "error", "message": "ID required"})

    supabase.table("watchlist").delete().eq("id", row_id).execute()

    return jsonify({"status": "success", "message": "Removed from watchlist"})

@app.route("/api/save-signal-detail", methods=["POST"])
def api_save_signal_detail():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Not logged in"})

    data = request.get_json(silent=True) or {}

    symbol = clean_symbol_text(data.get("symbol"))

    if not symbol:
        return jsonify({"status": "error", "message": "Symbol required"})

    row = {
        "symbol": symbol,
        "stock_name": data.get("stock_name", ""),
        "timeframe": data.get("timeframe", "15m"),
        "setup_focus": data.get("setup_focus", ""),
        "trade_call": data.get("trade_call", ""),
        "final_direction": data.get("final_direction", ""),
        "final_entry": to_float(data.get("final_entry")),
        "final_stop_loss": to_float(data.get("final_stop_loss")),
        "final_target_1": to_float(data.get("final_target_1")),
        "final_target_2": to_float(data.get("final_target_2")),
        "final_quantity": to_int(data.get("final_quantity")),
        "final_risk_percent": to_float(data.get("final_risk_percent")),
        "final_ai_guidance": data.get("final_ai_guidance", ""),
        "raw_data": data
    }

    supabase.table("signal_details").insert(row).execute()

    return jsonify({"status": "success", "message": "Signal saved"})


@app.route("/api/signal-details")
def api_signal_details():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Not logged in"})

    symbol = request.args.get("symbol", "").strip().upper()

    query = supabase.table("signal_details").select("*").order("created_at", desc=True)

    if symbol:
        query = query.eq("symbol", symbol)

    data = query.limit(100).execute()

    return jsonify({"status": "success", "signals": data.data})

@app.route("/api/trade-history")
def api_trade_history():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Not logged in"})

    data = supabase.table("trade_history").select("*").order("created_at", desc=True).execute()

    trades = data.data or []

    total = len(trades)
    wins = len([x for x in trades if x.get("result") == "WIN"])
    losses = len([x for x in trades if x.get("result") == "LOSS"])
    open_trades = len([x for x in trades if x.get("status") == "OPEN"])
    closed_trades = len([x for x in trades if x.get("status") == "CLOSED"])
    net_pnl = round(sum(to_float(x.get("realized_pnl")) for x in trades), 2)
    win_rate = round((wins / closed_trades) * 100, 2) if closed_trades else 0

    return jsonify({
        "status": "success",
        "trades": trades,
        "summary": {
            "total": total,
            "wins": wins,
            "losses": losses,
            "open": open_trades,
            "closed": closed_trades,
            "net_pnl": net_pnl,
            "win_rate": win_rate
        }
    })


@app.route("/api/profit-calculator", methods=["POST"])
def api_profit_calculator():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Not logged in"})

    data = request.get_json(silent=True) or {}

    symbol = clean_symbol_text(data.get("symbol"))
    direction = str(data.get("direction", "bullish")).lower()

    entry = to_float(data.get("entry"))
    exit_price = to_float(data.get("exit_price"))
    qty = to_int(data.get("quantity"))
    brokerage = to_float(data.get("brokerage"))

    if not entry or not exit_price or not qty:
        return jsonify({
            "status": "error",
            "message": "Entry, exit price and quantity required"
        })

    if direction == "bearish":
        pnl = round((entry - exit_price) * qty - brokerage, 2)
    else:
        pnl = round((exit_price - entry) * qty - brokerage, 2)

    capital_used = entry * qty
    roi_percent = round((pnl / capital_used) * 100, 2) if capital_used else 0

    row = {
        "symbol": symbol,
        "direction": direction,
        "entry": entry,
        "exit_price": exit_price,
        "quantity": qty,
        "brokerage": brokerage,
        "pnl": pnl,
        "roi_percent": roi_percent
    }

    supabase.table("profit_calculations").insert(row).execute()

    return jsonify({
        "status": "success",
        "pnl": pnl,
        "roi_percent": roi_percent,
        "capital_used": round(capital_used, 2),
        "message": "Profit calculated"
    })

@app.route("/api/app-settings", methods=["GET", "POST"])
def api_app_settings():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Not logged in"})

    if request.method == "GET":
        data = supabase.table("app_settings").select("*").execute()
        settings = {}

        for row in data.data or []:
            settings[row["setting_key"]] = row["setting_value"]

        return jsonify({"status": "success", "settings": settings})

    payload = request.get_json(silent=True) or {}

    setting_key = payload.get("setting_key")
    setting_value = payload.get("setting_value")

    if not setting_key:
        return jsonify({"status": "error", "message": "Setting key required"})

    existing = supabase.table("app_settings").select("*").eq("setting_key", setting_key).execute()

    if existing.data:
        supabase.table("app_settings").update({
            "setting_value": setting_value,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("setting_key", setting_key).execute()
    else:
        supabase.table("app_settings").insert({
            "setting_key": setting_key,
            "setting_value": setting_value
        }).execute()

    return jsonify({"status": "success", "message": "Settings saved"})

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)