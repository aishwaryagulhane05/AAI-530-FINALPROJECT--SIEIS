import React from 'react';

const SIEISCompactArchitecture = () => {
  const Arrow = () => (
    <svg viewBox="0 0 24 24" className="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M5 12h14m-4-4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );

  const DownArrow = () => (
    <svg viewBox="0 0 24 24" className="w-4 h-4 text-cyan-500" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 5v14m-4-4l4 4 4-4" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );

  return (
    <div className="w-full max-w-4xl mx-auto bg-slate-950 p-6 rounded-2xl font-sans" style={{ aspectRatio: '16/9' }}>
      {/* Header */}
      <div className="text-center mb-4">
        <h1 className="text-2xl font-bold">
          <span className="bg-gradient-to-r from-cyan-400 to-emerald-400 bg-clip-text text-transparent">SIEIS</span>
          <span className="text-white ml-2 text-lg font-normal">Architecture</span>
        </h1>
        <p className="text-slate-500 text-xs">Smart Indoor Environmental Intelligent System | 4 Containers</p>
      </div>

      {/* Data Source */}
      <div className="flex justify-center mb-2">
        <div className="bg-gradient-to-r from-cyan-500/10 to-emerald-500/10 border border-cyan-500/30 rounded-lg px-4 py-2 flex items-center gap-3">
          <div className="w-8 h-8 rounded bg-cyan-500/20 flex items-center justify-center">
            <svg viewBox="0 0 24 24" className="w-5 h-5 text-cyan-400" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/>
            </svg>
          </div>
          <div className="text-left">
            <div className="text-white text-sm font-medium">Intel Lab Dataset</div>
            <div className="text-slate-400 text-xs">2.3M records • 54 sensors • CSV</div>
          </div>
        </div>
      </div>

      <div className="flex justify-center mb-2"><DownArrow /></div>

      {/* Docker Container */}
      <div className="border border-dashed border-blue-500/40 rounded-xl p-4 bg-blue-950/20">
        {/* Docker Label */}
        <div className="flex items-center gap-2 mb-3">
          <svg viewBox="0 0 24 24" className="w-5 h-5">
            <path fill="#2496ED" d="M13.983 11.078h2.119a.186.186 0 00.186-.185V9.006a.186.186 0 00-.186-.186h-2.119a.185.185 0 00-.185.186v1.887c0 .102.083.185.185.185m-2.954-5.43h2.118a.186.186 0 00.186-.186V3.574a.186.186 0 00-.186-.185h-2.118a.185.185 0 00-.185.185v1.888c0 .102.082.185.185.186m0 2.716h2.118a.187.187 0 00.186-.186V6.29a.186.186 0 00-.186-.185h-2.118a.185.185 0 00-.185.185v1.887c0 .102.082.186.185.186m-2.93 0h2.12a.186.186 0 00.184-.186V6.29a.185.185 0 00-.185-.185H8.1a.185.185 0 00-.185.185v1.887c0 .102.083.186.185.186m-2.964 0h2.119a.186.186 0 00.185-.186V6.29a.185.185 0 00-.185-.185H5.136a.186.186 0 00-.186.185v1.887c0 .102.084.186.186.186m5.893 2.715h2.118a.186.186 0 00.186-.185V9.006a.186.186 0 00-.186-.186h-2.118a.185.185 0 00-.185.186v1.887c0 .102.082.185.185.185m-2.93 0h2.12a.185.185 0 00.184-.185V9.006a.185.185 0 00-.184-.186h-2.12a.185.185 0 00-.184.186v1.887c0 .102.083.185.185.185m-2.964 0h2.119a.185.185 0 00.185-.185V9.006a.185.185 0 00-.185-.186h-2.119a.186.186 0 00-.186.186v1.887c0 .102.084.185.186.185m-2.92 0h2.12a.185.185 0 00.184-.185V9.006a.185.185 0 00-.184-.186h-2.12a.186.186 0 00-.186.186v1.887c0 .102.084.185.186.185M23.763 9.89c-.065-.051-.672-.51-1.954-.51-.338.001-.676.03-1.01.087-.248-1.7-1.653-2.53-1.716-2.566l-.344-.199-.226.327c-.284.438-.49.922-.612 1.43-.23.97-.09 1.882.403 2.661-.595.332-1.55.413-1.744.42H.751a.751.751 0 00-.75.748 11.376 11.376 0 00.692 4.062c.545 1.428 1.355 2.48 2.41 3.124 1.18.723 3.1 1.137 5.275 1.137.983.003 1.963-.086 2.93-.266a12.248 12.248 0 003.823-1.389c.98-.567 1.86-1.288 2.61-2.136 1.252-1.418 1.998-2.997 2.553-4.4h.221c1.372 0 2.215-.549 2.68-1.009.309-.293.55-.65.707-1.046l.098-.288Z"/>
          </svg>
          <span className="text-blue-400 text-xs font-mono">Docker Compose</span>
        </div>

        {/* 4 Containers Grid */}
        <div className="grid grid-cols-4 gap-3">
          {/* Redpanda */}
          <div className="bg-slate-900/80 border border-red-500/30 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-7 h-7 rounded bg-red-500 flex items-center justify-center flex-shrink-0">
                <svg viewBox="0 0 32 32" className="w-4 h-4">
                  <circle cx="12" cy="14" r="2" fill="white"/>
                  <circle cx="20" cy="14" r="2" fill="white"/>
                  <path fill="white" d="M16 22c-2 0-3.5-1-3.5-2h7c0 1-1.5 2-3.5 2z"/>
                </svg>
              </div>
              <div>
                <div className="text-white text-xs font-semibold">Redpanda</div>
                <div className="text-slate-500 text-[10px]">:9092</div>
              </div>
            </div>
            <div className="text-slate-400 text-[10px]">Message Broker</div>
            <div className="text-slate-600 text-[9px] mt-1">Kafka-compatible</div>
          </div>

          {/* InfluxDB */}
          <div className="bg-slate-900/80 border border-cyan-500/30 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-7 h-7 rounded bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center flex-shrink-0">
                <svg viewBox="0 0 24 24" className="w-4 h-4">
                  <circle cx="12" cy="6" r="2.5" fill="white"/>
                  <circle cx="6" cy="12" r="2.5" fill="white"/>
                  <circle cx="18" cy="12" r="2.5" fill="white"/>
                  <circle cx="12" cy="18" r="2.5" fill="white"/>
                </svg>
              </div>
              <div>
                <div className="text-white text-xs font-semibold">InfluxDB</div>
                <div className="text-slate-500 text-[10px]">:8086</div>
              </div>
            </div>
            <div className="text-slate-400 text-[10px]">Time-Series DB</div>
            <div className="text-slate-600 text-[9px] mt-1">v2.7</div>
          </div>

          {/* Python App */}
          <div className="bg-slate-900/80 border border-yellow-500/30 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-7 h-7 rounded bg-gradient-to-br from-blue-500 to-yellow-400 flex items-center justify-center flex-shrink-0">
                <svg viewBox="0 0 24 24" className="w-4 h-4">
                  <path fill="white" d="M12 2c-2.5 0-4 1.5-4 3.5v2h4v1H6c-2 0-3.5 1.5-3.5 4s1.5 4 3.5 4h1.5v-2.5c0-1.5 1.5-3 3-3h4c1.5 0 2.5-1 2.5-2.5v-3C17 4 15 2 12 2z"/>
                  <path fill="white" d="M12 22c2.5 0 4-1.5 4-3.5v-2h-4v-1h6c2 0 3.5-1.5 3.5-4s-1.5-4-3.5-4h-1.5v2.5c0 1.5-1.5 3-3 3h-4c-1.5 0-2.5 1-2.5 2.5v3C7 20 9 22 12 22z"/>
                </svg>
              </div>
              <div>
                <div className="text-white text-xs font-semibold">App</div>
                <div className="text-slate-500 text-[10px]">:8000</div>
              </div>
            </div>
            <div className="text-slate-400 text-[10px]">Simulator + Consumer</div>
            <div className="text-slate-600 text-[9px] mt-1">+ FastAPI ML</div>
          </div>

          {/* Streamlit */}
          <div className="bg-slate-900/80 border border-pink-500/30 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-7 h-7 rounded bg-gradient-to-br from-red-500 to-pink-500 flex items-center justify-center flex-shrink-0">
                <svg viewBox="0 0 24 24" className="w-4 h-4">
                  <path fill="white" d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                </svg>
              </div>
              <div>
                <div className="text-white text-xs font-semibold">Dashboard</div>
                <div className="text-slate-500 text-[10px]">:8501</div>
              </div>
            </div>
            <div className="text-slate-400 text-[10px]">Streamlit UI</div>
            <div className="text-slate-600 text-[9px] mt-1">Heatmap + Alerts</div>
          </div>
        </div>

        {/* Data Flow */}
        <div className="mt-4 pt-3 border-t border-slate-800/50">
          <div className="flex items-center justify-center gap-1 flex-wrap">
            <span className="text-slate-400 text-[10px] bg-slate-800/50 px-2 py-1 rounded">CSV</span>
            <Arrow />
            <span className="text-green-400 text-[10px] bg-green-900/30 px-2 py-1 rounded">Simulator</span>
            <Arrow />
            <span className="text-red-400 text-[10px] bg-red-900/30 px-2 py-1 rounded">Redpanda</span>
            <Arrow />
            <span className="text-purple-400 text-[10px] bg-purple-900/30 px-2 py-1 rounded">Consumer</span>
            <Arrow />
            <span className="text-cyan-400 text-[10px] bg-cyan-900/30 px-2 py-1 rounded">InfluxDB</span>
            <Arrow />
            <span className="text-pink-400 text-[10px] bg-pink-900/30 px-2 py-1 rounded">Dashboard</span>
          </div>
        </div>
      </div>

      {/* Bottom Stats */}
      <div className="flex justify-center gap-6 mt-4">
        {[
          { label: 'Sensors', value: '54', color: 'text-emerald-400' },
          { label: 'Records', value: '2.3M', color: 'text-cyan-400' },
          { label: 'Interval', value: '31s', color: 'text-yellow-400' },
          { label: 'Metrics', value: '4', color: 'text-pink-400' },
        ].map((stat, i) => (
          <div key={i} className="text-center">
            <div className={`text-lg font-bold ${stat.color}`}>{stat.value}</div>
            <div className="text-slate-500 text-[10px] uppercase">{stat.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default SIEISCompactArchitecture;
