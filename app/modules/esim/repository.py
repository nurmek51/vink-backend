from app.infrastructure.firestore import get_db
from typing import List, Optional
import anyio

class EsimRepository:
    def __init__(self):
        self._db = None

    @property
    def db(self):
        if self._db is None:
            self._db = get_db()
        return self._db

    @property
    def collection(self):
        return self.db.collection("vink_sim_esims")

    async def get_esim(self, esim_id: str) -> Optional[dict]:
        doc_ref = self.collection.document(esim_id)
        doc = await anyio.to_thread.run_sync(doc_ref.get)
        if doc.exists:
            return doc.to_dict()
        return None

    async def save_esim(self, esim_data: dict):
        doc_ref = self.collection.document(esim_data["id"])
        await anyio.to_thread.run_sync(doc_ref.set, esim_data)

    async def get_user_esims(self, user_id: str) -> List[dict]:
        query = self.collection.where("user_id", "==", user_id)
        docs = await anyio.to_thread.run_sync(query.get)
        return [doc.to_dict() for doc in docs]

    async def get_all_allocated_imsis(self) -> List[str]:
        query = self.collection.where("user_id", "!=", None)
        docs = await anyio.to_thread.run_sync(query.get)
        return [doc.to_dict().get("imsi") for doc in docs if doc.to_dict().get("imsi")]

    async def get_unassigned_esims(self) -> List[dict]:
        query = self.collection.where("user_id", "==", None)
        docs = await anyio.to_thread.run_sync(query.get)
        return [doc.to_dict() for doc in docs]

    async def update_activation_code_by_iccid(self, iccid: str, activation_code: str) -> bool:
        query = self.collection.where("iccid", "==", iccid).limit(1)
        docs = await anyio.to_thread.run_sync(query.get)
        found = False
        for doc in docs:
            await anyio.to_thread.run_sync(doc.reference.update, {"activation_code": activation_code})
            found = True
        return found

    async def get_esim_by_imsi(self, imsi: str) -> Optional[dict]:
        query = self.collection.where("imsi", "==", imsi).limit(1)
        docs = await anyio.to_thread.run_sync(query.get)
        for doc in docs:
            return doc.to_dict()
        return None
