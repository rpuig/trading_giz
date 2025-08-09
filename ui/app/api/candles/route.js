export const runtime = 'nodejs';

import { NextResponse } from 'next/server';
import { getDB } from '@/lib/db';

export async function GET(req) {
  const { searchParams } = new URL(req.url);
  const exchange = searchParams.get('exchange');
  const symbol = searchParams.get('symbol');
  const timeframe = searchParams.get('timeframe');
  const limit = Number(searchParams.get('limit') || '500');

  if (!exchange || !symbol || !timeframe) {
    return NextResponse.json({ error: 'Missing exchange/symbol/timeframe' }, { status: 400 });
  }

  const db = getDB();
  const sql = `
    SELECT ts, open, high, low, close, volume
    FROM candles
    WHERE exchange=@exchange AND symbol=@symbol AND timeframe=@tf
    ORDER BY ts DESC
    LIMIT @limit
  `;
  const rows = db.prepare(sql).all({ exchange, symbol, tf: timeframe, limit });
  rows.reverse();

  const series = rows.map(r => ({
    time: Math.floor(r.ts / 1000),
    open: r.open, high: r.high, low: r.low, close: r.close
  }));

  return NextResponse.json({ series });
}
