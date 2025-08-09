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
  const stmt = db.prepare(sql);
  const rows = stmt.all({ ...params, limit });

  const uniq = (arr) => [...new Set(arr)].sort();
  const allSql = db.prepare('SELECT exchange, symbol, timeframe, signal FROM signals LIMIT 100000').all();
  const exchanges = uniq(allSql.map(r => r.exchange));
  const symbols = uniq(allSql.map(r => r.symbol));
  const timeframes = uniq(allSql.map(r => r.timeframe));
  const signals = uniq(allSql.map(r => r.signal));

  return NextResponse.json({ rows, meta: { exchanges, symbols, timeframes, signals } });
}
