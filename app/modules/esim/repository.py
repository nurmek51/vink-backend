from app.infrastructure.firestore import get_db
from typing import List, Optional
import anyio
from google.cloud.exceptions import Conflict

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

    @property
    def reservation_collection(self):
        return self.db.collection("esim_reservations")

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

    async def create_reservation(self, imsi: str, payload: dict) -> bool:
        ref = self.reservation_collection.document(imsi)
        try:
            await anyio.to_thread.run_sync(ref.create, payload)
            return True
        except Conflict:
            return False
        except Exception:
            return False

    async def get_reserved_imsis(self) -> List[str]:
        docs = await anyio.to_thread.run_sync(self.reservation_collection.get)
        return [doc.id for doc in docs]

    async def get_reservation_by_payment_id(self, payment_id: str) -> Optional[dict]:
        query = self.reservation_collection.where("payment_id", "==", payment_id).limit(1)
        docs = await anyio.to_thread.run_sync(query.get)
        for doc in docs:
            data = doc.to_dict() or {}
            data["imsi"] = doc.id
            return data
        return None

    async def delete_reservation(self, imsi: str) -> None:
        ref = self.reservation_collection.document(imsi)
        await anyio.to_thread.run_sync(ref.delete)
