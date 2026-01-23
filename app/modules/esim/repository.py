from app.infrastructure.firestore import get_db
from typing import List, Optional

class EsimRepository:
    def __init__(self):
        pass

    @property
    def collection(self):
        return get_db().collection("vink_sim_esims")

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

    async def get_all_allocated_imsis(self) -> List[str]:
        # Get all esims that have an IMSI assigned and a user_id
        docs = self.collection.where("user_id", "!=", None).stream()
        return [doc.to_dict().get("imsi") for doc in docs if doc.to_dict().get("imsi")]

    async def update_activation_code_by_iccid(self, iccid: str, activation_code: str) -> bool:
        docs = self.collection.where("iccid", "==", iccid).limit(1).stream()
        found = False
        for doc in docs:
            # We assume unique ICCID, so we update the first one found
            doc.reference.update({"activation_code": activation_code})
            found = True
        return found


    async def get_esim_by_imsi(self, imsi: str) -> Optional[dict]:
        docs = self.collection.where("imsi", "==", imsi).limit(1).stream()
        for doc in docs:
            return doc.to_dict()
        return None
