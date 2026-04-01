import os
import json
import sqlite3
import random
import logging
from pathlib import Path

import cv2
import numpy as np
import requests
from urllib.parse import quote, quote_plus

from dotenv import load_dotenv
from pinscrape import Pinterest
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, ForceReply
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.DEBUG,
)
logger = logging.getLogger(__name__)

# ============ TỪ KHÓA PINTEREST THEO THỂ LOẠI ============

KEYWORDS_DB = Path(__file__).parent / "data" / "keywords.db"


def _get_db() -> sqlite3.Connection:
    KEYWORDS_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(KEYWORDS_DB)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS keywords "
        "(category TEXT NOT NULL, keyword TEXT NOT NULL, "
        "PRIMARY KEY (category, keyword))"
    )
    conn.commit()
    return conn


def load_keywords() -> dict[str, list[str]]:
    """Tải từ khóa từ SQLite."""
    with _get_db() as conn:
        rows = conn.execute("SELECT category, keyword FROM keywords ORDER BY category, rowid").fetchall()
    result: dict[str, list[str]] = {}
    for cat, kw in rows:
        result.setdefault(cat, []).append(kw)
    return result


def save_keywords(kw: dict) -> None:
    """Ghi toàn bộ dict vào SQLite (xóa hết rồi insert lại)."""
    with _get_db() as conn:
        conn.execute("DELETE FROM keywords")
        conn.executemany(
            "INSERT OR IGNORE INTO keywords (category, keyword) VALUES (?, ?)",
            [(cat, k) for cat, kws in kw.items() for k in kws],
        )
        conn.commit()


KEYWORDS: dict[str, list[str]] = load_keywords()

# ============ CÂU TRẢ LỜI THEO PHONG CÁCH THƯ KÝ ============

RESPONSES: dict[str, dict[str, list[str]]] = {
    "girl": {
        "loading": [
            "🙈 Để em tìm ngay cho sếp nhé, đợi em một xíu thôi ạ~",
            "💅 Em đang chọn cô nàng xinh nhất cho sếp, chờ em tí ạ...",
            "🌸 Ồ sếp thích gái xinh à~ Em tìm ngay đây ạ!",
        ],
        "caption": [
            "😍 Sếp ơi, em tìm được cô này cho sếp rồi, đẹp không ạ~",
            "🌸 Xinh chưa sếp? Em chọn kỹ lắm đấy ạ 😘",
            "💕 Cô này hợp gu sếp không? Em nghĩ là sếp sẽ thích đó ạ~",
            "✨ Em dâng sếp một cô gái xinh, sếp có hài lòng không ạ? 🥰",
            "🎀 Hôm nay em chọn riêng cho sếp đó nha, đừng nhìn người khác nữa ạ~",
        ],
    },
    "sexy": {
        "loading": [
            "🔥 Ôi sếp... thích xem ảnh 'đặc biệt' hả~ Em tìm liền ạ!",
            "😏 Sếp hôm nay có gu quá~ Đợi em một chút ạ...",
            "💋 Em biết sếp thích gì rồi~ Để em phục vụ ngay ạ!",
        ],
        "caption": [
            "🔥 Nóng quá không sếp? Cẩn thận bỏng tay đó ạ~ 😏",
            "💋 Sếp có thích không? Em tìm 'chất' lắm đấy ạ~",
            "😈 Hôm nay em phục vụ sếp món đặc biệt rồi đó nha~",
            "🌡️ Nhiệt độ phòng tăng lên rồi kìa sếp ơi~ 😘",
            "💦 Sếp coi xong nhớ uống nước kẻo nóng ạ~ 🔥",
        ],
    },
    "bikini": {
        "loading": [
            "👙 Sếp muốn đi biển à~ Em tìm ảnh bikini đẹp cho sếp ngay!",
            "🏖️ Ồ sếp thích bikini hả, hèn gì~ Đợi em tí ạ!",
            "🌊 Để em chọn cô nào 'mát mẻ' nhất cho sếp nhé~",
        ],
        "caption": [
            "👙 Mùa hè đến rồi sếp ơi~ Cô này đi biển trông ngon không ạ? 😍",
            "🏖️ Sếp có muốn được 'cứu hộ' không ạ~ 😏",
            "🌊 Mát lạnh chưa sếp? Em chọn cô 'nước' nhất cho sếp rồi đó~",
            "☀️ Nắng hè gay gắt nhưng nhìn cô này lại thấy mát ạ~ 💦",
            "🐚 Biển xanh cát trắng và... sếp thích chứ ạ? Em biết mà~ 😘",
        ],
    },
    "cosplay": {
        "loading": [
            "🎭 Ôi sếp thích cosplay~ Em là thư ký kiêm luôn nhé😍 Đợi em tí!",
            "✨ Để em tìm 'nhân vật' phù hợp gu sếp nào~",
            "🎀 Sếp thích waifu nào? Em tìm ngay cho sếp ạ!",
        ],
        "caption": [
            "🎭 Sếp thấy cô này có đạt không ạ? Em nghĩ sếp sẽ 'save' ngay đó~ 😏",
            "✨ Waifu hôm nay của sếp đây ạ~ Em ghen rồi đó nha! 😤💕",
            "🎀 Cosplay đẹp thế này sếp có muốn em mặc thử không ạ~ 😳",
            "💫 Nhân vật trong mơ của sếp đây rồi~ Thích chưa ạ? 🥰",
            "🎌 Sếp là người có gu cao đó nha~ Em phục lắm ạ! 😍",
        ],
    },
    "asian": {
        "loading": [
            "🌸 Sếp thích gái Hàn hay Nhật ạ~ Em tìm cả hai cho sếp!",
            "✨ Idol kpop hay ulzzang sếp thích hơn? Để em bốc thăm~",
            "💗 Ồ sếp có gu Châu Á~ Để em tìm 'bạch tuyết' cho sếp ạ!",
        ],
        "caption": [
            "🌸 Sếp thấy cô idol này có đẹp không ạ? Em cũng ghen với cô ấy luôn~ 😤",
            "💗 Da trắng mắt to, sếp thích chứ ạ? Em biết gu sếp mà~ 😘",
            "✨ Hôm nay em tìm được 'bản giới hạn' cho sếp rồi đó nha~",
            "🎋 Châu Á huyền bí lắm sếp ơi~ Cô này đúng gu chưa ạ? 🥰",
            "💕 Mỹ nhân Châu Á dâng sếp đây ạ~ Sếp nhớ cảm ơn em nhé! 😏",
        ],
    },
    "onlyfans": {
        "loading": [
            "💋 Sếp... têu têu thật đó~ Em tìm 'hàng VIP' cho sếp ngay ạ!",
            "🔞 Ôi sếp hôm nay 'táo bạo' nhỉ~ Đợi em một chút ạ... 😏",
            "💎 Sếp xứng đáng được phục vụ hàng 'cao cấp'~ Em chiều sếp ạ!",
        ],
        "caption": [
            "💎 Hàng 'VIP' cho sếp đây ạ~ Xem xong đừng quên em nhé! 😘",
            "🔥 Sếp ơi... cẩn thận tim nhé~ Nóng lắm đó ạ! 💋",
            "😏 Em tìm được 'báu vật' cho sếp rồi~ Sếp có hài lòng không ạ?",
            "💦 Đây là phần thưởng cho sếp chăm chỉ hôm nay~ 🔞",
            "🌡️ Nhiệt kế vỡ rồi sếp ơi~ Cô này 'nhiệt' quá ạ! 🔥",
        ],
    },
    "random": {
        "loading": [
            "🎲 Sếp thích bất ngờ~ Em random cho sếp một cô đặc biệt nhé!",
            "✨ Hôm nay em chọn giúp sếp~ Cái gì ngon nhất sẽ hiện ra ạ!",
            "🎁 Bất ngờ từ thư ký đây sếp ơi~ Đợi em tí ạ!",
        ],
        "caption": [
            "🎲 Sếp may mắn hôm nay~ Em random ra cô xinh ghê ạ! 😍",
            "🎁 Quà bất ngờ từ em cho sếp đây~ Sếp thích không ạ? 🥰",
            "✨ Em chọn đúng gu sếp chưa? Nếu chưa thì sếp gõ lại em tìm tiếp ạ~ 😘",
        ],
    },
}


