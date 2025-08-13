#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import time
import sqlite3
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
import ccxt.async_support as ccxt  # async

DB_PATH = Path("../market_data.sqlite")

# ---------- utilidades simples ----------
def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()

def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()

# ---------- indicadores básicos ----------
def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0.0)
    down = (-delta.clip(upper=0.0))
    roll_up = up.rolling(period).mean()
    roll_down = down.rolling(period).mean()
    rs = roll_up / roll_down.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def macd(series: pd.Series, fast=12, slow=26, signal=9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

def bollinger(series: pd.Series, window=20, n_std=2) -> Tuple[pd.Series, pd.Series, pd.Series]:
    ma = sma(series, window)
    std = series.rolling(window=window, min_periods=window).std()
    upper = ma + n_std * std
    lower = ma - n_std * std
    return lower, ma, upper

# ---------- indicadores adicionales (foto) ----------
def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    # On-Balance Volume clásico
    direction = np.sign(close.diff().fillna(0))
    return (direction * volume.fillna(0)).cumsum()

def dmi_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14):
    # Implementación compacta de +DI, -DI y ADX (Wilder)
    up_move = high.diff()
    down_move = (-low.diff())
    plus_dm = ((up_move > down_move) & (up_move > 0)).astype(float) * up_move
    minus_dm = ((down_move > up_move) & (down_move > 0)).astype(float) * down_move

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.rolling(period).mean()
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr.replace(0, np.nan))
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr.replace(0, np.nan))
    dx = 100 * ( (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) )
    adx = dx.rolling(period).mean()
    return plus_di, minus_di, adx

def cci(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20) -> pd.Series:
    tp = (high + low + close) / 3.0
    sma_tp = tp.rolling(period).mean()
    mad = (tp - sma_tp).abs().rolling(period).mean()
    return (tp - sma_tp) / (0.015 * mad.replace(0, np.nan))

def stoch_rsi(series: pd.Series, rsi_period: int = 14, k: int = 3, d: int = 3):
    r = rsi(series, rsi_period)
    low_r = r.rolling(rsi_period).min()
    high_r = r.rolling(rsi_period).max()
    k_raw = 100 * (r - low_r) / (high_r - low_r).replace(0, np.nan)
    k_line = k_raw.rolling(k).mean()
    d_line = k_line.rolling(d).mean()
    return k_line, d_line

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    # Requiere columnas: open, high, low, close, volume
    close = df["close"]; high = df["high"]; low = df["low"]; vol = df["volume"]

    # MAs
    df["sma20"]  = sma(close, 20)
    df["sma50"]  = sma(close, 50)
    df["sma100"] = sma(close, 100)

    # RSI, MACD, Bollinger
    df["rsi14"] = rsi(close, 14)
    macd_line, signal_line, hist = macd(close, 12, 26, 9)
    df["macd"] = macd_line; df["macd_signal"] = signal_line; df["macd_hist"] = hist
    bb_low, bb_mid, bb_up = bollinger(close, 20, 2)
    df["bb_low"] = bb_low; df["bb_mid"] = bb_mid; df["bb_up"]  = bb_up

    # OBV y su EMA7 para pendiente
    df["obv"] = obv(close, vol)
    df["obv_ema7"] = ema(df["obv"], 7)

    # DMI/ADX(14)
    plus_di, minus_di, adx = dmi_adx(high, low, close, 14)
    df["+di14"] = plus_di; df["-di14"] = minus_di; df["adx14"] = adx

    # CCI(20)
    df["cci20"] = cci(high, low, close, 20)

    # Stoch RSI 14,3,3
    k, d = stoch_rsi(close, 14, 3, 3)
    df["stoch_k"] = k; df["stoch_d"] = d

    return df

