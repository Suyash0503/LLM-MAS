"""
Agent-Based Shipping Service
Replaces the original Go gRPC shippingservice with an agentic Python implementation.
Each gRPC call is orchestrated by a ShippingOrchestrator that delegates to
specialized sub-agents via Claude tool-use.
"""

import os
import asyncio
import logging
import signal
import threading
from concurrent import futures

import grpc
from grpc_health.v1 import health, health_pb2, health_pb2_grpc

import demo_pb2
import demo_pb2_grpc
from orchestrator import ShippingOrchestrator

logging.basicConfig(
    level=logging.DEBUG,
    format='{"timestamp": "%(asctime)s", "severity": "%(levelname)s", "message": "%(message)s"}',
)
log = logging.getLogger(__name__)

PORT = os.environ.get("PORT", "50051")


class ShippingServicer(demo_pb2_grpc.ShippingServiceServicer):
    """
    gRPC Servicer: thin adapter layer that translates protobuf requests
    into Python dicts, passes them to the ShippingOrchestrator, and
    returns the result as protobuf responses.
    """

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(
            target=self.loop.run_forever,
            daemon=True
        )
        self.loop_thread.start()

        self.orchestrator = ShippingOrchestrator()
        log.info("ShippingServicer initialized with agent orchestrator")

    def run_async(self, coro):
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result()

    def GetQuote(self, request, context):
        log.info("GetQuote called")
        try:
            address = {
                "street_address": request.address.street_address,
                "city": request.address.city,
                "state": request.address.state,
                "country": request.address.country,
                "zip_code": request.address.zip_code,
            }

            items = [
                {"product_id": item.product_id, "quantity": item.quantity}
                for item in request.items
            ]

            result = self.run_async(self.orchestrator.get_quote(address, items))

            units = int(result["cost_usd"])
            nanos = int(round((result["cost_usd"] - units) * 1e9))

            return demo_pb2.GetQuoteResponse(
                cost_usd=demo_pb2.Money(
                    currency_code="USD",
                    units=units,
                    nanos=nanos,
                )
            )

        except Exception as e:
            log.error(f"GetQuote failed: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return demo_pb2.GetQuoteResponse()

    
    def ShipOrder(self, request, context):
        log.info("ShipOrder called")
        try:
            address = {
                "street_address": request.address.street_address,
                "city": request.address.city,
                "state": request.address.state,
                "country": request.address.country,
                "zip_code": request.address.zip_code,
            }
            items = [
                {"product_id": item.product_id, "quantity": item.quantity}
                for item in request.items
            ]

            result = self.orchestrator.tracking_agent.generate(
    carrier="FedEx",
    address=address,
    item_count=sum(item["quantity"] for item in items)
)
            log.warning(f"[SHIPMENT_TRACE] ShipOrder result={result}")

            return demo_pb2.ShipOrderResponse(tracking_id=result["tracking_id"])
        except Exception as e:
            log.error(f"ShipOrder failed: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return demo_pb2.ShipOrderResponse()


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    demo_pb2_grpc.add_ShippingServiceServicer_to_server(ShippingServicer(), server)

    # Health check
    health_servicer = health.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)

    server.add_insecure_port(f"[::]:{PORT}")
    server.start()
    log.info(f"Agent-based ShippingService listening on port {PORT}")

    def handle_sigterm(*_):
        log.info("Received SIGTERM, shutting down gracefully...")
        server.stop(5)

    signal.signal(signal.SIGTERM, handle_sigterm)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
