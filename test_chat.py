import requests
import collections

BASE_URL = "http://localhost:20128/v1"
history: collections.deque = collections.deque(maxlen=20)


def list_models() -> list[dict]:
    """Lấy danh sách các model từ API."""
    response = requests.get(f"{BASE_URL}/models")
    response.raise_for_status()
    return response.json().get("data", [])


def select_model(models: list[dict]) -> str:
    """Hiện menu chọn model, trả về model id được chọn."""
    print("\n=== DANH SÁCH MODEL ===")
    for i, m in enumerate(models):
        print(f"  [{i + 1}] {m['id']}")
    print("=======================")

    while True:
        try:
            choice = input(f"Chọn model (1-{len(models)}) [Enter = 1]: ").strip()
            if choice == "":
                idx = 0
            else:
                idx = int(choice) - 1
            if 0 <= idx < len(models):
                selected = models[idx]["id"]
                print(f"✅ Dùng model: {selected}\n")
                return selected
            print(f"❌ Nhập số từ 1 đến {len(models)}")
        except ValueError:
            print("❌ Vui lòng nhập số hợp lệ")


def chat(model: str, message: str) -> str:
    """Gửi tin nhắn chat đến model kèm lịch sử."""
    history.append({"role": "user", "content": message})
    payload = {
        "model": model,
        "messages": list(history),
        "stream": False,
    }
    response = requests.post(f"{BASE_URL}/chat/completions", json=payload)
    response.raise_for_status()
    reply = response.json()["choices"][0]["message"]["content"]
    history.append({"role": "assistant", "content": reply})
    return reply


if __name__ == "__main__":
    print(f"Kết nối tới: {BASE_URL}")

    try:
        models = list_models()
    except Exception as e:
        print(f"❌ Không kết nối được API: {e}")
        exit(1)

    if not models:
        print("❌ Không có model nào khả dụng.")
        exit(1)

    selected_model = select_model(models)

    print("Nhập 'quit' để thoát | 'clear' để xóa lịch sử | 'model' để đổi model\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nTạm biệt!")
            break

        if not user_input:
            continue
        if user_input.lower() == "quit":
            print("Tạm biệt!")
            break
        if user_input.lower() == "clear":
            history.clear()
            print("🧹 Đã xóa lịch sử hội thoại\n")
            continue
        if user_input.lower() == "model":
            selected_model = select_model(models)
            history.clear()
            print("🧹 Lịch sử đã được reset do đổi model\n")
            continue

        try:
            reply = chat(selected_model, user_input)
            print(f"Bot: {reply}\n")
        except Exception as e:
            print(f"❌ Lỗi: {e}\n")