def get_response(category: str, key: str) -> str:
    """Lấy ngẫu nhiên một câu theo category và loại (loading/caption)."""
    cat = RESPONSES.get(category) or RESPONSES.get("random") or {}
    msgs = cat.get(key) or RESPONSES["random"].get(key, [""])
    return random.choice(msgs)
FETCH_COUNT = 20
# Số ảnh tối đa kiểm tra face detection mỗi keyword
FACE_CHECK_LIMIT = 6

pinterest = Pinterest()

# ── Cookie management: load từ file, fallback về hardcode ──
_COOKIES_FILE = Path(__file__).parent / "data" / "pinterest_cookies.json"

_FALLBACK_COOKIES = {
    "csrftoken":          "1c404f7351edff46c90be26b71b4e76e",
    "_routing_id":        '"dadc71a3-3eca-46d9-bf2b-54de877bcd73"',
    "_auth":              "1",
    "_pinterest_sess":    "TWc9PSZOUzl6Zm56Z294WSt6Q01XRmMrM3RtYythZWo2aU9MTDAxSGpnalFUYjBoRVcwR1RxQnc0UHFDSVNsdzQ5TVpDcXZlNFlqTWUzRFBTZU5JYTN1WFRtc2VDTG9zMERicDd4ZVBycDdhdzBPQVIycHV2VnpFai9nMXNlV051REVqWjlNSi9Kd1FlR1JpN1N4cjdjTVpOdGUwM056cFgxcFhBVXl2Q1grVVlMWHJEWlNzbG1CNm1jb1VTNkE1MGt0UStJYjRwNSs3TldrTXNrUU5WZ2NiM2tzRmtna3VmTUlYOFkxTmNOancrejZsMzBYSnM1K2pXcjROQ2xtajlHaDc2VkJkRUZZVng5VURhVER2K0hBMVk3eVlDeE5pdlpVSE5sU1hoUU4yMXRLejBKMStKTm04eXJCanRubFRySFR1b3BJM0c1eTFhTWFUL2dCcGhKMHJqMm10RGdMOHgyajR1aGFFSFBuWlZLUTJKQjlPVy9GRHZHU0dKYldLQjhNaHhHeTlseUt0T1RWMm4wYUluZk9MY0lIT0JURkh0WVpPNmhZdnduNFI1UEJXak1UZitiSHNGYWFpUGwzajVQaW9XYnpoNXA0YWdnREVjbzRlN3k3eXRES2pkUDM0OU9qeUV6eEtjNERjUW4ra2JYZTN6SWxRL0trbERPY2dJK045N01QYUtieG84SDRTM3FEMU8vTzZvMVQycmFTdnV6U3YvWjJ0bWlvVklvbE1WSCt1WVBEMnZPbGUxUHhvVHN2aUhnWWplcFdxVGhMay9MY0diakdvNzJPeE9jaDFxZnY4bGxibjV3aE5YeVZaUEl5VVJYTXlEZUpFNEN2UDJqWE9LY09wV00wQXlSNzY5blBnZ2JjNHJEUFhQMkJKNjNkY01ER0hMZlRoKzlkdm55WFc0NDMrMnd1N0EvdjlVZFVTUlBleHRyaGREQnNYMWM5U0hRVU1sL053L1RJczBZa0dFVXluODMwcGVUb0hGazVtZ3BaN2dUdkkwNHQ1V0wvdktPUncrcUt6bTVIRjZFaHVqemJQRE5vb0RBRDZRTHBLNHFqMDJDNUxrSVJqZnZEWnZjSVNwMDFPZG1rZlFlSnV6YSsvL2I0azNWeHp1WmxHbTZYbVQrdFBpYnpMQjlzellvQmNHTEtSWDl6Umx3R2tOSVUvOGo5Wkx6cjI0RGhxcFhhakV1UUhzbGYrdWNTcEdmSTRkczhDR0NrVjlqd2xBQUpwNDBvNzJIYUhIZE5hbm5oa09IM0xuMUU0L0xieWV3NVRHUVNmdjZqdVloZ3dnNzR2WHdBT0M4VjRkYS9kR3VvQitLOUdJNmhHYmpTRi9zVU5iMDRyRjN0NTBaMHB2aWY0OFVSb2FoTHcxc3lsako4U2ZxOXFQeUhVNHRNOENRZHN0NzVwT3BUcFZtd3ozeDI2bjA0VldnOVFPUUh5YWdQWm1hdGdGcFFEU2pXMVZGV3lCblpUSTJVOUY1VTB6MFFma3VaWkpLZmVhU1g1a1NNZ1RaMDM0cGdSTlhBLyt5NWZ6Q0lOaXdVaVlKV255d2YxaXBway8xeE1ndUgxMm9IZzNzTzhhL2h3bjJDK2VhcUFQR0gwbUx3LzZzMFBmWENkMUM0MCsrRlV4NzNCdUt0YnpGbnJ5Z2R6a2UvcU9IdnNiVk8rTlJhUTBmL3o0WVdpT0pKM0F6R2V0MXNoNENzTGJtMTNJZWF3NXFTc1pqdEg5V3JMc2ttbUI5N2hONzZwNmpQSklCbk0rOUthdHlxcHlGNE45bVBPcXdPWjUmVDc2TVJsMG8rTzlzV3ZNZzdVdjUzMEVkM0wwPQ==",
    "__Secure-s_a":       "RHd3MGl0U3ZZZFZXVVluZDA5SWhEaXpPbzNERjZ1MlhwYlNqT2k1S3RHckovOHhTRENDcTVxaktxQTNTcEVvMVUxck9RaFhINUdwUkcrK0tWVW81OFRaRnlCK29QRHFaajBLeHBId2VOZkwralpJQ0IxY0w0VEZTYkc3RlVaTnljcUFLcUhYRHVSV24wNjVIR2JDTk9yRUNSeDV3ZENUbUN1dHk4ajF4TGZrU2lhK05UWGdLRkhGSzRBalRDTWVyNGJpb1FyRHh5d0xMK0pRQ0QvMUdhRFVud0lTbGpnTkxVTkY1M2NNeDRsVkRHbmlDUFhiWUduYUo1dG9KQjBZcE1VMjdaUHFCU1pDSnBrTDRzd1A5NGlhaTF1WC9NWkRyZU5kRGZDUlBjWDFLanFuV2lZNWJTZVpvaWYrcUVKU2RLUDQ3QnJXY2F6bXV1V1diNGZKQWxoRGg2Rm1tbG1nNDV4aHBaRHVEU2JabEQ1a0V6WmdoTXU1bm0wVXgxd3lDamdlSXBkdUczN0tHbG5Bc21hSFVIeW9ncDlrb3UyZloxR1hQSldKUUxTQ0RKU1JhRjc2N1R0a0NsN29KclNocDExcFNWc0FJazJrc3dFOUFhWERLL05PWklEQ3pyOEFLMDhjd0x4SkJhdWQweThtRnI3ZzV0V1o1cWRWZGdQZXRYYXEzdmdoVyt5TEMyV2tyZ0tZWjFRS05FemJPdlh2WkY5cUg1VlpCYjZTb0N5bDZqTzBReHdiRmpPZHRIQTZ1dVRieHNYenVSSzFObWtQVGVvNzRZcHhUY3B5SXBlMFF4eVlaQ09FWFJ5NC90TkZrdHJrMWVFbWJKS2c2Y2dmNVJDZ2V2YUVnR2hneUt1bFZpN3VoaDE5TzlDQUw5aU56OHQ5THJhZGdxN2hncTZGYTg0SEhBeXJNMUF3dVZTUGg3SFRTbmRRT2xGTHpBVVVBVFZGOEdzbjJiaGxNb3pRUWJWNGUrR2FTVkJ3cytxd1RzR0tWSkNsamdJb0tBWGpVZUV2L1dwSjBKaWhFeVVNK3k5MWpabkRSMXIvYnlidmd0aWR1bHpRclo3NUEzRnpBc0RxeS9IN3lTTmhUaW5pZU9ZV3MraVZsaUcxc05GMFlHbGNEV0ZSUzBmYUQySlV2UWx6WVQ4TFdHQ3ZTai9ZZmw5UU9Nc3I3VHhkcG1Jcmd4Q1o4VFB0QktMZFZva1JFS2tFVnM2Y2M4bTlkNGdyYTlwZDI5MHYvVEYxOFRvZEI4TDB1WTB0SjZmYU5wNkdaK1pHb3ZIdnUyK1dIRzB0OTJqVnBSclpiY0QzWitDSkNRdzJ0WmtDRm82cz0mK0p1TTNSajlRc1JVamtLMHJQT2JOSjg0UHNVPQ==",
    "_b":                 '"AZKZo5PpspRJnpkkV+A2b7hFxEmnIJgUOcluyUf0n2blrCuL8D4EzgCOv/FJ4nnbTGE="',
    "sessionFunnelEventLogged": "1",
}


