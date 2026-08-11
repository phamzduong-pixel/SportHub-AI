"""Create the initial SYSTEM_ADMIN without exposing a public elevation API."""
import argparse
import getpass
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.security import get_password_hash  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description='Tạo tài khoản SYSTEM_ADMIN SportHub')
    parser.add_argument('--email', required=True)
    parser.add_argument('--name', default='SportHub System Admin')
    args = parser.parse_args()
    email = args.email.strip().lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        raise SystemExit('Email không hợp lệ.')
    password = getpass.getpass('Mật khẩu SYSTEM_ADMIN (tối thiểu 12 ký tự): ')
    confirmation = getpass.getpass('Nhập lại mật khẩu: ')
    if password != confirmation:
        raise SystemExit('Mật khẩu xác nhận không khớp.')
    if len(password) < 12:
        raise SystemExit('Mật khẩu phải có tối thiểu 12 ký tự.')
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == email))
        if existing:
            raise SystemExit('Email đã tồn tại; script không tự nâng quyền tài khoản hiện có.')
        admin = User(
            full_name=args.name.strip(), email=email, hashed_password=get_password_hash(password),
            role=UserRole.SYSTEM_ADMIN.value, is_active=True,
        )
        db.add(admin); db.commit()
        print(f'Đã tạo SYSTEM_ADMIN: {email}')


if __name__ == '__main__':
    main()
