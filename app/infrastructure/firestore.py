import json
import firebase_admin
from firebase_admin import credentials, firestore
from app.core.config import settings
from app.common.logging import logger
import os
from unittest.mock import MagicMock

db = None

def init_firestore():
    global db
    
    # Check for Testing environment
    if os.getenv("TESTING") == "True":
        logger.warning("TESTING mode active: Using Mock Firestore Client.")
        db = MagicMock()
        return

    try:
        if not firebase_admin._apps:
            if settings.FIREBASE_CREDENTIALS_JSON:
                cred = credentials.Certificate(json.loads(settings.FIREBASE_CREDENTIALS_JSON))
                firebase_admin.initialize_app(cred)
                logger.info("Firebase initialized with credentials from FIREBASE_CREDENTIALS_JSON.")
            elif settings.FIREBASE_CREDENTIALS_PATH and os.path.exists(settings.FIREBASE_CREDENTIALS_PATH):
                cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
                firebase_admin.initialize_app(cred)
                logger.info("Firebase initialized with credentials.")
            else:
                logger.warning(
                    "Firebase credentials file not found at %s. Falling back to default credentials.",
                    settings.FIREBASE_CREDENTIALS_PATH,
                )
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
