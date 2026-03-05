import streamlit as st
import google.generativeai as genai
import os
import time
from pydub import AudioSegment

# --- 1. 錯誤翻譯字典 ---
ERROR_MESSAGES = {
    "404": "🔍 找不到 AI 模型：這可能是因為型號名稱輸入錯誤，請檢查設定。",
    "429": "⏳ 哎呀，AI 累了：目前使用人數過多或超過免費額度，請等一分鐘後再試。",
    "403": "🚫 鑰匙失效：您的 API 金鑰無權限使用此模型，請檢查 Google AI Studio 設定。",
    "500": "🤒 伺服器感冒了：Google 那端暫時出了點問題，請稍後再試。",
    "quota": "📈 額度用完囉：今天的免費次數已達上限，明天請早，或換一個模型試試！",
    "499": "⚡ 連線逾時：音檔處理時間過長，已自動切換為分段模式處理。"
}

##### 2. 側邊欄：設定與金鑰輸入 [1]
with st.sidebar:
    st.header("設定")
    
    # 讓使用者自備金鑰
    api_key = st.text_input("輸入金鑰", type="password")
    
    # 新增：取得 API 金鑰的連結按鈕
    st.link_button("🔑 取得 Google API 金鑰", "https://aistudio.google.com/app/apikey")
    
    # 模型設定
    model_choice = st.selectbox(
        "選擇模型 (Gemini 3 系列)",
        [
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.5-flash",
            "gemini-3-flash-preview",
            "gemini-3.1-flash-lite-preview",
        ]
    )
    use_thinking = st.checkbox("啟用思考模式")

# --- 3. 工具函數：重疊切割音檔 ---
def split_audio_with_overlap(file_path, chunk_min=10, overlap_sec=30):
    """
    將音檔切割成有重疊的小段，避免斷句在關鍵處
    """
    audio = AudioSegment.from_file(file_path)
    chunk_length = chunk_min * 60 * 1000
    overlap = overlap_sec * 1000
    
    chunks = []
    start = 0
    count = 0
    
    while start < len(audio):
        end = start + chunk_length
        chunk = audio[start:end]
        chunk_name = f"chunk_{count}_{os.path.basename(file_path)}"
        chunk.export(chunk_name, format="mp4") # m4a 容器
        chunks.append(chunk_name)
        
        start += (chunk_length - overlap)
        count += 1
        if len(audio) - start < 30000: # 剩餘不足30秒則跳出
            break
    return chunks

# --- 4. 頁面設定 ---
st.set_page_config(page_title="我的 AI 秒聽錄音 - 專業分段版", layout="wide")
st.title("🎙️ 我的專屬 AI 錄音轉寫工具 (長音檔優化版)")
st.write("針對長音檔自動執行「切割、轉錄、去重、總結」流水線。")

# --- 5. 側邊欄：設定 ---
with st.sidebar:
    st.header("⚙️ 核心設定")
    # 模型設定
    model_choice = st.selectbox(
        "選擇模型 (Gemini 3 系列)",
        [
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.5-flash",
            "gemini-3-flash-preview",
            "gemini-3.1-flash-lite-preview",
        ]
    )
    use_thinking = st.checkbox("啟用思考模式")

    
    context_input = st.text_area(
        "專業背景描述 (重要)",
        placeholder="                   ",
        help="提供背景能大幅提升專有名詞辨識率"
    )
    
    chunk_size = st.slider("每段切割長度 (分鐘)", 5, 15, 10)

# --- 6. 上傳介面 ---
uploaded_files = st.file_uploader("上傳音檔 (支援多檔)", type=['mp3', 'wav', 'm4a'], accept_multiple_files=True)

