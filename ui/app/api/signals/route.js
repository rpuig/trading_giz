export const runtime = 'nodejs';

import { NextResponse } from 'next/server';
import { getDB } from '@/lib/db';

export async function GET(req) {
  const { searchParams } = new URL(req.url);
  const exchange  = searchParams.get('exchange')  || '';
  const symbol    = searchParams.get('symbol')    || '';
  const timeframe = searchParams.get('timeframe') || '';
  const signal    = searchParams.get('signal')    || '';
  const limit     = Number(searchParams.get('limit') || '500');

  const filters = [];
  const params = {};
  if (exchange)  { filters.push('exchange = @exchange');   params.exchange = exchange; }
  if (symbol)    { filters.push('symbol = @symbol');       params.symbol   = symbol; }
  if (timeframe) { filters.push('timeframe = @timeframe'); params.timeframe= timeframe; }
  if (signal)    { filters.push('signal = @signal');       params.signal   = signal; }

  const where = filters.length ? `WHERE ${filters.join(' AND ')}` : '';

  const db = getDB();

  // filas de señales (tabla signals)
  const rows = db.prepare(
    `SELECT exchange, symbol, timeframe, ts, signal, price, payload
     FROM signals
     ${where}
     ORDER BY ts DESC
     LIMIT @limit`
  ).all({ ...params, limit });

  // -------- META: construir desplegables desde candles ∪ signals --------
  const unions = {
    exchanges: db.prepare(`
      SELECT exchange FROM candles GROUP BY exchange
      UNION
      SELECT exchange FROM signals GROUP BY exchange
    `).all().map(r => r.exchange),

    symbols: db.prepare(`
      SELECT symbol FROM candles GROUP BY symbol
      UNION
      SELECT symbol FROM signals GROUP BY symbol
    `).all().map(r => r.symbol),

    timeframes: db.prepare(`
      SELECT timeframe FROM candles GROUP BY timeframe
      UNION
      SELECT timeframe FROM signals GROUP BY timeframe
    `).all().map(r => r.timeframe),

    signals: db.prepare(`SELECT signal FROM signals GROUP BY signal`).all().map(r => r.signal),
  };

  // Señales “conocidas” aunque aún no existan
  const knownSignals = ['supersold','superbought','almost_supersold','almost_superbought'];

  const uniqSort = (arr) => [...new Set(arr)].sort();

  const meta = {
    exchanges: uniqSort(unions.exchanges),
    symbols:   uniqSort(unions.symbols),
    timeframes:uniqSort(unions.timeframes),
    signals:   uniqSort([...unions.signals, ...knownSignals]),
  };

  return NextResponse.json({ rows, meta });
}