# ---------- señales ----------
def compute_signal(df: pd.DataFrame) -> Optional[Dict]:
    """Senales compuestas con scoring:
    - superbought / supersold: TODAS las condiciones (11/11)
    - almost_superbought / almost_supersold: >= ALMOST_MIN_MATCH condiciones (por defecto 7/11)
    Umbral configurable con env ALMOST_MIN_MATCH.
    """
    import os
    if len(df) < 100:
        return None
    last = df.iloc[-1]

    ALMOST_MIN = int(os.getenv("ALMOST_MIN_MATCH", "7"))

    # Condiciones en sobreventa
    oversold_conds = [
        (last["close"] <= last["bb_low"]),
        (last["rsi14"] <= 30),
        (last["stoch_k"] <= 20),
        (last["stoch_d"] <= 20),
        (last["cci20"] <= -100),
        (last["macd"] < last["macd_signal"]),
        (last["macd"] < 0),
        (last["close"] < last["sma50"]),
        (last["close"] < last["sma100"]),
        (last["obv"] < last["obv_ema7"]),
        (last["-di14"] > last["+di14"]) and (last["adx14"] >= 18),
    ]

    # Condiciones en sobrecompra
    overbought_conds = [
        (last["close"] >= last["bb_high"]),
        (last["rsi14"] >= 70),
        (last["stoch_k"] >= 80),
        (last["stoch_d"] >= 80),
        (last["cci20"] >= 100),
        (last["macd"] > last["macd_signal"]),
        (last["macd"] > 0),
        (last["close"] > last["sma50"]),
        (last["close"] > last["sma100"]),
        (last["obv"] > last["obv_ema7"]),
        (last["+di14"] > last["-di14"]) and (last["adx14"] >= 18),
    ]

    # Comprobar totales
    oversold_count = sum(oversold_conds)
    overbought_count = sum(overbought_conds)

    if oversold_count == len(oversold_conds):
        return {"signal": "supersold"}
    elif overbought_count == len(overbought_conds):
        return {"signal": "superbought"}
    elif oversold_count >= ALMOST_MIN:
        return {"signal": "almost_supersold"}
    elif overbought_count >= ALMOST_MIN:
        return {"signal": "almost_superbought"}

    return None

