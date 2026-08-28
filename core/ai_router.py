import os
import json
import re
from PIL import Image

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

AI_ENABLED = False
gemini_model = None

if GEMINI_API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        # Sử dụng model hỗ trợ tốt cả text và vision
        gemini_model = genai.GenerativeModel('gemini-2.5-flash')
        AI_ENABLED = True
        print("✅ Đã kết nối thành công với Gemini AI!")
    except Exception as e:
        print(f"⚠️ Không khởi tạo được Gemini AI: {e}")
else:
    print("⚠️ Chưa cấu hình Gemini API Key, trợ lý sẽ dùng chế độ tìm kiếm thông thường.")

def ai_route_command(command):
    """Phân loại lệnh văn bản phức tạp hoặc trò chuyện thông qua Gemini"""
    if not AI_ENABLED or not gemini_model:
        return None

    prompt = f"""Bạn là bộ phân loại lệnh cho trợ lý điều khiển điện thoại Android qua giọng nói tiếng Việt tên là Zero.
Người dùng vừa nói: "{command}"

Phân loại thành MỘT trong các hành động, CHỈ trả lời bằng JSON thuần túy, không thêm chữ nào khác, không markdown:
- "open_app": muốn mở một ứng dụng. Trích tên ứng dụng vào "app_query".
- "wake_screen": muốn bật/đánh thức màn hình điện thoại.
- "volume": điều chỉnh âm lượng. Trích tham số vào "param".
- "media": điều khiển phát nhạc/video. Trích tham số vào "param".
- "storage": kiểm tra bộ nhớ thiết bị.
- "open_web": mở trang web. Trích URL vào "param".
- "agent_task": tác vụ tự động hóa màn hình phức tạp.
- "chat": câu hỏi/trò chuyện thường. Trả lời ngắn gọn (1-2 câu tiếng Việt) vào "reply".

Định dạng JSON bắt buộc:
{{"action": "open_app hoặc wake_screen hoặc volume hoặc media or storage hoặc open_web hoặc agent_task hoặc chat", "app_query": "chuỗi hoặc null", "param": "chuỗi hoặc null", "reply": "chuỗi hoặc null"}}
"""
    try:
        response = gemini_model.generate_content(prompt)
        raw_text = response.text.strip()
        match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
        if not match:
            return None
        data = json.loads(match.group(0))
        if "action" not in data:
            return None
        return data
    except Exception as e:
        print(f"⚠️ Lỗi khi gọi Gemini AI (route): {e}")
        return None

def ai_agent_act(user_command, screenshot_path):
    """AI Agent quan sát ảnh chụp màn hình điện thoại và quyết định hành động tiếp theo"""
    if not AI_ENABLED or not gemini_model or not os.path.exists(screenshot_path):
        return {"action": "finish", "reply": "Không thể chạy Agent do thiếu API Key hoặc ảnh chụp màn hình."}
    
    try:
        img = Image.open(screenshot_path)
        prompt = f"""
        Bạn là một Smart Agent tự động điều khiển điện thoại Android. 
        Mục tiêu của người dùng: "{user_command}"
        Dựa vào ảnh chụp màn hình hiện tại, hãy phân tích và trả về MỘT JSON thuần (không markdown) với các trường:
        - action: "tap", "type", "scroll", hoặc "finish"
        - x: tọa độ pixel theo chiều ngang trên màn hình (nếu chọn tap)
        - y: tọa độ pixel theo chiều dọc trên màn hình (nếu chọn tap)
        - text: văn bản cần nhập (nếu chọn type)
        - reply: mô tả ngắn gọn bước làm hoặc thông báo hoàn thành
        """
        
        response = gemini_model.generate_content([img, prompt])
        raw_text = response.text.strip()
        match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
        if not match:
            return {"action": "finish", "reply": "Không phân tích được phản hồi từ Agent."}
        return json.loads(match.group(0))
    except Exception as e:
        print(f"⚠️ Lỗi khi gọi Gemini AI (agent): {e}")
        return {"action": "finish", "reply": f"Lỗi xử lý Agent: {str(e)}"}