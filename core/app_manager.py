import os
import json
import difflib
import re
from core.adb_helper import adb
import core.adb_helper as adb_helper
from core.tts_audio import speak

CACHE_FILE = "app_names_cache.json"
ACTIVITY_CACHE_FILE = "activity_cache.json"

installed_packages = []
DISPLAY_NAMES = {}
APP_CACHE = {}  # Thêm biến này để tương thích hoàn toàn với main.py

def init_app_scanner():
    global installed_packages, DISPLAY_NAMES, APP_CACHE
    print("🔄 Đang quét danh sách ứng dụng trên điện thoại...")
    if not adb_helper.TARGET_SERIAL:
        print("❌ Không có thiết bị hợp lệ nào để quét app.")
        installed_packages = []
        DISPLAY_NAMES = {}
        APP_CACHE = {}
        return
    try:
        result = adb("shell", "pm", "list", "packages", timeout=15)
        if result.returncode != 0:
            print(f"⚠️ Lỗi khi chạy adb: {result.stderr.strip() if result.stderr else ''}")
            installed_packages = []
        else:
            installed_packages = [
                line.replace("package:", "").strip()
                for line in result.stdout.splitlines()
                if line.startswith("package:")
            ]
            print(f"✅ Đã quét thành công {len(installed_packages)} ứng dụng trên máy!")
            
            # Gán tên hiển thị nhanh từ package name
            DISPLAY_NAMES = {pkg: pkg.split(".")[-1] for pkg in installed_packages}
            APP_CACHE = DISPLAY_NAMES  # Đồng bộ dữ liệu vào APP_CACHE cho main.py dùng
            
            try:
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(DISPLAY_NAMES, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
    except Exception as e:
        print(f"⚠️ Lỗi: Không thể quét app ({e}).")
        installed_packages = []

def load_display_names():
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

# Tải cache lúc khởi động module
DISPLAY_NAMES = load_display_names()
APP_CACHE = DISPLAY_NAMES

def remove_vietnamese_accent(text):
    if not text:
        return ""
    s = text.lower()
    s = re.sub(r'[àáảãạăằắẳẵặâầấẩẫậ]', 'a', s)
    s = re.sub(r'[èéẻẽẹêềếểễệ]', 'e', s)
    s = re.sub(r'[ìíỉĩị]', 'i', s)
    s = re.sub(r'[òóỏõọôồốổỗộơờớởỡợ]', 'o', s)
    s = re.sub(r'[ùúủũụưừứửữự]', 'u', s)
    s = re.sub(r'[ỳýỷỹỵ]', 'y', s)
    s = re.sub(r'[đ]', 'd', s)
    return s

APP_ALIASES = {
    "dien thoai": ["dialer", "incallui", "phone", "call"],
    "goi dien": ["dialer", "incallui", "phone", "call"],
    "danh ba": ["contacts", "people"],
    "nhan tin": ["mms", "messaging", "sms", "messages"],
    "tin nhan": ["mms", "messaging", "sms", "messages"],
    "cai dat": ["settings"],
    "may anh": ["camera"],
    "chup anh": ["camera"],
    "trinh duyet": ["chrome", "browser"],
    "may tinh": ["calculator"],
    "lich": ["calendar"],
    "dong ho": ["deskclock", "clock", "alarm"],
    "bao thuc": ["deskclock", "clock", "alarm"],
    "thu vien anh": ["gallery", "photos", "album"],
    "hinh anh": ["gallery", "photos", "album"],
    "nhac": ["music", "player"],
    "thu dien tu": ["gmail", "email"],
}

def _match_via_alias(cmd_norm):
    for alias_key, keywords in APP_ALIASES.items():
        if alias_key in cmd_norm:
            candidates = []
            for pkg in installed_packages:
                pkg_lower = pkg.lower()
                if any(kw in pkg_lower for kw in keywords):
                    candidates.append(pkg)
            if candidates:
                system_candidates = [p for p in candidates if p.startswith(("com.android.", "com.google.android."))]
                return (system_candidates or candidates)[0]
    return None

def find_package(command, debug=True):
    cmd_norm = remove_vietnamese_accent(command)
    cmd_words = set(cmd_norm.split())

    alias_match = _match_via_alias(cmd_norm)
    if alias_match:
        if debug:
            print(f"DEBUG - Khớp qua từ đồng nghĩa hệ thống -> {alias_match}")
        return alias_match

    best_pkg, best_score, best_name = None, 0.0, None

    for pkg, name in DISPLAY_NAMES.items():
        name_norm = remove_vietnamese_accent(name)
        if name_norm and name_norm in cmd_norm:
            if debug:
                print(f"DEBUG - Khớp chính xác: '{name}' -> {pkg}")
            return pkg

        if name_norm:
            score = difflib.SequenceMatcher(None, name_norm, cmd_norm).ratio()
            if score > best_score:
                best_score, best_pkg, best_name = score, pkg, name

    for pkg in installed_packages:
        parts = [p for p in pkg.split('.') if len(p) > 2]
        for part in parts:
            if part in cmd_words:
                if debug:
                    print(f"DEBUG - Khớp theo package: '{part}' -> {pkg}")
                return pkg

    if best_score > 0.55:
        if debug:
            print(f"DEBUG - Khớp mờ (score={best_score:.2f}): '{best_name}' -> {best_pkg}")
        return best_pkg

    if debug:
        print(f"DEBUG - Không tìm thấy app khớp với: '{command}'")
    return None

def wake_screen():
    try:
        wake_res = adb("shell", "input", "keyevent", "224", timeout=3)
        if wake_res.returncode == 0:
            print("💡 Đã gửi lệnh đánh thức màn hình (KEYCODE_WAKEUP).")
        else:
            print(f"⚠️ Lệnh đánh thức trả về lỗi: {wake_res.stderr.strip() if wake_res.stderr else wake_res.returncode}")

        res = adb("shell", "dumpsys", "power", timeout=4)
        if "mWakefulness=Awake" in res.stdout:
            print("💡 Xác nhận: màn hình đang ở trạng thái Awake.")
        elif "mWakefulness=Asleep" in res.stdout or "mWakefulness=Dozing" in res.stdout:
            print("⚠️ Màn hình vẫn báo Asleep/Dozing.")

        adb("shell", "input", "swipe", "540", "1800", "540", "800", "200", timeout=3)
    except Exception as e:
        print(f"⚠️ Không thể đánh thức màn hình: {e}")

def _load_activity_cache():
    if not os.path.exists(ACTIVITY_CACHE_FILE):
        return {}
    try:
        with open(ACTIVITY_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_activity_cache(cache):
    try:
        with open(ACTIVITY_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

ACTIVITY_CACHE = _load_activity_cache()

def open_android_app(package):
    wake_screen()
    speak("Đang mở ứng dụng cho bạn.")

    cached_activity = ACTIVITY_CACHE.get(package)
    if cached_activity:
        if adb("shell", "am", "start", "--user", "0", "-n", cached_activity, timeout=3).returncode == 0:
            return
        ACTIVITY_CACHE.pop(package, None)

    try:
        res = adb("shell", "cmd", "package", "resolve-activity", "--brief", "--user", "0", package, timeout=4)
        lines = [l.strip() for l in res.stdout.splitlines() if l.strip()]
        if lines and "/" in lines[-1]:
            activity = lines[-1]
            if adb("shell", "am", "start", "--user", "0", "-n", activity, timeout=3).returncode == 0:
                ACTIVITY_CACHE[package] = activity
                _save_activity_cache(ACTIVITY_CACHE)
                return
    except Exception:
        pass

    try:
        if adb("shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1", timeout=6).returncode == 0:
            return
    except Exception:
        pass

    print(f"⚠️ Không thể mở app ({package}).")