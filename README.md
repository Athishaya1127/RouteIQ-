# RouteIQ — AI-Powered Delivery Route Optimization

RouteIQ is a delivery route optimization system designed to help businesses plan efficient last-mile deliveries across multiple delivery partners. It combines graph-based routing, Google OR-Tools, congestion-aware cost calculation, machine learning–based traffic and demand forecasting, and an interactive map dashboard.

The system allows users to place shops, delivery partners, and customers on a map, optimize delivery sequences, visualize routes, and monitor simulated traffic conditions and proactive fleet events.

## Key Features

- **Multi-Vehicle Route Optimization:** Uses Google OR-Tools to determine delivery sequences across multiple delivery partners.
- **Shop-Based Customer Assignment:** Initially assigns customers to their geographically nearest eligible delivery partner using Haversine distance.
- **Congestion-Aware Routing:** Calculates route costs using distance, duration, and predicted congestion.
- **Graph-Based Pathfinding:** Uses a road graph and time-dependent Dijkstra routing to estimate costs and travel times between locations.
- **Traffic Prediction:** Uses Random Forest models to estimate future congestion from traffic-related features.
- **Demand Forecasting:** Predicts future demand levels for predefined delivery zones.
- **Delay-Aware Optimization:** Adds soft penalties when cumulative route time exceeds a configured threshold.
- **Interactive Map Visualization:** Displays shops, customers, partners, delivery paths, congestion zones, and demand hotspots.
- **Fleet Dashboard:** Shows delivery assignments, route distance, estimated duration, fuel estimates, and route costs.
- **Proactive Fleet Events:** Demonstrates rerouting, delivery-priority adaptation, and driver repositioning through an orchestration layer.
- **WebSocket Updates:** Streams traffic simulation and orchestration events to the frontend.
- **Vehicle Mode Selection:** Provides scooter, motorcycle, bicycle, auto-rickshaw, and car display options.

## Technology Stack

| Layer | Technologies |
|---|---|
| Frontend | React, Vite, Tailwind CSS |
| Mapping | React Leaflet, Leaflet, OpenStreetMap-based map tiles |
| Backend | Python, FastAPI, Uvicorn |
| Optimization | Google OR-Tools |
| Routing and Geometry | Custom road graph, Dijkstra, OpenRouteService, OSRM fallback |
| Machine Learning | Scikit-learn, Random Forest |
| Database | SQLite, SQLAlchemy |
| Communication | REST API, WebSockets |
| Configuration | Python dotenv |

## System Architecture

```text
React Frontend
    |
    |-- MapDashboard
    |-- Sidebar
    |-- RouteVisualizer
    |-- AIPanel
    |
    | REST API + WebSocket
    v
FastAPI Backend
    |
    |-- Location Validation
    |-- Customer-to-Partner Assignment
    |-- Road Graph and Dijkstra Routing
    |-- Congestion-Aware Cost Matrices
    |-- Google OR-Tools VRP Solver
    |-- Route Geometry and Metrics
    |-- Traffic Simulation and ML Forecasting
    |
    v
SQLite Database + Routing Services
```

## How RouteIQ Works

### 1. Define Delivery Locations

Users interact with the map to add shops, delivery partners, and customers. Each location has an identifier, coordinates, a location type, and an optional shop association.

### 2. Assign Customers to Partners

The backend calculates the geographic distance between each customer and eligible delivery partners using the Haversine formula. Each customer is initially assigned to the nearest eligible partner.

This initial assignment constrains which customers each vehicle can serve during optimization.

### 3. Build the Routing Matrices

The backend snaps locations to nodes in the configured road graph and calculates pairwise travel costs, durations, distances, and path details.

The graph-based routing component uses time-dependent Dijkstra logic to estimate paths using edge length, predicted congestion, travel-time estimates, and congestion-related penalties.

OpenRouteService and OSRM are also used to obtain route geometry and routing details, depending on service availability and configuration.

### 4. Calculate Congestion-Aware Costs

