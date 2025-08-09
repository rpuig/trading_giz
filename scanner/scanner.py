#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import time
import sqlite3
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd

import ccxt.async_support as ccxt  # versión async

DB_PATH = Path("../market_data.sqlite")

def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()

def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    up = np.where(delta > 0, delta, 0.0)
    down = np.where(delta < 0, -delta, 0.0)
    roll_up = pd.Series(up, index=series.index).rolling(period).mean()
    roll_down = pd.Series(down, index=series.index).rolling(period).mean()
    rs = roll_up / (roll_down.replace(0, np.nan))
    rsi = 100 - (100 / (1 + rs))
    return rsi

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

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    close = df["close"]
    df["sma20"] = sma(close, 20)
    df["ema20"] = ema(close, 20)
    df["ema50"] = ema(close, 50)
    df["rsi14"] = rsi(close, 14)
    macd_line, signal_line, hist = macd(close)
    df["macd"] = macd_line
    df["macd_signal"] = signal_line
    df["macd_hist"] = hist
    bb_low, bb_mid, bb_up = bollinger(close, 20, 2)
    df["bb_low"] = bb_low
    df["bb_mid"] = bb_mid
    df["bb_up"]  = bb_up
    return df

def compute_signal(df: pd.DataFrame) -> Optional[Dict]:
    if len(df) < 50:
        return None
    last = df.iloc[-1]
    prev = df.iloc[-2]

    macd_cross_up = (prev["macd"] <= prev["macd_signal"]) and (last["macd"] > last["macd_signal"])
    rsi_rebound   = (prev["rsi14"] < 30) and (last["rsi14"] > prev["rsi14"])
    above_ema     = last["close"] > last["ema20"]

    if macd_cross_up and rsi_rebound and above_ema:
        return {
            "timestamp": int(last.name),
            "price": float(last["close"]),
            "signal": "LONG_MACD_RSI_EMA",
            "details": {
                "rsi14": float(last["rsi14"]),
                "macd": float(last["macd"]),
                "macd_signal": float(last["macd_signal"])
            }
        }
    return None

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

async def fetch_ohlcv_incremental(ex, exchange_name: str, symbol: str, timeframe: str,
                                  limit: int = 500, db_path: Path = DB_PATH) -> pd.DataFrame:
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
    ohlcv = None
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

    if not ohlcv:
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
    import argparse, json
    parser = argparse.ArgumentParser(description="Crypto scanner barato (OHLCV + indicadores locales)")
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
                    found.append({
                        "symbol": sym, "timeframe": tf,
                        "price": info["last_close"],
                        "signal": info["signal"]["signal"],
                        "ts": info["signal"]["timestamp"]
                    })
        if found:
            df = pd.DataFrame(found).sort_values(["timeframe", "symbol"])
            print(df.to_string(index=False))
        else:
            print("Sin señales en esta ejecución.")

    print(f"Listo. Pares procesados: {len(data)} en {took:.2f}s. DB: {DB_PATH.resolve()}")

if __name__ == "__main__":
    main()
