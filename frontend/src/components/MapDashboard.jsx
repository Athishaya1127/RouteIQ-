import { MapContainer, TileLayer, Marker, Popup, useMapEvents, Circle, Tooltip } from 'react-leaflet';
import L from 'leaflet';
import RouteVisualizer from './RouteVisualizer';
import { VEHICLES_CONFIG } from './Sidebar';

// Fix for default Leaflet icons in React
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

// Custom icons
const shopIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

const customerIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

const getPartnerIcon = (partnerId, result, vehicleType) => {
  const emoji = VEHICLES_CONFIG[vehicleType]?.emoji || '🛵';
  
  let color = '#22c55e'; // Default partner green
  if (result && result.routes) {
    const route = result.routes[partnerId];
    if (route && route.vehicle_index !== undefined) {
      const idx = route.vehicle_index;
      const colors = ['#22c55e', '#f97316', '#a855f7', '#eab308', '#64748b', '#000000', '#d97706'];
      color = colors[idx % colors.length];
    }
  }

  const html = `
    <div class="partner-map-marker" style="--partner-color: ${color};">
      <div class="partner-marker-ring"></div>
      <div class="partner-marker-bg">
        <span class="partner-emoji">${emoji}</span>
      </div>
    </div>
  `;

  return L.divIcon({
    html: html,
    className: 'partner-div-icon',
    iconSize: [40, 40],
    iconAnchor: [20, 20],
    popupAnchor: [0, -20]
  });
};

// Component to handle map clicks
const MapEvents = ({ onAddLocation }) => {
  useMapEvents({
    click(e) {
      onAddLocation(e.latlng);
    },
  });
  return null;
};

