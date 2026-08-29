from core.listener import wait_for_wake_word, listen_active_command
from core.app_manager import init_app_scanner, find_package, open_android_app
from core.adb_helper import check_device, adb
from core.tts_audio import speak
from core.app_manager import APP_CACHE

def handle_app_count(cmd_lower):
    """Xử lý ý định đếm số lượng ứng dụng bất kỳ dựa trên từ khóa người dùng nói."""
    # Lọc ra từ khóa cần tìm (ví dụ: "có bao nhiêu bản roblox" -> từ khóa là "roblox")
    query = cmd_lower.replace("có bao nhiêu bản", "").replace("có mấy", "").replace("tìm", "").strip()
    if not query:
        query = cmd_lower.replace("bao nhiêu", "").strip()
        
    if query:
        matching_apps = [name for name in APP_CACHE.keys() if query in name.lower()]
        count = len(matching_apps)
        if count > 0:
            app_list_str = ", ".join(matching_apps[:5]) # Đọc tối đa 5 app đầu tiên cho đỡ dài
            speak(f"Tìm thấy {count} ứng dụng liên quan đến {query}, bao gồm: {app_list_str}")
            print(f"📊 Các app khớp với '{query}': {matching_apps}")
        else:
            speak(f"Không tìm thấy ứng dụng nào liên quan đến {query} trên thiết bị.")
    else:
            speak("Bạn muốn kiểm tra số lượng ứng dụng gì ạ?")

def handle_battery_status():
    """Kiểm tra dung lượng pin điện thoại qua ADB."""
    res = adb("shell", "dumpsys", "battery")
    if res.returncode == 0:
        for line in res.stdout.splitlines():
            if "level" in line:
                level = line.split(":")[-1].strip()
                speak(f"Pin điện thoại hiện tại là {level} phần trăm.")
                print(f"🔋 Trạng thái pin: {level}%")
                return
    speak("Không thể lấy thông tin pin từ thiết bị.")

def main():
    print("==================================================")
    print("🤖 ZERO - Trợ lý điều khiển Android Đa Năng đã sẵn sàng!")
    print("==================================================")
    
    if not check_device():
        print("❌ Không tìm thấy thiết bị Android nào kết nối qua ADB!")
        speak("Không tìm thấy thiết bị Android.")
        return

    init_app_scanner()
    speak("Hệ thống Zero đa năng đã sẵn sàng phục vụ bạn.")
    print("💡 Gợi ý: Gọi 'Zero' rồi ra lệnh mở app, đếm app, hoặc kiểm tra pin.\n")

    while True:
        # 1. Chờ gọi tên "zero" lần đầu tiên để thức dậy
        if wait_for_wake_word("zero"):
            speak("Tôi nghe đây, bạn cứ nói.")
            
            # 2. Bắt đầu phiên trò chuyện liên tục
            while True:
                cmd = listen_active_command(duration=6)
                
                if not cmd:
                    speak("Tôi ngắt kết nối phiên tạm thời nhé.")
                    print("💤 Zero quay lại trạng thái chờ gọi tên...")
                    break
                
                cmd_lower = cmd.lower()
                
                # Lệnh kết thúc phiên
                if any(kw in cmd_lower for kw in ["ngủ đi", "tạm biệt", "thôi", "dừng lại"]):
                    speak("Vâng, chào bạn.")
                    print("💤 Zero đi ngủ.")
                    break
                
                # Ý định 1: Kiểm tra pin điện thoại
                if "pin" in cmd_lower:
                    handle_battery_status()
                
                # Ý định 2: Đếm/Thống kê ứng dụng (ví dụ: "có bao nhiêu bản...", "tìm mấy...")
                elif "bao nhiêu" in cmd_lower or "có mấy" in cmd_lower:
                    handle_app_count(cmd_lower)
                
                # Ý định 3: Mở ứng dụng trực tiếp
                elif "mở" in cmd_lower:
                    app_query = cmd_lower.replace("mở", "").strip()
                    if app_query:
                        pkg = find_package(app_query)
                        if pkg:
                            open_android_app(pkg)
                        else:
                            speak(f"Không tìm thấy ứng dụng {app_query}")
                            print(f"⚠️ Không tìm thấy package cho: {app_query}")
                    else:
                        speak("Bạn muốn mở ứng dụng gì ạ?")
                else:
                    speak("Tôi chưa rõ lệnh này, bạn thử lệnh khác xem.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Đã dừng Zero. Hẹn gặp lại bạn!")