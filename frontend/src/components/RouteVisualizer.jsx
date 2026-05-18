import React, { useEffect } from 'react';
import { Polyline, Tooltip, useMap, Marker } from 'react-leaflet';
import L from 'leaflet';

const RouteVisualizer = ({ result, isPrevious = false }) => {
  const map = useMap();

  // Dynamic road-segment level congestion colors (0.1 to 0.95)
  const getCongestionStyle = (congestion) => {
    if (congestion > 0.75) return { color: '#ef4444', weight: 8, label: 'Severe Bottleneck (75%+)' }; // Red
    if (congestion > 0.4) return { color: '#f97316', weight: 7, label: 'Moderate Traffic (40%-75%)' }; // Orange
    return { color: '#3b82f6', weight: 6, label: 'Clear Flow (<40%)' }; // Blue
  };

  useEffect(() => {
    if (result && result.full_route_geometry && result.full_route_geometry.length > 0) {
      const bounds = L.latLngBounds(result.full_route_geometry);
      map.fitBounds(bounds, { padding: [50, 50] });
    }
  }, [result, map]);

  if (!result || !result.segments || result.segments.length === 0) return null;

  return (
    <>
      {result.segments.map((segment, idx) => {
        if (!segment.geometry || segment.geometry.length === 0) return null;
        
        let color = '#ef4444';
        let weight = 4;
        let opacity = 0.4;
        let dashArray = '5, 10';
        let lineCap = 'round';
        let lineJoin = 'round';
        let className = '';
        let styleLabel = 'Previous Route';

        if (!isPrevious) {
          const style = getCongestionStyle(segment.congestion || 0.1);
          color = style.color;
          weight = style.weight;
          opacity = 0.85;
          dashArray = undefined;
          className = segment.congestion > 0.75 ? 'route-path-animation bottleneck-pulse' : 'route-path-animation';
          styleLabel = style.label;
        }
        
        const formatLabel = (id) => {
          if (id.startsWith('shop')) return `Shop ${id.slice(4)}`;
          if (id.startsWith('cus')) return `Customer ${id.slice(3)}`;
          if (id.startsWith('part')) return `Partner ${id.slice(4)}`;
          return id;
        };

        const arrowNodes = [];
        if (!isPrevious && segment.geometry.length > 1) {
          // Find the exact midpoint index
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
            
            const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="${color}" width="20px" height="20px" style="transform: rotate(${brng}deg); filter: drop-shadow(0px 1px 2px rgba(0,0,0,0.6)); stroke: white; stroke-width: 1.5px; display: block;"><path d="M12 2L22 20L12 17L2 20L12 2Z" /></svg>`;
            const arrowIcon = L.divIcon({
              html: svg,
              className: '',
              iconSize: [20, 20],
              iconAnchor: [10, 10]
            });
            
            arrowNodes.push(
              <Marker key={`arrow-${idx}-mid`} position={p2} icon={arrowIcon} interactive={false} />
            );
          }
        }

        return (
          <React.Fragment key={`frag-${segment.from_id}-${segment.to_id}`}>
            <Polyline 
              key={isPrevious ? `prev-${segment.from_id}-${segment.to_id}` : `act-${segment.from_id}-${segment.to_id}`}
              positions={segment.geometry} 
              pathOptions={{ 
                color: color, 
                weight: weight,
                opacity: opacity,
                lineCap: lineCap,
                lineJoin: lineJoin,
                dashArray: dashArray,
                smoothFactor: isPrevious ? 1.0 : 1.5,
                className: className
              }}
            >
              {!isPrevious && (
                <Tooltip sticky>
                  <div className="font-sans text-sm p-1 leading-relaxed">
                    <strong className="text-indigo-700 block text-xs uppercase tracking-wider mb-1">
                      {segment.road_name || "Connecting Road"}
                    </strong>
                    <div className="font-bold mb-1">
                      {formatLabel(segment.from_id)} → {formatLabel(segment.to_id)}
                    </div>
                    <div>Distance: <strong>{segment.distance.toFixed(2)} km</strong></div>
                    <div>Travel Time: <strong>{segment.duration.toFixed(2)} mins</strong></div>
                    {segment.estimated_arrival_time && (
                      <div className="text-teal-600 font-semibold">
                        ETA at Road: {segment.estimated_arrival_time}
                      </div>
                    )}
                    {segment.adjusted_edge_cost && (
                      <div className="text-gray-500 text-xs">
                        Adjusted Score: {segment.adjusted_edge_cost}
                      </div>
                    )}
                    <span className="block mt-1 font-bold text-xs" style={{ color: color }}>
                      {styleLabel} ({(segment.congestion * 100).toFixed(0)}%)
                    </span>
                  </div>
                </Tooltip>
              )}
            </Polyline>
            {arrowNodes}
          </React.Fragment>
        );
      })}
    </>
  );
};

export default RouteVisualizer;
