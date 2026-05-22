import React, { useEffect, useState } from 'react';
import { Polyline, Tooltip, useMap, Marker } from 'react-leaflet';
import L from 'leaflet';
import { VEHICLES_CONFIG } from './Sidebar';

const RouteVisualizer = ({ result, isPrevious = false, vehicleIndex = 0, vehicleType }) => {
  const map = useMap();

  useEffect(() => {
    if (result && result.full_route_geometry && result.full_route_geometry.length > 0) {
      const bounds = L.latLngBounds(result.full_route_geometry);
      map.fitBounds(bounds, { padding: [50, 50] });
    }
  }, [result, map]);

  if (!result) return null;

  const [currentIdx, setCurrentIdx] = useState(0);
  const [bearing, setBearing] = useState(0);

  const geom = result.full_route_geometry || [];

  // Reset animation when geometry changes
  useEffect(() => {
    setCurrentIdx(0);
    setBearing(0);
  }, [result]);

  // Periodic ticker for moving the bike along the route geometry
  useEffect(() => {
    if (isPrevious || geom.length < 2) return;

    const interval = setInterval(() => {
      setCurrentIdx((prevIdx) => {
        const nextIdx = (prevIdx + 1) % geom.length;
        
        // Calculate bearing between current point and next point
        const p1 = geom[prevIdx];
        const p2 = geom[nextIdx];
        if (p1 && p2) {
          const lat1 = p1[0] * Math.PI / 180;
          const lon1 = p1[1] * Math.PI / 180;
          const lat2 = p2[0] * Math.PI / 180;
          const lon2 = p2[1] * Math.PI / 180;

          const y = Math.sin(lon2 - lon1) * Math.cos(lat2);
          const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(lon2 - lon1);
          const brng = (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
          
          // Emojis typically face left (bearing 270). Align to North by adding 90 degrees.
          setBearing((brng + 90) % 360);
        }
        
        return nextIdx;
      });
    }, 350); // Progress along route every 350ms

    return () => clearInterval(interval);
  }, [geom, isPrevious]);

  const renderMovingVehicle = () => {
    if (isPrevious || geom.length === 0 || !geom[currentIdx]) return null;

    const vehicleColors = ['#22c55e', '#f97316', '#a855f7', '#eab308', '#64748b', '#000000', '#d97706'];
    const vIdx = result.vehicle_index !== undefined ? result.vehicle_index : vehicleIndex;
    const color = vehicleColors[vIdx % vehicleColors.length] || '#22c55e';

    const emoji = VEHICLES_CONFIG[vehicleType]?.emoji || '🛵';

    const markerHtml = `
      <div class="moving-bike-marker-container" style="transform: rotate(${bearing}deg); --partner-color: ${color};">
        <div class="moving-bike-tail"></div>
        <div class="moving-bike-bg">
          <span class="moving-bike-emoji">${emoji}</span>
        </div>
      </div>
    `;

    const movingIcon = L.divIcon({
      html: markerHtml,
      className: 'moving-bike-div-icon',
      iconSize: [46, 46],
      iconAnchor: [23, 23]
    });

    return (
      <Marker 
        position={geom[currentIdx]} 
        icon={movingIcon} 
        zIndexOffset={1000}
      >
        <Tooltip permanent direction="top" offset={[0, -22]}>
          <div className="font-sans font-semibold text-[10px] bg-slate-900 text-white px-2 py-0.5 rounded shadow-lg flex items-center gap-1.5 opacity-90 border border-slate-750">
            <span>{emoji} Partner {result.partner_id ? result.partner_id.slice(4) : ''}</span>
            <span className="bg-indigo-600 px-1 rounded text-[8px] font-extrabold">{Math.round((currentIdx / (geom.length - 1)) * 100)}%</span>
          </div>
        </Tooltip>
      </Marker>
    );
  };

  const formatLabel = (id) => {
    if (id.startsWith('shop')) return `Shop ${id.slice(4)}`;
    if (id.startsWith('cus')) return `Customer ${id.slice(3)}`;
    if (id.startsWith('part')) return `Partner ${id.slice(4)}`;
    return id;
  };

  // 1. Render Rejected / Avoided Congested Roads
  const renderRejectedEdges = () => {
    if (isPrevious || !result.rejected_edges || result.rejected_edges.length === 0) return null;

    return result.rejected_edges.map((edge) => {
      if (!edge.geometry || edge.geometry.length === 0) return null;

      return (
        <Polyline
          key={`rejected-${edge.edge_id}`}
          positions={edge.geometry}
          pathOptions={{
            color: '#ef4444', // Crimson Red
            weight: 7,
            opacity: 0.7,
            dashArray: '10, 8',
            lineCap: 'round',
            lineJoin: 'round',
            className: 'route-path-animation bottleneck-pulse' // Glowing pulse warning animation
          }}
        >
          <Tooltip sticky>
            <div className="font-sans text-sm p-2 leading-relaxed max-w-[280px]">
              <strong className="text-red-600 block text-xs uppercase tracking-wider mb-1 flex items-center gap-1">
                🔴 Future Congestion Avoided
              </strong>
              <div className="font-bold text-slate-800 mb-1 border-b border-slate-100 pb-1">
                {edge.road_name || "Bypassed Corridor"}
              </div>
              <div className="text-slate-600 text-xs mb-1">
                The AI predicted severe future traffic delays here and bypassed this road.
              </div>
              <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 mt-1.5 text-xs text-slate-700">
                <div>Congestion:</div>
                <div className="font-extrabold text-red-600">{(edge.predicted_congestion * 100).toFixed(0)}%</div>
                <div>Avoided ETA:</div>
                <div className="font-semibold">{edge.estimated_arrival_time}</div>
                <div>Travel Cost:</div>
                <div className="font-mono">{edge.travel_time.toFixed(1)} mins</div>
              </div>
              <div className="bg-red-50 text-red-700 p-1.5 rounded mt-2 border border-red-100 text-[10px] font-medium leading-snug">
                ⚠️ Rejection: {edge.rejection_reason}
              </div>
            </div>
          </Tooltip>
        </Polyline>
      );
    });
  };

  // 2. Render Active Optimal / Previous Route
  const renderActiveRoute = () => {
    if (!result.segments || result.segments.length === 0) return null;

    return result.segments.map((segment, idx) => {
      if (!segment.geometry || segment.geometry.length === 0) return null;

      let color = '#ef4444';
      let weight = 4;
      let opacity = 0.4;
      let dashArray = '5, 10';
      let className = '';

      if (isPrevious) {
        // Faded legacy path
        color = '#64748b';
        weight = 5;
        opacity = 0.35;
        dashArray = '5, 10';
      } else {
        // Dynamic multi-vehicle colors
        const vehicleColors = ['#22c55e', '#f97316', '#a855f7', '#eab308', '#64748b', '#000000', '#d97706'];
        const vIdx = result.vehicle_index !== undefined ? result.vehicle_index : vehicleIndex;
        color = vehicleColors[vIdx % vehicleColors.length] || '#22c55e';
        weight = 8;
        opacity = 1.0;
        dashArray = undefined;
      }

      const arrowNodes = [];
      if (!isPrevious && segment.geometry.length > 1) {
        // Find the exact midpoint index to inject directional arrow
        const midIdx = Math.floor(segment.geometry.length / 2);
        const p1 = segment.geometry[midIdx - 1];
        const p2 = segment.geometry[midIdx];

        if (p1 && p2) {
          // Calculate bearing
          const lat1 = p1[0] * Math.PI / 180;
          const lon1 = p1[1] * Math.PI / 180;
          const lat2 = p2[0] * Math.PI / 180;
          const lon2 = p2[1] * Math.PI / 180;

          const y = Math.sin(lon2 - lon1) * Math.cos(lat2);
          const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(lon2 - lon1);
          const brng = (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;

          const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="${color}" width="22px" height="22px" style="transform: rotate(${brng}deg); filter: drop-shadow(0px 1.5px 3px rgba(0,0,0,0.5)); stroke: white; stroke-width: 2px; display: block;"><path d="M12 2L22 20L12 17L2 20L12 2Z" /></svg>`;
          const arrowIcon = L.divIcon({
            html: svg,
            className: '',
            iconSize: [22, 22],
            iconAnchor: [11, 11]
          });

          arrowNodes.push(
            <Marker key={`arrow-${idx}-mid`} position={p2} icon={arrowIcon} interactive={false} />
          );
        }
      }

      return (
        <React.Fragment key={`frag-${segment.from_id}-${segment.to_id}`}>
          {/* Main solid neon green path */}
          <Polyline
            key={isPrevious ? `prev-${segment.from_id}-${segment.to_id}` : `act-${segment.from_id}-${segment.to_id}`}
            positions={segment.geometry}
            pathOptions={{
              color: color,
              weight: weight,
              opacity: opacity,
              lineCap: 'round',
              lineJoin: 'round',
              dashArray: dashArray,
              smoothFactor: isPrevious ? 1.0 : 1.5
            }}
          >
            <Tooltip sticky>
              <div className="font-sans text-sm p-2 leading-relaxed max-w-[280px]">
                <strong className="block text-xs uppercase tracking-wider mb-1 flex items-center gap-1" style={{ color: isPrevious ? '#64748b' : '#16a34a' }}>
                  {isPrevious ? '⚪ Previous Route Option' : '🟢 AI-Selected Safest/Fastest Path'}
                </strong>
                <div className="font-bold text-slate-800 mb-1 border-b border-slate-100 pb-1">
                  {segment.road_name || "Connecting Road"}
                </div>
                <div className="font-bold text-indigo-700 text-xs mb-1 bg-indigo-50/50 px-1.5 py-0.5 rounded inline-block">
                  {formatLabel(segment.from_id)} → {formatLabel(segment.to_id)}
                </div>
                <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 mt-1.5 text-xs text-slate-700 border-t border-slate-50 pt-1.5">
                  <div>Distance:</div>
                  <div className="font-semibold">{segment.distance.toFixed(2)} km</div>
                  <div>Travel Time:</div>
                  <div className="font-semibold">{segment.duration.toFixed(2)} mins</div>
                  {segment.estimated_arrival_time && (
                    <>
                      <div>ETA at Road:</div>
                      <div className="font-semibold text-teal-600">{segment.estimated_arrival_time}</div>
                    </>
                  )}
                  {!isPrevious && (
                    <>
                      <div>Congestion:</div>
                      <div className="font-extrabold text-green-600">{(segment.congestion * 100).toFixed(0)}% (Low)</div>
                    </>
                  )}
                </div>
                {!isPrevious && (
                  <div className="bg-green-50 text-green-800 p-1.5 rounded mt-2 border border-green-100 text-[10px] font-medium leading-snug">
                    🚀 Decision: Bypassed heavy future congestion zones dynamically.
                  </div>
                )}
              </div>
            </Tooltip>
          </Polyline>

          {/* Animated beam overlay (Only on active optimal route) */}
          {!isPrevious && (
            <Polyline
              key={`beam-${segment.from_id}-${segment.to_id}`}
              positions={segment.geometry}
              pathOptions={{
                color: '#ffffff', // White flowing light beam
                weight: 3,
                opacity: 0.6,
                dashArray: '8, 12',
                lineCap: 'round',
                lineJoin: 'round',
                className: 'route-path-animation' // flow dash animation
              }}
              interactive={false}
            />
          )}

          {arrowNodes}
        </React.Fragment>
      );
    });
  };

  return (
    <>
      {/* 1. Show Avoided Congested Roads in Crimson Red */}
      {renderRejectedEdges()}

      {/* 2. Show Active Route in Neon Green */}
      {renderActiveRoute()}

      {/* 3. Moving Bike/Vehicle Animation Overlay */}
      {renderMovingVehicle()}
    </>
  );
};

export default RouteVisualizer;
