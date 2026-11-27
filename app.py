import streamlit as st
from google import genai
from streamlit_mic_recorder import mic_recorder
import base64
import json
from gtts import gTTS
import os
import time

# 1. Cấu hình trang
st.set_page_config(page_title="AI English Tutor - Đa cấp độ", page_icon="🎓", layout="centered")
st.title("🎓 AI English Tutor - Đa cấp độ (A1-C2)")
st.caption("Học tiếng Anh với AI - Tự động điều chỉnh theo trình độ của bạn")

# 2. CSS ghim nút mic xuống dưới
st.markdown("""
<style>
.bottom-spacer { height: 220px; }
.mic-container {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: white;
    padding: 15px 20px;
    border-top: 2px solid #e0e0e0;
    z-index: 1000;
    box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
}
</style>
""", unsafe_allow_html=True)

# 3. Sidebar
# Ưu tiên lấy Key từ Streamlit Secrets (khi deploy lên web)
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    # Nếu chạy local thì vẫn hiện ô nhập tay
    api_key = st.sidebar.text_input("🔑 Google API Key:", type="password")

# ⭐ MENU CHỌN TRÌNH ĐỘ
level = st.sidebar.selectbox(
    "📊 Chọn trình độ của bạn:",
    ["A1 - Mới bắt đầu", "A2 - Sơ cấp", "B1 - Trung cấp", "B2 - Trung cao", "C1 - Cao cấp", "C2 - Thành thạo"]
)

selected_model = st.sidebar.selectbox(
    "🤖 Chọn Model AI:",
    [ "gemini-3.5-flash-lite"]
)
auto_speak = st.sidebar.toggle("🔊 Tự động đọc câu trả lời", value=True)
speak_rate = st.sidebar.slider("⚡ Tốc độ đọc:", 0.5, 1.5, 0.9, 0.1)

# Nút Reset
if st.sidebar.button("🔄 Reset Micro & Xóa lịch sử"):
    st.session_state.pop("mic_key", None)
    st.session_state.messages = []
    st.rerun()

# 4. Session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "mic_key" not in st.session_state:
    st.session_state.mic_key = 0
if "audio_counter" not in st.session_state:
    st.session_state.audio_counter = 0
if "current_level" not in st.session_state:
    st.session_state.current_level = level