def _load_cookies_from_file() -> dict:
    try:
        if _COOKIES_FILE.exists():
            import json as _j
            data = _j.loads(_COOKIES_FILE.read_text())
            if data:
                return data
    except Exception:
        pass
    return _FALLBACK_COOKIES


def apply_pinterest_cookies() -> None:
    """Đọc cookie từ file (hoặc fallback) và inject vào session."""
    cookies = _load_cookies_from_file()
    pinterest.session.cookies.clear()
    pinterest.session.cookies.update(cookies)
    csrf = cookies.get("csrftoken", "")
    pinterest.session.headers.update({
        "x-csrftoken": csrf,
        "x-app-version": "b85ab6b",
    })
    logger.info(f"[Cookie] Đã load cookie, csrftoken={csrf[:8]}...")


apply_pinterest_cookies()

# Load các Haar cascade một lần tại module level
_cascade_frontal = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
_cascade_profile = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
_cascade_body    = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_upperbody.xml")
_cascade_full    = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_fullbody.xml")


def has_person(url: str, timeout: int = 8) -> bool:
    """Kiểm tra ảnh có người bằng nhiều cascade: frontal, profile, upper body, full body."""
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        arr = np.frombuffer(resp.content, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return False

        # Scale nhỏ lại để detection nhanh hơn + chuẩn hóa sáng
        h, w = img.shape
        if w > 800:
            scale = 800 / w
            img = cv2.resize(img, (800, int(h * scale)))
        img = cv2.equalizeHist(img)

        # 1. Mặt nhìn thẳng
        if len(_cascade_frontal.detectMultiScale(img, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30))) > 0:
            return True
        # 2. Mặt nghiêng
        if len(_cascade_profile.detectMultiScale(img, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30))) > 0:
            return True
        # 3. Upper body
        if len(_cascade_body.detectMultiScale(img, scaleFactor=1.05, minNeighbors=3, minSize=(50, 50))) > 0:
            return True
        # 4. Full body (bắt ảnh toàn thân)
        if len(_cascade_full.detectMultiScale(img, scaleFactor=1.05, minNeighbors=3, minSize=(30, 60))) > 0:
            return True

        logger.debug(f"[PersonDetect] ❌ {url}")
        return False
    except Exception as e:
        logger.debug(f"[PersonDetect] Lỗi {url}: {e}")
        return False


