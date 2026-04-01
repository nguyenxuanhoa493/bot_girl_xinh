import os
import sqlite3
from pathlib import Path

from flask import Flask, render_template_string, request, redirect, url_for, flash
from dotenv import load_dotenv

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
  <form method="post" action="{{ url_for('add_keyword', name=name) }}" class="form-row" style="margin-bottom:20px">
    <input type="text" name="keyword" placeholder="Nhập từ khóa mới..." required>
    <button class="btn btn-primary" type="submit">+ Thêm</button>
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
    kw = request.form.get("keyword", "").strip()
    if not kw:
        flash("Từ khóa không được để trống.", "error")
        return redirect(url_for("category", name=name))
    with get_db() as conn:
        try:
            conn.execute(
                "INSERT INTO keywords (category, keyword) VALUES (?, ?)", (name, kw)
            )
            conn.commit()
            flash(f"Đã thêm '{kw}'.", "success")
        except sqlite3.IntegrityError:
            flash(f"Từ khóa '{kw}' đã tồn tại.", "error")
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


# ============ MAIN ============

if __name__ == "__main__":
    port = int(os.getenv("ADMIN_PORT", 8080))
    print(f"🌐 Web admin chạy tại http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
