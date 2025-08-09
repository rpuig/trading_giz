#!/usr/bin/env python3
# Simple loop runner: runs scanner every N seconds
import os, time, subprocess, sys

INTERVAL = int(os.getenv("SCAN_INTERVAL", "60"))  # seconds
EXCHANGE = os.getenv("EXCHANGE", "binance")
SYMBOLS = os.getenv("SYMBOLS", "BTC/USDT,ETH/USDT,SOL/USDT")
TIMEFRAMES = os.getenv("TIMEFRAMES", "1m,5m,15m,1h,4h,1d")
CONCURRENCY = os.getenv("CONCURRENCY", "5")

def run_once():
    cmd = [
        sys.executable, "scanner.py",
        "--exchange", EXCHANGE,
        "--symbols", *SYMBOLS.split(","),
        "--timeframes", *TIMEFRAMES.split(","),
        "--concurrency", CONCURRENCY
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=False)

if __name__ == "__main__":
    while True:
        run_once()
        time.sleep(INTERVAL)
