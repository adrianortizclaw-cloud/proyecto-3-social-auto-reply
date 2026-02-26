from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, rate_limit_user
from app.core.security import encrypt_secret
from app.db.session import get_db
from app.models.models import SocialAccount, User
from app.schemas.accounts import SocialAccountCreate, SocialAccountOut
from app.services.audit_service import log_action

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.post("", response_model=SocialAccountOut)
def create_account(
    payload: SocialAccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(rate_limit_user),
):
    account = SocialAccount(
        owner_id=current_user.id,
        platform=payload.platform,
        account_handle=payload.account_handle,
        prompt_persona=payload.prompt_persona,
        instagram_token_encrypted=encrypt_secret(payload.instagram_token) if payload.instagram_token else None,
        openai_key_encrypted=encrypt_secret(payload.openai_api_key) if payload.openai_api_key else None,
        auto_mode=payload.auto_mode,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    log_action(db, action="account_created", user_id=current_user.id, entity_type="social_account", entity_id=str(account.id))
    return account


@router.get("", response_model=list[SocialAccountOut])
def list_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(SocialAccount)
        .filter(SocialAccount.owner_id == current_user.id)
        .order_by(SocialAccount.id.desc())
        .all()
    )


@router.delete("/{account_id}")
def delete_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(rate_limit_user),
):
    account = db.get(SocialAccount, account_id)
    if not account or account.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(account)
    db.commit()
    log_action(db, action="account_deleted", user_id=current_user.id, entity_type="social_account", entity_id=str(account_id))
    return {"ok": True}
