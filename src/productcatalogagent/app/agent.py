from app.grpc_client import ProductCatalogGrpcClient

client = ProductCatalogGrpcClient()


class ProductCatalogAgent:
    def run(self, query: str, product_ids=None):
        q = query.lower().strip()

        if product_ids:
            products = [client.get_product(pid) for pid in product_ids]
            return {
                "mode": "agent",
                "action": "get_product",
                "data": products
            }

        if "all products" in q or "list products" in q or "show products" in q or q == "catalog":
            return {
                "mode": "agent",
                "action": "list_products",
                "data": client.list_products()
            }

        return {
            "mode": "agent",
            "action": "search_products",
            "data": client.search_products(query)
        }