# ---------- DB ----------
def init_db(db_path: Path = DB_PATH):
    with sqlite3.connect(db_path) as con:
        cur = con.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS candles (
            exchange TEXT NOT NULL,
            symbol   TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            ts INTEGER NOT NULL,
            open REAL, high REAL, low REAL, close REAL, volume REAL,
            PRIMARY KEY (exchange, symbol, timeframe, ts)
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            exchange TEXT NOT NULL,
            symbol   TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            ts INTEGER NOT NULL,
            signal TEXT NOT NULL,
            price REAL,
            payload TEXT,
            PRIMARY KEY (exchange, symbol, timeframe, ts, signal)
        )
        """)
        con.commit()

def last_ts(con: sqlite3.Connection, exchange: str, symbol: str, timeframe: str) -> Optional[int]:
    cur = con.cursor()
    cur.execute("""
        SELECT MAX(ts) FROM candles
        WHERE exchange=? AND symbol=? AND timeframe=?
    """, (exchange, symbol, timeframe))
    row = cur.fetchone()
    return row[0] if row and row[0] else None

def df_to_sql(con: sqlite3.Connection, exchange: str, symbol: str, timeframe: str, df: pd.DataFrame):
    if df.empty:
        return
    rows = [
        (exchange, symbol, timeframe, int(ts),
         float(r.open), float(r.high), float(r.low), float(r.close), float(r.volume))
        for ts, r in df.iterrows()
    ]
    cur = con.cursor()
    cur.executemany("""
        INSERT INTO candles (exchange, symbol, timeframe, ts, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(exchange, symbol, timeframe, ts) DO UPDATE SET
            open=excluded.open,
            high=excluded.high,
            low=excluded.low,
            close=excluded.close,
            volume=excluded.volume
    """, rows)
    con.commit()

def save_signal(con: sqlite3.Connection, exchange: str, symbol: str, timeframe: str, sig: Dict):
    cur = con.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO signals (exchange, symbol, timeframe, ts, signal, price, payload)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (exchange, symbol, timeframe,
          int(sig["timestamp"]), sig["signal"], float(sig.get("price", 0.0)), str(sig.get("details"))))
    con.commit()

# ---------- fetch & loop ----------
async def fetch_ohlcv_incremental(ex, exchange_name: str, symbol: str, timeframe: str,
                                  limit: int = 1000, db_path: Path = DB_PATH) -> pd.DataFrame:
    ms_in_min = 60 * 1000
    tf_map = {
        "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "2h": 120,
        "4h": 240, "6h": 360, "8h": 480, "12h": 720, "1d": 1440, "3d": 4320, "1w": 10080
    }
    with sqlite3.connect(db_path) as con:
        since_ts = last_ts(con, exchange_name, symbol, timeframe)
    since = None
    if since_ts:
        since = since_ts + tf_map.get(timeframe, 1) * ms_in_min

    retries = 0
    while retries < 5:
        try:
            ohlcv = await ex.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit)
            break
        except ccxt.NetworkError:
            retries += 1
            await asyncio.sleep(0.5 * retries)
        except ccxt.ExchangeError as e:
            print(f"[{exchange_name}] Error en {symbol} {timeframe}: {e}")
            return pd.DataFrame()
    else:
        return pd.DataFrame()

    df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
    df.set_index("ts", inplace=True)
    df.sort_index(inplace=True)

    with sqlite3.connect(db_path) as con:
        df_to_sql(con, exchange_name, symbol, timeframe, df)

    return df

async def process_pair(ex, exchange_name: str, symbol: str, timeframes: List[str]) -> Dict[str, Dict]:
    result = {}
    for tf in timeframes:
        df = await fetch_ohlcv_incremental(ex, exchange_name, symbol, tf, limit=1000)
        if df.empty:
            continue
        df_ind = add_indicators(df.copy())
        sig = compute_signal(df_ind)
        result[tf] = {
            "last_close": float(df_ind["close"].iloc[-1]),
            "last_ts": int(df_ind.index[-1]),
            "signal": sig
        }
    return result

async def run_scanner(
    exchange_name: str = "binance",
    symbols: Optional[List[str]] = None,
    timeframes: Optional[List[str]] = None,
    concurrency: int = 5
) -> Dict[str, Dict[str, Dict]]:
    init_db(DB_PATH)
    symbols = symbols or ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]
    timeframes = timeframes or ["1m", "5m", "15m", "1h", "4h", "1d"]

    cls = getattr(ccxt, exchange_name)
    ex = cls({"enableRateLimit": True})
    await ex.load_markets()

    sem = asyncio.Semaphore(concurrency)

    async def task(symbol):
        async with sem:
            return symbol, await process_pair(ex, exchange_name, symbol, timeframes)

    tasks = [asyncio.create_task(task(sym)) for sym in symbols]
    results = await asyncio.gather(*tasks)
    await ex.close()
    return {sym: data for sym, data in results}

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Crypto scanner (OHLCV + indicadores locales + supersold/superbought)")
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--symbols", nargs="*", default=None)
    parser.add_argument("--timeframes", nargs="*", default=None)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--print", dest="do_print", action="store_true")
    args = parser.parse_args()

    start = time.time()
    data = asyncio.run(run_scanner(
        exchange_name=args.exchange,
        symbols=args.symbols,
        timeframes=args.timeframes,
        concurrency=args.concurrency
    ))
    took = time.time() - start

    with sqlite3.connect(DB_PATH) as con:
        for sym, per_tf in data.items():
            for tf, info in per_tf.items():
                sig = info.get("signal")
                if sig:
                    save_signal(con, args.exchange, sym, tf, sig)

    if args.do_print:
        found = []
        for sym, per_tf in data.items():
            for tf, info in per_tf.items():
                if info.get("signal"):
                    s = info["signal"]
                    found.append({
                        "symbol": sym, "timeframe": tf,
                        "price": info["last_close"],
                        "signal": s["signal"],
                        "ts": s["timestamp"]
                    })
        if found:
            df = pd.DataFrame(found).sort_values(["timeframe", "symbol"])
            print(df.to_string(index=False))
        else:
            print("Sin señales en esta ejecución.")

    print(f"Listo. Pares procesados: {len(data)} en {took:.2f}s. DB: {DB_PATH.resolve()}")

if __name__ == "__main__":
    main()
