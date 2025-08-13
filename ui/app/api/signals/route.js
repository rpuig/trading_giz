export const runtime = 'nodejs';

import { NextResponse } from 'next/server';
import { getDB } from '@/lib/db';

export async function GET(req) {
  const { searchParams } = new URL(req.url);
  const exchange = searchParams.get('exchange') || '';
  const symbol = searchParams.get('symbol') || '';
  const timeframe = searchParams.get('timeframe') || '';
  const signal = searchParams.get('signal') || '';
  const limit = Number(searchParams.get('limit') || '500');

  const filters = [];
  const params = {};
  if (exchange) { filters.push('exchange = @exchange'); params.exchange = exchange; }
  if (symbol)   { filters.push('symbol = @symbol');     params.symbol = symbol; }
  if (timeframe){ filters.push('timeframe = @tf');      params.tf = timeframe; }
  if (signal)   { filters.push('signal = @sig');        params.sig = signal; }

  const where = filters.length ? `WHERE ${filters.join(' AND ')}` : '';
  const sql = `
    SELECT exchange, symbol, timeframe, ts, signal, price, payload
    FROM signals
    ${where}
    ORDER BY ts DESC
    LIMIT @limit
  `;

  const db = getDB();
  const rows = db.prepare(sql).all({ ...params, limit });

  // meta
  const all = db.prepare('SELECT exchange, symbol, timeframe, signal FROM signals LIMIT 100000').all();
  const uniq = (arr) => [...new Set(arr)].sort();

  const exchanges = uniq(all.map(r => r.exchange));
  const symbols   = uniq(all.map(r => r.symbol));
  const timeframes= uniq(all.map(r => r.timeframe));
  const dbSignals = uniq(all.map(r => r.signal));

  // señales conocidas aunque aún no existan en la DB
  const knownSignals = ['supersold','superbought','almost_supersold','almost_superbought'];

  const signals = uniq([...dbSignals, ...knownSignals]);

  return NextResponse.json({ rows, meta: { exchanges, symbols, timeframes, signals } });
}
