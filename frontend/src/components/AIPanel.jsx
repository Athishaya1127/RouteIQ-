import React from 'react';

const AIPanel = ({ simulationData, result }) => {
  if (!simulationData) {
    return (
      <div className="p-4 text-center text-gray-500 bg-white shadow-lg w-80 h-full border-l">
        Waiting for AI Orchestrator...
      </div>
    );
  }

  return (
    <div className="bg-white p-4 border-l border-gray-200 overflow-y-auto w-80 h-full shadow-lg">
      <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center">
        <span className="w-2 h-2 bg-green-500 rounded-full mr-2 animate-pulse"></span>
        AI Routing Engine
      </h2>

      {/* AI Decision Feed */}
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-gray-600 mb-2 uppercase tracking-wide">Live Interventions</h3>
        <div className="bg-gray-50 rounded-lg p-3 border border-gray-200 min-h-[100px] max-h-40 overflow-y-auto space-y-2">
          {simulationData.ai_events && simulationData.ai_events.length > 0 ? (
            simulationData.ai_events.map((evt, idx) => (
              <div key={idx} className="text-xs bg-white p-2 rounded shadow-sm border-l-2 border-indigo-500 text-gray-700">
                {evt}
              </div>
            ))
          ) : (
            <div className="text-xs text-gray-400 italic">Monitoring traffic patterns...</div>
          )}
        </div>
      </div>

      {/* Prediction Cards */}
      <div>
        <h3 className="text-sm font-semibold text-gray-600 mb-2 uppercase tracking-wide">Zone Forecast (15m)</h3>
        <div className="space-y-2">
          {simulationData.traffic && simulationData.traffic.map((zoneData) => (
            <div key={zoneData.zone} className="bg-gray-50 p-2 rounded border border-gray-100 flex justify-between items-center">
              <div className="text-sm font-medium text-gray-700">{zoneData.zone}</div>
              <div className="text-xs flex items-center space-x-2">
                 <span className="text-gray-500">{(zoneData.current_congestion * 100).toFixed(0)}%</span>
                 <span className="text-gray-300">→</span>
                 <span className={`font-bold ${zoneData.predicted_congestion > 0.75 ? 'text-red-500' : zoneData.predicted_congestion > 0.4 ? 'text-yellow-600' : 'text-green-500'}`}>
                    {(zoneData.predicted_congestion * 100).toFixed(0)}%
                 </span>
              </div>
            </div>
          ))}
        </div>
      </div>
      
    </div>
  );
};

export default AIPanel;
