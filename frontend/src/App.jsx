import React, { useState, useEffect } from 'react';
import MapDashboard from './components/MapDashboard';
import Sidebar from './components/Sidebar';
import AIPanel from './components/AIPanel';
import axios from 'axios';

function App() {
  const [locations, setLocations] = useState([]);
  const [optimizationResult, setOptimizationResult] = useState(null);
  const [previousRoute, setPreviousRoute] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [placementMode, setPlacementMode] = useState('shop'); // shop, customer, partner
  const [simulationData, setSimulationData] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  // New State Variables
  const [selectedShopForCustomers, setSelectedShopForCustomers] = useState('');
  const [selectedPartnerForOpt, setSelectedPartnerForOpt] = useState('');
  const [selectedShopForOpt, setSelectedShopForOpt] = useState('');
  const [departureHour, setDepartureHour] = useState(9);

  // Counters for human readable IDs
  const [shopCounter, setShopCounter] = useState(0);
  const [customerCounter, setCustomerCounter] = useState(0);
  const [partnerCounter, setPartnerCounter] = useState(0);

  // Auto-Cleanup: Reset route states when shop or partner changes
  useEffect(() => {
    setOptimizationResult(null);
    setPreviousRoute(null);
    setSuccessMessage(null);
    setError(null);
  }, [selectedShopForOpt, selectedPartnerForOpt]);

  // Handle Websocket updates
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws');
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'SIMULATION_TICK') {
          setSimulationData(data);

          // Check for reroute trigger
          if (data.traffic) {
            const shouldReroute = data.traffic.some(t => t.reroute_triggered);
            // In a real app, you'd only reroute if the current route goes through the zone
            // For demo, we just trigger it if we have an active route
            if (shouldReroute && optimizationResult && !isLoading) {
              console.log("Auto rerouting triggered by AI prediction!");
              handleOptimize(true); // Reuse existing function to fetch new route, pass true for isAutoReroute
            }
          }
        }
      } catch (err) {
        console.error("Failed to parse websocket message", err);
      }
    };
    return () => ws.close();
  }, [optimizationResult, isLoading, locations, selectedPartnerForOpt, selectedShopForOpt]);

  const handleAddLocation = (latlng) => {
    if (placementMode === 'customer' && !selectedShopForCustomers) {
      setError("Please select a shop for the customer first.");
      return;
    }

    setError(null);
    let newId = '';
    if (placementMode === 'shop') {
      setShopCounter(prev => prev + 1);
      newId = `shop${shopCounter + 1}`;
    } else if (placementMode === 'customer') {
      setCustomerCounter(prev => prev + 1);
      newId = `cus${customerCounter + 1}`;
    } else if (placementMode === 'partner') {
      setPartnerCounter(prev => prev + 1);
      newId = `part${partnerCounter + 1}`;
    }

    const newLocation = {
      id: newId,
      type: placementMode,
      lat: latlng.lat,
      lng: latlng.lng
    };

    if (placementMode === 'customer') {
      newLocation.shop_id = selectedShopForCustomers;
    }

    setLocations([...locations, newLocation]);
  };

  const handleClear = () => {
    setLocations([]);
    setOptimizationResult(null);
    setPreviousRoute(null);
    setError(null);
    setSuccessMessage(null);
    setSelectedShopForCustomers('');
    setSelectedPartnerForOpt('');
    setSelectedShopForOpt('');
    setShopCounter(0);
    setCustomerCounter(0);
    setPartnerCounter(0);
  };

  const handleOptimize = async (isAutoReroute = false) => {
    // STEP 1 - BUTTON VALIDATION
    const customersForShop = locations.filter(loc => loc.type === 'customer' && loc.shop_id === selectedShopForOpt);
    if (!selectedPartnerForOpt || !selectedShopForOpt) {
      setError("Please select a Delivery Partner and a Shop to optimize.");
      return;
    }
    if (customersForShop.length === 0) {
      setError("No customers found for the selected shop. Please add customers first.");
      return;
    }

    // STEP 6 - DEBUG LOGGING
    console.log("[RouteIQ] Optimization request started...");
    setIsLoading(true);
    setError(null);
    setSuccessMessage(null);

    const payload = {
      locations: locations,
      selected_partner_id: selectedPartnerForOpt,
      selected_shop_id: selectedShopForOpt,
      departure_hour: departureHour
    };
    
    console.log("[RouteIQ] Payload sent:", payload);

    try {
      const response = await axios.post('http://localhost:8000/optimize-route', payload);
      console.log("[RouteIQ] Response received:", response.data);
      
      if (isAutoReroute && optimizationResult) {
        setPreviousRoute(optimizationResult);
      }
      
      setOptimizationResult(response.data);
      setSuccessMessage("AI route optimized successfully.");
      console.log("[RouteIQ] Route rendered successfully.");
    } catch (err) {
      setError(err.response?.data?.detail || "Route optimization failed. Please check backend connection.");
      console.error("[RouteIQ] Optimization Error:", err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-full overflow-hidden bg-gray-50">
      <Sidebar
        locations={locations}
        onClear={handleClear}
        onOptimize={handleOptimize}
        isLoading={isLoading}
        error={error}
        successMessage={successMessage}
        result={optimizationResult}
        previousRoute={previousRoute}
        placementMode={placementMode}
        setPlacementMode={setPlacementMode}
        selectedShopForCustomers={selectedShopForCustomers}
        setSelectedShopForCustomers={setSelectedShopForCustomers}
        selectedPartnerForOpt={selectedPartnerForOpt}
        setSelectedPartnerForOpt={setSelectedPartnerForOpt}
        selectedShopForOpt={selectedShopForOpt}
        setSelectedShopForOpt={setSelectedShopForOpt}
        departureHour={departureHour}
        setDepartureHour={setDepartureHour}
      />
      <div className="flex-1 relative">
        <MapDashboard
          locations={locations}
          onAddLocation={handleAddLocation}
          result={optimizationResult}
          previousRoute={previousRoute}
          simulationData={simulationData}
        />
      </div>
      <AIPanel simulationData={simulationData} result={optimizationResult} />
    </div>
  );
}

export default App;

