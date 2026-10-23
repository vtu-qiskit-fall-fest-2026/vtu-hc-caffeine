"""Illustrative corridors for discussing where a future quantum network controller may apply.

These are geographic concepts only. They are not deployed quantum links or
inputs to the Chennai repeater simulation.
"""

CORRIDORS = {
    "India research backbone concept": {
        "ocean": "India · terrestrial research backbone concept",
        "route": ["Delhi", "Jaipur", "Ahmedabad", "Mumbai", "Pune", "Hyderabad", "Bengaluru", "Chennai", "Visakhapatnam", "Kolkata", "Guwahati"],
        "coordinates": [(28.6139, 77.2090), (26.9124, 75.7873), (23.0225, 72.5714), (19.0760, 72.8777), (18.5204, 73.8567), (17.3850, 78.4867), (12.9716, 77.5946), (13.0827, 80.2707), (17.6868, 83.2185), (22.5726, 88.3639), (26.1445, 91.7362)],
        "use": "A planning sketch linking research, cloud, and metropolitan gateway locations across India. The city sequence is illustrative and does not assert that quantum equipment or a continuous fiber path exists.",
    },
    "Bay of Bengal · Andaman gateway concept": {
        "ocean": "Bay of Bengal · satellite and coastal gateway concept",
        "route": ["Chennai", "Visakhapatnam", "Port Blair", "Phuket", "Singapore"],
        "coordinates": [(13.0827, 80.2707), (17.6868, 83.2185), (11.6234, 92.7265), (7.8804, 98.3923), (1.3521, 103.8198)],
        "use": "Explore hybrid coastal and satellite-assisted entanglement distribution between India's east coast, the Andaman region, and Southeast Asian gateways.",
    },
    "Western Indian Ocean · island gateway concept": {
        "ocean": "Arabian Sea · Maldives · Western Indian Ocean",
        "route": ["Mumbai", "Kochi", "Malé", "Victoria · Seychelles", "Port Louis · Mauritius"],
        "coordinates": [(19.0760, 72.8777), (9.9312, 76.2673), (4.1755, 73.5093), (-4.6191, 55.4513), (-20.1609, 57.5012)],
        "use": "Study long-haul memory lifetime, link availability, and scheduling across Indian Ocean island gateways. Satellite relays or multiple independent links would be required; this is not a proposed deployed route.",
    },
    "Transpacific concept": {
        "ocean": "Pacific Ocean",
        "route": ["Los Angeles", "Honolulu", "Tokyo"],
        "coordinates": [(34.0522, -118.2437), (21.3099, -157.8581), (35.6762, 139.6503)],
        "use": "Study scheduling across long-haul repeater or satellite-assisted segments between North America and East Asia.",
    },
    "Indian Ocean concept": {
        "ocean": "Indian Ocean",
        "route": ["Mumbai", "Kochi", "Colombo", "Singapore"],
        "coordinates": [(19.0760, 72.8777), (9.9312, 76.2673), (6.9271, 79.8612), (1.3521, 103.8198)],
        "use": "Explore memory-aware coordination between South Asian and Southeast Asian research or satellite gateway networks.",
    },
    "Transatlantic concept": {
        "ocean": "Atlantic Ocean",
        "route": ["New York", "Azores", "Lisbon"],
        "coordinates": [(40.7128, -74.0060), (37.7412, -25.6756), (38.7223, -9.1393)],
        "use": "Explore multi-domain entanglement scheduling between North American and European network testbeds.",
    },
}
