from app.modules.wallet.repository import WalletRepository

class WalletService:
    def __init__(self):
        self.repository = WalletRepository()
