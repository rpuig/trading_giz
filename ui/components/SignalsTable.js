'use client';
import useSWR from 'swr';
import { useEffect, useMemo, useState } from 'react';

const fetcher = (...args) => fetch(...args).then(r => r.json());

export default function SignalsTable({ onSelect }) {
  const [filters, setFilters] = useState({ exchange:'', symbol:'', timeframe:'', signal:'' });
  const [refreshMs, setRefreshMs] = useState(10000);

  // sort state
  const [sortKey, setSortKey] = useState('ts');     // 'ts' | 'exchange' | 'symbol' | 'timeframe' | 'signal' | 'price' | 'payload'
  const [sortDir, setSortDir] = useState('desc');   // 'asc' | 'desc'

  const qs = new URLSearchParams();
  Object.entries(filters).forEach(([k,v]) => v && qs.append(k,v));
  qs.append('limit','500');

  const { data, isLoading, mutate } = useSWR(`/api/signals?${qs.toString()}`, fetcher, { refreshInterval: refreshMs });
  useEffect(() => { const id = setInterval(() => mutate(), refreshMs); return () => clearInterval(id); }, [refreshMs, mutate]);

  const meta = data?.meta || { exchanges:[], symbols:[], timeframes:[], signals:[] };
  const rowsRaw = data?.rows || [];

  // sorting
  const rows = useMemo(() => {
    const arr = [...rowsRaw];
    const dir = sortDir === 'asc' ? 1 : -1;
    arr.sort((a,b) => {
      let va = a[sortKey], vb = b[sortKey];
      // normalize
      if (sortKey === 'ts') { va = Number(va); vb = Number(vb); }
      else if (sortKey === 'price') { va = Number(va); vb = Number(vb); }
      else { va = String(va || ''); vb = String(vb || ''); }
      if (va < vb) return -1 * dir;
      if (va > vb) return 1 * dir;
      // tie‑break by ts desc to keep consistent
      return (Number(b.ts) - Number(a.ts));
    });
    return arr;
  }, [rowsRaw, sortKey, sortDir]);

  const onRowClick = (r) => onSelect?.({ exchange: r.exchange, symbol: r.symbol, timeframe: r.timeframe });

  const onSort = (key) => {
    if (sortKey === key) setSortDir(d => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortKey(key); setSortDir(key === 'ts' ? 'desc' : 'asc'); }
  };

  const Arrow = ({col}) => (
    <span style={{marginLeft:6, opacity: sortKey===col ? 1 : 0.35, fontSize:12}}>
      {sortKey===col ? (sortDir==='asc' ? '▲' : '▼') : '⇅'}
    </span>
  );

  return (
    <div className="panel">
      <div className="header">
        <h1>Señales</h1>
        <div className="small">{isLoading ? 'Cargando…' : `Mostrando ${rows.length} filas`}</div>
      </div>

      <div className="row" style={{marginBottom:12}}>
        <select value={filters.exchange} onChange={e=>setFilters(f=>({...f, exchange:e.target.value}))}>
          <option value="">Exchange</option>
          {meta.exchanges.map(x => <option key={x} value={x}>{x}</option>)}
        </select>
        <select value={filters.symbol} onChange={e=>setFilters(f=>({...f, symbol:e.target.value}))}>
          <option value="">Símbolo</option>
          {meta.symbols.map(x => <option key={x} value={x}>{x}</option>)}
        </select>
        <select value={filters.timeframe} onChange={e=>setFilters(f=>({...f, timeframe:e.target.value}))}>
          <option value="">Timeframe</option>
          {meta.timeframes.map(x => <option key={x} value={x}>{x}</option>)}
        </select>
        <select value={filters.signal} onChange={e=>setFilters(f=>({...f, signal:e.target.value}))}>
          <option value="">Tipo de señal</option>
          {meta.signals.map(x => <option key={x} value={x}>{x}</option>)}
        </select>
        <select value={refreshMs} onChange={e=>setRefreshMs(Number(e.target.value))}>
          <option value="0">No auto‑refresh</option>
          <option value="5000">5s</option>
          <option value="10000">10s</option>
          <option value="30000">30s</option>
          <option value="60000">60s</option>
        </select>
        <button className="button" onClick={()=>setFilters({exchange:'',symbol:'',timeframe:'',signal:''})}>Limpiar</button>
      </div>

      <div style={{overflowX:'auto'}}>
        <table>
          <thead>
            <tr>
              <th style={{cursor:'pointer'}} onClick={()=>onSort('ts')}>
                TS <Arrow col="ts" />
              </th>
              <th style={{cursor:'pointer'}} onClick={()=>onSort('exchange')}>
                Exchange <Arrow col="exchange" />
              </th>
              <th style={{cursor:'pointer'}} onClick={()=>onSort('symbol')}>
                Símbolo <Arrow col="symbol" />
              </th>
              <th style={{cursor:'pointer'}} onClick={()=>onSort('timeframe')}>
                TF <Arrow col="timeframe" />
              </th>
              <th style={{cursor:'pointer'}} onClick={()=>onSort('signal')}>
                Señal <Arrow col="signal" />
              </th>
              <th style={{cursor:'pointer'}} onClick={()=>onSort('price')}>
                Precio <Arrow col="price" />
              </th>
              <th>Payload</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, idx) => (
              <tr key={idx} onClick={()=>onRowClick(r)} style={{cursor:'pointer'}}>
                <td>{new Date(r.ts).toLocaleString()}</td>
                <td><span className="badge">{r.exchange}</span></td>
                <td>{r.symbol}</td>
                <td>{r.timeframe}</td>
                <td><span className="badge">{r.signal}</span></td>
                <td>{Number(r.price).toFixed(6)}</td>
                <td className="small" style={{maxWidth:300, whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis'}}>{r.payload}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="small" style={{marginTop:8}}>Tip: haz click en el encabezado para ordenar (toggle asc/desc).</div>
    </div>
  );
}
