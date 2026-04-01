import os
import sqlite3
import sys
from pathlib import Path

from flask import Flask, render_template_string, request, redirect, url_for, flash, jsonify
from dotenv import load_dotenv

# Import hàm tìm kiếm từ bot.py
sys.path.insert(0, str(Path(__file__).parent))
try:
    from bot import _search_with_meta, apply_pinterest_cookies
    _SEARCH_AVAILABLE = True
except Exception as _e:
    _SEARCH_AVAILABLE = False
    _SEARCH_ERROR = str(_e)

try:
    from get_cookie import get_cookies as _selenium_get_cookies
    _SELENIUM_AVAILABLE = True
except Exception:
    _SELENIUM_AVAILABLE = False

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-me-in-production")

KEYWORDS_DB = Path(__file__).parent / "data" / "keywords.db"

# ============ DB HELPERS ============

def get_db() -> sqlite3.Connection:
    KEYWORDS_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(KEYWORDS_DB)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS keywords "
        "(category TEXT NOT NULL, keyword TEXT NOT NULL, "
        "PRIMARY KEY (category, keyword))"
    )
    conn.commit()
    return conn


def load_all() -> dict[str, list[str]]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT category, keyword FROM keywords ORDER BY category, rowid"
        ).fetchall()
    result: dict[str, list[str]] = {}
    for cat, kw in rows:
        result.setdefault(cat, []).append(kw)
    return result


# ============ TEMPLATES ============

