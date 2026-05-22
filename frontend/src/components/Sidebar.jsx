import React from 'react';
import { Play, Trash2, MapPin, Loader, AlertTriangle, CheckCircle, Route } from 'lucide-react';

export const VEHICLES_CONFIG = {
  scooter: { name: 'Moto (Scooter)', emoji: '🛵', etaMultiplier: 1.0, costMultiplier: 1.0, desc: 'Rapido Bike - Fast, standard rate' },
  motorcycle: { name: 'Moto (Sports)', emoji: '🏍️', etaMultiplier: 0.85, costMultiplier: 1.25, desc: 'Express Motorcycle - Faster ETA' },
  bicycle: { name: 'Eco (Bicycle)', emoji: '🚲', etaMultiplier: 1.8, costMultiplier: 0.5, desc: 'Eco Delivery - Green, lowest cost' },
  auto: { name: 'Auto Rickshaw', emoji: '🛺', etaMultiplier: 1.15, costMultiplier: 1.4, desc: 'Medium Cargo - Good in traffic' },
  car: { name: 'Premium (Taxi)', emoji: '🚗', etaMultiplier: 1.3, costMultiplier: 2.2, desc: 'Uber Go Sedan - Premium rate' }
};

const Sidebar = ({ 
  locations, onClear, onOptimize, isLoading, error, successMessage, result, previousRoute,
  placementMode, setPlacementMode,
  selectedShopForCustomers, setSelectedShopForCustomers,
  selectedPartnerForOpt, setSelectedPartnerForOpt,
  selectedShopForOpt, setSelectedShopForOpt,
  departureHour, setDepartureHour,
  vehicleType, setVehicleType
}) => {
  const shops = locations.filter(loc => loc.type === 'shop');
  const partners = locations.filter(loc => loc.type === 'partner');

  const [activeTab, setActiveTab] = React.useState('fleet');

  React.useEffect(() => {
    setActiveTab('fleet');
  }, [result]);

  const config = VEHICLES_CONFIG[vehicleType] || VEHICLES_CONFIG.scooter;

  const getModifiedDuration = (baseDuration) => (baseDuration * config.etaMultiplier).toFixed(1);
  const getModifiedFuel = (baseFuel) => (baseFuel * config.costMultiplier).toFixed(0);
  const getModifiedCost = (baseCost) => {
    if (typeof baseCost === 'string') {
      const num = parseFloat(baseCost.replace(/[^0-9.]/g, ''));
      if (!isNaN(num)) {
        return `₹${(num * config.costMultiplier).toFixed(0)}`;
      }
    }
    const val = parseFloat(baseCost);
    if (!isNaN(val)) {
      return (val * config.costMultiplier).toFixed(0);
    }
    return baseCost;
  };

  const formatLabel = (id) => {
    if (id.startsWith('shop')) return `Shop ${id.slice(4)}`;
    if (id.startsWith('cus')) return `Customer ${id.slice(3)}`;
    if (id.startsWith('part')) return `Partner ${id.slice(4)}`;
    return id;
  };

  return (
    <div className="w-80 bg-white shadow-xl flex flex-col h-full z-10 border-r border-slate-200/80">
      <div className="p-6 bg-white border-b border-slate-100">
        <h1 className="text-2xl font-black text-slate-900 flex items-center gap-2 tracking-tight">
          <Route className="text-indigo-600 stroke-[2.5]" size={26} />
          RouteIQ
        </h1>
        <p className="text-slate-400 text-[10px] mt-1 uppercase font-extrabold tracking-wider">Shop-Based Delivery Assignment</p>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Placement Mode Selector */}
        <div>
          <div className="bg-slate-50 p-1.5 rounded-lg flex border border-slate-200">
            <button 
              onClick={() => setPlacementMode('shop')}
              className={`flex-1 py-1.5 text-sm font-medium rounded-md transition-colors ${placementMode === 'shop' ? 'bg-white shadow-sm text-blue-600' : 'text-slate-500 hover:text-slate-700'}`}
            >
              Shop
            </button>
            <button 
              onClick={() => setPlacementMode('customer')}
              className={`flex-1 py-1.5 text-sm font-medium rounded-md transition-colors ${placementMode === 'customer' ? 'bg-white shadow-sm text-red-600' : 'text-slate-500 hover:text-slate-700'}`}
            >
              Customer
            </button>
            <button 
              onClick={() => setPlacementMode('partner')}
              className={`flex-1 py-1.5 text-sm font-medium rounded-md transition-colors ${placementMode === 'partner' ? 'bg-white shadow-sm text-green-600' : 'text-slate-500 hover:text-slate-700'}`}
            >
              Partner
            </button>
          </div>
          
          {(placementMode === 'customer' || placementMode === 'partner') && (
            <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 mt-3">
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Assign {placementMode === 'customer' ? 'Customer' : 'Partner'} to Shop
              </label>
              <select 
                value={selectedShopForCustomers} 
                onChange={(e) => setSelectedShopForCustomers(e.target.value)}
                className="w-full p-2 rounded border border-slate-300 text-sm"
              >
                <option value="" disabled>Select a Shop</option>
                {shops.map(shop => (
                  <option key={shop.id} value={shop.id}>{shop.id}</option>
                ))}
              </select>
            </div>
          )}
        </div>

        {/* Route Assignment & Controls */}
        <div className="space-y-4">
          <div className="bg-blue-50 p-4 rounded-xl border border-blue-100 space-y-3">
            <h3 className="font-semibold text-blue-900 text-sm">Route Assignment</h3>
            <div>
              <label className="block text-xs font-medium text-blue-800 mb-1">Delivery Partner</label>
              <select 
                value={selectedPartnerForOpt} 
                onChange={(e) => setSelectedPartnerForOpt(e.target.value)}
                className="w-full p-2 rounded border border-blue-200 text-sm bg-white"
              >
                <option value="" disabled>Select Partner</option>
                {partners.map(p => (
                  <option key={p.id} value={p.id}>{p.id}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-blue-800 mb-1">Target Shop</label>
              <select 
                value={selectedShopForOpt} 
                onChange={(e) => setSelectedShopForOpt(e.target.value)}
                className="w-full p-2 rounded border border-blue-200 text-sm bg-white"
              >
                <option value="" disabled>Select Shop</option>
                {shops.map(shop => (
                  <option key={shop.id} value={shop.id}>{shop.id}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-blue-800 mb-1">Departure Hour</label>
              <select 
                value={departureHour} 
                onChange={(e) => setDepartureHour(Number(e.target.value))}
                className="w-full p-2 rounded border border-blue-200 text-sm bg-white"
              >
                <option value={9}>09:00 AM (Morning Rush)</option>
                <option value={13}>01:00 PM (Midday Traffic)</option>
                <option value={18}>06:00 PM (Evening Rush)</option>
                <option value={23}>11:00 PM (Late Night Freeflow)</option>
              </select>
            </div>

            {/* Ride / Delivery Mode Selector */}
            <div className="space-y-2">
              <label className="block text-xs font-semibold text-blue-900">Ride / Delivery Mode</label>
              <div className="grid grid-cols-5 gap-1 bg-white p-1 rounded-lg border border-blue-200">
                {Object.entries(VEHICLES_CONFIG).map(([key, item]) => {
                  const isSelected = vehicleType === key;
                  return (
                    <button
                      key={key}
                      onClick={() => setVehicleType(key)}
                      className={`flex flex-col items-center justify-center py-2 px-1 rounded transition-all ${
                        isSelected 
                          ? 'bg-blue-600 text-white shadow-md scale-[1.05] font-bold' 
                          : 'bg-slate-50 text-slate-600 hover:bg-slate-100 hover:text-slate-850'
                      }`}
                      title={item.desc}
                      type="button"
                    >
                      <span className="text-lg mb-0.5">{item.emoji}</span>
                      <span className="text-[8px] tracking-tight leading-none text-center">{item.name.split(' ')[0]}</span>
                    </button>
                  );
                })}
              </div>
              <div className="text-[10px] text-slate-500 bg-white/70 p-2 rounded border border-blue-100/50 leading-relaxed italic shadow-inner">
                {config.desc} <br/>
                <span className="font-semibold text-blue-700">Speed: {config.etaMultiplier}x</span> • <span className="font-semibold text-green-700">Cost: {config.costMultiplier}x</span>
              </div>
            </div>

            <button 
              onClick={onOptimize}
              disabled={isLoading || locations.length < 2 || !selectedPartnerForOpt || !selectedShopForOpt}
              className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-lg font-medium flex justify-center items-center gap-2 transition-colors mt-2"
            >
              {isLoading ? <Loader className="animate-spin" size={20} /> : <Play size={20} />}
              {isLoading ? "Optimizing..." : "Optimize Route"}
            </button>
          </div>
          
          <button 
            onClick={onClear}
            disabled={isLoading || locations.length === 0}
            className="w-full py-2 bg-slate-100 hover:bg-slate-200 disabled:opacity-50 text-slate-700 rounded-lg font-medium flex justify-center items-center gap-2 transition-colors"
          >
            <Trash2 size={18} />
            Clear Map
          </button>
        </div>

        {/* Error State */}
        {error && (
          <div className="p-4 bg-red-50 text-red-700 border border-red-200 rounded-lg flex items-start gap-3 text-sm">
            <AlertTriangle className="shrink-0 mt-0.5" size={18} />
            <span>{error}</span>
          </div>
        )}

        {/* Success State */}
        {successMessage && (
          <div className="p-4 bg-green-50 text-green-700 border border-green-200 rounded-lg flex items-start gap-3 text-sm">
            <CheckCircle className="shrink-0 mt-0.5" size={18} />
            <span>{successMessage}</span>
          </div>
        )}

        {/* Results Dashboard */}
        {result && !error && (() => {
          const routeKeys = result.routes ? Object.keys(result.routes) : [];
          
          return (
            <div className="space-y-4">
              <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-sm space-y-3">
                <h4 className="font-semibold text-slate-800 border-b pb-2 flex justify-between items-center">
                  <span>Optimized Route</span>
                  <span className={`px-2 py-0.5 rounded text-xs font-bold
                    ${result.traffic_level === 'Low' ? 'bg-blue-100 text-blue-700' : 
                      result.traffic_level === 'Moderate' ? 'bg-orange-100 text-orange-700' : 
                      'bg-red-100 text-red-700'}`}>
                    {result.traffic_level} Traffic
                  </span>
                </h4>

                {/* Horizontal Route Tabs Selector */}
                {routeKeys.length > 0 && (
                  <div className="flex border-b border-slate-200 gap-2 mb-3 overflow-x-auto pb-1">
                    <button
                      onClick={() => setActiveTab('fleet')}
                      className={`pb-2 px-1 text-xs font-semibold whitespace-nowrap transition-colors border-b-2 ${activeTab === 'fleet' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
                    >
                      Fleet Overview
                    </button>
                    {routeKeys.map(k => {
                      const label = k.startsWith('part') ? `Partner ${k.slice(4)}` : k;
                      return (
                        <button
                          key={k}
                          onClick={() => setActiveTab(k)}
                          className={`pb-2 px-1 text-xs font-semibold whitespace-nowrap transition-colors border-b-2 ${activeTab === k ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
                        >
                          {label}
                        </button>
                      );
                    })}
                  </div>
                )}

                <div className="bg-slate-50 border border-slate-200 p-3 rounded-lg space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-slate-500 font-medium">Version</span>
                    <span className="text-xs font-mono text-slate-700">{result.route_version}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-slate-500 font-medium">AI Route Score</span>
                    <span className="text-xs font-bold text-slate-700">{result.route_score}</span>
                  </div>
                  {previousRoute && (
                    <div className="flex justify-between items-center pt-1 mt-1 border-t border-slate-200">
                      <span className="text-xs text-slate-500 font-medium">Score Delta</span>
                      <span className={`text-xs font-bold ${result.route_score < previousRoute.route_score ? 'text-green-600' : 'text-orange-600'}`}>
                        {result.route_score < previousRoute.route_score ? 'Improved by ' : 'Penalty of '}
                        {Math.abs((previousRoute.route_score - result.route_score).toFixed(2))}
                      </span>
                    </div>
                  )}
                  <div className="pt-2 border-t border-slate-200">
                    <p className="text-[10px] uppercase text-slate-400 font-bold mb-1">Reasoning</p>
                    <p className="text-xs text-slate-600 italic">{result.optimization_reason}</p>
                  </div>
                </div>

                {activeTab === 'fleet' ? (
                  <>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="bg-slate-50 p-2 rounded">
                        <p className="text-xs text-slate-500 uppercase tracking-wider">Fleet Dist</p>
                        <p className="font-medium text-slate-900">{result.total_distance} km</p>
                      </div>
                      <div className="bg-slate-50 p-2 rounded">
                        <p className="text-xs text-slate-500 uppercase tracking-wider">Fleet Max Time</p>
                        <p className="font-medium text-slate-900">{getModifiedDuration(result.total_duration)} min</p>
                      </div>
                      <div className="bg-slate-50 p-2 rounded">
                        <p className="text-xs text-slate-500 uppercase tracking-wider">Fleet Fuel</p>
                        <p className="font-medium text-slate-900">₹{getModifiedFuel(result.fuel)}</p>
                      </div>
                      <div className="bg-slate-50 p-2 rounded">
                        <p className="text-xs text-slate-500 uppercase tracking-wider">Fleet Cost</p>
                        <p className="font-medium text-slate-900">{getModifiedCost(result.cost)}</p>
                      </div>
                    </div>

                    <div className="space-y-2 pt-2 border-t">
                      <p className="text-xs text-slate-500 uppercase tracking-wider font-bold mb-1">Fleet Assignments</p>
                      {Object.entries(result.routes).map(([pId, r]) => {
                        const pName = pId.startsWith('part') ? `Partner ${pId.slice(4)}` : pId;
                        const custs = r.sequence
                          .filter(id => id.startsWith('cus'))
                          .map(id => `Customer ${id.slice(3)}`);
                        return (
                          <div key={pId} className="bg-slate-50 p-2 rounded border border-slate-200/60 text-xs">
                            <div className="font-bold text-indigo-700 flex justify-between">
                              <span>{pName}</span>
                              <span className="text-slate-500 font-normal">{r.total_distance} km • {getModifiedDuration(r.total_duration)} min</span>
                            </div>
                            <div className="text-slate-600 mt-1">
                              {custs.length > 0 ? (
                                <span>Delivers to: <strong className="text-slate-800">{custs.join(', ')}</strong></span>
                              ) : (
                                <span className="text-slate-400 italic">No assigned customers (Idle)</span>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </>
                ) : (() => {
                  const activeRoute = result.routes[activeTab];
                  if (!activeRoute) return <div className="text-xs text-slate-500 italic">Route data not found.</div>;
                  const activeCustomers = activeRoute.sequence
                    .filter(id => id.startsWith('cus'))
                    .map(id => `Customer ${id.slice(3)}`);
                    
                  return (
                    <>
                      <div className="text-xs text-slate-600 bg-indigo-50/50 p-2.5 rounded border border-indigo-100/50 space-y-1">
                        <p><strong>Delivery Partner:</strong> {formatLabel(activeRoute.partner_id)}</p>
                        <p><strong>Assigned Shop:</strong> {formatLabel(result.shop_id)}</p>
                        <p><strong>Assigned Customers:</strong> {activeCustomers.length > 0 ? activeCustomers.join(', ') : 'None'}</p>
                      </div>

                      <div className="grid grid-cols-2 gap-3">
                        <div className="bg-slate-50 p-2 rounded">
                          <p className="text-xs text-slate-500 uppercase tracking-wider">Distance</p>
                          <p className="font-medium text-slate-900">{activeRoute.total_distance} km</p>
                        </div>
                        <div className="bg-slate-50 p-2 rounded">
                          <p className="text-xs text-slate-500 uppercase tracking-wider">Est. Time</p>
                          <p className="font-medium text-slate-900">{getModifiedDuration(activeRoute.total_duration)} min</p>
                        </div>
                        <div className="bg-slate-50 p-2 rounded">
                          <p className="text-xs text-slate-500 uppercase tracking-wider">Fuel Cost</p>
                          <p className="font-medium text-slate-900">₹{getModifiedFuel(activeRoute.fuel)}</p>
                        </div>
                        <div className="bg-slate-50 p-2 rounded">
                          <p className="text-xs text-slate-500 uppercase tracking-wider">Route Cost</p>
                          <p className="font-medium text-slate-900">{getModifiedCost(activeRoute.cost)}</p>
                        </div>
                      </div>

                      <div className="pt-2 border-t">
                        <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Delivery Sequence</p>
                        <div className="flex flex-col gap-2">
                          {activeRoute.sequence.map((locationId, i) => (
                            <div key={i} className="flex items-center text-sm">
                              <span className={`w-6 h-6 flex items-center justify-center rounded-full text-xs font-bold text-white shrink-0
                                ${i === 0 ? 'bg-green-500' : i === 1 ? 'bg-blue-500' : 'bg-red-500'}`}>
                                {i + 1}
                              </span>
                              <span className="ml-2 text-slate-700 truncate">{formatLabel(locationId)}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="pt-2 border-t">
                        <p className="text-xs text-slate-500 uppercase tracking-wider mb-3">Time-Aware Segment Timeline</p>
                        <div className="flex flex-col gap-3 relative border-l border-indigo-100 pl-4 ml-2">
                          {activeRoute.segments.map((segment, i) => {
                            const isHigh = segment.congestion > 0.75;
                            const isMod = segment.congestion > 0.4;
                            
                            return (
                              <div key={i} className="relative group text-sm bg-white p-3 rounded-lg border border-slate-200 shadow-sm transition-all hover:shadow-md">
                                <div className={`absolute -left-[25px] top-[14px] w-4 h-4 rounded-full border-2 border-white shadow-sm flex items-center justify-center
                                  ${isHigh ? 'bg-red-500' : isMod ? 'bg-orange-500' : 'bg-blue-500'}`} 
                                />
                                
                                <div>
                                  <div className="flex justify-between items-start mb-1">
                                    <span className="font-bold text-slate-800 text-xs truncate max-w-[120px]">
                                      {segment.road_name || "Connector Link"}
                                    </span>
                                    {segment.estimated_arrival_time && (
                                      <span className="text-[10px] font-semibold text-teal-600 bg-teal-50 px-1.5 py-0.5 rounded">
                                        {segment.estimated_arrival_time}
                                      </span>
                                    )}
                                  </div>
                                  
                                  <div className="flex items-center gap-1.5 text-xs text-slate-500 mb-2">
                                    <span>{formatLabel(segment.from_id)}</span>
                                    <span>→</span>
                                    <span>{formatLabel(segment.to_id)}</span>
                                  </div>

                                  <div className="flex justify-between items-center text-xs">
                                    <div className="flex gap-2 text-slate-500 font-medium">
                                      <span>{segment.distance.toFixed(1)} km</span>
                                      <span>•</span>
                                      <span>{getModifiedDuration(segment.duration)} min</span>
                                    </div>
                                    
                                    <span className={`px-1.5 py-0.5 text-[9px] font-extrabold rounded uppercase tracking-wider
                                      ${isHigh ? 'bg-red-100 text-red-700 animate-pulse' : 
                                        isMod ? 'bg-orange-100 text-orange-700' : 
                                        'bg-blue-100 text-blue-700'}`}>
                                      {isHigh ? `Severe (${(segment.congestion * 100).toFixed(0)}%)` : 
                                       isMod ? `Moderate (${(segment.congestion * 100).toFixed(0)}%)` : 
                                       `Clear`}
                                    </span>
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    </>
                  );
                })()}
              </div>
            </div>
          );
        })()}

        {/* Locations List */}
        <div>
          <h3 className="font-semibold text-slate-800 mb-3 flex items-center justify-between">
            Locations <span className="bg-slate-200 text-slate-600 px-2 py-0.5 rounded-full text-xs">{locations.length}</span>
          </h3>
          {locations.length === 0 ? (
            <p className="text-sm text-slate-500 italic text-center py-4 bg-slate-50 rounded-lg border border-dashed border-slate-300">
              Select a mode above and click on the map to add locations.
            </p>
          ) : (
            <div className="space-y-2">
              {locations.map((loc) => {
                const formatLabel = (id) => {
                  if (id.startsWith('shop')) return `Shop ${id.slice(4)}`;
                  if (id.startsWith('cus')) return `Customer ${id.slice(3)}`;
                  if (id.startsWith('part')) return `Partner ${id.slice(4)}`;
                  return id;
                };
                
                return (
                  <div key={loc.id} className="flex flex-col gap-1 p-3 bg-white border border-slate-200 rounded-lg shadow-sm">
                    <div className="flex items-center gap-3">
                      <div className={`w-3 h-3 rounded-full ${loc.type === 'shop' ? 'bg-blue-500' : loc.type === 'customer' ? 'bg-red-500' : 'bg-green-500'}`} />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-slate-900 truncate">
                          {formatLabel(loc.id)}
                        </p>
                      </div>
                    </div>
                    {(loc.type === 'customer' || loc.type === 'partner') && loc.shop_id && (
                      <p className="text-xs text-slate-500 ml-6">
                        Belongs to: {formatLabel(loc.shop_id)}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Sidebar;
