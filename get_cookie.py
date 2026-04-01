"""
Tự động đăng nhập Pinterest (headless) và lưu cookie
vào data/pinterest_cookies.json để bot.py và web_admin.py sử dụng.

Cấu hình trong .env:
    PINTEREST_EMAIL=your_email
    PINTEREST_PASSWORD=your_password

Cách dùng:
    python get_cookie.py
"""

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

load_dotenv()

COOKIES_FILE = Path(__file__).parent / "data" / "pinterest_cookies.json"

REQUIRED_KEYS = {
    "csrftoken", "_auth", "_pinterest_sess",
    "__Secure-s_a", "_b", "_routing_id",
    "sessionFunnelEventLogged",
}


def get_cookies(email: str, password: str) -> dict:
    """Đăng nhập Pinterest headless, trả về dict cookie."""
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
    )
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])

    driver = webdriver.Chrome(options=opts)
    wait = WebDriverWait(driver, 20)

    try:
        print("🌐  Đang mở Pinterest login...")
        driver.get("https://www.pinterest.com/login/")

        # Nhập email
        email_input = wait.until(EC.presence_of_element_located((By.ID, "email")))
        email_input.clear()
        email_input.send_keys(email)

        # Nhập password
        pass_input = driver.find_element(By.ID, "password")
        pass_input.clear()
        pass_input.send_keys(password)

        # Click nút đăng nhập
        login_btn = driver.find_element(
            By.CSS_SELECTOR, "button[type='submit'], div[data-test-id='registerFormSubmitButton']"
        )
        login_btn.click()
        print("🔐  Đang đăng nhập...")

        # Chờ cookie _auth=1 xuất hiện (đăng nhập thành công)
        for _ in range(30):
            time.sleep(2)
            cookies = driver.get_cookies()
            auth = next((c for c in cookies if c["name"] == "_auth"), None)
            if auth and auth["value"] == "1":
                break
        else:
            raise RuntimeError(
                "Đăng nhập thất bại — không thấy cookie _auth=1. "
                "Kiểm tra lại email/password hoặc Pinterest yêu cầu xác minh."
            )

        # Chuyển sang dict
        cookie_dict = {c["name"]: c["value"] for c in driver.get_cookies()}
        return cookie_dict

    finally:
        driver.quit()


def main() -> None:
    email = os.getenv("PINTEREST_EMAIL", "")
    password = os.getenv("PINTEREST_PASSWORD", "")

    if not email or not password:
        print("❌  Thiếu PINTEREST_EMAIL hoặc PINTEREST_PASSWORD trong file .env")
        print("   Thêm vào .env:")
        print("     PINTEREST_EMAIL=your_email")
        print("     PINTEREST_PASSWORD=your_password")
        return

    COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)

    cookie_dict = get_cookies(email, password)

    # Lưu file
    COOKIES_FILE.write_text(json.dumps(cookie_dict, indent=2, ensure_ascii=False))
    print(f"✅  Đăng nhập thành công!")
    print(f"💾  Đã lưu {len(cookie_dict)} cookies vào {COOKIES_FILE}")

    found = REQUIRED_KEYS & cookie_dict.keys()
    missing = REQUIRED_KEYS - cookie_dict.keys()
    print(f"    ✔ Có: {', '.join(sorted(found))}")
    if missing:
        print(f"    ⚠ Thiếu: {', '.join(sorted(missing))}")
    print("\n🎉  Xong! Restart bot.py để sử dụng cookie mới.")


if __name__ == "__main__":
    main()
