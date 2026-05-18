import requests

payload = {
    "locations": [
        {"id": "part1", "type": "partner", "lat": 13.0827, "lng": 80.2707},
        {"id": "shop1", "type": "shop", "lat": 13.0418, "lng": 80.2341},
        {"id": "cus1", "type": "customer", "lat": 12.9229, "lng": 80.2234, "shop_id": "shop1"}
    ],
    "selected_partner_id": "part1",
    "selected_shop_id": "shop1"
}

try:
    resp = requests.post("http://localhost:8000/optimize-route", json=payload)
    print("STATUS:", resp.status_code)
    print("RESPONSE:", resp.text)
except Exception as e:
    print("ERROR:", e)
