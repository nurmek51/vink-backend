from app.infrastructure.firestore import get_db

class WalletRepository:
    def __init__(self):
        self.db = get_db()
        self.collection = self.db.collection("vink_wallet_accounts")
