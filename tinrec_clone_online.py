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