def _auto_refresh_cookies() -> bool:
    """Tự động đăng nhập lại Pinterest lấy cookie mới. Trả về True nếu thành công."""
    email = os.getenv("PINTEREST_EMAIL", "")
    password = os.getenv("PINTEREST_PASSWORD", "")
    if not email or not password:
        logger.error("[Cookie] Thiếu PINTEREST_EMAIL/PINTEREST_PASSWORD trong .env")
        return False
    try:
        from get_cookie import get_cookies
        cookie_dict = get_cookies(email, password)
        _COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)
        _COOKIES_FILE.write_text(json.dumps(cookie_dict, indent=2, ensure_ascii=False))
        apply_pinterest_cookies()
        logger.info("[Cookie] ✅ Đã tự động refresh cookie thành công")
        return True
    except Exception as e:
        logger.error(f"[Cookie] ❌ Auto refresh thất bại: {e}")
        return False


def _search_with_meta(query: str, page_size: int = 20, rs: str = "typed") -> list[dict]:
    """Gọi thẳng Pinterest API, trả về list dict {url, title, caption}."""
    source_url = f"/search/pins/?q={quote(query)}&rs={rs}"
    pinterest.session.get(f"{pinterest.BASE_URL}{source_url}", headers=pinterest.BASE_HEADERS)

    import json as _json
    payload = {
        "options": {
            "applied_unified_filters": None, "appliedProductFilters": "---",
            "article": None, "auto_correction_disabled": False, "corpus": None,
            "customized_rerank_type": None, "domains": None, "filters": None,
            "journey_depth": None, "page_size": page_size, "price_max": None,
            "price_min": None, "query_pin_sigs": None, "query": query,
            "redux_normalize_feed": True, "request_params": None, "rs": rs,
            "scope": "pins", "selected_one_bar_modules": None, "source_id": None,
            "source_module_id": None, "seoDrawerEnabled": False,
            "source_url": source_url, "top_pin_id": None, "top_pin_ids": None,
        },
        "context": {},
    }
    encoded = quote_plus(_json.dumps(payload, separators=(",", ":")))

    url = (
        f"{pinterest.BASE_URL}/resource/BaseSearchResource/get/"
        f"?source_url={quote_plus(source_url)}&data={encoded}&_={pinterest.time_epoch}"
    )
    headers = pinterest.BASE_HEADERS.copy()
    headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "Accept-Language": "vi,en-US;q=0.9,en;q=0.8",
        "X-Pinterest-Source-Url": source_url,
        "X-Pinterest-Pws-Handler": "www/search/[scope].js",
        "X-Pinterest-Appstate": "active",
        "X-App-Version": "b85ab6b",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Ch-Ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"macOS"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    })

    resp = pinterest.session.get(url, headers=headers, proxies=pinterest.proxies)
    if resp.status_code in (401, 403):
        logger.warning(f"[Cookie] ⚠️ Cookie hết hạn (HTTP {resp.status_code}) — đang tự động lấy lại...")
        if _auto_refresh_cookies():
            resp = pinterest.session.get(url, headers=headers, proxies=pinterest.proxies)
        if resp.status_code in (401, 403):
            logger.error("[Cookie] ❌ Refresh cookie thất bại")
            return []
    if resp.status_code != 200:
        logger.warning(f"[Cookie] HTTP {resp.status_code}")
        return []

    raw_results = resp.json().get("resource_response", {}).get("data", {}).get("results", [])
    items = []
    for r in raw_results:
        # Bỏ qua video và story pin — không phải ảnh tĩnh
        if r.get("is_video") or r.get("type") in ("story", "story_pin"):
            continue
        images = r.get("images") or {}
        orig = images.get("orig") or {}
        img_url = orig.get("url", "")
        if not img_url:
            continue
        w = orig.get("width", 0) or 0
        h = orig.get("height", 0) or 0
        title   = (r.get("title") or r.get("grid_title") or "").strip()
        caption = (r.get("description") or r.get("alt_text") or "").strip()
        items.append({"url": img_url, "title": title, "caption": caption, "width": w, "height": h})
    # Ưu tiên ảnh dọc (portrait) — ảnh người/gái gần như luôn dọc
    items.sort(key=lambda x: x["height"] / max(x["width"], 1), reverse=True)
    return items