# ⭐ SYSTEM PROMPTS CHO TỪNG CẤP ĐỘ
SYSTEM_PROMPTS = {
    "A1 - Mới bắt đầu": """
Bạn là giáo viên tiếng Anh thân thiện, chuyên dạy học viên trình độ A1 (Mới bắt đầu).
Đặc điểm:
- Dùng từ vựng cơ bản nhất (500 từ thông dụng)
- Câu ngắn, đơn giản, dễ hiểu
- Giải thích lỗi ngữ pháp bằng tiếng Việt
- Luôn khuyến khích và khen ngợi
- Kết thúc bằng câu hỏi đơn giản để duy trì hội thoại
Ví dụ: "I has a cat" → "Bạn đã gần đúng! Với 'I', chúng ta dùng 'have'. Câu đúng: 'I have a cat.' Chú mèo của bạn tên gì?"
""",

    "A2 - Sơ cấp": """
Bạn là giáo viên tiếng Anh, dạy học viên trình độ A2 (Sơ cấp).
Đặc điểm:
- Dùng từ vựng thông dụng (1000-1500 từ)
- Giới thiệu thì quá khứ đơn, tương lai đơn
- Câu phức hơn một chút (because, although, when)
- Giải thích ngắn bằng tiếng Việt, nhưng khuyến khích học viên đọc hiểu tiếng Anh
- Sửa lỗi và đưa ra ví dụ thực tế
Ví dụ: "I go to school yesterday" → "Gần đúng! Vì có 'yesterday', chúng ta dùng thì quá khứ: 'I went to school yesterday.' Bạn đi học bằng gì?"
""",

    "B1 - Trung cấp": """
You are an English teacher for B1 level (Intermediate) students.
Characteristics:
- Use common idioms and phrasal verbs (give up, look forward to, etc.)
- Introduce more complex grammar (present perfect, conditionals)
- Explain mistakes in simple English, with Vietnamese only for difficult concepts
- Encourage students to express opinions and feelings
- Ask open-ended questions to practice fluency
Example: "I very like football" → "Almost! In English, we say 'I really like football' or 'I like football very much.' What's your favorite team?"
""",

    "B2 - Trung cao": """
You are an English teacher for B2 level (Upper-Intermediate) students.
Characteristics:
- Use academic vocabulary and collocations (make a decision, take responsibility)
- Focus on natural expressions and native-like phrasing
- Explain all corrections in English
- Discuss topics like technology, environment, culture
- Challenge students with nuanced grammar (passive voice, reported speech)
Example: "I think that technology is very important for our life" → "Good point! A more natural way: 'I believe technology plays a crucial role in our daily lives.' What specific technology has changed your life the most?"
""",

    "C1 - Cao cấp": """
You are an English teacher for C1 level (Advanced) students.
Characteristics:
- Discuss complex topics: economics, politics, philosophy, science
- Use sophisticated vocabulary and formal register
- Focus on precision, nuance, and stylistic choices
- Correct subtle errors in word choice, register, or tone
- Encourage critical thinking and argumentation
- All explanations in English
Example: "The government should do more for poor people" → "Your point is valid. A more sophisticated expression: 'The government ought to implement more comprehensive social welfare programs for disadvantaged communities.' What specific policies would you propose?"
""",

    "C2 - Thành thạo": """
You are an English teacher for C2 level (Proficiency/Mastery) students.
Characteristics:
- Analyze subtle nuances in meaning, tone, and register
- Discuss literary, academic, and professional texts
- Focus on idiomatic expressions, cultural references, and stylistic devices
- Challenge students with near-native precision
- Discuss connotations, implied meanings, and rhetorical strategies
- All explanations in English, at a native-speaker level
Example: "The movie was good" → "While grammatically correct, this lacks precision. Consider: 'The film was compelling, with nuanced character development and a thought-provoking narrative.' What aspects of the cinematography stood out to you?"
"""
}

# Lấy system prompt theo trình độ đã chọn
current_prompt = SYSTEM_PROMPTS[level]

# ⭐ Nếu người dùng đổi trình độ, hỏi xem có muốn reset chat không
if st.session_state.current_level != level:
    st.session_state.current_level = level
    if st.session_state.messages:
        st.warning(f"⚠️ Bạn đã chuyển sang trình độ **{level}**. Lịch sử chat cũ có thể không phù hợp.")
        if st.sidebar.button("🗑️ Xóa lịch sử và bắt đầu lại"):
            st.session_state.messages = []
            st.rerun()


# 5. HÀM ĐỌC BẰNG gTTS
def speak_with_gtts(text, rate=0.9):
    try:
        st.session_state.audio_counter += 1
        filename = f"response_{st.session_state.audio_counter}_{int(time.time())}.mp3"
        is_slow = rate < 0.9
        tts = gTTS(text=text, lang='en', slow=is_slow)
        tts.save(filename)
        with open(filename, 'rb') as f:
            audio_bytes = f.read()
        b64 = base64.b64encode(audio_bytes).decode('utf-8')
        os.remove(filename)
        audio_html = f"""
        <div style="margin-top: 10px;">
            <audio id="audio_{st.session_state.audio_counter}" 
                   src="data:audio/mp3;base64,{b64}" 
                   autoplay 
                   controls 
                   style="width: 100%;">
            </audio>
        </div>
        <script>
        (function() {{
            const audio = document.getElementById('audio_{st.session_state.audio_counter}');
            if (audio) {{
                const playPromise = audio.play();
                if (playPromise !== undefined) {{
                    playPromise.catch(error => {{
                        console.log('Autoplay bị chặn');
                    }});
                }}
            }}
        }})();
        </script>
        """
        st.components.v1.html(audio_html, height=60)
        return True
    except Exception as e:
        st.warning(f"⚠️ Lỗi tạo giọng nói: {e}")
        return False