BASE_HTML = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bot Admin</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:        #080b10;
    --surface:   #0e1219;
    --surface2:  #151b25;
    --border:    #1e2736;
    --border2:   #253045;
    --accent:    #7c6aff;
    --accent2:   #6355e0;
    --pink:      #e040fb;
    --text:      #d4dae8;
    --muted:     #5a6478;
    --success-bg:#0d2218; --success-fg:#4ade80; --success-bd:#1a4030;
    --danger-bg: #220d0d; --danger-fg: #f87171; --danger-bd:  #401a1a;
  }

  body {
    font-family: 'Inter', -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    font-size: 14px;
    line-height: 1.6;
  }

  /* ── Navbar ── */
  .navbar {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 0 28px;
    height: 56px;
    display: flex;
    align-items: center;
    gap: 12px;
    position: sticky;
    top: 0;
    z-index: 100;
    backdrop-filter: blur(8px);
  }
  .navbar-logo {
    font-size: 20px;
    line-height: 1;
  }
  .navbar h1 {
    font-size: 15px;
    font-weight: 600;
    background: linear-gradient(135deg, var(--accent) 0%, var(--pink) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -.3px;
  }
  .navbar-spacer { flex: 1; }
  .navbar-link {
    color: var(--muted);
    text-decoration: none;
    font-size: 13px;
    padding: 5px 10px;
    border-radius: 6px;
    border: 1px solid var(--border);
    transition: all .15s;
  }
  .navbar-link:hover { color: var(--text); border-color: var(--border2); background: var(--surface2); }
  .navbar-link.active { color: var(--accent); border-color: rgba(124,106,255,.4); background: rgba(124,106,255,.08); }

  /* ── Layout ── */
  .container {
    max-width: 1000px;
    margin: 0 auto;
    padding: 32px 20px 60px;
  }

  /* ── Alerts ── */
  .alert {
    padding: 11px 16px;
    border-radius: 8px;
    margin-bottom: 18px;
    font-size: 13.5px;
    display: flex;
    align-items: center;
    gap: 8px;
    border: 1px solid;
    animation: slideIn .2s ease;
  }
  @keyframes slideIn { from { opacity:0; transform:translateY(-6px); } to { opacity:1; transform:none; } }
  .alert-success { background: var(--success-bg); color: var(--success-fg); border-color: var(--success-bd); }
  .alert-error   { background: var(--danger-bg);  color: var(--danger-fg);  border-color: var(--danger-bd); }

  /* ── Card ── */
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 20px;
  }

  /* ── Top bar ── */
  .top-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
    flex-wrap: wrap;
    gap: 10px;
  }
  .top-bar-title {
    font-size: 16px;
    font-weight: 700;
    color: #fff;
    display: flex;
    align-items: center;
    gap: 10px;
  }

  /* ── Category grid ── */
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 12px;
  }
  .cat-card {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 18px;
    text-decoration: none;
    color: inherit;
    transition: border-color .15s, transform .15s, box-shadow .15s;
    display: block;
    position: relative;
    overflow: hidden;
  }
  .cat-card::before {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, rgba(124,106,255,.07) 0%, transparent 60%);
    opacity: 0;
    transition: opacity .2s;
  }
  .cat-card:hover { border-color: var(--accent); transform: translateY(-2px); box-shadow: 0 8px 24px rgba(124,106,255,.15); }
  .cat-card:hover::before { opacity: 1; }
  .cat-card .name { font-weight: 600; font-size: 14px; color: #fff; }
  .cat-card .count {
    font-size: 12px;
    color: var(--muted);
    margin-top: 5px;
    display: flex;
    align-items: center;
    gap: 4px;
  }

  /* ── Badge ── */
  .badge {
    display: inline-flex;
    align-items: center;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 500;
    background: rgba(124,106,255,.15);
    color: var(--accent);
    border: 1px solid rgba(124,106,255,.25);
  }

  /* ── Buttons ── */
  .btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    border-radius: 8px;
    border: none;
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    font-family: inherit;
    text-decoration: none;
    transition: all .15s;
    white-space: nowrap;
  }
  .btn-primary {
    background: linear-gradient(135deg, var(--accent) 0%, var(--accent2) 100%);
    color: #fff;
    box-shadow: 0 2px 12px rgba(124,106,255,.3);
  }
  .btn-primary:hover { filter: brightness(1.12); box-shadow: 0 4px 18px rgba(124,106,255,.4); }
  .btn-danger {
    background: rgba(239,68,68,.12);
    color: #f87171;
    border: 1px solid rgba(239,68,68,.25);
  }
  .btn-danger:hover { background: rgba(239,68,68,.22); }
  .btn-secondary {
    background: var(--surface2);
    color: var(--text);
    border: 1px solid var(--border2);
  }
  .btn-secondary:hover { background: var(--border); }
  .btn-sm { padding: 5px 12px; font-size: 12px; border-radius: 6px; }
  .btn-ghost {
    background: transparent;
    color: var(--muted);
    border: 1px solid var(--border);
  }
  .btn-ghost:hover { background: var(--surface2); color: var(--text); }

  /* ── Inputs ── */
  input[type=text] {
    background: var(--surface2);
    border: 1px solid var(--border2);
    color: var(--text);
    padding: 9px 14px;
    border-radius: 8px;
    font-size: 13.5px;
    font-family: inherit;
    width: 100%;
    transition: border-color .15s, box-shadow .15s;
  }
  input[type=text]:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(124,106,255,.15);
  }
  input[type=text]::placeholder { color: var(--muted); }

  textarea {
    background: var(--surface2);
    border: 1px solid var(--border2);
    color: var(--text);
    padding: 9px 14px;
    border-radius: 8px;
    font-size: 13.5px;
    font-family: inherit;
    width: 100%;
    resize: vertical;
    min-height: 80px;
    transition: border-color .15s, box-shadow .15s;
  }
  textarea:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(124,106,255,.15);
  }
  textarea::placeholder { color: var(--muted); }

  /* ── Form row ── */
  .add-bar {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px;
    margin-bottom: 20px;
    display: none;
  }
  .add-bar.open { display: block; animation: slideIn .15s ease; }
  .form-row { display: flex; gap: 8px; }
  .form-row input { flex: 1; }

  /* ── Table ── */
  .table-wrap { overflow-x: auto; border-radius: 10px; border: 1px solid var(--border); }
  table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
  thead { background: var(--surface2); }
  th { text-align: left; padding: 11px 16px; color: var(--muted); font-weight: 500; font-size: 12px; text-transform: uppercase; letter-spacing: .5px; }
  td { padding: 11px 16px; border-top: 1px solid var(--border); }
  tbody tr { transition: background .1s; }
  tbody tr:hover td { background: var(--surface2); }
  td.num { color: var(--muted); width: 48px; }
  td.kw { color: var(--text); }
  td.action { text-align: right; width: 80px; }

  /* ── Back link ── */
  .back {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: var(--muted);
    text-decoration: none;
    font-size: 13px;
    margin-bottom: 18px;
    padding: 6px 12px;
    border-radius: 7px;
    border: 1px solid var(--border);
    background: var(--surface2);
    transition: all .15s;
  }
  .back:hover { color: var(--text); border-color: var(--border2); }

  /* ── Empty state ── */
  .empty { padding: 40px 16px; text-align: center; color: var(--muted); font-size: 13px; }
