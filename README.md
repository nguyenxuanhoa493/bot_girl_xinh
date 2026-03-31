# 🤖 Bot Gái Xinh - Telegram

Bot Telegram gửi ảnh từ Pinterest theo category, kèm phát hiện người bằng OpenCV. Phong cách thư ký dễ thương 💋

## Tính năng

- Ảnh được lấy trực tiếp từ Pinterest API (độ phân giải gốc)
- Lọc ảnh có người bằng Haar Cascade (mặt thẳng, mặt nghiêng, thân trên, toàn thân)
- Quản lý từ khóa & category qua SQLite, có menu inline admin
- Hỗ trợ thêm/xóa từ khóa và category trực tiếp trong chat qua ForceReply
- Tự động xóa keyword không có kết quả (giữ tối thiểu 3 keyword/category)

## Cài đặt

```bash
# 1. Tạo môi trường ảo
python3 -m venv venv
source venv/bin/activate

# 2. Cài thư viện
pip install -r requirements.txt

# 3. Tạo file .env và điền token
echo "TELEGRAM_BOT_TOKEN=your_token_here" > .env
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

| Lệnh | Mô tả |
|------|-------|
| `/start` | Khởi động & xem danh sách lệnh |
| `/girl` | 📸 Ảnh gái xinh |
| `/sexy` | 🔥 Ảnh sexy |
| `/bikini` | 👙 Ảnh bikini |
| `/cosplay` | 🎭 Ảnh cosplay |
| `/asian` | 🌸 Ảnh gái Châu Á |
| `/onlyfans` | 💎 Ảnh OnlyFans style |
| `/random` | 🎲 Random một category bất kỳ |
| `/s <từ khóa>` | 🔍 Tìm ảnh theo từ khóa tự do |
| `/help` | 💡 Hướng dẫn |
| `/admin` | 🔧 Menu quản lý từ khóa & category |

## Quản lý Admin

Dùng `/admin` để mở menu inline:
- Xem danh sách từ khóa theo category
- Thêm từ khóa mới (ForceReply — tự focus ô nhập)
- Xóa từ khóa từng cái
- Thêm / xóa category

Hoặc dùng lệnh trực tiếp:
```
/addkw <category> <từ khóa>
/addcat <tên category>
```

## Cấu trúc dữ liệu

```
data/
  keywords.db   # SQLite: bảng keywords(category, keyword)
```

## Yêu cầu

- Python 3.10+
- Các thư viện trong `requirements.txt`:
  - `python-telegram-bot==21.6`
  - `pinscrape==5.1.0`
  - `opencv-python-headless`
  - `numpy`
  - `requests`
  - `python-dotenv`
