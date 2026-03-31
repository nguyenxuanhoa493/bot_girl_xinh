# 🤖 Bot Gái Xinh - Telegram

Bot Telegram gửi ảnh gái xinh ngẫu nhiên khi dùng lệnh `/girl`.

## Cài đặt

```bash
# 1. Tạo môi trường ảo
python3 -m venv venv
source venv/bin/activate

# 2. Cài thư viện
pip install -r requirements.txt

# 3. Tạo file .env và điền token
cp .env.example .env
# Sửa file .env, thêm token bot từ @BotFather
```

## Lấy Bot Token

1. Mở Telegram, tìm **@BotFather**
2. Gửi `/newbot` và làm theo hướng dẫn
3. Copy token và dán vào file `.env`

## Chạy bot

```bash
python bot.py
```

## Lệnh bot

| Lệnh    | Mô tả                        |
| -------- | ----------------------------- |
| `/start` | Khởi động bot                 |
| `/girl`  | Nhận ảnh gái xinh ngẫu nhiên  |
| `/help`  | Xem hướng dẫn                 |

## Thêm bot vào nhóm

1. Mở **@BotFather** → `/mybots` → chọn bot → **Bot Settings** → **Allow Groups** → **Turn on**
2. Mở nhóm Telegram → **Add Members** → tìm tên bot → thêm vào
3. Gõ `/girl` trong nhóm để dùng