</style>
</head>
<body>
<div class="navbar">
  <span class="navbar-logo">🤖</span>
  <h1>Bot Admin</h1>
  <div class="navbar-spacer"></div>
  <a class="navbar-link" href="/">📂 Từ khóa</a>
  <a class="navbar-link" href="/search">🔍 Test tìm kiếm</a>
  <a class="navbar-link" href="/cookies">🍪 Cookie</a>
</div>
<div class="container">
  {% with msgs = get_flashed_messages(with_categories=true) %}
    {% for cat, msg in msgs %}
    <div class="alert alert-{{ cat }}">{{ msg }}</div>
    {% endfor %}
  {% endwith %}
  {% block content %}{% endblock %}
</div>
</body>
</html>
"""

INDEX_HTML = BASE_HTML.replace("{% block content %}{% endblock %}", """
<div class="card">
  <div class="top-bar">
    <div class="top-bar-title">📂 Danh mục <span class="badge">{{ data|length }}</span></div>
    <button class="btn btn-primary btn-sm" onclick="this.closest('.card').querySelector('.add-bar').classList.toggle('open')">+ Thêm danh mục</button>
  </div>
  <div class="add-bar">
    <form method="post" action="{{ url_for('add_category') }}" class="form-row">
      <input type="text" name="name" placeholder="Nhập tên danh mục..." required autofocus>
      <button class="btn btn-primary" type="submit">Thêm</button>
      <button class="btn btn-secondary" type="button" onclick="this.closest('.add-bar').classList.remove('open')">Hủy</button>
    </form>
  </div>
  <div class="grid">
    {% for cat, kws in data.items() %}
    <a class="cat-card" href="{{ url_for('category', name=cat) }}">
      <div class="name">{{ cat }}</div>
      <div class="count">🔑 {{ kws|length }} từ khóa</div>
    </a>
    {% else %}
    <div class="empty">Chưa có danh mục nào. Hãy tạo danh mục đầu tiên!</div>
    {% endfor %}
  </div>
</div>
""")

CATEGORY_HTML = BASE_HTML.replace("{% block content %}{% endblock %}", """
<a class="back" href="{{ url_for('index') }}">← Tất cả danh mục</a>
<div class="card">
  <div class="top-bar">
    <div class="top-bar-title">📂 {{ name }} <span class="badge">{{ keywords|length }} từ khóa</span></div>
    <form method="post" action="{{ url_for('delete_category', name=name) }}"
          onsubmit="return confirm('Xóa toàn bộ danh mục {{ name }}?')">
      <button class="btn btn-danger btn-sm" type="submit">🗑 Xóa danh mục</button>
    </form>
  </div>
  <form method="post" action="{{ url_for('add_keyword', name=name) }}" style="margin-bottom:20px">
    <textarea name="keywords" placeholder="Nhập từ khóa (mỗi dòng một từ, hoặc cách nhau bằng dấu phẩy)..."></textarea>
    <div style="display:flex;gap:8px;margin-top:8px">
      <button class="btn btn-primary" type="submit">+ Thêm</button>
    </div>
  </form>
  <div class="table-wrap">
  <table>
    <thead>
      <tr><th>#</th><th>Từ khóa</th><th></th></tr>
    </thead>
    <tbody>
      {% for kw in keywords %}
      <tr>
        <td class="num">{{ loop.index }}</td>
        <td class="kw">{{ kw }}</td>
        <td class="action">
          <form method="post" action="{{ url_for('delete_keyword', name=name) }}" style="display:inline">
            <input type="hidden" name="keyword" value="{{ kw }}">
            <button class="btn btn-danger btn-sm" type="submit">Xóa</button>
          </form>
        </td>
      </tr>
      {% else %}
      <tr><td colspan="3"><div class="empty">Chưa có từ khóa nào</div></td></tr>
      {% endfor %}
    </tbody>
  </table>
  </div>
