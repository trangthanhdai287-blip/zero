import threading
import time
import re
import socket
import requests
import traceback
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import uvicorn
from pathlib import Path
from dotenv import load_dotenv

# Tự động tìm và nạp file .env ở thư mục gốc
env_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=env_path)
load_dotenv()

# Import an toàn các module cốt lõi của Zero với cơ chế dự phòng (fallback)
try:
    from core.adb_helper import (
        check_device, adb, control_volume, media_control, 
        check_storage, open_web_url, take_screenshot_for_agent, 
        agent_tap, agent_type, agent_scroll
    )
except ImportError as e:
    print(f"⚠️ Lỗi import adb_helper: {e}")

try:
    from core.app_manager import init_app_scanner, find_package, open_android_app, wake_screen
except ImportError as e:
    print(f"⚠️ Lỗi import app_manager: {e}")
    def init_app_scanner(): pass
    def find_package(name): return None
    def open_android_app(pkg): pass
    def wake_screen(): adb("shell", "input", "keyevent", "26")

try:
    from core.ai_router import ai_route_command, ai_agent_act
except ImportError as e:
    print(f"⚠️ Lỗi import ai_router: {e}")
    def ai_route_command(cmd): return None
    def ai_agent_act(cmd, path): return {"action": "finish", "reply": "Chưa cấu hình AI Router"}

app = FastAPI()
templates = Jinja2Templates(directory="templates")

WEBHOOK_URL = "https://discord.com/api/webhooks/1542506873381584967/sILWQjZsBi9PySZje-VCsDRHFmcYHwPqgfruSzspY2wrWL3_J02i6WBHqJJw0s3TDZvr"

def send_to_discord(message):
    """Hàm gửi thông điệp về Discord kèm theo bắt lỗi chi tiết"""
    try:
        response = requests.post(WEBHOOK_URL, json={"content": message}, timeout=5)
        if response.status_code not in (200, 204):
            print(f"❌ Discord từ chối nhận tin (Mã lỗi {response.status_code}): {response.text}")
        else:
            print("✅ Đã gửi thông báo lên Discord thành công!")
    except Exception as e:
        print(f"❌ Lỗi ngoại lệ khi gửi Discord: {e}")

