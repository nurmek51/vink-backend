from app.providers.esim_provider.schemas import ImsiListItem, ImsiInfoResponse
from app.modules.esim.schemas import Esim

def map_imsi_to_esim(imsi_item: ImsiListItem) -> Esim:
    return Esim(
        id=imsi_item.imsi, # Using IMSI as ID for now
        iccid="UNKNOWN", # List endpoint doesn't return ICCID
        imsi=imsi_item.imsi,
        msisdn=imsi_item.msisdn,
        country="Global", # Default
        provider="Vink",
        provider_balance=imsi_item.balance,
        data_used=0.0, # Not provided
        data_limit=imsi_item.balance, 
        is_active=True
    )

def map_imsi_info_to_esim(info: ImsiInfoResponse) -> Esim:
    return Esim(
        id=info.IMSI,
        iccid=info.ICCID,
        imsi=info.IMSI,
        msisdn=info.MSISDN,
        country=str(info.LASTMCC) if info.LASTMCC else "Global",
        provider="Vink",
        provider_balance=float(info.BALANCE) if info.BALANCE is not None else 0.0,
        data_used=0.0,
        data_limit=10.0,
        is_active=True
    )
