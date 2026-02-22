from typing import Optional

import anyio

from app.infrastructure.firestore import get_db


class PaymentEsimRepository:
    def __init__(self) -> None:
        self._db = None

    @property
    def db(self):
        if self._db is None:
            self._db = get_db()
        return self._db

    @property
    def collection(self):
        return self.db.collection("vink_sim_esims")

    async def get_user_esim(self, user_id: str, esim_id: str) -> Optional[dict]:
        doc_ref = self.collection.document(esim_id)
        doc = await anyio.to_thread.run_sync(doc_ref.get)
        if not doc.exists:
            return None
        data = doc.to_dict()
        if data.get("user_id") != user_id:
            return None
        return data

    async def update_esim(self, esim_data: dict) -> None:
        doc_ref = self.collection.document(esim_data["id"])
        await anyio.to_thread.run_sync(doc_ref.set, esim_data)
