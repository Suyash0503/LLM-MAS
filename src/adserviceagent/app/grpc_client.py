import grpc
from typing import List, Dict

from app.config import ADSERVICE_HOST, ADSERVICE_PORT
from app.clients import demo_pb2, demo_pb2_grpc


class AdServiceClient:
    def __init__(self):
        target = f"{ADSERVICE_HOST}:{ADSERVICE_PORT}"
        self.channel = grpc.insecure_channel(target)
        self.stub = demo_pb2_grpc.AdServiceStub(self.channel)

    def get_ads(self, context_keys: List[str]) -> List[Dict]:
        request = demo_pb2.AdRequest(context_keys=context_keys)
        response = self.stub.GetAds(request)

        ads = []
        for ad in response.ads:
            ads.append(
                {
                    "redirect_url": ad.redirect_url,
                    "text": ad.text,
                }
            )

        return ads