</div>
""")


SEARCH_HTML = BASE_HTML.replace("{% block content %}{% endblock %}", """
<div class="card">
  <div class="top-bar">
    <div class="top-bar-title">🔍 Test tìm kiếm Pinterest</div>
  </div>
  <form method="get" action="{{ url_for('search_page') }}" style="display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap">
    <input type="text" name="q" value="{{ q|e }}" placeholder="Nhập từ khóa (vd: gái việt xinh)..." autofocus style="flex:1;min-width:200px">
    <select name="rs" style="background:var(--surface2);border:1px solid var(--border2);color:var(--text);padding:9px 12px;border-radius:8px;font-size:13px;font-family:inherit">
      {% for v,label in [('typed','typed — gõ từ từ kết quả phổ biến'),('rs','rs — related search'),('srs','srs — suggested'),('trending','trending')] %}
      <option value="{{ v }}" {% if v == rs_mode %}selected{% endif %}>{{ label }}</option>
      {% endfor %}
    </select>
    <select name="n" style="background:var(--surface2);border:1px solid var(--border2);color:var(--text);padding:9px 12px;border-radius:8px;font-size:13px;font-family:inherit">
      {% for v in [10,20,30,50] %}
      <option value="{{ v }}" {% if v == page_size %}selected{% endif %}>{{ v }} ảnh</option>
      {% endfor %}
    </select>
    <button class="btn btn-primary" type="submit">Tìm</button>
  </form>

  {% if q %}
  <div style="background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:10px 14px;margin-bottom:16px;font-size:12px;color:var(--muted)">
    <b style="color:var(--text)">Debug info:</b>
    &nbsp;query=<code style="color:var(--accent)">{{ q|e }}</code>
    &nbsp;rs=<code style="color:var(--pink)">{{ rs_mode }}</code>
    &nbsp;page_size=<code>{{ page_size }}</code>
    {% if results is not none %}
    &nbsp;→&nbsp;<b style="color:var(--success-fg)">{{ results|length }} kết quả</b>
    &nbsp;(dọc: {{ results|selectattr('height','gt',results|map(attribute='width')|list|first if results else 0)|list|length if results else 0 }})
    {% endif %}
    &nbsp;&mdash;&nbsp;<a href="https://www.pinterest.com/search/pins/?q={{ q|urlencode }}&rs={{ rs_mode }}" target="_blank" style="color:var(--accent)">Mở trên Pinterest ↗</a>
  </div>
  {% endif %}

  {% if error %}
  <div class="alert alert-error">⚠️ {{ error }}</div>
  {% elif q and results is not none %}
  {% if results %}
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px">
    {% for item in results %}
    {% set is_portrait = item.height > item.width %}
    <div style="background:var(--surface2);border:1px solid {% if is_portrait %}rgba(124,106,255,.4){% else %}var(--border){% endif %};border-radius:10px;overflow:hidden;display:flex;flex-direction:column">
      <a href="{{ item.url }}" target="_blank" style="display:block;aspect-ratio:{% if is_portrait %}3/4{% else %}4/3{% endif %};overflow:hidden;background:#0a0d12">
        <img src="{{ item.url }}" alt="" loading="lazy"
          style="width:100%;height:100%;object-fit:cover"
          onerror="this.parentElement.style.display='none'">
      </a>
      <div style="padding:8px 10px;flex:1;display:flex;flex-direction:column;gap:3px">
        {% if item.title %}
        <div style="font-size:11.5px;font-weight:600;color:#fff;line-height:1.3;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical">{{ item.title }}</div>
        {% endif %}
        {% if item.caption %}
        <div style="font-size:11px;color:var(--muted);line-height:1.4;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical">{{ item.caption }}</div>
        {% endif %}
        <div style="font-size:10.5px;color:var(--muted);margin-top:auto;padding-top:4px;display:flex;gap:6px;align-items:center">
          {% if item.width and item.height %}<span>{{ item.width }}×{{ item.height }}</span>{% endif %}
          <span style="color:{% if is_portrait %}var(--accent){% else %}var(--muted){% endif %};font-weight:{% if is_portrait %}600{% else %}400{% endif %}">
            {% if is_portrait %}✔ dọc{% else %}ngang{% endif %}
          </span>
        </div>
      </div>
    </div>
    {% endfor %}
  </div>
  {% else %}
  <div class="empty">Không tìm thấy ảnh nào cho từ khóa này.</div>
  {% endif %}
  {% elif not q %}
  <div class="empty" style="padding:60px 0">
    <div style="font-size:32px;margin-bottom:12px">🔍</div>
    Nhập từ khóa để test kết quả<br>
    <span style="font-size:12px;margin-top:8px;display:block">So sánh các chế độ <b>rs</b> khác nhau để tìm ra cái gần nhất với Pinterest UI</span>
  </div>
  {% endif %}
