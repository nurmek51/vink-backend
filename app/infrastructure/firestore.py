import firebase_admin
from firebase_admin import credentials, firestore
from app.core.config import settings
from app.common.logging import logger
import os

db = None

def init_firestore():
    global db
    try:
        if not firebase_admin._apps:
            if os.path.exists(settings.FIREBASE_CREDENTIALS_PATH):
                cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
                firebase_admin.initialize_app(cred)
                logger.info("Firebase initialized with credentials.")
            else:
                logger.warning(f"Firebase credentials not found at {settings.FIREBASE_CREDENTIALS_PATH}. Using mock/anonymous or failing.")
                # For development without creds, we might want to just warn or use a mock if possible.
                # But Firestore client usually needs creds. 
                # We will initialize with default if available (e.g. GCloud env vars)
                try:
                    firebase_admin.initialize_app()
                    logger.info("Firebase initialized with default credentials.")
                except Exception as e:
                    logger.error(f"Failed to initialize Firebase: {e}")
                    return

        db = firestore.client()
    except Exception as e:
        logger.error(f"Error initializing Firestore: {e}")
        raise e

def get_db():
    if db is None:
        init_firestore()
    return db
