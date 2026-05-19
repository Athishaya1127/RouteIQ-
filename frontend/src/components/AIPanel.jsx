import React from 'react';
import { ShieldAlert, Zap, Compass, RefreshCw, Layers } from 'lucide-react';

const AIPanel = ({ simulationData, result }) => {
  if (!simulationData) {
    return (
      <div className="p-6 text-center text-slate-500 bg-white w-80 h-full border-l border-slate-200/80 flex flex-col justify-center items-center gap-3">
        <RefreshCw className="animate-spin text-indigo-600" size={32} />
        <span className="text-sm font-medium">Initializing AI Orchestrator...</span>
      </div>
    );
  }

  const orchestration = simulationData.orchestration || { demand_forecasts: {}, risk_score: null, events: [] };
  const events = orchestration.events || [];
  const demand_forecasts = orchestration.demand_forecasts || {};
  const active_risk = result?.risk_score || null;

  return (
    <div className="bg-white p-5 border-l border-slate-200/80 overflow-y-auto w-80 h-full shadow-2xl text-slate-800 flex flex-col space-y-6">
      
      {/* Header */}
      <div>
        <h2 className="text-lg font-extrabold text-slate-900 flex items-center gap-2 tracking-tight">
          <span className="w-2.5 h-2.5 bg-indigo-600 rounded-full animate-ping"></span>
          Orchestration Hub
        </h2>
        <p className="text-[11px] text-slate-500 mt-1 uppercase tracking-widest font-bold">Proactive AI Fleet Control</p>
      </div>

      {/* Proactive Risk Scoring for Active Route */}
      {active_risk ? (
        <div className="bg-slate-50 border border-slate-200/80 rounded-xl p-4 space-y-3 shadow-sm">
          <div className="flex justify-between items-center border-b border-slate-150 pb-2">
            <h3 className="text-xs font-extrabold text-indigo-600 uppercase tracking-wider flex items-center gap-1.5">
              <ShieldAlert size={14} /> Active Route Risk
            </h3>
            <span className={`text-[10px] px-1.5 py-0.5 rounded font-extrabold uppercase ${
              active_risk.delivery_delay_probability > 0.6 ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-blue-50 text-blue-700 border border-blue-200'
            }`}>
              {active_risk.delivery_delay_probability > 0.6 ? 'High Alert' : 'Nominal'}
            </span>
          </div>

          <div className="space-y-2.5">
            <div>
              <div className="flex justify-between text-xs text-slate-500 mb-1">
                <span>Congestion Risk</span>
                <span className="font-bold text-slate-800">{Math.round(active_risk.future_congestion_risk * 100)}%</span>
              </div>
              <div className="w-full bg-slate-200 h-1.5 rounded-full overflow-hidden">
                <div 
                  className={`h-full rounded-full ${active_risk.future_congestion_risk > 0.6 ? 'bg-red-500' : 'bg-indigo-600'}`} 
                  style={{ width: `${active_risk.future_congestion_risk * 100}%` }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs text-slate-500 mb-1">
                <span>ETA Volatility Risk</span>
                <span className="font-bold text-slate-800">{Math.round(active_risk.eta_risk * 100)}%</span>
              </div>
              <div className="w-full bg-slate-200 h-1.5 rounded-full overflow-hidden">
                <div 
                  className={`h-full rounded-full ${active_risk.eta_risk > 0.5 ? 'bg-orange-500' : 'bg-teal-600'}`} 
                  style={{ width: `${active_risk.eta_risk * 100}%` }}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 pt-1">
              <div className="bg-white p-2 rounded-lg border border-slate-200 text-center shadow-sm">
                <p className="text-[9px] text-slate-400 uppercase font-bold">Bottleneck Probability</p>
                <p className="text-sm font-extrabold text-slate-800 mt-0.5">{Math.round(active_risk.bottleneck_probability * 100)}%</p>
              </div>
              <div className="bg-white p-2 rounded-lg border border-slate-200 text-center shadow-sm">
                <p className="text-[9px] text-slate-400 uppercase font-bold">Delay Probability</p>
                <p className="text-sm font-extrabold text-slate-800 mt-0.5">{Math.round(active_risk.delivery_delay_probability * 100)}%</p>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-slate-50/50 border border-slate-200/60 rounded-xl p-4 text-center text-xs text-slate-400 italic shadow-inner">
          Optimize a route to initialize active predictive risk scoring.
        </div>
      )}

      {/* LIVE ORCHESTRATION FEED */}
      <div>
        <h3 className="text-xs font-extrabold text-slate-500 mb-2.5 uppercase tracking-widest flex items-center gap-1.5">
          <Zap size={14} className="text-indigo-600" /> Proactive Events
        </h3>
        <div className="bg-slate-50/80 rounded-xl p-3 border border-slate-200/80 min-h-[160px] max-h-64 overflow-y-auto space-y-3 scrollbar-thin shadow-inner">
          {events.length > 0 ? (
            events.map((evt, idx) => {
              let borderClass = 'border-blue-600';
              let badgeColor = 'bg-blue-50 text-blue-700 border border-blue-200';
              if (evt.type === 'REROUTE') {
                borderClass = 'border-orange-500 animate-pulse';
                badgeColor = 'bg-orange-50 text-orange-700 border border-orange-200';
              } else if (evt.type === 'REPOSITION') {
                borderClass = 'border-teal-500';
                badgeColor = 'bg-teal-50 text-teal-700 border border-teal-200';
              } else if (evt.type === 'PRIORITY') {
                borderClass = 'border-purple-500';
                badgeColor = 'bg-purple-50 text-purple-700 border border-purple-200';
              }

              return (
                <div key={idx} className={`text-xs bg-white p-3 rounded-lg border-l-3 ${borderClass} border border-slate-150 shadow-sm space-y-1.5`}>
                  <div className="flex justify-between items-center">
                    <span className={`text-[9px] px-1.5 py-0.5 rounded font-extrabold uppercase ${badgeColor}`}>
                      {evt.type}
                    </span>
                    <span className="text-[9px] text-slate-400 font-semibold">{evt.timestamp}</span>
                  </div>
                  <p className="text-[11px] text-slate-700 font-medium leading-relaxed">{evt.reason}</p>
                  {evt.recommended_driver && (
                    <div className="text-[10px] text-slate-500">
                      Target Fleet Agent: <strong className="text-teal-600 font-semibold">{evt.recommended_driver}</strong>
                    </div>
                  )}
                  {evt.eta_impact && (
                    <div className="text-[10px] text-indigo-600 font-bold flex items-center gap-1">
                      <Compass size={11} /> {evt.eta_impact}
                    </div>
                  )}
                </div>
              );
            })
          ) : (
            <div className="text-xs text-slate-400 italic text-center py-8">
              Waiting for operational events...
            </div>
          )}
        </div>
      </div>

      {/* Demand Forecast Hotspots */}
      <div>
        <h3 className="text-xs font-extrabold text-slate-500 mb-2.5 uppercase tracking-widest flex items-center gap-1.5">
          <Layers size={14} className="text-indigo-600" /> ML Demand Forecasting (20m)
        </h3>
        <div className="space-y-2">
          {simulationData.traffic && simulationData.traffic.map((zoneData) => {
            const forecast = demand_forecasts[zoneData.zone] || 0.1;
            return (
              <div key={zoneData.zone} className="bg-slate-50 border border-slate-200/60 p-2.5 rounded-xl flex justify-between items-center transition-all hover:bg-slate-100/60 shadow-sm">
                <div>
                  <div className="text-xs font-extrabold text-slate-800">{zoneData.zone}</div>
                  <div className="text-[9px] text-slate-400 font-semibold">ETA Congestion {(zoneData.predicted_congestion * 100).toFixed(0)}%</div>
                </div>
                <div className="text-right">
                  <div className={`text-xs font-black ${forecast > 0.70 ? 'text-red-600' : forecast > 0.40 ? 'text-orange-600' : 'text-teal-600'}`}>
                    {(forecast * 100).toFixed(0)}%
                  </div>
                  <div className="text-[8px] text-slate-400 font-bold uppercase tracking-wider">Demand Spike</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
      
    </div>
  );
};

export default AIPanel;
