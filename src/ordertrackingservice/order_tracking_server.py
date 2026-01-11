import logging
import os
import threading
import time
from concurrent import futures
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import grpc

import demo_pb2
import demo_pb2_grpc
from grpc_health.v1 import health_pb2
from grpc_health.v1 import health_pb2_grpc


def _now_unix_ms() -> int:
	return int(time.time() * 1000)


@dataclass
class _OrderRecord:
	order_id: str
	tracking_id: str
	email: str
	address: Optional[demo_pb2.Address]
	items: List[demo_pb2.OrderItem]
	note: str
	current_status: int
	last_updated_unix_ms: int
	events: List[demo_pb2.OrderEvent] = field(default_factory=list)


class OrderTrackingService(demo_pb2_grpc.OrderTrackingServiceServicer):
	def __init__(self) -> None:
		self._lock = threading.RLock()
		self._orders: Dict[str, _OrderRecord] = {}
		self._log = logging.getLogger("ordertrackingservice")

		self._disable_simulation = os.environ.get("DISABLE_STATUS_SIMULATION", "0") == "1"
		self._sim_shipped_after_s = float(os.environ.get("SIM_SHIPPED_AFTER_S", "7200"))
		# Default progression: PLACED (t0) -> SHIPPED (t0+2h) -> OUT_FOR_DELIVERY (t0+3h) -> DELIVERED (t0+4h)
		self._sim_out_for_delivery_after_s = float(os.environ.get("SIM_OUT_FOR_DELIVERY_AFTER_S", "10800"))
		self._sim_delivered_after_s = float(os.environ.get("SIM_DELIVERED_AFTER_S", "14400"))

	def _to_info(self, record: _OrderRecord) -> demo_pb2.OrderTrackingInfo:
		return demo_pb2.OrderTrackingInfo(
			order_id=record.order_id,
			tracking_id=record.tracking_id,
			current_status=record.current_status,
			last_updated_unix_ms=record.last_updated_unix_ms,
		)

	def _append_event(self, record: _OrderRecord, status: int, message: str) -> None:
		ts = _now_unix_ms()
		record.current_status = status
		record.last_updated_unix_ms = ts
		record.events.append(
			demo_pb2.OrderEvent(
				status=status,
				timestamp_unix_ms=ts,
				message=message,
			)
		)

	def _schedule_status_updates(self, order_id: str) -> None:
		if self._disable_simulation:
			return

		def set_status(new_status: int, message: str) -> None:
			with self._lock:
				record = self._orders.get(order_id)
				if record is None:
					return
				if record.current_status in (
					demo_pb2.CANCELED,
					demo_pb2.DELIVERED,
				):
					return
				if record.current_status == new_status:
					return
				self._append_event(record, new_status, message)
				self._log.info(
					"status_update order_id=%s status=%s",
					order_id,
					demo_pb2.OrderTrackingStatus.Name(new_status),
				)

		shipped_after_s = self._sim_shipped_after_s
		out_for_delivery_after_s = self._sim_out_for_delivery_after_s
		delivered_after_s = self._sim_delivered_after_s
		threading.Timer(
			shipped_after_s,
			set_status,
			args=(demo_pb2.SHIPPED, "Shipped by Online Boutique Delivery Service"),
		).start()
		threading.Timer(
			out_for_delivery_after_s,
			set_status,
			args=(demo_pb2.OUT_FOR_DELIVERY, "Out for delivery"),
		).start()
		threading.Timer(
			delivered_after_s,
			set_status,
			args=(demo_pb2.DELIVERED, "Delivered"),
		).start()

	def CreateOrderTracking(self, request: demo_pb2.CreateOrderTrackingRequest, context: grpc.ServicerContext):
		if not request.order_id:
			context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
			context.set_details("order_id is required")
			return demo_pb2.CreateOrderTrackingResponse(created=False)

		with self._lock:
			existing = self._orders.get(request.order_id)
			if existing is not None:
				return demo_pb2.CreateOrderTrackingResponse(created=False, info=self._to_info(existing))

			now_ms = _now_unix_ms()
			address = None
			if request.HasField("address"):
				address = demo_pb2.Address()
				address.CopyFrom(request.address)

			items: List[demo_pb2.OrderItem] = []
			for it in request.items:
				copy_it = demo_pb2.OrderItem()
				copy_it.CopyFrom(it)
				items.append(copy_it)

			record = _OrderRecord(
				order_id=request.order_id,
				tracking_id=request.tracking_id,
				email=request.email,
				address=address,
				items=items,
				note=request.note,
				current_status=demo_pb2.PLACED,
				last_updated_unix_ms=now_ms,
			)
			self._append_event(record, demo_pb2.PLACED, "Order placed")
			self._orders[request.order_id] = record

		self._log.info(
			"created order_id=%s tracking_id=%s",
			request.order_id,
			request.tracking_id,
		)
		self._schedule_status_updates(request.order_id)

		return demo_pb2.CreateOrderTrackingResponse(created=True, info=self._to_info(record))

	def GetOrderStatus(self, request: demo_pb2.GetOrderStatusRequest, context: grpc.ServicerContext):
		with self._lock:
			record = self._orders.get(request.order_id)

		if record is None:
			context.set_code(grpc.StatusCode.NOT_FOUND)
			context.set_details("unknown order_id")
			return demo_pb2.GetOrderStatusResponse()

		return demo_pb2.GetOrderStatusResponse(info=self._to_info(record))

	def ListOrderEvents(self, request: demo_pb2.ListOrderEventsRequest, context: grpc.ServicerContext):
		with self._lock:
			record = self._orders.get(request.order_id)

		if record is None:
			context.set_code(grpc.StatusCode.NOT_FOUND)
			context.set_details("unknown order_id")
			return demo_pb2.ListOrderEventsResponse()

		return demo_pb2.ListOrderEventsResponse(info=self._to_info(record), events=list(record.events))

	def GetOrderDetails(self, request: demo_pb2.GetOrderDetailsRequest, context: grpc.ServicerContext):
		with self._lock:
			record = self._orders.get(request.order_id)

		if record is None:
			context.set_code(grpc.StatusCode.NOT_FOUND)
			context.set_details("unknown order_id")
			return demo_pb2.GetOrderDetailsResponse()

		resp = demo_pb2.GetOrderDetailsResponse(
			info=self._to_info(record),
			email=record.email,
			note=record.note,
			events=list(record.events),
		)
		if record.address is not None:
			resp.address.CopyFrom(record.address)
		resp.items.extend(record.items)
		return resp

	# gRPC health checks for Kubernetes readiness/liveness probes.
	def Check(self, request: health_pb2.HealthCheckRequest, context: grpc.ServicerContext):
		return health_pb2.HealthCheckResponse(status=health_pb2.HealthCheckResponse.SERVING)

	def Watch(self, request: health_pb2.HealthCheckRequest, context: grpc.ServicerContext):
		return health_pb2.HealthCheckResponse(status=health_pb2.HealthCheckResponse.UNIMPLEMENTED)


def serve() -> None:
	logging.basicConfig(
		level=os.environ.get("LOG_LEVEL", "INFO"),
		format="%(asctime)s %(levelname)s %(name)s %(message)s",
	)

	port = os.environ.get("PORT", "8080")
	server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
	service = OrderTrackingService()

	demo_pb2_grpc.add_OrderTrackingServiceServicer_to_server(service, server)
	health_pb2_grpc.add_HealthServicer_to_server(service, server)

	server.add_insecure_port(f"[::]:{port}")
	logging.getLogger("ordertrackingservice").info("listening on port=%s", port)
	server.start()
	try:
		while True:
			time.sleep(3600)
	except KeyboardInterrupt:
		server.stop(0)


if __name__ == "__main__":
	serve()
