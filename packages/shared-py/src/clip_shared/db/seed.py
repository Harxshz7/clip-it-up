import uuid

from clip_shared.config import get_settings
from clip_shared.db.models import Project, User
from clip_shared.db.session import get_sync_db

settings = get_settings()


def seed_database():
    with get_sync_db() as db:
        dev_user_id = uuid.UUID(settings.DEV_USER_ID)
        user = db.query(User).filter(User.id == dev_user_id).first()
        if not user:
            user = User(
                id=dev_user_id,
                clerk_user_id=settings.DEV_CLERK_USER_ID,
                email=settings.DEV_USER_EMAIL,
            )
            db.add(user)
            db.flush()
            print(f"Created dev user: {user.email} ({user.id})")

        project = db.query(Project).filter(Project.user_id == user.id, Project.name == "Default Project").first()
        if not project:
            project = Project(
                id=uuid.uuid4(),
                user_id=user.id,
                name="Default Project",
            )
            db.add(project)
            db.flush()
            print(f"Created default project: {project.name} ({project.id})")


if __name__ == "__main__":
    seed_database()