</div>
""")


import json as _json
import re as _re

COOKIES_FILE = Path(__file__).parent / "data" / "pinterest_cookies.json"

COOKIES_HTML = BASE_HTML.replace("{% block content %}{% endblock %}", """
<div class="card">
  <div class="top-bar">
    <div class="top-bar-title">🔐 Đăng nhập tự động</div>
    <a href="/cookies/status" class="btn btn-secondary btn-sm">🔍 Kiểm tra cookie</a>
  </div>

  {% if not selenium_available %}
  <div class="alert alert-error">⚠️ Chưa cài selenium. Chạy: <code>pip install selenium</code></div>
  {% else %}
  <form method="post" action="/cookies/login" style="margin-bottom:16px">
    <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:end">
      <div style="flex:1;min-width:200px">
        <label style="font-size:12px;color:var(--muted);display:block;margin-bottom:4px">Email</label>
        <input type="text" name="email" value="{{ email }}" placeholder="Pinterest email..." required>
      </div>
      <div style="flex:1;min-width:200px">
        <label style="font-size:12px;color:var(--muted);display:block;margin-bottom:4px">Password</label>
        <input type="text" name="password" value="{{ password }}" placeholder="Pinterest password..." required>
      </div>
      <button class="btn btn-primary" type="submit">🔐 Đăng nhập & Lấy cookie</button>
    </div>
  </form>
  {% endif %}
</div>

<div class="card">
  <div class="top-bar">
    <div class="top-bar-title">🍪 Paste cURL thủ công</div>
  </div>

  <div style="background:var(--surface2);border:1px solid var(--border);border-radius:10px;padding:14px 18px;margin-bottom:20px;font-size:13px;line-height:1.7">
    <b>Cách lấy curl:</b> Mở pinterest.com → F12 → Network → Copy as cURL → Dán bên dưới
  </div>

  <form method="post" action="/cookies/update">
    <div style="margin-bottom:10px">
      <textarea name="curl_cmd" rows="6" style="font-family:monospace;font-size:12px"
        placeholder="curl 'https://www.pinterest.com/...' -b 'csrftoken=...' ..."></textarea>
    </div>
    <button class="btn btn-primary" type="submit">💾 Lưu cookie</button>
  </form>
</div>

{% if current %}
<div class="card">
  <div class="top-bar">
    <div class="top-bar-title">📋 Cookie hiện tại</div>
  </div>
  <div style="background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:14px;font-family:monospace;font-size:11.5px;color:var(--muted);word-break:break-all;white-space:pre-wrap;max-height:300px;overflow-y:auto">{{ current }}</div>
