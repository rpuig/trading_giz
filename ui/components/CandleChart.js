'use client';
import { createChart } from 'lightweight-charts';
import { useEffect, useRef, useState } from 'react';

export default function CandleChart({ selection }) {
  const ref = useRef(null);
  const chartRef = useRef(null);
  const seriesRef = useRef(null);
  const vlineRef = useRef(null); // overlay vertical line
  const [loading, setLoading] = useState(false);

  // create chart once
  useEffect(() => {
    if (!ref.current) return;
    const el = ref.current;
    el.style.position = 'relative'; // for overlay
    const chart = createChart(el, {
      width: el.clientWidth, height: 420,
      layout: { background: { type: 'solid', color: '#0b0f14' }, textColor: '#e5e7eb' },
      grid: { horzLines: { color: '#1f2937' }, vertLines: { color: '#1f2937' } }
    });
    const candleSeries = chart.addCandlestickSeries();

    // overlay vertical line
    const vline = document.createElement('div');
    vline.style.cssText = `
      position:absolute; top:0; bottom:0; width:1.5px;
      background:#60a5fa; opacity:0.9; pointer-events:none; display:none;
    `;
    el.appendChild(vline);

    chartRef.current = chart;
    seriesRef.current = candleSeries;
    vlineRef.current = vline;

    const onResize = () => chart.applyOptions({ width: el.clientWidth });
    window.addEventListener('resize', onResize);
    return () => { window.removeEventListener('resize', onResize); chart.remove(); };
  }, []);

  // helper to place vline at given unix seconds
  const placeVLine = (unixSec) => {
    const chart = chartRef.current;
    const vline = vlineRef.current;
    if (!chart || !vline || !unixSec) return;
    const x = chart.timeScale().timeToCoordinate(unixSec);
    if (x == null) { vline.style.display = 'none'; return; }
    vline.style.left = `${Math.round(x)}px`;
    vline.style.display = 'block';
  };

  // fetch candles when selection changes
  useEffect(() => {
    if (!selection || !seriesRef.current) return;
    const { exchange, symbol, timeframe, ts } = selection;
    setLoading(true);
    fetch(`/api/candles?exchange=${encodeURIComponent(exchange)}&symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}&limit=500`)
      .then(r => r.json())
      .then(d => {
        const series = d.series || [];
        seriesRef.current.setData(series);
        chartRef.current.timeScale().fitContent();

        // señal: la DB guarda ms; lightweight-charts usa segundos
        const signalUnix = ts ? Math.floor(Number(ts) / 1000) : null;
        placeVLine(signalUnix);

        // re-colocar la línea cuando cambie el rango visible o se redimensione
        const tsApi = chartRef.current.timeScale();
        const handler = () => placeVLine(signalUnix);
        tsApi.subscribeVisibleTimeRangeChange(handler);
        const obs = new ResizeObserver(() => handler());
        obs.observe(ref.current);
        // cleanup al cambiar de selección
        return () => {
          tsApi.unsubscribeVisibleTimeRangeChange(handler);
          obs.disconnect();
        };
      })
      .finally(() => setLoading(false));
  }, [selection]);

  return (
    <div className="panel" style={{marginTop:12}}>
      <div className="header">
        <h1>Gráfico</h1>
        <div className="small">
          {selection ? `${selection.exchange} • ${selection.symbol} • ${selection.timeframe}` : 'Selecciona una señal'}
        </div>
      </div>
      <div ref={ref} />
      {loading && <div className="small" style={{marginTop:6}}>Cargando velas…</div>}
    </div>
  );
}
