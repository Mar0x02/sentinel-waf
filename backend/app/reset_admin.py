"""Run inside the backend container to reset the admin password - the
equivalent of SafeLine's `docker exec safeline-mgt resetadmin`:

    docker compose exec backend python -m app.reset_admin

Prints the new password once, directly to this terminal (unlike the
initial-boot password, no waiting is needed here - `docker compose exec`
is synchronous, so there's no install.sh-style polling required).
"""

from app.auth import reset_admin_password
from app.db import SessionLocal


def main() -> None:
    db = SessionLocal()
    try:
        result = reset_admin_password(db)
    finally:
        db.close()

    if result is None:
        print("No admin account exists yet - one will be created automatically on the backend's next startup.")
        return

    username, new_password = result
    print(
        "\n"
        "==================================================================\n"
        "  Sentinel WAF - admin password reset\n"
        f"  username: {username}\n"
        f"  password: {new_password}\n"
        "  This password is shown ONLY this one time - it is not stored in\n"
        "  plaintext anywhere. All other logged-in sessions have been\n"
        "  signed out. Log in and change this password from the dashboard.\n"
        "==================================================================\n"
    )


if __name__ == "__main__":
    main()