def get_pinterest_image(category: str) -> tuple[str, str, str] | None:
    """Trả về (url, title, caption) ảnh Pinterest có người; None nếu không tìm được."""

    # Pool động: shuffle toàn bộ keyword, thử lần lượt đến khi ra ảnh hoặc hết
    cat_kws = KEYWORDS.get(category, KEYWORDS["girl"])
    pool = list(cat_kws)  # bản sao để pop, không ảnh hưởng KEYWORDS gốc
    random.shuffle(pool)

    tried = 0
    MAX_TRY = min(6, len(pool))  # thử tối đa 6 keyword mỗi lần gọi

    while pool and tried < MAX_TRY:
        kw = pool.pop(0)
        tried += 1
        try:
            logger.debug(f"[Pinterest] Tìm '{kw}' (category={category}, lần {tried})...")
            items = _search_with_meta(kw, FETCH_COUNT)
            logger.debug(f"[Pinterest] '{kw}' -> {len(items)} ảnh")

            if not items:
                # Xóa keyword chết khỏi database, giữ ít nhất 3 keyword/category
                live_kws = KEYWORDS.get(category, [])
                if kw in live_kws and len(live_kws) > 3:
                    live_kws.remove(kw)
                    save_keywords(KEYWORDS)
                    logger.info(f"[Pinterest] 🗑️ Đã xóa keyword hết kết quả: '{kw}'")
                continue

            random.shuffle(items)
            pool10 = items[:10]
            random.shuffle(pool10)
            for item in pool10:
                chosen = item["url"].replace("/236x/", "/originals/")
                if has_person(chosen):
                    logger.info(f"[Pinterest] ✅ Chọn ảnh '{kw}': {chosen}")
                    return chosen, item["title"], item["caption"]
            logger.warning(f"[Pinterest] ⚠️ Không có ảnh người cho '{kw}', thử keyword tiếp...")
        except Exception as e:
            logger.warning(f"[Pinterest] Lỗi tìm '{kw}': {e}")

    logger.warning(f"[Pinterest] ❌ Không tìm được ảnh cho category={category}")
    return None


_FIXED_CMDS = [
    ("🎲", "random", "Để em chọn cho sếp~"),
    ("🔍", "s", "Tìm theo ý sếp <i>&lt;từ khóa&gt;</i>"),
    ("💡", "help", "Hướng dẫn"),
    ("🔧", "admin", "Quản lý từ khóa & category"),
]

_CAT_EMOJI = {
    "girl": "📸", "sexy": "🔥", "bikini": "👙",
    "cosplay": "🎭", "asian": "🌸", "onlyfans": "💎",
}


