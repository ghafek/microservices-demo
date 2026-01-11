Order Tracking Service (CSE)
============================

Local dev
---------

1) Generate stubs (creates `demo_pb2.py` and `demo_pb2_grpc.py`):

	./genproto.sh

2) Run the server (defaults to port 8080):

	PORT=8080 python3 order_tracking_server.py

3) Run the sanity client (server must be running):

	ORDER_TRACKING_ADDR=localhost:8080 python3 sanity_check.py

Notes
-----
- Status progression is simulated by default (PLACED -> SHIPPED -> OUT_FOR_DELIVERY -> DELIVERED).
- Disable simulation by setting: `DISABLE_STATUS_SIMULATION=1`.
