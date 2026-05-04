from app.grpc_client import RecommendationGrpcClient

client = RecommendationGrpcClient()


class RecommendationAgent:
    def get_recommendations(self, user_id: str, product_ids: list[str]) -> dict:
        """Fetch recommended product IDs for a user given their current product context."""
        recommended_ids = client.list_recommendations(
            user_id=user_id,
            product_ids=product_ids,
        )
        return {
            "mode": "agent",
            "action": "list_recommendations",
            "user_id": user_id,
            "input_product_ids": product_ids,
            "recommended_product_ids": recommended_ids,
        }

    def explain_recommendations(self, user_id: str, product_ids: list[str]) -> dict:
        """
        Fetch recommendations and return raw data so the LLM node can
        generate a human-readable explanation downstream.
        """
        recommended_ids = client.list_recommendations(
            user_id=user_id,
            product_ids=product_ids,
        )
        return {
            "mode": "agent",
            "action": "explain_recommendations",
            "user_id": user_id,
            "input_product_ids": product_ids,
            "recommended_product_ids": recommended_ids,
        }