const MapDashboard = ({ locations, onAddLocation, result, previousRoute, simulationData, vehicleType }) => {
  const defaultCenter = [13.0827, 80.2707];

  const ZONES_COORDS = {
    "T Nagar": [13.0418, 80.2341],
    "OMR": [12.9229, 80.2234],
    "Velachery": [12.9815, 80.2180],
    "Anna Nagar": [13.0850, 80.2101],
    "Tambaram": [12.9249, 80.1000],
    "Adyar": [13.0012, 80.2565]
  };

  const getStopInfo = (locId) => {
    if (!result) return null;
    if (result.routes) {
      for (const [partnerId, route] of Object.entries(result.routes)) {
        const stopIndex = route.sequence.indexOf(locId);
        if (stopIndex !== -1) {
          const partnerName = partnerId.startsWith('part') ? `Partner ${partnerId.slice(4)}` : partnerId;
          return {
            stopNum: stopIndex + 1,
            partnerName: partnerName
          };
        }
      }
    }
    if (result.sequence) {
      const stopIndex = result.sequence.indexOf(locId);
      if (stopIndex !== -1) {
        return {
          stopNum: stopIndex + 1
        };
      }
    }
    return null;
  };

  return (
    <div className="w-full h-full relative z-0">
      <MapContainer
        center={defaultCenter}
        zoom={12}
        className="w-full h-full"
        zoomControl={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
        />

        <MapEvents onAddLocation={onAddLocation} />

        {locations.map((loc) => {
          const stopInfo = getStopInfo(loc.id);

          const formatLabel = (id) => {
            if (id.startsWith('shop')) return `Shop ${id.slice(4)}`;
            if (id.startsWith('cus')) return `Customer ${id.slice(3)}`;
            if (id.startsWith('part')) return `Partner ${id.slice(4)}`;
            return id;
          };

          return (
            <Marker
              key={loc.id}
              position={[loc.lat, loc.lng]}
              icon={loc.type === 'shop' ? shopIcon : loc.type === 'partner' ? getPartnerIcon(loc.id, result, vehicleType) : customerIcon}
            >
              <Popup>
                <div className="text-center font-sans">
                  <strong>
                    {formatLabel(loc.id)}
                  </strong>
                  <br />
                  {loc.type === 'customer' && loc.shop_id && (
                    <div className="text-xs text-slate-500 mb-1">
                      Shop: {formatLabel(loc.shop_id)}
                    </div>
                  )}
                  <span className="text-xs text-gray-500">
                    {loc.lat.toFixed(4)}, {loc.lng.toFixed(4)}
                  </span>
                  {stopInfo && (
                    <div className="mt-2">
                      <span className="bg-blue-100 text-blue-800 rounded px-2 py-1 text-xs font-bold inline-block">
                        Route Stop #{stopInfo.stopNum} {stopInfo.partnerName ? `(${stopInfo.partnerName})` : ''}
                      </span>
                    </div>
                  )}
                </div>
              </Popup>
            </Marker>
          );
        })}

        {/* Congestion Circles Overlay */}
        {simulationData && simulationData.traffic && simulationData.traffic.map((zone, idx) => {
          const coords = ZONES_COORDS[zone.zone];
          if (!coords) return null;
          
          const isHighCongestion = zone.predicted_congestion > 0.75;
          const isRerouteTriggered = zone.reroute_triggered;
          
          return (
            <Circle
              key={`traffic-${idx}`}
              center={coords}
              radius={2000} // 2km radius
              eventHandlers={{
                click: (e) => {
                  if (onAddLocation) {
                    onAddLocation(e.latlng);
                  }
                }
              }}
              pathOptions={{
                fillColor: isHighCongestion ? '#ef4444' : (zone.predicted_congestion > 0.4 ? '#f97316' : '#22c55e'),
                fillOpacity: 0.2,
                color: isHighCongestion ? '#b91c1c' : (zone.predicted_congestion > 0.4 ? '#c2410c' : '#15803d'),
                weight: 1,
                dashArray: isRerouteTriggered ? '5, 5' : undefined
              }}
            >
              <Popup>
                <div className="text-sm">
                  <strong>{zone.zone}</strong><br/>
                  Congestion: {(zone.predicted_congestion * 100).toFixed(1)}%<br/>
                  Density: {zone.vehicle_density} veh/km²<br/>
                  {isRerouteTriggered && <span className="text-red-500 font-bold">Reroute Triggered!</span>}
                </div>
              </Popup>
            </Circle>
          );
        })}

        {/* ML Demand Forecasting Hotspots Overlay */}
        {simulationData && simulationData.orchestration && simulationData.orchestration.demand_forecasts && 
          Object.entries(simulationData.orchestration.demand_forecasts).map(([zoneName, demandVal], idx) => {
            const coords = ZONES_COORDS[zoneName];
            if (!coords || demandVal <= 0.40) return null; // Only show significant hotspots
            
            return (
              <Circle
                key={`demand-${idx}`}
                center={coords}
                radius={1500}
                eventHandlers={{
                  click: (e) => {
                    if (onAddLocation) {
                      onAddLocation(e.latlng);
                    }
                  }
                }}
                pathOptions={{
                  fillColor: '#8b5cf6', // Indigo/Purple
                  fillOpacity: 0.15 + (demandVal * 0.1),
                  color: '#6d28d9',
                  weight: demandVal > 0.70 ? 2 : 1,
                  dashArray: demandVal > 0.70 ? '4, 8' : undefined
                }}
              >
                <Tooltip sticky>
                  <div className="font-sans text-xs p-1">
                    <strong className="text-purple-700 block mb-0.5">🔮 ML Demand Forecast</strong>
                    Zone: <strong>{zoneName}</strong>
                    <br/>
                    Expected Order Density: <strong>{Math.round(demandVal * 100)}%</strong>
                    {demandVal > 0.70 && <span className="block text-red-500 font-extrabold mt-1 animate-pulse">⚠️ Spike Looming!</span>}
                  </div>
                </Tooltip>
              </Circle>
            );
          })
        }

        {/* Previous Faded Routes */}
        {previousRoute && previousRoute.routes && Object.values(previousRoute.routes).map((route, idx) => (
          <RouteVisualizer key={`prev-route-${route.partner_id}`} result={route} isPrevious={true} vehicleIndex={idx} />
        ))}

        {/* Active Routes */}
        {result && result.routes && Object.values(result.routes).map((route) => (
          <RouteVisualizer 
            key={`act-route-${route.partner_id}`} 
            result={route} 
            isPrevious={false} 
            vehicleIndex={route.vehicle_index} 
            vehicleType={vehicleType}
          />
        ))}

      </MapContainer>

      {/* Map Legend overlay */}
      {result && (
        <div className="absolute bottom-6 left-6 bg-white/95 backdrop-blur-md px-4 py-3 rounded-2xl shadow-xl border border-slate-200/80 z-[1000] font-sans text-xs flex flex-col gap-2.5 min-w-[200px]">
          <div className="font-bold text-slate-800 tracking-wider uppercase text-[10px] border-b border-slate-100 pb-1.5">
            🚦 AI Route Orchestrator
          </div>
          {result.routes && Object.values(result.routes).map((route) => {
            const vehicleColors = ['#22c55e', '#f97316', '#a855f7', '#eab308', '#64748b', '#000000', '#d97706'];
            const vIdx = route.vehicle_index !== undefined ? route.vehicle_index : 0;
            const color = vehicleColors[vIdx % vehicleColors.length] || '#22c55e';
            const partnerName = route.partner_id.startsWith('part') 
              ? `Partner ${route.partner_id.slice(4)}` 
              : route.partner_id;
            return (
              <div key={route.partner_id} className="flex items-center gap-3">
                <span 
                  className="w-5 h-2 rounded-full inline-block shadow-sm" 
                  style={{ 
                    backgroundColor: color, 
                    boxShadow: `0 1px 3px ${color}80` 
                  }}
                />
                <span className="font-semibold text-slate-700">{partnerName} Route</span>
              </div>
            );
          })}
          <div className="flex items-center gap-3">
            <span className="w-5 h-2 rounded-full bg-[#ef4444] border-dashed border border-red-500 inline-block shadow-sm shadow-red-500/50 animate-pulse"></span>
            <span className="font-semibold text-slate-700">Future Congestion Avoided</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default MapDashboard;