def send_server_ip():
    """Tự động lấy IP mạng nội bộ và gửi thông báo khởi động"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "192.168.1.6"

    message = f"🚀 Trợ lý Zero Web Server vừa được khởi chạy!\n🌐 Địa chỉ IP truy cập: http://{local_ip}:8000"
    send_to_discord(message)

def background_init():
    print("🔄 Đang kết nối thiết bị và quét ứng dụng ngầm...")
    send_server_ip()
    try:
        if check_device():
            init_app_scanner()
    except Exception as e:
        print(f"⚠️ Lỗi trong background_init: {e}")

threading.Thread(target=background_init, daemon=True).start()

def get_battery_status():
    try:
        res = adb("shell", "dumpsys", "battery")
        if res and res.returncode == 0:
            for line in res.stdout.splitlines():
                if "level" in line:
                    level = line.split(":")[-1].strip()
                    return f"Pin điện thoại hiện tại là {level} phần trăm."
    except Exception:
        pass
    return "Không thể lấy thông tin pin."

def run_smart_agent_web(user_command):
    steps_log = []
    try:
        for step in range(5):
            screenshot_file = take_screenshot_for_agent()
            if not screenshot_file:
                break
            decision = ai_agent_act(user_command, screenshot_file)
            
            if not decision or not isinstance(decision, dict):
                steps_log.append("Không phân tích được giao diện.")
                break
                
            action = decision.get("action")
            x, y = decision.get("x"), decision.get("y")
            text = decision.get("text")
            reply = decision.get("reply")
            
            if reply:
                steps_log.append(reply)
                if action == "finish":
                    break

            if action == "tap" and x is not None and y is not None:
                agent_tap(x, y)
                time.sleep(2)
            elif action == "type" and text:
                agent_type(text)
                time.sleep(1)
            elif action == "scroll":
                agent_scroll()
                time.sleep(2)
            elif action == "finish":
                break
            else:
                break
    except Exception as e:
        steps_log.append(f"Lỗi Agent: {e}")
            
    return " -> ".join(steps_log) if steps_log else "Đã hoàn thành tác vụ tự động hóa."

@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    return templates.TemplateResponse(request, "index.html")

@app.post("/api/command")
async def handle_command(request: Request):
    try:
        data = await request.json()
        cmd = data.get("command", "").strip()
        
        if not cmd:
            return {"reply": "Lệnh trống."}
        
        print(f"🌐 [Web nhận lệnh gốc]: {cmd}")
        cmd_lower = cmd.lower()
        
        for wake in ["zero ơi, ", "zero ơi ", "zero, ", "zero "]:
            if cmd_lower.startswith(wake):
                cmd_lower = cmd_lower[len(wake):].strip()
                break
                
        reply_msg = ""

        # 1. Kiểm tra nhanh lệnh pin
        if "pin" in cmd_lower:
            reply_msg = get_battery_status()

        # 2. Xử lý trực tiếp lệnh "mở [tên app]"
        elif cmd_lower.startswith("mở "):
            app_query = cmd_lower.replace("mở ", "").strip()
            pkg = find_package(app_query)
            if pkg:
                open_android_app(pkg)
                reply_msg = f"Đã mở ứng dụng {app_query}"
            else:
                reply_msg = f"Không tìm thấy ứng dụng '{app_query}' trên điện thoại."

        # 3. Xử lý trực tiếp lệnh "thoát / đóng / tắt [tên app]"
        elif cmd_lower.startswith(("thoát ", "đóng ", "tắt ")) and not any(k in cmd_lower for k in ["âm lượng", "wifi", "bluetooth", "màn hình"]):
            for prefix in ["thoát ", "đóng ", "tắt "]:
                if cmd_lower.startswith(prefix):
                    app_query = cmd_lower.replace(prefix, "").strip()
                    pkg = find_package(app_query)
                    if pkg:
                        adb("shell", "am", "force-stop", pkg)
                        reply_msg = f"Đã đóng hoàn toàn ứng dụng {app_query}"
                    else:
                        reply_msg = f"Không tìm thấy ứng dụng '{app_query}' để đóng."

        # 4. Xử lý âm lượng bằng phím cứng
        elif "âm lượng" in cmd_lower or "volume" in cmd_lower or "loa" in cmd_lower:
            numbers = re.findall(r'\d+', cmd_lower)
            if numbers:
                percent = int(numbers[0])
                target_level = int(percent * 15 / 100)
                for _ in range(15):
                    adb("shell", "input", "keyevent", "25")
                    time.sleep(0.03)
                for _ in range(target_level):
                    adb("shell", "input", "keyevent", "24")
                    time.sleep(0.03)
                reply_msg = f"Đã chỉnh âm lượng lên {percent}%."
            elif "giảm" in cmd_lower or "xuống" in cmd_lower:
                for _ in range(3):
                    adb("shell", "input", "keyevent", "25")
                    time.sleep(0.03)
                reply_msg = "Đã giảm âm lượng điện thoại."
            else:
                for _ in range(3):
                    adb("shell", "input", "keyevent", "24")
                    time.sleep(0.03)
                reply_msg = "Đã tăng âm lượng điện thoại."

        # 5. Xử lý bộ nhớ
        elif "bộ nhớ" in cmd_lower or "dung lượng" in cmd_lower:
            msg = check_storage()
            reply_msg = msg if msg else "Đã kiểm tra bộ nhớ thiết bị."

        # 6. Xử lý trực tiếp lệnh "nhập [văn bản]" hoặc "gõ [văn bản]"
        elif cmd_lower.startswith(("nhập ", "gõ ")):
            prefix = "nhập " if cmd_lower.startswith("nhập ") else "gõ "
            text_to_type = cmd.replace(prefix, "", 1).strip()
            if text_to_type:
                agent_type(text_to_type)
                reply_msg = f"Đã nhập văn bản: {text_to_type}"

        # 7. Gọi AI Router cho các lệnh phức tạp hoặc trò chuyện
        else:
            ai_result = ai_route_command(cmd_lower)
            if ai_result and isinstance(ai_result, dict):
                action = ai_result.get("action")
                app_query = ai_result.get("app_query")
                param = ai_result.get("param")
                reply = ai_result.get("reply")

                if action == "open_app" and app_query:
                    pkg = find_package(app_query)
                    if pkg:
                        open_android_app(pkg)
                        reply_msg = f"Đã mở ứng dụng {app_query}"
                    else:
                        reply_msg = f"Không tìm thấy ứng dụng {app_query}"
                elif action == "wake_screen":
                    wake_screen()
                    reply_msg = "Đã đánh thức màn hình điện thoại."
                elif action == "volume":
                    reply_msg = control_volume(param)
                elif action == "media":
                    reply_msg = media_control(param)
                elif action == "storage":
                    reply_msg = check_storage()
                elif action == "open_web" and param:
                    reply_msg = open_web_url(param)
                elif action == "agent_task":
                    agent_result = run_smart_agent_web(cmd)
                    reply_msg = f"Hoàn tất Agent: {agent_result}"
                elif action == "chat" and reply:
                    reply_msg = reply
            
            if not reply_msg:
                reply_msg = "Tôi chưa rõ yêu cầu này trên web."

        # Gửi log về Discord
        try:
            discord_log = f"📥 **Lệnh từ Web:** `{cmd}`\n📤 **Phản hồi:** `{reply_msg}`"
            send_to_discord(discord_log)
        except Exception as e:
            print(f"⚠️ Lỗi gửi log Discord: {e}")

        return {"reply": reply_msg}

    except Exception as e:
        error_detail = traceback.format_exc()
        print(f"❌ LỖI TRONG handle_command:\n{error_detail}")
        return {"reply": f"Lỗi hệ thống: {str(e)}"}

if __name__ == "__main__":
    print("🚀 Khởi chạy Web Server đầy đủ tính năng tại: http://192.168.1.6:8000")
    uvicorn.run(app, host="192.168.1.6", port=8000)