if uploaded_files:
    for uploaded_file in uploaded_files:
        st.info(f"📁 已準備就緒：{uploaded_file.name}")

    if st.button("🚀 開始自動化分段處理"):
        for uploaded_file in uploaded_files:
            with st.status(f"正在處理：{uploaded_file.name}", expanded=True) as status:
                try:
                    # A. 儲存原始檔案
                    raw_filename = f"raw_{uploaded_file.name}"
                    with open(raw_filename, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                    # B. 執行重疊切割
                    st.write("正在進行重疊切割...")
                    chunks = split_audio_with_overlap(raw_filename, chunk_min=chunk_size)
                    
                    all_chunk_texts = []
                    progress_bar = st.progress(0)
                    
                    # C. 初始化模型
                    model = genai.GenerativeModel(
                        model_name=model_choice,
                        system_instruction="你是一位擁有20年經驗的「首席速記官與語意分析專家」。你具備極強的邏輯推理能力，能從模糊的語音資訊中，根據前後文精準還原對話內容。"
                    )

                    # D. 循序處理每一個片段
                    for i, chunk_path in enumerate(chunks):
                        st.write(f"正在轉錄第 {i+1}/{len(chunks)} 段...")
                        
                        google_file = genai.upload_file(path=chunk_path)
                        while google_file.state.name == "PROCESSING":
                            time.sleep(2)
                            google_file = genai.get_file(google_file.name)
                        
                        chunk_prompt = f"請逐字轉錄此片段。背景為：{context_input}。請標註說話人與時間戳。"
                        response = model.generate_content([chunk_prompt, google_file])
                        all_chunk_texts.append(response.text)
                        
                        progress_bar.progress((i + 1) / len(chunks))
                        os.remove(chunk_path) # 清理片段檔

                    # E. 大一統語意整合 (Grand Synthesis)
                    st.write("正在執行「大一統」語意整合與去重...")
                    full_raw_context = "\n\n--- 分段線 ---\n\n".join(all_chunk_texts)
                    
                    final_prompt = f"""
                    以下是長音檔分段轉錄的結果（包含重疊部分）。
                    請執行以下任務：
                    1.上下文校準：不要只進行單字轉譯。請掃描整段對話，若出現發音相似但邏輯不通的詞彙請根據語境與專有名詞庫自動修正。
                    2.專有名詞優先：對技術名詞、公司產品名、專案代號保持高度敏感。若語音模糊，請根據背景「{context_input}」修正所有專有名詞。
                    3.辨識不同的說話人（標註為 說話人 A, B...）。
                    4.每段話前加上 [mm:ss] 時間戳。
                    5.【精準去重】：移除段落接縫處重複的語句，整合成流暢的全文。
                    6.【結構化摘要】：提供 300 字摘要與 5 個行動重點。
                    7.【全文輸出】：輸出校正後的完整逐字稿。
                    
                    待處理文本：
                    {full_raw_context}
                    """
                    
                    final_response = model.generate_content(final_prompt)
                    
                    status.update(label="✅ 全文處理完成！", state="complete", expanded=False)

                    # F. 呈現結果
                    st.success(f"🎉 {uploaded_file.name} 處理完畢！")
                    st.subheader("📝 最終整合報告")
                    st.markdown(final_response.text)
                    
                    st.download_button(
                        label="📥 下載完整報告",
                        data=final_response.text,
                        file_name=f"Final_{uploaded_file.name}.md",
                        mime="text/markdown",
                        key=f"dl_{uploaded_file.name}"
                    )

                    # 最終清理
                    os.remove(raw_filename)

                except Exception as e:
                    error_msg = str(e)
                    for code, msg in ERROR_MESSAGES.items():
                        if code in error_msg:
                            error_msg = msg
                            break
                    st.error(f"錯誤：{error_msg}")
                    status.update(label="❌ 處理中斷", state="error")
import streamlit as st
import google.generativeai as genai
import os
import time

# 設定頁面 [1]
st.set_page_config(page_title="AI 錄音轉文字", layout="wide")

st.title("🎙️ AI 錄音轉寫工具") 
st.write("上傳音檔，讓 Gemini 3 系列幫你自動分段、辨識說話人與總結。")

##### 2. 側邊欄：設定與金鑰輸入 [1]
with st.sidebar:
    st.header("設定")
    
    # 讓使用者自備金鑰
    api_key = st.text_input("輸入金鑰", type="password")
    
    # 新增：取得 API 金鑰的連結按鈕
    st.link_button("🔑 取得 Google API 金鑰", "https://aistudio.google.com/app/apikey")
    
    # 模型設定
    model_choice = st.selectbox(
        "選擇模型 (Gemini 3 系列)",
        [
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.5-flash",
            "gemini-3-flash-preview",
            "gemini-3.1-flash-lite-preview",
        ]
    )
    use_thinking = st.checkbox("啟用思考模式")

# 檢查金鑰是否存在
if not api_key:
    st.warning("請輸入金鑰以啟用 AI 功能")
    st.stop()

# 若已輸入金鑰，則進行設定
genai.configure(api_key=api_key)

##### 3. 上傳檔案介面
uploaded_files = st.file_uploader("選擇錄音檔 (mp3, wav, m4a)", type=['mp3', 'wav', 'm4a'], accept_multiple_files=True)

# 檢查是否有上傳檔案 (此時 uploaded_files 會是一個列表)
if uploaded_files:
    # 使用 for 迴圈逐一處理上傳的每一個檔案
    for uploaded_file in uploaded_files:
        st.write(f"**音檔：{uploaded_file.name}**") # 顯示目前播放的檔名 (此行說明非來自來源，為因應多檔案新增的邏輯)
        st.audio(uploaded_file)
    
    if st.button("開始轉錄並生成摘要"):
        with st.status("正在處理音訊...", expanded=True) as status:
            try:
                # A. 儲存臨時檔案
                temp_filename = "temp_audio.mp3"
                with open(temp_filename, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # B. 上傳至 Google File API
                st.write("檔案上傳中...")
                audio_file = genai.upload_file(path=temp_filename)
                
                while audio_file.state.name == "PROCESSING":
                    time.sleep(2)
                    audio_file = genai.get_file(audio_file.name)
                
                st.write("AI 正在解析並思考內容...")
                
                # C. 初始化模型與設定
                model = genai.GenerativeModel(model_name=model_choice)
                
                # 設定生成參數 (含思考功能)
                gen_config = {}
                if use_thinking and "pro" in model_choice:
                    gen_config["thinking_config"] = {"include_thoughts": True}
                
                # D. 定義 Prompt
                prompt = """
                請幫我完成以下任務：
                1. 逐字轉錄這段音頻。
                2. 辨識不同的說話人（標註為 說話人 A, B...）。
                3. 每段話前加上 [mm:ss] 時間戳。
                4. 在最後提供一個簡潔的會議摘要與 3 個重點行動清單。
                """
                
                # E. 發送請求
                response = model.generate_content(
                    [prompt, audio_file],
                    generation_config=gen_config
                )
                
                status.update(label="轉錄完成！", state="complete", expanded=False)
                
                # F. 顯示結果與下載按鈕
                st.subheader("📝 轉錄結果與摘要")
                st.markdown(response.text)
                
                st.download_button(
                    label="📥 下載轉錄結果 (Markdown)",
                    data=response.text,
                    file_name="transcription_result.md",
                    mime="text/markdown"
                )
                
                # 清理
                os.remove(temp_filename)
                
            except Exception as e:
                st.error(f"發生錯誤：{e}")
