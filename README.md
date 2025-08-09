# Trading Kit (Scanner + UI)

Monorepo integrado con:
- **scanner/** (Python + ccxt): descarga OHLCV, calcula indicadores y escribe en `market_data.sqlite`
- **ui/** (Next.js): lee la base y muestra señales + velas

## Requisitos (local)
- Python 3.11+, Node 18+
- `market_data.sqlite` se crea automáticamente al correr el scanner

## 1) Instalar y correr el scanner (local)
```bash
cd scanner
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scanner.py --exchange binance --symbols BTC/USDT ETH/USDT SOL/USDT --timeframes 5m 15m 1h --print
# esto crea/actualiza ../market_data.sqlite
```

## 2) Correr la UI (local)
```bash
cd ui
npm install
npm run dev
# http://localhost:4000
```

## 3) Runner en loop (local)
```bash
# en otra terminal
cd scanner
SCAN_INTERVAL=60 EXCHANGE=binance SYMBOLS=BTC/USDT,ETH/USDT,SOL/USDT TIMEFRAMES=1m,5m,15m,1h,4h,1d python runner.py
```

## 4) Docker Compose
```bash
docker compose build
docker compose up -d
# UI en http://localhost:4000
```

## Notas
- La base `market_data.sqlite` vive en la raíz del repo y es compartida por ambos servicios.
- Ajusta símbolos/timeframes/envs a tu gusto.
# trading_giz
