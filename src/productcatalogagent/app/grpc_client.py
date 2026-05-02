import grpc
from app.config import PRODUCT_CATALOG_HOST, PRODUCT_CATALOG_PORT
from app.clients import demo_pb2
from app.clients import demo_pb2_grpc


class ProductCatalogGrpcClient:
    def __init__(self):
        target = f"{PRODUCT_CATALOG_HOST}:{PRODUCT_CATALOG_PORT}"
        self.channel = grpc.insecure_channel(target)
        self.stub = demo_pb2_grpc.ProductCatalogServiceStub(self.channel)

    def _product_to_dict(self, p):
        return {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "picture": getattr(p, "picture", ""),
            "categories": list(getattr(p, "categories", [])),
            "price_usd": {
                "currency_code": getattr(p.price_usd, "currency_code", ""),
                "units": getattr(p.price_usd, "units", 0),
                "nanos": getattr(p.price_usd, "nanos", 0),
            }
        }

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