# 6. HÀM ĐỌC BẰNG speechSynthesis
def speak_with_browser(text, rate=0.9):
    safe_text = json.dumps(text)
    js_code = f"""
    <script>
    (function() {{
        if (!window.speechSynthesis) return;
        window.speechSynthesis.cancel();
        if (!window._speechKeepAlive) {{
            window._speechKeepAlive = setInterval(() => {{
                if (window.speechSynthesis.speaking) {{
                    window.speechSynthesis.resume();
                }}
            }}, 10000);
        }}
        setTimeout(() => {{
            const u = new SpeechSynthesisUtterance({safe_text});
            u.lang = 'en-US';
            u.rate = {rate};
            u.pitch = 1;
            try {{
                window.speechSynthesis.speak(u);
            }} catch(e) {{}}
        }}, 100);
    }})();
    </script>
    """
    st.components.v1.html(js_code, height=0)


# 7. HÀM NÚT ĐỌC THỦ CÔNG
def add_speak_button(text, button_id, rate=0.9):
    safe_text = json.dumps(text)
    js_code = f"""
    <script>
    function speak_{button_id}() {{
        if (window.speechSynthesis) {{
            window.speechSynthesis.cancel();
            const u = new SpeechSynthesisUtterance({safe_text});
            u.lang = 'en-US';
            u.rate = {rate};
            window.speechSynthesis.speak(u);
        }}
    }}
    </script>
    <button onclick="speak_{button_id}()" style="
        background-color:#4CAF50;color:white;padding:6px 12px;border:none;
        border-radius:5px;cursor:pointer;font-size:13px;margin-top:5px;">
        🔊 Đọc câu này</button>
    """
    st.components.v1.html(js_code, height=45)
# ⭐ ĐỊNH NGHĨA CÁC CÔNG CỤ (TOOLS) CHO AI
tools = [
    {
        "name": "search_dictionary",
        "description": "Tra cứu từ vựng tiếng Anh. Dùng khi user yêu cầu tra từ, hỏi nghĩa, hoặc hỏi cách phát âm.",
        "parameters": {
            "type": "object",
            "properties": {
                "word": {"type": "string", "description": "Từ tiếng Anh cần tra cứu"}
            },
            "required": ["word"]
        }
    },
    {
        "name": "generate_quiz",
        "description": "Tạo bài tập trắc nghiệm tiếng Anh theo chủ đề ngữ pháp hoặc từ vựng. Dùng khi user yêu cầu làm bài tập, luyện tập.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Chủ đề bài tập (ví dụ: present_simple, vocabulary_food, conditionals)"},
                "num_questions": {"type": "integer", "description": "Số lượng câu hỏi (mặc định 5)"}
            },
            "required": ["topic"]
        }
    }
]

# ⭐ HÀM THỰC THI CÔNG CỤ (AI sẽ gọi hàm này)
def execute_tool(tool_name, args):
    if tool_name == "search_dictionary":
        word = args.get("word", "")
        # Giả lập tra từ điển (sau này có thể thay bằng API thật như FreeDictionaryAPI)
        return f"""
        📖 **{word.capitalize()}** 
        *Phát âm:* /.../ 
        *Nghĩa:* (Đang cập nhật - AI sẽ điền nghĩa chính xác dựa trên ngữ cảnh)
        *Ví dụ:* I learned the word '{word}' today.
        """
    
    elif tool_name == "generate_quiz":
        topic = args.get("topic", "general")
        num = args.get("num_questions", 5)
        # Giả lập tạo quiz (sau này có thể thay bằng logic tạo câu hỏi thật)
        quiz_text = f"📝 **Bài tập: {topic.replace('_', ' ').title()}** ({num} câu)\n\n"
        for i in range(1, num + 1):
            quiz_text += f"{i}. [Câu hỏi mẫu về {topic}] ...\n   A. ...  B. ...  C. ...  D. ...\n\n"
        quiz_text += "*💡 Gợi ý: Hãy thử trả lời trước khi xem đáp án!*"
        return quiz_text
    
    return "❌ Không tìm thấy công cụ này."