</div>
{% endif %}
""")


def _parse_curl_cookies(curl_cmd: str) -> dict:
    """Parse chuỗi -b '...' từ lệnh curl thành dict."""
    # Tìm -b '...' hoặc --cookie '...'
    m = _re.search(r"""(?:-b|--cookie)\s+['"](.*?)['"](?=\s+-|\s*$|\s*\\)""", curl_cmd, _re.DOTALL)
    if not m:
        # Thử không có quote
        m = _re.search(r"""(?:-b|--cookie)\s+(\S+)""", curl_cmd)
    if not m:
        return {}
    cookie_str = m.group(1).strip()
    cookies = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            cookies[k.strip()] = v.strip()
    return cookies


# ============ ROUTES ============

@app.route("/")
def index():
    data = load_all()
    return render_template_string(INDEX_HTML, data=data)


@app.route("/category/add", methods=["POST"])
def add_category():
    name = request.form.get("name", "").strip().lower()
    if not name:
        flash("Tên danh mục không được để trống.", "error")
        return redirect(url_for("index"))
    with get_db() as conn:
        existing = conn.execute(
            "SELECT 1 FROM keywords WHERE category = ?", (name,)
        ).fetchone()
    if existing:
        flash(f"Danh mục '{name}' đã tồn tại.", "error")
        return redirect(url_for("index"))
    # Insert placeholder rỗng để category tồn tại
    # (category chỉ hiện khi có ít nhất 1 keyword — tạo rỗng bằng cách xử lý ở load_all)
    # thay vào đó lưu vào bảng riêng nếu cần — ở đây chỉ flash success
    flash(f"Đã tạo danh mục '{name}'. Hãy thêm từ khóa.", "success")
    return redirect(url_for("category", name=name))


@app.route("/category/<name>")
def category(name: str):
    data = load_all()
    keywords = data.get(name, [])
    return render_template_string(CATEGORY_HTML, name=name, keywords=keywords)


@app.route("/category/<name>/delete", methods=["POST"])
def delete_category(name: str):
    with get_db() as conn:
        conn.execute("DELETE FROM keywords WHERE category = ?", (name,))
        conn.commit()
    flash(f"Đã xóa danh mục '{name}'.", "success")
    return redirect(url_for("index"))


@app.route("/category/<name>/keyword/add", methods=["POST"])
def add_keyword(name: str):
    raw = request.form.get("keywords", "").strip()
    if not raw:
        flash("Từ khóa không được để trống.", "error")
        return redirect(url_for("category", name=name))
    import re
    parts = re.split(r"[,\n]+", raw)
    kws = [p.strip() for p in parts if p.strip()]
    if not kws:
        flash("Từ khóa không được để trống.", "error")
        return redirect(url_for("category", name=name))
    added, skipped = 0, 0
    with get_db() as conn:
        for kw in kws:
            try:
                conn.execute(
                    "INSERT INTO keywords (category, keyword) VALUES (?, ?)", (name, kw)
                )
                added += 1
            except sqlite3.IntegrityError:
                skipped += 1
        conn.commit()
    if added:
        flash(f"Đã thêm {added} từ khóa." + (f" ({skipped} bị bỏ qua do trùng)" if skipped else ""), "success")
    else:
        flash(f"Tất cả {skipped} từ khóa đã tồn tại.", "error")
    return redirect(url_for("category", name=name))


@app.route("/category/<name>/keyword/delete", methods=["POST"])
def delete_keyword(name: str):
    kw = request.form.get("keyword", "").strip()
    with get_db() as conn:
        conn.execute(
            "DELETE FROM keywords WHERE category = ? AND keyword = ?", (name, kw)
        )
        conn.commit()
    flash(f"Đã xóa '{kw}'.", "success")
    return redirect(url_for("category", name=name))


@app.route("/search")
def search_page():
    q = request.args.get("q", "").strip()
    rs_mode = request.args.get("rs", "typed")
    if rs_mode not in ("typed", "rs", "srs", "trending"):
        rs_mode = "typed"
    try:
        page_size = int(request.args.get("n", 20))
    except ValueError:
        page_size = 20
    page_size = max(1, min(page_size, 50))

    results = None
    error = None
    if q:
        if not _SEARCH_AVAILABLE:
            error = f"Không thể import bot.py: {_SEARCH_ERROR}"
        else:
            try:
                results = _search_with_meta(q, page_size, rs=rs_mode)
            except Exception as e:
                error = str(e)
    return render_template_string(SEARCH_HTML, q=q, results=results, error=error,
                                  page_size=page_size, rs_mode=rs_mode)


