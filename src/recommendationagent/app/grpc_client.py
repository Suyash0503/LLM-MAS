import grpc
from app.config import RECOMMENDATION_HOST, RECOMMENDATION_PORT
from app.clients import demo_pb2
from app.clients import demo_pb2_grpc


class RecommendationGrpcClient:
    def __init__(self):
        target = f"{RECOMMENDATION_HOST}:{RECOMMENDATION_PORT}"
        self.channel = grpc.insecure_channel(target)
        self.stub = demo_pb2_grpc.RecommendationServiceStub(self.channel)

    def list_recommendations(self, user_id: str, product_ids: list[str]) -> list[str]:
        """
        Calls RecommendationService.ListRecommendations.
        Returns a list of recommended product IDs.
        """
        request = demo_pb2.ListRecommendationsRequest(
            user_id=user_id,
            product_ids=product_ids,
        )
        response = self.stub.ListRecommendations(request)
        return list(response.product_ids)