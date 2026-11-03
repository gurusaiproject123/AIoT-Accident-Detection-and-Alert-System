from getpass import getpass

from app.core.database import get_supabase_admin


def main():
    password = getpass("Enter your new password: ")
    confirmation = getpass("Confirm your new password: ")

    if password != confirmation:
        print("Passwords do not match. Account was not created.")
        return

    if not password:
        print("Password cannot be empty.")
        return

    db = get_supabase_admin()

    result = db.auth.admin.create_user(
        {
            "email": "petermufudza112@gmail.com",
            "password": password,
            "email_confirm": True,
            "user_metadata": {
                "full_name": "Peter Mufudza",
            },
        }
    )

    if result.user:
        print("SUCCESS: Auth account created.")
        print("User ID:", result.user.id)
        print("Your database trigger creates the superuser profile.")


if __name__ == "__main__":
    main()