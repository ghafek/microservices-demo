import os
import time

import grpc

import demo_pb2
import demo_pb2_grpc


def main() -> None:
    target = os.environ.get("ORDER_TRACKING_ADDR", "localhost:8080")
    channel = grpc.insecure_channel(target)
    stub = demo_pb2_grpc.OrderTrackingServiceStub(channel)

    order_id = f"cse-order-{int(time.time())}"
    tracking_id = f"track-{int(time.time())}"

    print("Target:", target)
    print("Order:", order_id)

    create_resp = stub.CreateOrderTracking(
        demo_pb2.CreateOrderTrackingRequest(order_id=order_id, tracking_id=tracking_id)
    )
    print("Create created=", create_resp.created)
    print("Create status=", demo_pb2.OrderTrackingStatus.Name(create_resp.info.current_status))

    status_resp = stub.GetOrderStatus(demo_pb2.GetOrderStatusRequest(order_id=order_id))
    print("Get status=", demo_pb2.OrderTrackingStatus.Name(status_resp.info.current_status))

    events_resp = stub.ListOrderEvents(demo_pb2.ListOrderEventsRequest(order_id=order_id))
    print("Events count=", len(events_resp.events))
    for ev in events_resp.events:
        print("-", demo_pb2.OrderTrackingStatus.Name(ev.status), ev.timestamp_unix_ms, ev.message)


if __name__ == "__main__":
    main()
