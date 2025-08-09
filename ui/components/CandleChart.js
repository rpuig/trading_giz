'use client';
import { createChart } from 'lightweight-charts';
import { useEffect, useRef, useState } from 'react';

export default function CandleChart({ selection }) {
  const ref = useRef(null);
  const chartRef = useRef(null);
  const seriesRef = useRef(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!ref.current) return;
    chartRef.current?.remove();
    const el = ref.current;
    const chart = createChart(el, { width: el.clientWidth, height: 420, layout: { background: { type: 'solid', color: '#0b0f14' }, textColor: '#e5e7eb' }, grid: { horzLines: { color: '#1f2937' }, vertLines: { color: '#1f2937' } } });
    const candleSeries = chart.addCandlestickSeries();
    chartRef.current = chart;
    seriesRef.current = candleSeries;
    const onResize = () => chart.applyOptions({ width: el.clientWidth });
    window.addEventListener('resize', onResize);
    return () => { window.removeEventListener('resize', onResize); chart.remove(); };
  }, []);

  useEffect(() => {
    if (!selection || !seriesRef.current) return;
    const { exchange, symbol, timeframe } = selection;
    setLoading(true);
    fetch(`/api/candles?exchange=${encodeURIComponent(exchange)}&symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}&limit=500`)
      .then(r => r.json())
      .then(d => {
        seriesRef.current.setData(d.series || []);
        chartRef.current.timeScale().fitContent();
      })
      .finally(() => setLoading(false));
  }, [selection]);

  return (
    <div className="panel" style={{marginTop:12}}>
      <div className="header">
        <h1>Gráfico</h1>
        <div className="small">{selection ? `${selection.exchange} • ${selection.symbol} • ${selection.timeframe}` : 'Selecciona una señal'}</div>
      </div>
      <div ref={ref} />
      {loading && <div className="small" style={{marginTop:6}}>Cargando velas…</div>}
    </div>
  );
}
