# RouteIQ - AI Route Optimization Engine

RouteIQ is a multi-vehicle urban-delivery route optimization application. It uses road-network distances and baseline durations from OpenRouteService (ORS), with an OSRM fallback, and combines them with a demo traffic forecast and Google OR-Tools to assign orders to delivery partners and sequence their stops. A React + Leaflet dashboard lets a user place shops, customers, and partners and inspect the resulting routes.

RouteIQ is a prototype, not a live dispatch or traffic-intelligence service. Road-network results are provider-derived, but live traffic inputs, demand estimates, proactive incident spikes, and related risk metrics are simulated. See [Data accuracy and limitations](#data-accuracy-and-limitations) before interpreting displayed metrics as real-world measurements.

## Problem overview

An urban delivery operation must decide which eligible delivery partner should serve each order and in what order to visit the stops. A useful plan has to balance road distance and estimated time while respecting operational requirements such as the shop pickup, partner availability and capacity, order service times, customer delivery windows, and a maximum route duration.

Choosing the nearest next stop independently is not enough: a locally short leg can make the entire fleet plan longer, infeasible, or unfairly loaded. RouteIQ models the task as a multi-vehicle vehicle-routing problem (VRP). For a selected shop, the optimizer jointly assigns its customers to eligible partners and chooses each partner's stop sequence.

**Inputs**

- Map coordinates and a selected shop.
- One or more available delivery partners associated with that shop.
- Customers belonging to that shop; each customer has a demand and can optionally specify a service time and delivery window.
- An optional planned departure hour and partner capacities.

**Outputs**

- A partner-by-partner open route: partner start, required shop pickup, then assigned customer stops. The route does not include a return journey.
- Road geometry, segment distances, estimated durations, customer arrival times, route totals, and a feasibility-validation result.
- Demo traffic, demand, and risk indicators for illustrating forecasting and re-optimization behavior.

## How it works

1. **Place and assign locations.** Select Shop, Customer, or Partner in the sidebar and click the map to add a location. Customers and partners are associated with a shop. A shop, partner, or customer marker can also be clicked to select its corresponding shop or partner in the controls.
2. **Choose the route request.** Select the target shop, departure hour, and display mode. The optimize request includes the locations and optional operational constraints.
3. **Validate and prepare the fleet.** The FastAPI backend validates the request, finds the selected shop's customers and available partners associated with that shop, checks constraints, and prepares routing nodes. Each partner gets a start node and a duplicated shop node so each route can visit its own shop pickup.
4. **Fetch the road matrix.** ORS supplies pairwise road distances and baseline durations when configured. If ORS is not configured or its request fails, the backend tries the public OSRM service. Unreachable legs remain unavailable rather than being treated as zero-cost.
5. **Estimate demo traffic.** Each origin-destination pair is assigned to its nearest predefined zone based on its midpoint. A Random Forest produces a congestion estimate from the latest simulator state; the estimate adjusts the baseline duration as `baseline duration / max(0.1, 1 - congestion)`. Those congestion inputs are synthetic in the current application.
6. **Build the objective and solve the VRP.** The cost engine combines normalized predicted duration, predicted delay, road distance, and a congestion premium using configurable weights. OR-Tools then jointly assigns customers and orders the stops. The travel-time dimension uses predicted duration, service time, and applicable waiting time; capacity and customer time windows are hard constraints. The solver uses a bounded search time.
7. **Validate the plan independently.** The route validator checks that all required customers are served exactly once and checks reachability, partner capacities, delivery windows, and the maximum route duration. An infeasible plan is returned as an error rather than a success-shaped result.
8. **Get directions and render results.** Directions provide final road geometry and per-leg distance/baseline duration. The backend applies its congestion estimate to the directions duration for displayed ETAs, checks the final route constraints, and returns the response. The frontend draws the paths, markers, stops, and arrival times on the map.
9. **Stream the demo orchestration feed.** A background task generates synthetic observations for six named zones about every five seconds, stores traffic observations in SQLite, and broadcasts the latest traffic and orchestration data over WebSocket. When its simulated thresholds are crossed, the orchestrator can demonstrate a proactive re-optimization or a partner-repositioning event.

## Architecture

```text
React + Leaflet browser
  ├─ Sidebar: location placement, shop/partner selection, constraints, results
  ├─ MapDashboard: map clicks, location markers, traffic overlays
  ├─ RouteVisualizer: route geometry, segment details, vehicle animation
  └─ AIPanel: demo forecasts, risks, and orchestration events
       │ HTTP POST /optimize-route       │ WebSocket /ws
       ▼                                 ▲
FastAPI application (backend/main.py)    │
  ├─ Pydantic request/response schemas   │
  ├─ optimization_workflow               │
  │    ├─ ORS / OSRM road matrices and directions
  │    ├─ traffic_prediction + road_predictor
  │    ├─ cost_engine
  │    ├─ optimizer (Google OR-Tools VRP)
  │    └─ route_validator
  ├─ simulation → orchestrator ──────────┘
  └─ SQLAlchemy → SQLite traffic_logs
```

The request path is synchronous from the user's perspective: the frontend sends an HTTP optimization request and renders its response. Independently, the backend startup task runs the demo simulator and publishes WebSocket updates to the dashboard. The traffic database currently stores simulation logs; it is not a production order, fleet, or historical traffic system.

### Main modules

| Area | Responsibilities |
| --- | --- |
| `frontend/src/App.jsx` | UI state, location creation/selection, optimization request, WebSocket subscription |
| `frontend/src/components/Sidebar.jsx` | Placement modes, shop/partner selectors, optimization controls, route summaries |
| `frontend/src/components/MapDashboard.jsx` | Leaflet map, click-to-place, markers, congestion overlays |
| `frontend/src/components/RouteVisualizer.jsx` | Route polylines, leg tooltips, and partner marker animation |
| `frontend/src/components/AIPanel.jsx` | Displays simulator forecasts, risk values, and event feed |
| `backend/main.py` | FastAPI app, CORS, startup simulator, HTTP and WebSocket endpoints |
| `backend/models/schemas.py` | Pydantic location, request, and route-segment schemas |
| `backend/services/optimization_workflow.py` | End-to-end request validation, matrix/prediction/solver coordination, directions, response |
| `backend/services/routing_api.py` | ORS integration and OSRM fallback for road matrices and directions |
| `backend/services/traffic_prediction.py`, `backend/ml/road_predictor.py` | Trip-level congestion and adjusted-duration prediction |
| `backend/services/cost_engine.py` | Weighted route objective, delay and congestion cost calculation |
| `backend/services/optimizer.py` | OR-Tools multi-vehicle assignment, sequencing, capacity, and time constraints |
| `backend/services/route_validator.py` | Independent checks of the solver's assignments and route feasibility |
| `backend/services/simulation.py`, `backend/services/orchestrator.py` | Synthetic zone updates, demo risk/demand forecasts, and proactive event examples |
| `backend/database.py`, `backend/models/db_models.py` | SQLite connection and traffic log table |

### Optimization model and route conventions

- For `V` eligible partners and `C` customers, the optimization matrix contains partner starts, `V` duplicated copies of the selected shop, and the `C` customer nodes. Requests are currently limited to 50 total matrix nodes.
- A partner must start at their own map location and visit their assigned copy of the shop before visiting customers. The solver's end node is a virtual marker mapped to the same node as that partner's start; the virtual return arc has zero cost. Thus, the displayed route is **open-ended** and excludes a drive back to the partner start.
- The selected shop determines which customers are included. Eligible, available partners associated with that shop are optimized together; the selected partner control is a request/default selection and does not make other eligible partners ineligible.
- The default objective weights are 40% predicted duration, 30% predicted delay, 20% distance, and 10% congestion penalty. Configuration can change the weights; the backend normalizes them to sum to one.
- Predicted travel time is separate from the blended objective: it drives feasibility and estimated arrivals, with service times and delivery-window waiting included as applicable.
- Partner capacity and customer time windows are enforced as hard constraints. A soft delay penalty can discourage routes that exceed the configured delay threshold, while the maximum route duration is a hard limit.

## API and data flow

- `GET /` — backend health message.
- `POST /optimize-route` — accepts `locations`, `selected_partner_id`, `selected_shop_id`, and optional `departure_hour`; returns route assignments, sequences, geometry, segment and aggregate metrics, prediction provenance, and validation information.
- `GET /route-summary` — currently returns a placeholder message; it is not a persisted optimization history endpoint.
- `WS /ws` — streams demo simulation ticks and orchestration events to connected clients.
- `GET /docs` — interactive FastAPI/OpenAPI documentation.

Each location has an `id`, a `type` (`shop`, `partner`, or `customer`), latitude, and longitude. Partner/customer locations may include `shop_id`; customers may include `demand`, `service_minutes`, `ready_after_minutes`, and `due_by_minutes`; partners may include `available` and `capacity`. Delivery-window offsets are measured in minutes from dispatch. See `backend/models/schemas.py` for the request model and validation bounds.

## Data accuracy and limitations

| Displayed data | Current source | How to interpret it |
| --- | --- | --- |
| Road-network distance, baseline time, and geometry | ORS, or OSRM fallback | Provider-derived for its road graph and routing profile; not a guarantee of the exact real-world journey |
| Congestion and traffic-adjusted duration / arrival estimates | Random Forest plus simulator state | Demo estimates only: simulator observations are synthetic and the bundled model is trained on synthetic data |
| Zone demand forecasts and “demand spike” events | Demand model plus randomly generated simulator inputs | Synthetic demonstration values, not measured customer demand |
| Delay-avoided messages and several risk probabilities | Orchestrator thresholds and heuristic/randomized event values | Demonstration of system behavior, not validated traffic predictions or measured time savings |
| Route cost and fuel figures | Application objective / heuristic calculations | Optimization/display indicators, not guaranteed currency prices or fuel consumption |
| Vehicle mode | Frontend display setting | Changes the displayed vehicle and its cost multiplier; it does not change the backend road-routing profile or route duration |

In particular, ORS/OSRM matrix durations are baseline estimates, **not live traffic measurements**. A green route, a “Low Traffic” label, a precise percentage, or a claimed number of minutes avoided should not be treated as a verified real-world result. The router currently requests the `driving-car` profile even when the UI shows a bicycle or two-wheeler. Do not use the current app to dispatch real orders or promise delivery times.

## Training with historical observations

To replace the bundled synthetic-trained zone-level Random Forest, provide a CSV with `timestamp`, `zone`, `congestion` (0-1), `vehicle_density` (0-1), and `avg_speed` columns. Use the current zone labels (`T Nagar`, `OMR`, `Velachery`, `Anna Nagar`, `Tambaram`, `Adyar`). Each row's target is the next recorded congestion observation for the same zone. The training command uses chronological 70/15/15 train/validation/test periods, reports MAE/RMSE (and R² where measurable), and saves the model used by RouteIQ:

To train the zone-level Random Forest from historical observations, provide a CSV with `timestamp`, `zone`, `congestion` (0-1), `vehicle_density` (0-1), and `avg_speed` columns. Use the current zone labels (`T Nagar`, `OMR`, `Velachery`, `Anna Nagar`, `Tambaram`, `Adyar`). Each row's target is the next recorded congestion observation for the same zone. The training command uses chronological 70/15/15 train/validation/test periods, reports MAE/RMSE (and R² where measurable), and saves the model used by RouteIQ:

```bash
python -m backend.ml.train_road_predictor path\to\traffic.csv
```

Restart the backend after training. The route API reports both model provenance and the current synthetic live-input source. **Training on historical data does not make the simulator's live inputs real**, and offline metrics alone do not establish that the model is accurate for future operating conditions.

## Optional delivery constraints

`POST /optimize-route` accepts optional fields on each location:

- Customer `demand` and `service_minutes`.
- Customer `ready_after_minutes` and `due_by_minutes`, both measured relative to dispatch.
- Partner `capacity`; when omitted, no effective capacity restriction is applied for the current request.
- Partner `available`; unavailable riders are excluded from the optimization.

Demands and capacities must be non-negative integers. Delivery windows must be finite, non-negative minute offsets no later than the configured maximum route duration. Invalid constraint inputs are rejected, and vehicle-to-customer permissions are enforced as hard assignment constraints.

Configure the four objective weights, congestion threshold, maximum route duration, and solver time budget in `backend/.env`. The four weights are normalized to sum to one at runtime.

## Project Structure

- `backend/main.py`: FastAPI application and HTTP/WebSocket entry points.
- `backend/config.py`, `backend/.env.example`: Runtime configuration and example settings.
- `backend/models/`: Pydantic API schemas and SQLAlchemy traffic-log model.
- `backend/services/`: Routing provider integrations, optimization workflow, cost model, OR-Tools solver, route validation, simulator, and orchestration.
- `backend/ml/`: Traffic and demand prediction models and historical traffic model training command.
- `backend/tests/`: Backend optimization and workflow tests.
- `frontend/src/App.jsx`: Main React application state and API/WebSocket coordination.
- `frontend/src/components/`: Sidebar controls, Leaflet map, route visualizer, and orchestration panel.
- `frontend/src/utils/`: Shared frontend vehicle display settings and their tests.
- `routeiq.db`: Local SQLite database created at runtime for synthetic traffic logs.

## Setup Instructions

### 1. OpenRouteService API Key

An OpenRouteService API key is recommended. When no usable key is configured, the application tries the public OSRM service; its availability and usage limits are outside RouteIQ's control.
1. Sign up at [OpenRouteService](https://openrouteservice.org/dev/#/signup).
2. Generate an API Key (Standard).

### 2. Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   # Windows PowerShell:
   .\venv\Scripts\Activate.ps1
   # macOS/Linux:
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Configure Environment Variables:
   Copy `.env.example` to `.env` and insert your ORS API Key:
   ```bash
   # Windows PowerShell:
   Copy-Item .env.example .env
   # macOS/Linux:
   cp .env.example .env
   ```
   **Edit `.env`:**
   ```
   ORS_API_KEY=your_actual_api_key_here
   AVERAGE_SPEED_KMPH=30
   DELAY_THRESHOLD_MINS=45
   DELAY_PENALTY_COST=50
   ```
   
4. From the repository root, start the FastAPI server:
   ```bash
   cd ..
   python -m uvicorn backend.main:app --reload --port 8000
   ```
   *The API will be available at http://localhost:8000*
   *Interactive API Docs: http://localhost:8000/docs*

### 3. Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm run dev
   ```
   *The UI will be available at http://localhost:5173*

## Example Test Dataset (Chennai)

To test the system, you can add the following coordinates to the map (click roughly on these locations):

1. **Shop**: Anna Nagar (13.0827, 80.2707)
2. **Customer 1**: T Nagar (13.0418, 80.2341)
3. **Customer 2**: Velachery (12.9774, 80.2227)
4. **Customer 3**: Adyar (13.0012, 80.2565)
5. **Customer 4**: OMR / Thoraipakkam (12.9349, 80.2312)

Add at least one delivery partner as well as the shop and customers. The system will request a road matrix for the locations and solve a demo route using road distance, baseline routing duration, synthetic traffic estimates, and any configured delivery constraints. Route and baseline road information come from the routing provider; the traffic adjustments and forecast metrics are not live traffic.
