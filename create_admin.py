from getpass import getpass
import mysql.connector
from werkzeug.security import generate_password_hash
from config import DB_CONFIG

username = input("Username admin: ").strip()
fullname = input("Nama admin: ").strip()
password = getpass("Password admin: ")

if not username or not fullname or not password:
    raise SystemExit("Semua data wajib diisi.")

conn = mysql.connector.connect(**DB_CONFIG)
cursor = conn.cursor()

try:
    cursor.execute(
        """
        INSERT INTO users (username, password_hash, fullname, role)
        VALUES (%s, %s, %s, 'ADMIN')
        """,
        (username, generate_password_hash(password), fullname)
    )
    conn.commit()
    print("Akun admin berhasil dibuat.")

except mysql.connector.IntegrityError:
    print("Username sudah digunakan. Gunakan username lain.")

finally:
    cursor.close()
    conn.close()