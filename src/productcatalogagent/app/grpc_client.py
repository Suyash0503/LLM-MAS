import grpc
from app.config import PRODUCT_CATALOG_HOST, PRODUCT_CATALOG_PORT, FAULT_MODE, BUSINESS_EXCEPTION
from app.clients import demo_pb2
from app.clients import demo_pb2_grpc


class ProductCatalogGrpcClient:
    def __init__(self):
        target = f"{PRODUCT_CATALOG_HOST}:{PRODUCT_CATALOG_PORT}"
        self.channel = grpc.insecure_channel(target)
        self.stub = demo_pb2_grpc.ProductCatalogServiceStub(self.channel)

    def _product_to_dict(self, p):
        product = {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "picture": getattr(p, "picture", ""),
            "categories": list(getattr(p, "categories", [])),
            "price_usd": {
                "currency_code": getattr(p.price_usd, "currency_code", ""),
                "units": getattr(p.price_usd, "units", 0),
                "nanos": getattr(p.price_usd, "nanos", 0),
            },
            "inventory": {
                "actual_stock": 0,
                "reported_stock": 0
            }
        }

        print(f"[FAULT DEBUG] BUSINESS_EXCEPTION={BUSINESS_EXCEPTION}, FAULT_MODE={FAULT_MODE}")   
        if BUSINESS_EXCEPTION == "inventory_mismatch":
            product["inventory"]["actual_stock"] = 0

            if FAULT_MODE == "FM-3.2":
                product["inventory"]["reported_stock"] = 5
                product["fault_injected"] = True
                product["fault_type"] = "tool_response_manipulation"
                product["mast_mode"] = "FM-3.2"
                product["root_cause"] = "Product catalog tool response reported stock as available although actual stock was zero."

            elif FAULT_MODE == "FM-2.4":
                product["inventory"] = {
                    "reported_stock": 5
                }
                product["fault_injected"] = True
                product["fault_type"] = "information_withholding"
                product["mast_mode"] = "FM-2.4"
                product["root_cause"] = "Actual stock field was withheld from the agent response."

            elif FAULT_MODE == "FM-1.3":
                product["inventory"]["reported_stock"] = 5
                product["fault_injected"] = True
                product["fault_type"] = "step_repetition"
                product["mast_mode"] = "FM-1.3"
                product["root_cause"] = "Inventory reservation/check step is repeated or duplicated downstream."

            else:
                product["inventory"]["reported_stock"] = 0
                product["fault_injected"] = False
                
        print("[PRODUCT DEBUG]", product)

        return product

    def list_products(self):
        request = demo_pb2.Empty()
        response = self.stub.ListProducts(request)
        return [self._product_to_dict(p) for p in response.products]

    def get_product(self, product_id: str):
        request = demo_pb2.GetProductRequest(id=product_id)
        response = self.stub.GetProduct(request)
        return self._product_to_dict(response)

    def search_products(self, query: str):
        request = demo_pb2.SearchProductsRequest(query=query)
        response = self.stub.SearchProducts(request)
        return [self._product_to_dict(p) for p in response.results]