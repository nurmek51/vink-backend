from app.infrastructure.firestore import get_db
from app.modules.esim.schemas import Esim
from typing import List, Optional

class EsimRepository:
    def __init__(self):
        self.db = get_db()
        self.collection = self.db.collection("vink_sim_esims")

    async def get_esim(self, esim_id: str) -> Optional[dict]:
        doc = self.collection.document(esim_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    async def save_esim(self, esim_data: dict):
        self.collection.document(esim_data["id"]).set(esim_data)

    async def get_user_esims(self, user_id: str) -> List[dict]:
        # Assuming we store user_id in the esim document
        docs = self.collection.where("user_id", "==", user_id).stream()
        return [doc.to_dict() for doc in docs]
