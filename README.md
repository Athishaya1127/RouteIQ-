# RouteIQ - AI Route Optimization Engine

RouteIQ is a powerful, multi-objective route optimization engine designed for urban delivery, specifically featuring real-time traffic constraints. It uses Google OR-Tools for solving Vehicle Routing Problems (VRP) and OpenRouteService (ORS) for dynamic, traffic-aware travel matrices.

## Features

- **Multi-Objective Optimization**: Minimizes a weighted cost function of Duration (40%), Delay (30%), Distance (20%), and Fuel (10%).
- **Congestion-Aware Fuel Model**: Dynamically increases fuel costs based on traffic delays (actual vs ideal duration).
- **Cumulative Delay Penalty**: Tracks route duration and penalizes routes that exceed the delivery time threshold.
- **Dynamic VRP Engine**: Uses Google OR-Tools configured for multiple vehicles.
- **Interactive Map Dashboard**: Built with React and Leaflet, displaying live routes colored by congestion (Green = Low, Orange = Moderate, Red = Heavy).

## Project Structure

- `backend/`: FastAPI Python application containing the optimization logic and OR-Tools integration.
- `frontend/`: React Vite application with a modern Tailwind dashboard and Leaflet maps.

## Setup Instructions

### 1. OpenRouteService API Key

This project requires a free OpenRouteService API Key.
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
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Configure Environment Variables:
   Copy `.env.example` to `.env` and insert your ORS API Key:
   ```bash
   cp .env.example .env
   ```
   **Edit `.env`:**
   ```
   ORS_API_KEY=your_actual_api_key_here
   AVERAGE_SPEED_KMPH=30
   DELAY_THRESHOLD_MINS=45
   DELAY_PENALTY_COST=50
   ```
   
4. Start the FastAPI server:
   ```bash
   uvicorn main:app --reload --port 8000
   
   uvicorn backend.main:app --reload --port 8000

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

The system will build a dynamic cost matrix for these 5 locations and determine the optimal delivery sequence considering traffic and distance.