# ⭐ HÀM GỌI AI ĐÃ NÂNG CẤP (Hỗ trợ Function Calling)
def call_ai(chat_history):
    if not api_key:
        st.error("⚠️ Vui lòng nhập API Key ở thanh bên trái!")
        return None
    try:
        client = genai.Client(api_key=api_key)
        
        # ⭐ Gửi kèm danh sách tools cho AI
        response = client.models.generate_content(
            model=selected_model,
            contents=chat_history,
            config={
                "response_modalities": ["TEXT"],
                "tools": tools  # ⭐ Dòng quan trọng nhất
            }
        )
        
        # ⭐ KIỂM TRA XEM AI CÓ MUỐN GỌI TOOL KHÔNG
        candidate = response.candidates[0]
        
        # Nếu AI trả về function_call thay vì text
        if hasattr(candidate.content.parts[0], 'function_call') and candidate.content.parts[0].function_call:
            fc = candidate.content.parts[0].function_call
            tool_name = fc.name
            args = dict(fc.args)
            
            # Thực thi tool
            tool_result = execute_tool(tool_name, args)
            
            # ⭐ Gửi kết quả tool обратно cho AI để nó tổng hợp câu trả lời
            chat_history.append({"role": "model", "parts": [{"function_call": {"name": tool_name, "args": args}}]})
            chat_history.append({"role": "user", "parts": [{"function_response": {"name": tool_name, "response": {"result": tool_result}}}]})
            
            # Gọi AI lần 2 để nó dùng kết quả tool tạo câu trả lời cuối cùng
            final_response = client.models.generate_content(
                model=selected_model,
                contents=chat_history,
                config={"response_modalities": ["TEXT"]}
            )
            return final_response.text
        
        # Nếu AI trả về text bình thường
        return response.text
        
    except Exception as e:
        st.error(f"❌ Lỗi AI: {str(e)}")
        return None

# 9. HÀM XỬ LÝ 1 LƯỢT HỘI THOẠI
def handle_turn(user_display, user_part):
    chat_history = [{"role": "user", "parts": [{"text": current_prompt}]}]
    for msg in st.session_state.messages:
        role = "user" if msg["role"] == "user" else "model"
        chat_history.append({"role": role, "parts": [{"text": msg["content"]}]})
    chat_history.append({"role": "user", "parts": [user_part]})

    with st.chat_message("user"):
        st.markdown(user_display)
    st.session_state.messages.append({"role": "user", "content": user_display})

    with st.chat_message("assistant"):
        with st.spinner("🤖 AI đang xử lý..."):
            ai_text = call_ai(chat_history)
            if ai_text:
                st.markdown(ai_text)
                if auto_speak:
                    speak_with_browser(ai_text, speak_rate)
                    speak_with_gtts(ai_text, speak_rate)
                add_speak_button(ai_text, f"btn_{len(st.session_state.messages)}", speak_rate)
                st.session_state.messages.append({"role": "assistant", "content": ai_text})
            else:
                st.warning("⚠️ AI không trả lời.")
def handle_image_turn(image_bytes, mime_type):
    """Xử lý khi người dùng tải lên một bức ảnh"""
    # Chuyển ảnh sang base64 để gửi cho Gemini
    image_b64 = base64.b64encode(image_bytes).decode('utf-8')
    
    # Tạo prompt đặc biệt cho ảnh
    image_prompt = f"Nhìn bức ảnh này. Hãy dạy tôi từ vựng tiếng Anh liên quan đến bức ảnh này ở trình độ {level}. Với mỗi từ, hãy đưa ra cách phát âm, nghĩa tiếng Việt và một câu ví dụ đơn giản."
    
    # Chuẩn bị lịch sử chat (giống như text, nhưng thêm phần ảnh)
    chat_history = [{"role": "user", "parts": [{"text": current_prompt}]}]
    for msg in st.session_state.messages:
        role = "user" if msg["role"] == "user" else "model"
        chat_history.append({"role": role, "parts": [{"text": msg["content"]}]})
    
    # ⭐ ĐÂY LÀ ĐIỂM KHÁC BIỆT: Gửi cả TEXT và INLINE_DATA (Ảnh)
    chat_history.append({"role": "user", "parts": [
        {"text": image_prompt},
        {"inline_data": {"mime_type": mime_type, "data": image_b64}}
    ]})

    # Hiển thị ảnh lên màn hình chat
    with st.chat_message("user"):
        st.markdown("*(📷 Bạn đã gửi một bức ảnh)*")
        st.image(image_bytes, width=200)
    st.session_state.messages.append({"role": "user", "content": "*(📷 Bạn đã gửi một bức ảnh)*"})

    # Gọi AI và nhận phản hồi
    with st.chat_message("assistant"):
        with st.spinner("👁️ AI đang quan sát bức ảnh..."):
            ai_text = call_ai(chat_history)
            if ai_text:
                st.markdown(ai_text)
                if auto_speak:
                    speak_with_browser(ai_text, speak_rate)
                    speak_with_gtts(ai_text, speak_rate)
                add_speak_button(ai_text, f"btn_img_{len(st.session_state.messages)}", speak_rate)
                st.session_state.messages.append({"role": "assistant", "content": ai_text})
            else:
                st.warning("⚠️ AI không trả lời.")