The cost engine normalizes distance, duration, and predicted congestion values before combining them into the optimization cost matrix.

The current implementation uses the following weights:

| Cost component | Weight |
|---|---:|
| Normalized distance | 20% |
| Normalized duration | 30% |
| Normalized predicted congestion | 50% |

Fuel estimates are calculated separately and are not currently included in this weighted objective.

### 5. Optimize Delivery Sequences

Google OR-Tools solves a Vehicle Routing Problem (VRP) using the cost matrix, travel-duration matrix, vehicle start/end configuration, and vehicle-specific customer restrictions.

The solver uses `PATH_CHEAPEST_ARC` as its initial solution strategy. A time dimension with soft upper-bound penalties discourages routes from exceeding the configured duration threshold.

### 6. Generate Route Results

The backend constructs a response containing delivery sequences, route segments, geometry, estimated distance and duration, cost estimates, and fleet-level summaries.

### 7. Visualize the Fleet

The React frontend renders the optimized routes on the map. Different delivery partners receive different route colors, and the dashboard provides route metrics and individual delivery sequences.

The moving vehicle markers are frontend animations along route coordinates, rather than verified GPS positions from physical delivery vehicles.

### 8. Monitor Traffic and Demand

A background simulation updates traffic conditions across predefined Chennai zones. Random Forest models estimate traffic and demand levels, while the orchestration layer evaluates route risk and can generate proactive fleet events.

WebSocket messages deliver simulation updates to the frontend, where congestion zones, demand hotspots, risk indicators, and event notifications are displayed.

## Machine Learning Components

### Traffic Forecasting

Random Forest regression models estimate future congestion using features such as:

- Hour of day
- Day of the week
- Historical congestion
- Vehicle density
- Average speed
- Neighboring or upstream traffic features, where supported by the model

Training and fallback logic use synthetic traffic data when pretrained model artifacts are unavailable.

### Demand Forecasting

A Random Forest model estimates future demand density for predefined zones using time, historical density, nearby congestion, and recent activity.

The orchestration layer uses these forecasts to demonstrate potential demand hotspots and driver-repositioning decisions.

**Important:** The current forecasting and simulation pipeline includes synthetic data and simulated traffic events. These results should not be interpreted as validated real-world traffic predictions without external-data integration and model evaluation.

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | Check whether the API is running |
| `POST` | `/optimize-route` | Validate locations and optimize delivery routes |
| `GET` | `/route-summary` | Retrieve the latest route summary when available |
| `WebSocket` | `/ws` | Receive traffic simulation and orchestration messages |

### Example Optimization Request

```json
{
  "locations": [
    {
      "id": "shop1",
      "type": "shop",
      "lat": 13.0418,
      "lng": 80.2341
    },
    {
      "id": "part1",
      "type": "partner",
      "lat": 13.0450,
      "lng": 80.2300,
      "shop_id": "shop1"
    },
    {
      "id": "cus1",
      "type": "customer",
      "lat": 13.0600,
      "lng": 80.2500,
      "shop_id": "shop1"
    }
  ],
  "selected_partner_id": "part1",
  "selected_shop_id": "shop1",
  "departure_hour": 9
}
```

Send this payload to `POST /optimize-route` after starting the backend. The example represents a single shop, partner, and customer; actual requests must satisfy the backend's validation rules.

## Project Structure

```text
RouteIQ/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models/
│   │   └── schemas.py
│   └── services/
│       ├── optimizer.py
│       ├── cost_engine.py
│       ├── delay_engine.py
│       ├── fuel_model.py
│       ├── road_graph.py
│       ├── routing_api.py
│       ├── simulation.py
│       ├── realtime_tracker.py
│       ├── orchestrator.py
│       ├── live_forecaster.py
│       ├── demand_forecaster.py
│       ├── road_predictor.py
│       ├── offline_training.py
│       ├── global_state.py
│       └── websocket.py
├── frontend/
│   └── src/
│       ├── App.jsx
│       ├── main.jsx
│       └── components/
│           ├── MapDashboard.jsx
│           ├── Sidebar.jsx
│           ├── RouteVisualizer.jsx
│           └── AIPanel.jsx
├── requirements.txt
└── README.md
```

