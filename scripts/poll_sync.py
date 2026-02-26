#!/usr/bin/env python3
import os
import time
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.models import SocialAccount
from app.services.sync_service import run_sync_for_account

INTERVAL_SECONDS = int(os.getenv("SYNC_POLL_INTERVAL_SECONDS", "180"))


def loop():
    while True:
        db: Session = SessionLocal()
        try:
            accounts = db.query(SocialAccount).all()
            for account in accounts:
                run_sync_for_account(db, account)
        finally:
            db.close()
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    loop()
