from sqlalchemy.orm import Session

from app.models.models import SocialAccount, SyncRun
from app.services.instagram_sync import sync_instagram


def run_sync_for_account(db: Session, account: SocialAccount) -> dict:
    result = sync_instagram(db, account)
    if result.get("ok"):
        row = SyncRun(
            social_account_id=account.id,
            status="success",
            created_posts=int(result.get("created_posts", 0)),
            created_comments=int(result.get("created_comments", 0)),
        )
    else:
        row = SyncRun(
            social_account_id=account.id,
            status="failed",
            error_reason=result.get("reason"),
            error_detail=str(result.get("detail", ""))[:2000],
        )
    db.add(row)
    db.commit()
    return result


def run_sync_for_owner(db: Session, owner_id: int) -> dict:
    accounts = db.query(SocialAccount).filter(SocialAccount.owner_id == owner_id).all()
    report = {"total": len(accounts), "ok": 0, "failed": 0, "results": []}
    for account in accounts:
        result = run_sync_for_account(db, account)
        report["results"].append({"account_id": account.id, "result": result})
        if result.get("ok"):
            report["ok"] += 1
        else:
            report["failed"] += 1
    return report