*The tree above illustrates the main modules. Adjust folder names and paths to match the exact layout of your repository.*

## Installation and Setup

### Prerequisites

- Python 3.10 or a compatible Python version supported by the installed dependencies
- Node.js and npm
- An OpenRouteService API key
- Git

### 1. Clone the Repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd RouteIQ
```

Replace the placeholder with your actual repository URL.

### 2. Configure the Backend

Create a `.env` file in the repository root or backend directory:

```env
ORS_API_KEY=your_openrouteservice_api_key
AVERAGE_SPEED_KMPH=30
DELAY_THRESHOLD_MINS=45
DELAY_PENALTY_COST=50
```

The current configuration validates the presence of `ORS_API_KEY` during startup, even though the routing service includes an OSRM fallback.

### 3. Install Python Dependencies

```bash
python -m venv .venv
```

Activate the environment.

**Windows PowerShell:**

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

### 4. Start the Backend

Run from the repository root:

```bash
uvicorn backend.main:app --reload
```

The API will normally be available at:

`http://localhost:8000`

Interactive API documentation:

`http://localhost:8000/docs`

### 5. Start the Frontend

Open another terminal and navigate to the frontend directory:

```bash
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite.

The frontend currently connects to `http://localhost:8000` for optimization requests and `ws://localhost:8000/ws` for WebSocket updates. Update these addresses when deploying the application.

## Database

RouteIQ uses SQLite through SQLAlchemy for traffic-log persistence. The database stores simulation-related traffic measurements, including zone congestion, vehicle density, average speed, and timestamps.

The database is created when the backend initializes its SQLAlchemy metadata.

## Configuration

| Variable | Default | Purpose |
|---|---:|---|
| `ORS_API_KEY` | Required | OpenRouteService configuration |
| `AVERAGE_SPEED_KMPH` | `30` | Fallback and ideal-speed calculations |
| `DELAY_THRESHOLD_MINS` | `45` | Delay threshold for route optimization |
| `DELAY_PENALTY_COST` | `50` | Soft penalty configuration for exceeding the threshold |

## Current Limitations

- Traffic conditions and some congestion events are simulated rather than sourced from a verified live traffic feed.
- Machine learning models may use synthetic training data; their predictions require evaluation against real observations before production use.
- Initial customer assignment uses straight-line geographic distance, not a globally optimized assignment across all partners.
- The current cost objective weights distance, duration, and predicted congestion; the separate fuel estimate is not part of the OR-Tools arc-cost objective.
- The fuel metric is an approximate distance-based estimate, not a calibrated fuel-consumption or monetary model.
- Vehicle-mode multipliers in the frontend modify displayed duration and cost estimates; they do not currently establish separate road-network constraints or independently optimize each vehicle type.
- The WebSocket and in-memory orchestration state are suitable for a demonstration but would need additional reliability, persistence, and coordination for production deployment.
- Routing service quotas, API availability, geographic coverage, and fallback behavior can affect results.

## Future Improvements

- Integrate verified live traffic and GPS feeds.
- Train and evaluate forecasting models using real traffic and delivery data.
- Include calibrated fuel consumption and operating costs in the optimization objective.
- Optimize customer assignment and route sequencing jointly.
- Add delivery time windows, vehicle capacities, and service-time constraints.
- Implement persistent event history and reliable background task management.
- Add automated tests, route-quality benchmarks, and monitoring for routing-service failures.
- Configure production API URLs, authentication, and deployment-specific environment variables.

## Project Goal

RouteIQ demonstrates how operations research, graph algorithms, machine learning, and interactive mapping can work together to improve last-mile delivery planning. Its architecture provides a foundation for evaluating route efficiency, traffic-aware decisions, and multi-partner fleet coordination.

---

**Note:** This project is a prototype. Predictions, costs, and simulated events should be validated before using the system for real-world delivery dispatch.