def _build_help_text(html: bool = False) -> str:
    lines = []
    for cat in KEYWORDS:
        emoji = _CAT_EMOJI.get(cat, "📷")
        lines.append(f"/{cat} - {emoji} {cat.capitalize()}")
    for emoji, cmd, desc in _FIXED_CMDS:
        lines.append(f"/{cmd} - {emoji} {desc}")
    body = "\n".join(lines)
    if html:
        return (
            "🗂 <b>Thư ký riêng của sếp — Phục vụ 24/7</b> 💋\n\n"
            + body
            + "\n\n📌 <i>Sếp cứ ra lệnh, em phục vụ~ 😘</i>"
        )
    return (
        "👋 Xin chào sếp~ Em là thư ký riêng của sếp đây ạ!\n"
        "Sếp muốn xem gì, em phục vụ liền~ 😘\n\n"
        + body
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(_build_help_text(html=False))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(_build_help_text(html=True), parse_mode="HTML")


async def send_pinterest_photo(
    update: Update, category: str, fallback_title: str, fallback_caption: str, loading_text: str
) -> None:
    """Helper gửi ảnh từ Pinterest. Ưu tiên title/caption thật từ Pinterest."""
    user = update.effective_user
    chat = update.effective_chat
    logger.info(f"[CMD] @{user.username}({user.id}) chat={chat.title or chat.id} -> /{category}")
    msg = await update.message.reply_text(loading_text)
    MAX_RETRY = 3
    for attempt in range(1, MAX_RETRY + 1):
        try:
            if attempt > 1:
                retry_text = get_response(category, "loading")
                await msg.edit_text(f"🔄 Thử lần {attempt}... {retry_text}")
            result = get_pinterest_image(category)
            if not result:
                if attempt < MAX_RETRY:
                    logger.warning(f"[CMD] Lần {attempt} không ra ảnh, thử lại...")
                    continue
                await msg.edit_text("❌ Không tìm được ảnh, thử lại sau nhé!")
                return
            url, pin_title, pin_caption = result
            logger.info(f"[CMD] Gửi ảnh cho @{user.username} (lần {attempt}): {url}")

            title   = pin_title   or fallback_title
            caption = pin_caption or fallback_caption

            parts = []
            if title:
                parts.append(f"<b>{title}</b>")
            if caption:
                parts.append(caption)
            full_caption = "\n".join(parts)

            await update.message.reply_photo(photo=url, caption=full_caption, parse_mode="HTML")
            await msg.delete()
            return
        except Exception as e:
            logger.error(f"[CMD] Lỗi gửi ảnh lần {attempt}: {e}", exc_info=True)
            if attempt < MAX_RETRY:
                continue
            await msg.edit_text("❌ Không lấy được ảnh, thử lại sau nhé!")


async def girl(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_pinterest_photo(update, "girl", "Gái xinh", get_response("girl", "caption"), get_response("girl", "loading"))


async def sexy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_pinterest_photo(update, "sexy", "Sexy", get_response("sexy", "caption"), get_response("sexy", "loading"))


async def bikini(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_pinterest_photo(update, "bikini", "Bikini", get_response("bikini", "caption"), get_response("bikini", "loading"))


async def cosplay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_pinterest_photo(update, "cosplay", "Cosplay", get_response("cosplay", "caption"), get_response("cosplay", "loading"))


async def asian(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_pinterest_photo(update, "asian", "Asian girl", get_response("asian", "caption"), get_response("asian", "loading"))


async def onlyfans(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_pinterest_photo(update, "onlyfans", "Gợi cảm", get_response("onlyfans", "caption"), get_response("onlyfans", "loading"))


async def random_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    category = random.choice(list(KEYWORDS.keys()))
    await send_pinterest_photo(update, category, "Random", get_response("random", "caption"), get_response("random", "loading"))


async def s_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tìm ảnh theo từ khóa tùy chỉnh."""
    user = update.effective_user
    if not context.args:
        await update.message.reply_text(
            "🔍 <b>Cách dùng:</b>\n"
            "<code>/s gái xinh bikini</code>\n"
            "<code>/s kpop idol</code>\n"
            "<code>/s cosplay anime</code>",
            parse_mode="HTML",
        )
        return

    keyword = " ".join(context.args)
    logger.info(f"[Search] @{user.username} tìm: '{keyword}'")
    msg = await update.message.reply_text(f"🔍 Đang tìm '{keyword}'...")

    try:
        items = _search_with_meta(keyword, FETCH_COUNT)
        logger.debug(f"[Search] '{keyword}' -> {len(items)} ảnh")
        if not items:
            await msg.edit_text(f"❌ Không tìm thấy ảnh cho '{keyword}', thử từ khóa khác!")
            return

        # Thử person detection trên top 3, fallback về top 1 nếu không có
        chosen_item = None
        for item in items[:3]:
            url_candidate = item["url"].replace("/236x/", "/originals/")
            if has_person(url_candidate):
                chosen_item = {**item, "url": url_candidate}
                break
        if not chosen_item:
            chosen_item = {**items[0], "url": items[0]["url"].replace("/236x/", "/originals/")}

        logger.info(f"[Search] Gửi ảnh cho @{user.username}: {chosen_item['url']}")
        parts = [f"🔍 Kết quả cho: <b>{keyword}</b>"]
        if chosen_item.get("title"):
            parts.append(f"<b>{chosen_item['title']}</b>")
        if chosen_item.get("caption"):
            parts.append(chosen_item["caption"])
        await update.message.reply_photo(
            photo=chosen_item["url"],
            caption="\n".join(parts),
            parse_mode="HTML",
        )
        await msg.delete()
    except Exception as e:
        logger.error(f"[Search] Lỗi: {e}", exc_info=True)
        await msg.edit_text("❌ Lỗi khi tìm ảnh, thử lại sau!")


# ============ ADMIN QUẢN LÝ TỪ KHÓA ============

def is_admin(user_id: int) -> bool:
    return True


def _build_category_menu() -> InlineKeyboardMarkup:
    keyboard, row = [], []
    for cat in KEYWORDS:
        count = len(KEYWORDS[cat])
        row.append(InlineKeyboardButton(f"📂 {cat} ({count})", callback_data=f"cat:{cat}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([
        InlineKeyboardButton("➕ Thêm category", callback_data="addcat_prompt"),
        InlineKeyboardButton("🗑 Xóa category", callback_data="delcat_menu"),
    ])
    return InlineKeyboardMarkup(keyboard)


def _build_delcat_menu() -> InlineKeyboardMarkup:
    keyboard = []
    for cat in KEYWORDS:
        keyboard.append([InlineKeyboardButton(f"🗑 {cat} ({len(KEYWORDS[cat])} kw)", callback_data=f"delcat:{cat}")])
    keyboard.append([InlineKeyboardButton("⬅️ Quay lại", callback_data="admin_back")])
    return InlineKeyboardMarkup(keyboard)


def _build_keyword_menu(category: str) -> InlineKeyboardMarkup:
    kws = KEYWORDS.get(category, [])
    keyboard = []
    for i, kw in enumerate(kws):
        keyboard.append([
            InlineKeyboardButton(f"{i + 1}. {kw}", callback_data="noop"),
            InlineKeyboardButton("❌", callback_data=f"del:{category}:{i}"),
        ])
    keyboard.append([
        InlineKeyboardButton("⬅️ Quay lại", callback_data="admin_back"),
        InlineKeyboardButton("➕ Thêm", callback_data=f"add_prompt:{category}"),
    ])
    return InlineKeyboardMarkup(keyboard)


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "💋 <b>Khu vực riêng của sếp đây ạ~</b>\n\n"
        "🔐 Em đã chuẩn bị sẵn bảng điều khiển cho sếp rồi, sếp vào đây nha:\n\n"
        "👉 <a href=\"http://100.112.48.26:8080/\">http://100.112.48.26:8080/</a>\n\n"
        "<i>Sếp muốn thêm danh mục hay từ khóa gì, em phục vụ tận nơi ạ~ 😘</i>",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    data = query.data

    if data == "admin_back":
        await query.edit_message_text(
            "🔧 <b>Quản lý từ khóa Pinterest</b>\nChọn category:",
            reply_markup=_build_category_menu(),
            parse_mode="HTML",
        )

    elif data.startswith("cat:"):
        category = data[4:]
        kws = KEYWORDS.get(category, [])
        await query.edit_message_text(
            f"📂 <b>{category}</b> — {len(kws)} từ khóa\n"
            f"<i>Thêm: /addkw {category} &lt;từ khóa&gt;</i>",
            reply_markup=_build_keyword_menu(category),
            parse_mode="HTML",
        )

    elif data.startswith("del:"):
        _, category, idx_str = data.split(":", 2)
        idx = int(idx_str)
        cat_kws = KEYWORDS.get(category, [])
        if 0 <= idx < len(cat_kws):
            removed = cat_kws.pop(idx)
            save_keywords(KEYWORDS)
            await query.answer(f"✅ Đã xóa: {removed}", show_alert=True)
        await query.edit_message_text(
            f"📂 <b>{category}</b> — {len(KEYWORDS.get(category, []))} từ khóa\n"
            f"<i>Thêm: /addkw {category} &lt;từ khóa&gt;</i>",
            reply_markup=_build_keyword_menu(category),
            parse_mode="HTML",
        )

    elif data.startswith("add_prompt:"):
        category = data[11:]
        await query.message.reply_text(
            f"➕ Nhập từ khóa mới cho <b>{category}</b>:",
            reply_markup=ForceReply(selective=True, input_field_placeholder="từ khóa..."),
            parse_mode="HTML",
        )
        context.user_data["pending_action"] = "addkw"
        context.user_data["pending_category"] = category

    elif data == "addcat_prompt":
        await query.message.reply_text(
            "➕ Nhập tên category mới:",
            reply_markup=ForceReply(selective=True, input_field_placeholder="tên category..."),
        )
        context.user_data["pending_action"] = "addcat"

    elif data == "delcat_menu":
        await query.edit_message_text(
            "🗑 <b>Xóa category</b>\nChọn category muốn xóa:",
            reply_markup=_build_delcat_menu(),
            parse_mode="HTML",
        )

    elif data.startswith("delcat:"):
        category = data[7:]
        await query.edit_message_text(
            f"⚠️ Xác nhận xóa category <b>{category}</b> và toàn bộ {len(KEYWORDS.get(category, []))} từ khóa?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Xác nhận xóa", callback_data=f"delcat_confirm:{category}")],
                [InlineKeyboardButton("⬅️ Hủy", callback_data="delcat_menu")],
            ]),
            parse_mode="HTML",
        )

    elif data.startswith("delcat_confirm:"):
        category = data[15:]
        if category in KEYWORDS:
            del KEYWORDS[category]
            save_keywords(KEYWORDS)
            await query.answer(f"✅ Đã xóa category: {category}", show_alert=True)
        await query.edit_message_text(
            "🔧 <b>Quản lý từ khóa Pinterest</b>\nChọn category:",
            reply_markup=_build_category_menu(),
            parse_mode="HTML",
        )


async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý reply từ ForceReply trong admin menu."""
    action = context.user_data.pop("pending_action", None)
    if not action:
        return

    text = update.message.text.strip()

    if action == "addcat":
        name = text.lower()
        if name in KEYWORDS:
            await update.message.reply_text(f"⚠️ Category <code>{name}</code> đã tồn tại.", parse_mode="HTML")
            return
        KEYWORDS[name] = []
        save_keywords(KEYWORDS)
        await update.message.reply_text(
            f"✅ Đã tạo category <b>{name}</b>. Thêm từ khóa qua /admin nhé!",
            parse_mode="HTML",
        )

    elif action == "addkw":
        category = context.user_data.pop("pending_category", None)
        if not category:
            return
        if category not in KEYWORDS:
            await update.message.reply_text(f"❌ Category <code>{category}</code> không tồn tại.", parse_mode="HTML")
            return
        if text in KEYWORDS[category]:
            await update.message.reply_text(f"⚠️ Từ khóa <code>{text}</code> đã tồn tại.", parse_mode="HTML")
            return
        KEYWORDS[category].append(text)
        save_keywords(KEYWORDS)
        await update.message.reply_text(
            f"✅ Đã thêm <code>{text}</code> vào category <b>{category}</b>",
            parse_mode="HTML",
        )


async def addcat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Thêm category mới: /addcat <tên>"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Bạn không có quyền.")
        return
    if not context.args:
        await update.message.reply_text(
            "❌ <b>Cách dùng:</b> <code>/addcat &lt;tên category&gt;</code>",
            parse_mode="HTML",
        )
        return
    name = context.args[0].lower()
    if name in KEYWORDS:
        await update.message.reply_text(f"⚠️ Category <code>{name}</code> đã tồn tại.", parse_mode="HTML")
        return
    KEYWORDS[name] = []
    save_keywords(KEYWORDS)
    await update.message.reply_text(
        f"✅ Đã tạo category <b>{name}</b>. Thêm từ khóa: <code>/addkw {name} từ khóa</code>\n\n"
        + _build_help_text(html=True),
        parse_mode="HTML",
    )


async def addkw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Thêm từ khóa: /addkw <category> <từ khóa>"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Bạn không có quyền.")
        return
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ <b>Cách dùng:</b> <code>/addkw &lt;category&gt; &lt;từ khóa&gt;</code>\n"
            "Ví dụ: <code>/addkw girl gái xinh áo dài</code>",
            parse_mode="HTML",
        )
        return
    category = context.args[0].lower()
    keyword = " ".join(context.args[1:])
    if category not in KEYWORDS:
        cats = ", ".join(KEYWORDS.keys())
        await update.message.reply_text(f"❌ Category không tồn tại.\nCác category: <code>{cats}</code>", parse_mode="HTML")
        return
    if keyword in KEYWORDS[category]:
        await update.message.reply_text(f"⚠️ Từ khóa <code>{keyword}</code> đã tồn tại.", parse_mode="HTML")
        return
    KEYWORDS[category].append(keyword)
    save_keywords(KEYWORDS)
    await update.message.reply_text(
        f"✅ Đã thêm <code>{keyword}</code> vào category <b>{category}</b>",
        parse_mode="HTML",
    )


async def _set_commands(app: Application) -> None:
    """Đăng ký danh sách lệnh để Telegram hiện gợi ý khi gõ /."""
    commands = []
    for cat in KEYWORDS:
        emoji = _CAT_EMOJI.get(cat, "📷")
        commands.append(BotCommand(cat, f"{emoji} {cat.capitalize()}"))
    commands += [
        BotCommand("random", "🎲 Để em chọn cho sếp~"),
        BotCommand("s", "🔍 Tìm theo từ khóa"),
        BotCommand("help", "💡 Hướng dẫn"),
        BotCommand("admin", "🔧 Quản lý từ khóa & category"),
    ]
    await app.bot.set_my_commands(commands)
    logger.info(f"[Bot] Đã đăng ký {len(commands)} lệnh")


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("Chưa cấu hình TELEGRAM_BOT_TOKEN trong file .env")

    app = Application.builder().token(token).post_init(_set_commands).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_reply))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("girl", girl))
    app.add_handler(CommandHandler("sexy", sexy))
    app.add_handler(CommandHandler("bikini", bikini))
    app.add_handler(CommandHandler("cosplay", cosplay))
    app.add_handler(CommandHandler("asian", asian))
    app.add_handler(CommandHandler("onlyfans", onlyfans))
    app.add_handler(CommandHandler("random", random_all))
    app.add_handler(CommandHandler("s", s_command))
    app.add_handler(CommandHandler("search", s_command))  # alias backward compat
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("addkw", addkw))
    app.add_handler(CommandHandler("addcat", addcat))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^(cat:|del:|add_prompt:|admin_back|noop|addcat_prompt|delcat_menu|delcat:|delcat_confirm:)"))

    logger.info("🚀 Bot đang chạy...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