# 10. Hiển thị thông tin trình độ hiện tại
st.info(f"📚 Bạn đang học ở trình độ: **{level}**")

# 11. Hiển thị lịch sử chat
for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            add_speak_button(message["content"], f"hist_{i}", speak_rate)

# Khoảng trống để nút mic không bị che
st.markdown('<div class="bottom-spacer"></div>', unsafe_allow_html=True)

# 12. NÚT MICRO (Ghim dưới cùng)
st.markdown('<div class="mic-container">', unsafe_allow_html=True)
st.caption("🎤 Bấm nút dưới và nói tiếng Anh:")
audio = mic_recorder(
    start_prompt="🎙️ Bắt đầu nói",
    stop_prompt="⏹️ Dừng",
    just_once=True,
    key=f"mic_{st.session_state.mic_key}"
)

if audio:
    audio_b64 = base64.b64encode(audio['bytes']).decode('utf-8')
    handle_turn(
        "*(🎤 Bạn đã gửi một đoạn âm thanh)*",
        {"inline_data": {"mime_type": "audio/wav", "data": audio_b64}}
    )
    st.session_state.mic_key += 1
    st.rerun()

# Ô nhập text
if prompt := st.chat_input("Hoặc gõ câu tiếng Anh..."):
    if prompt.lower() in ['thoát', 'exit', 'quit']:
        st.session_state.messages = []
        st.rerun()
    handle_turn(prompt, {"text": prompt})
    st.rerun()
# Thêm tính năng tải ảnh lên
# ⭐ KHỞI TẠO FLAG ĐÁNH DẤU ẢNH ĐÃ XỬ LÝ
if "image_processed" not in st.session_state:
    st.session_state.image_processed = False

# Thêm tính năng tải ảnh lên
st.markdown("---")
st.caption("📷 Hoặc tải ảnh lên để AI dạy từ vựng:")
uploaded_file = st.file_uploader(
    "Chọn một bức ảnh...", 
    type=["jpg", "jpeg", "png"],
    key="img_uploader"  # ⭐ Key cố định để tránh bị reset
)

# ⭐ CHỈ XỬ LÝ KHI CÓ ẢNH MỚI VÀ CHƯA ĐƯỢC XỬ LÝ
if uploaded_file is not None and not st.session_state.image_processed:
    image_bytes = uploaded_file.read()
    mime_type = uploaded_file.type
    
    # Đánh dấu đã xử lý TRƯỚC KHI rerun
    st.session_state.image_processed = True
    
    # Gọi hàm xử lý ảnh
    handle_image_turn(image_bytes, mime_type)
    
    # Rerun để cập nhật giao diện chat
    st.rerun()

# ⭐ RESET FLAG SAU KHI RERUN HOÀN TẤT
# (Đoạn này nằm ngoài if uploaded_file, luôn chạy mỗi lần render)
if st.session_state.image_processed:
    st.session_state.image_processed = False
st.markdown('</div>', unsafe_allow_html=True)
