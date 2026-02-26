from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.models import SocialAccount, Post, Comment, Reply


def sync_mock_instagram(db: Session, account: SocialAccount):
    now = datetime.utcnow()

    post = Post(
        account_id=account.id,
        platform_post_id=f"mock-post-{int(now.timestamp())}",
        kind="post",
        caption="Promo de temporada en marcha 🚀",
        published_at=now - timedelta(minutes=20),
    )
    reel = Post(
        account_id=account.id,
        platform_post_id=f"mock-reel-{int(now.timestamp())}",
        kind="reel",
        caption="Behind the scenes del equipo",
        published_at=now - timedelta(minutes=10),
    )
    db.add_all([post, reel])
    db.flush()

    comment = Comment(
        post_id=post.id,
        platform_comment_id=f"mock-comment-{int(now.timestamp())}",
        author_handle="cliente_curioso",
        text="¿Tenéis disponibilidad mañana por la tarde?",
        created_at=now - timedelta(minutes=5),
    )
    db.add(comment)
    db.flush()

    reply = Reply(
        comment_id=comment.id,
        text="¡Sí! Escríbenos por DM y te confirmamos el horario.",
        status="draft",
        created_at=now - timedelta(minutes=3),
    )
    db.add(reply)
    db.commit()
