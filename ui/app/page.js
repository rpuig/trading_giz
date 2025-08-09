'use client';
import { useState } from 'react';
import SignalsTable from '@/components/SignalsTable';
import CandleChart from '@/components/CandleChart';
import './globals.css';

export default function Page() {
  const [selection, setSelection] = useState(null);

  return (
    <div className="container">
      <div style={{marginBottom:12}}>
        <h1>Crypto Scanner UI</h1>
        <div className="small">Lee datos de <code>market_data.sqlite</code> (OHLCV + señales) generados por el scanner.</div>
      </div>

      <SignalsTable onSelect={setSelection} />
      <CandleChart selection={selection} />
    </div>
  );
}
