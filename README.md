# RouteIQ - AI-Powered Delivery Route Optimization

RouteIQ is a multi-vehicle urban-delivery route optimization prototype. It uses OpenRouteService (ORS), with an OSRM fallback, for road-network distances, baseline durations, and directions. A FastAPI backend prepares a vehicle-routing problem and Google OR-Tools jointly assigns deliveries to available partners and orders their stops. A React and Leaflet dashboard lets users place shops, customers, and partners and inspect the resulting routes.

**Important:** Road-network data is provider-derived, but traffic inputs, forecasts, proactive incidents, demand spikes, and several risk and delay metrics are simulated. This is a demonstration system, not a live traffic or production dispatch service. See [Data accuracy and limitations](#data-accuracy-and-limitations).

## Problem overview

For a selected shop, a delivery operation must decide which eligible partner should serve each customer and in what order. A useful plan balances estimated travel time and distance while respecting operational rules such as shop pickup, partner availability and capacity, service time, customer delivery windows, and maximum route duration.

Choosing the nearest next stop in isolation may produce a worse fleet-wide plan or violate a constraint. RouteIQ formulates the task as a multi-vehicle vehicle-routing problem (VRP), jointly assigning the selected shop's customers and sequencing each partner's stops.

**Inputs**

- Shop, customer, and delivery-partner map coordinates.
- The selected shop; customers are assigned to a shop.
- Available partners associated with the selected shop.
- Optional customer demand, service time, and delivery-window offsets.
- Optional partner capacity and a planned departure hour.

**Outputs**

- An open route per active partner: partner start, required shop pickup, then assigned customers. A return trip is not included.
- Road geometry, segment distance and estimated duration, customer arrival times, and route totals.
- A validation result and demo traffic, demand, and risk indicators.

## How it works

1. **Place locations.** Select Shop, Customer, or Partner in the sidebar and click the map. Customers and partners are associated with a shop. Clicking an existing marker selects its corresponding shop or partner.
2. **Configure the request.** Select a target shop, departure hour, and vehicle display mode. The frontend sends the locations and optional operational constraints to the backend.
3. **Validate and prepare nodes.** The backend checks the selected shop, its customers, and available partners associated with it. It creates a start node per partner, a duplicated shop pickup node per partner, and customer nodes.
4. **Fetch a road matrix.** ORS supplies pairwise road distance and baseline duration when configured. If the ORS key is missing or a request fails, OSRM is attempted. Unreachable legs remain unavailable to the optimizer.
5. **Estimate demo traffic.** Each leg is associated with the nearest predefined zone to its midpoint. The traffic predictor uses the latest simulator state to estimate congestion, which adjusts baseline travel duration. In the current application, the live inputs to this predictor are synthetic.
6. **Build costs and optimize.** The cost engine combines normalized predicted duration, predicted delay, road distance, and a congestion penalty with configurable weights. OR-Tools jointly assigns customers and chooses stop sequences using a bounded solver time.
7. **Check feasibility.** The selected plan is independently checked for complete, non-duplicated customer coverage, reachability, capacities, time windows, and maximum route duration.
8. **Get directions and display.** The backend retrieves road geometry and directions for each selected leg, applies its congestion estimate to direction durations for displayed ETAs, and checks final constraints. The frontend renders the route, stop markers, and metrics.
9. **Stream demo events.** A background simulator creates observations for six named zones about every five seconds, writes them to SQLite, and broadcasts updates over WebSocket. The orchestrator can demonstrate simulated rerouting and partner-repositioning events.

## Architecture

```text
React + Leaflet browser
  ├─ Sidebar: placement, shop/partner selection, controls, summaries
  ├─ MapDashboard: map clicks, markers, route and traffic overlays
  ├─ RouteVisualizer: route geometry, leg details, vehicle animation
  └─ AIPanel: demo forecasts, risk values, orchestration events
       │ HTTP POST /optimize-route          │ WebSocket /ws
       ▼                                    ▲
FastAPI application (backend/main.py)       │
  ├─ Pydantic request schemas               │
  ├─ optimization_workflow                  │
  │    ├─ routing_api: ORS / OSRM           │
  │    ├─ traffic_prediction + road_predictor
  │    ├─ cost_engine
  │    ├─ optimizer: Google OR-Tools VRP
  │    └─ route_validator
  ├─ simulation → orchestrator ─────────────┘
  └─ SQLAlchemy → SQLite traffic logs
```

The user-triggered optimization uses HTTP and returns a route response. Separately, the backend startup task runs the traffic simulator and publishes WebSocket updates. The SQLite database stores simulation traffic logs; it is not a production order, fleet, or verified historical-traffic database.

### Main modules

| Area | Responsibilities |
| --- | --- |
| `frontend/src/App.jsx` | UI state, location creation/selection, optimization request, WebSocket subscription |
| `frontend/src/components/Sidebar.jsx` | Placement modes, selectors, optimization controls, route summaries |
| `frontend/src/components/MapDashboard.jsx` | Leaflet map, click-to-place, markers, traffic overlays |
| `frontend/src/components/RouteVisualizer.jsx` | Route polylines, segment details, partner animation |
| `frontend/src/components/AIPanel.jsx` | Simulator forecasts, risk values, event feed |
| `backend/main.py` | FastAPI setup, startup simulator, HTTP and WebSocket endpoints |
| `backend/models/schemas.py` | Pydantic request and response models |
| `backend/services/optimization_workflow.py` | Request validation, routing/prediction/solver coordination, response creation |
| `backend/services/routing_api.py` | ORS integration and OSRM fallback for matrices and directions |
| `backend/services/traffic_prediction.py`, `backend/ml/road_predictor.py` | Zone-based congestion and adjusted-duration prediction |
| `backend/services/cost_engine.py` | Weighted route objective and congestion/delay costs |
| `backend/services/optimizer.py` | OR-Tools vehicle assignment, sequencing, and constraints |
| `backend/services/route_validator.py` | Independent route and feasibility checks |
| `backend/services/simulation.py`, `backend/services/orchestrator.py` | Synthetic zone observations, demo forecasts, and proactive events |
| `backend/database.py`, `backend/models/db_models.py` | SQLite setup and traffic-log model |
| `backend/tests/` | Backend workflow and optimizer tests |

### Optimization model

- For `V` eligible partners and `C` customers, the matrix contains partner starts, `V` duplicated copies of the selected shop, and the customer nodes. A request is limited to 50 total matrix nodes.
- Each partner starts at their own location and must visit their assigned shop copy before visiting customers. The solver uses the partner start as a zero-cost virtual end marker, so no return journey is displayed or counted.
- All eligible, available partners associated with the selected shop are optimized together. The selected partner field is a request/default selection; it does not exclude other eligible partners.
- Default objective weights are 40% predicted duration, 30% predicted delay, 20% road distance, and 10% congestion penalty. They can be configured and are normalized to sum to one.
- Predicted travel time, not the blended cost score, drives time feasibility and estimated arrivals. Service time and applicable delivery-window waiting are also included.
- Capacities and customer time windows are hard constraints. The configured maximum route duration is a hard limit. A soft delay penalty discourages exceeding the configured delay threshold.

## API

- `GET /` — backend health message.
- `POST /optimize-route` — accepts `locations`, `selected_partner_id`, `selected_shop_id`, and optional `departure_hour`; returns route assignments, sequences, geometry, metrics, prediction provenance, and validation.
- `GET /route-summary` — currently returns a placeholder; it is not a persisted optimization history endpoint.
- `WS /ws` — streams demo simulation ticks and orchestration events.
- `GET /docs` — interactive FastAPI/OpenAPI documentation.

Each location has an `id`, a `type` (`shop`, `partner`, or `customer`), latitude, and longitude. Partner and customer locations may include `shop_id`; customers may include `demand`, `service_minutes`, `ready_after_minutes`, and `due_by_minutes`; partners may include `available` and `capacity`. Delivery-window offsets are measured in minutes from dispatch. See `backend/models/schemas.py` for the request model.

## Data accuracy and limitations

| Displayed data | Current source | Interpretation |
| --- | --- | --- |
| Road-network distance, baseline duration, and geometry | ORS, or OSRM fallback | Provider-derived for its road graph and profile; actual journeys can differ. |
| Congestion and traffic-adjusted durations / arrivals | Random Forest plus simulator state | Demo estimates only; simulator inputs and bundled model training data are synthetic. |
| Zone demand forecasts and demand-spike events | Demand model plus generated inputs | Synthetic demonstrations, not measured customer demand. |
| Delay-avoided claims and several risk probabilities | Orchestrator thresholds and heuristic/randomized values | Not validated predictions or measured time savings. |
| Route cost and fuel figures | Application objective and heuristic calculations | Not guaranteed currency prices or actual fuel consumption. |
| Vehicle mode | Frontend display setting | Changes the displayed vehicle and cost multiplier; it does not change backend route duration or routing profile. |

ORS/OSRM matrix durations are baseline estimates, **not live traffic measurements**. A green route, “Low Traffic” label, precise percentage, or stated number of minutes avoided is not a verified real-world result. The backend currently requests the `driving-car` profile even when the UI displays a bicycle or two-wheeler. Do not use the current application to dispatch real orders or promise delivery times.

## Train with historical observations

To train the zone-level Random Forest from historical observations, provide a CSV with `timestamp`, `zone`, `congestion` (0-1), `vehicle_density` (0-1), and `avg_speed` columns. Use the zone labels `T Nagar`, `OMR`, `Velachery`, `Anna Nagar`, `Tambaram`, and `Adyar`. Each row's target is the next recorded congestion observation for that zone. Training uses chronological 70/15/15 train/validation/test periods, reports MAE/RMSE (and R² where measurable), and saves the model:

```powershell
python -m backend.ml.train_road_predictor path\to\traffic.csv
```

Restart the backend after training. The route API reports model provenance and the current live-input source. **Training on historical data does not make the simulator's inputs real**, and offline metrics alone do not establish future accuracy.

## Optional delivery constraints

`POST /optimize-route` accepts:

- Customer `demand` and `service_minutes`.
- Customer `ready_after_minutes` and `due_by_minutes`, measured relative to dispatch.
- Partner `capacity`; when omitted, no effective capacity restriction is applied for that request.
- Partner `available`; unavailable partners are excluded.

Demands and capacities must be non-negative integers. Delivery-window offsets must be finite, non-negative, ordered, and no later than the configured maximum route duration. Invalid inputs are rejected. Configure objective weights, congestion threshold, maximum route duration, and solver time budget in `backend/.env`.

## Setup

### Prerequisites

- Python and Node.js/npm compatible with the installed project dependencies.
- An OpenRouteService API key is recommended. Without a usable key, routing tries the public OSRM service; availability and usage limits are outside RouteIQ's control.

### Backend

From the repository root, create and activate a virtual environment, install dependencies, and configure `backend/.env`:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env` to set your ORS key and runtime settings. At minimum, the example settings include:

```env
ORS_API_KEY=your_actual_api_key_here
AVERAGE_SPEED_KMPH=30
DELAY_THRESHOLD_MINS=45
DELAY_PENALTY_COST=50
```

From the repository root, run:

```powershell
python -m uvicorn backend.main:app --reload --port 8000
```

The API is available at `http://localhost:8000`; interactive documentation is at `http://localhost:8000/docs`.

### Frontend

In another terminal, from the repository root:

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite (normally `http://localhost:5173`). The frontend currently connects to `http://localhost:8000` and `ws://localhost:8000/ws`.

## Example Chennai map locations

Add a delivery partner as well as a shop and customers:

1. **Shop:** Anna Nagar (13.0827, 80.2707)
2. **Customer 1:** T Nagar (13.0418, 80.2341)
3. **Customer 2:** Velachery (12.9774, 80.2227)
4. **Customer 3:** Adyar (13.0012, 80.2565)
5. **Customer 4:** OMR / Thoraipakkam (12.9349, 80.2312)

The system requests a road matrix and solves a demo route using provider-derived road data, synthetic traffic estimates, and any configured constraints.
