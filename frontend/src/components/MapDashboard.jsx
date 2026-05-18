import { MapContainer, TileLayer, Marker, Popup, useMapEvents, Circle, Tooltip } from 'react-leaflet';
import L from 'leaflet';
import RouteVisualizer from './RouteVisualizer';

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

const partnerIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

// Component to handle map clicks
const MapEvents = ({ onAddLocation }) => {
  useMapEvents({
    click(e) {
      onAddLocation(e.latlng);
    },
  });
  return null;
};

const MapDashboard = ({ locations, onAddLocation, result, previousRoute, simulationData }) => {
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
    if (!result || !result.sequence) return null;
    const stopIndex = result.sequence.indexOf(locId);
    if (stopIndex !== -1) {
      return {
        stopNum: stopIndex + 1
      };
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
              icon={loc.type === 'shop' ? shopIcon : loc.type === 'partner' ? partnerIcon : customerIcon}
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
                        Route Stop #{stopInfo.stopNum}
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

        {/* Previous Faded Route */}
        {previousRoute && <RouteVisualizer result={previousRoute} isPrevious={true} />}

        {/* Active Route */}
        {result && <RouteVisualizer result={result} isPrevious={false} />}

      </MapContainer>
    </div>
  );
};

export default MapDashboard;
