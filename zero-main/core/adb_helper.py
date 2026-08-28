import subprocess
import os
import time

TARGET_SERIAL = None

def adb(*args, timeout=10):
    """
    Hàm cốt lõi để thực thi các lệnh ADB.
    Tự động gắn thêm cờ -s <serial> nếu đã xác định được thiết bị mục tiêu.
    """
    global TARGET_SERIAL
    cmd = ["adb"]
    if TARGET_SERIAL:
        cmd.extend(["-s", TARGET_SERIAL])
    cmd.extend(args)
    
    try:
        res = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=timeout, 
            encoding='utf-8', 
            errors='ignore'
        )
        return res
    except Exception as e:
        class DummyRes:
            returncode = 1
            stdout = ""
            stderr = str(e)
        return DummyRes()

def check_device():
    """
    Kiểm tra danh sách thiết bị Android đang kết nối qua cổng ADB,
    lấy thiết bị đầu tiên làm thiết bị mục tiêu cho toàn bộ trợ lý.
    """
    global TARGET_SERIAL
    res = adb("devices", timeout=5)
    if res.returncode != 0:
        print(f"⚠️ Lỗi khi kiểm tra thiết bị ADB: {res.stderr.strip()}")
        return False
        
    lines = res.stdout.splitlines()
    devices = []
    for line in lines[1:]:
        if "\tdevice" in line:
            devices.append(line.split("\t")[0])
            
    if devices:
        TARGET_SERIAL = devices[0]
        print(f"✅ Đã kết nối thành công với thiết bị: {TARGET_SERIAL}")
        return True
        
    print("❌ Không tìm thấy thiết bị Android nào đang kết nối!")
    return False

def control_volume(param):
    """Điều khiển âm lượng thiết bị"""
    param = str(param).lower()
    if "tăng" in param or "up" in param:
        for _ in range(5):
            adb("shell", "input", "keyevent", "24")
        return "Đã tăng âm lượng."
    elif "giảm" in param or "down" in param:
        for _ in range(5):
            adb("shell", "input", "keyevent", "25")
        return "Đã giảm âm lượng."
    elif "tắt" in param or "mute" in param:
        adb("shell", "input", "keyevent", "164")
        return "Đã tắt tiếng (Mute)."
    return "Đã điều chỉnh âm lượng."

def media_control(param):
    """Điều khiển phát media (Play, Pause, Next, Prev)"""
    param = str(param).lower()
    key_map = {
        "play": "126",
        "pause": "127",
        "toggle": "85",
        "next": "87",
        "previous": "88"
    }
    key = key_map.get(param, "85")
    adb("shell", "input", "keyevent", key)
    return f"Đã thực hiện lệnh media: {param}"

def check_storage():
    """Kiểm tra dung lượng bộ nhớ thiết bị"""
    res = adb("shell", "df", "/sdcard")
    if res and res.returncode == 0:
        lines = res.stdout.strip().splitlines()
        if len(lines) > 1:
            return f"Thông tin bộ nhớ:\n{lines[1]}"
    return "Không thể lấy thông tin bộ nhớ."

def open_web_url(url):
    """Mở một đường dẫn URL trên trình duyệt điện thoại"""
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    adb("shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", url)
    return f"Đã mở trang web: {url}"

def take_screenshot_for_agent():
    """Chụp màn hình phục vụ cho Smart Agent"""
    screenshot_path = "screenshot.png"
    adb("shell", "screencap", "-p", "/sdcard/screenshot.png")
    adb("pull", "/sdcard/screenshot.png", screenshot_path)
    if os.path.exists(screenshot_path):
        return screenshot_path
    return None

def agent_tap(x, y):
    """Chạm vào tọa độ (x, y) trên màn hình điện thoại"""
    adb("shell", "input", "tap", str(x), str(y))

def agent_type(text):
    """Nhập văn bản vào điện thoại"""
    formatted_text = text.replace(" ", "%s")
    adb("shell", "input", "text", formatted_text)

def agent_scroll():
    """Cuộn màn hình điện thoại"""
    adb("shell", "input", "swipe", "500", "1500", "500", "500", "300")