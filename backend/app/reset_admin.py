"""Run inside the backend container to reset a user's password - the
equivalent of SafeLine's `docker exec safeline-mgt resetadmin`:

    docker compose exec backend python -m app.reset_admin [username]

Defaults to "admin" if no username is given. Prints the new password once,
directly to this terminal (unlike the initial-boot password, no waiting is
needed here - `docker compose exec` is synchronous).
"""

import sys

from app.auth import DEFAULT_ADMIN_USERNAME, reset_user_password
from app.db import SessionLocal


def main() -> None:
    username = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ADMIN_USERNAME

    db = SessionLocal()
    try:
        new_password = reset_user_password(db, username)
    finally:
        db.close()

    if new_password is None:
        print(f"No user named '{username}' exists. List known usernames from the dashboard's Team page.")
        return

    print(
        "\n"
        "==================================================================\n"
        "  Sentinel WAF - password reset\n"
        f"  username: {username}\n"
        f"  password: {new_password}\n"
        "  This password is shown ONLY this one time - it is not stored in\n"
        "  plaintext anywhere. All other logged-in sessions have been\n"
        "  signed out. Log in and change this password from the dashboard.\n"
        "==================================================================\n"
    )


if __name__ == "__main__":
    main()