@app.route("/cookies")
def cookies_page():
    current = None
    if COOKIES_FILE.exists():
        try:
            current = COOKIES_FILE.read_text(encoding="utf-8")
        except Exception:
            pass
    return render_template_string(
        COOKIES_HTML,
        current=current,
        selenium_available=_SELENIUM_AVAILABLE,
        email=os.getenv("PINTEREST_EMAIL", ""),
        password=os.getenv("PINTEREST_PASSWORD", ""),
    )


@app.route("/cookies/login", methods=["POST"])
def cookies_login():
    if not _SELENIUM_AVAILABLE:
        flash("Chưa cài selenium.", "error")
        return redirect(url_for("cookies_page"))

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()
    if not email or not password:
        flash("Cần nhập email và password.", "error")
        return redirect(url_for("cookies_page"))

    try:
        cookie_dict = _selenium_get_cookies(email, password)
    except Exception as e:
        flash(f"❌ Đăng nhập thất bại: {e}", "error")
        return redirect(url_for("cookies_page"))

    COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    COOKIES_FILE.write_text(_json.dumps(cookie_dict, ensure_ascii=False, indent=2), encoding="utf-8")

    if _SEARCH_AVAILABLE:
        try:
            apply_pinterest_cookies()
            flash(f"✅ Đăng nhập thành công! Đã lưu & reload {len(cookie_dict)} cookies.", "success")
        except Exception:
            flash(f"✅ Đã lưu {len(cookie_dict)} cookies. Restart bot để áp dụng.", "success")
    else:
        flash(f"✅ Đã lưu {len(cookie_dict)} cookies.", "success")
    return redirect(url_for("cookies_page"))


@app.route("/cookies/update", methods=["POST"])
def cookies_update():
    curl_cmd = request.form.get("curl_cmd", "")
    if not curl_cmd.strip():
        flash("Vui lòng paste lệnh curl.", "error")
        return redirect(url_for("cookies_page"))

    cookies = _parse_curl_cookies(curl_cmd)
    if not cookies:
        flash("⚠️ Không phân tích được cookie từ curl. Kiểm tra lại.", "error")
        return redirect(url_for("cookies_page"))

    # Kiểm tra có _auth=1 không (cookie chưa đăng nhập thì vô dụng)
    if cookies.get("_auth") != "1":
        flash("⚠️ Cookie không có _auth=1 — cần đăng nhập Pinterest trước.", "error")
        return redirect(url_for("cookies_page"))

    COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    COOKIES_FILE.write_text(_json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")

    # Reload bot session nếu import được
    if _SEARCH_AVAILABLE:
        try:
            apply_pinterest_cookies()
            flash(f"✅ Đã lưu và reload {len(cookies)} cookie vào bot ngay lập tức.", "success")
        except Exception as e:
            flash(f"✅ Đã lưu {len(cookies)} cookie. Bot sẽ dùng khi khởi động lại. ({e})", "success")
    else:
        flash(f"✅ Đã lưu {len(cookies)} cookie vào file.", "success")
    return redirect(url_for("cookies_page"))


@app.route("/cookies/status")
def cookies_status():
    if not _SEARCH_AVAILABLE:
        flash(f"Không thể import bot.py: {_SEARCH_ERROR}", "error")
        return redirect(url_for("cookies_page"))
    try:
        results = _search_with_meta("girl", 1)
        if results:
            flash("✅ Cookie hợp lệ! API Pinterest trả về kết quả.", "success")
        else:
            flash("⚠️ Cookie có vẻ hết hạn — API trả về 0 kết quả.", "error")
    except Exception as e:
        flash(f"❌ Lỗi kiểm tra: {e}", "error")
    return redirect(url_for("cookies_page"))


# ============ MAIN ============

if __name__ == "__main__":
    port = int(os.getenv("ADMIN_PORT", 8080))
    print(f"🌐 Web admin chạy tại http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
