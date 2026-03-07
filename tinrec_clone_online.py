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
    "499": "⚡ 連線逾時：音檔處理時間過長，請改成切八段模式處理。"
}

# --- 2. 頁面設定 ---
st.set_page_config(page_title="AI 批次轉寫工具", layout="wide")

# --- 3. 輔助函數：強制判定 MIME 類型 ---
def get_valid_mime_type(filename):
    """根據副檔名回傳 Google API 支援的標準格式"""
    ext = filename.split('.')[-1].lower()
    mime_map = {
        "mp3": "audio/mpeg",
        "m4a": "audio/mp4",
        "wav": "audio/wav",
        "aac": "audio/aac",
        "ogg": "audio/ogg",
        "flac": "audio/flac"
    }
    return mime_map.get(ext, "application/octet-stream")

# --- 4. 側邊欄：統一設定區 ---
with st.sidebar:
    st.header("設定")
    api_key = st.text_input("輸入金鑰", type="password")
    st.link_button("🔑 取得 Google API 金鑰", "https://aistudio.google.com/app/apikey")
    
    model_choice = st.selectbox(
        "選擇模型（依照個人權限選擇）",
        [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-2.5-flash-lite",
            "gemini-3-flash-preview",
            "gemini-3.1-pro-preview",
            "gemini-3.1-flash-lite-preview",
        ]
    )
                    
    # 💡 根據最新文件，加入動態思考層級的設定
    gen_config = {}

    # 如果你在側邊欄勾選了「啟用思考模式」，且模型名稱包含 pro 或 3 系列
    if use_thinking:
        gen_config["thinking_config"] = {
    # "low" 可以縮短延遲並降低成本，適合指令遵循；
    # 如果遇到非常複雜的音檔，可以改成 "medium" 或 "high"
        "thinking_level": "low" 
        }
                    
    # 執行生成
    response = model.generate_content(
        [chunk_prompt, audio_file],
        generation_config=gen_config,
        request_options={"timeout": 600}
    )
    context_input = st.text_area(
        "專業背景描述 (重要)",
        placeholder="盡可能描述音檔背景、專業範圍...",
        help="提供背景能大幅提升專有名詞辨識率"
    )

# --- 5. 主頁面邏輯 ---
st.title("🎙️ 我的專屬 AI 錄音轉寫工具 (長音檔優化版)")
st.write("針對分段音檔自動執行「上傳、轉錄、每段逐字稿（逐字稿請自行複製貼上）、總結」流水線。")

if not api_key:
    st.warning("👈 請在側邊欄輸入 API 金鑰以啟用功能。")
    st.stop()

genai.configure(api_key=api_key)

# --- 6. 上傳檔案介面 ---
uploaded_files = st.file_uploader("選擇錄音檔 (mp3, wav, m4a)", type=['mp3', 'wav', 'm4a'], accept_multiple_files=True)

if uploaded_files:
    # 按照檔名排序，確保轉錄順序正確
    sorted_files = sorted(uploaded_files, key=lambda x: x.name)
    
    for uploaded_file in sorted_files:
        st.write(f"**已就緒：{uploaded_file.name}**")
        st.audio(uploaded_file)
    
    if st.button("開始轉錄並生成摘要"):
        all_transcripts = [] # 初始化存放所有轉錄結果的列表
        full_progress = st.progress(0) # 初始化進度條
        
        # --- 第一階段：逐一轉錄各個片段 ---
        for idx, uploaded_file in enumerate(sorted_files):
            with st.status(f"正在處理片段：{uploaded_file.name}...", expanded=True) as status:
                try:
                    # A. 儲存臨時檔案
                    temp_filename = f"temp_{uploaded_file.name}"
                    with open(temp_filename, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    # B. 上傳至 Google File API 並指定 MIME 類型
                    st.write("檔案上傳中...")
                    mime_type = get_valid_mime_type(uploaded_file.name)
                    audio_file = genai.upload_file(path=temp_filename, mime_type=mime_type)
                    
                    while audio_file.state.name == "PROCESSING":
                        time.sleep(2)
                        audio_file = genai.get_file(audio_file.name)
                    
                    # C. 初始化模型
                    model = genai.GenerativeModel(
                        model_name=model_choice,
                        system_instruction="你是一位擁有20年經驗的「首席速記官與語意分析專家」。你具備極強的邏輯推理能力，能從模糊的語音資訊中，根據前後文精準還原對話內容。"
                    )
                    
                   # D. 執行單段轉錄
                    st.write("AI 正在進行高精度轉錄與校對...")
                    
                    # 💡 將原本放在最後的「苦力活」全部移到這裡，讓 AI 分段處理！
                    chunk_prompt = f"""
                    請聽取這段音訊片段，並執行高品質的「完整逐字轉錄」。
                    請務必嚴格遵守以下 5 項規範：
                    1. 【精確轉錄】：將聽到的所有內容完整轉成文字，保留對話細節，**絕對不要擅自總結或刪減任何語句**。
                    2. 【上下文校準】：不要只做單字轉譯，請掃描整段對話，若出現發音相似但邏輯不通的詞彙，請自動修正。
                    3. 【專有名詞優先】：對技術名詞、公司產品名保持高度敏感。請根據背景資訊，自動修正模糊的專有名詞。
                    4. 【辨識說話人】：請分辨不同的說話人，並在每段話開頭標註（例如：說話人 A、說話人 B）。
                    5. 【加入時間戳】：在每個說話段落開頭，加上相對應的時間戳（例如：[00:15]）。
                    
                    提供的背景資訊/專有名詞庫：
                    {context_input}
                    """
                    
                    gen_config = {}
                    if use_thinking and "pro" in model_choice:
                        gen_config["thinking_config"] = {"include_thoughts": True}
                    
                    response = model.generate_content(
                        [chunk_prompt, audio_file],
                        generation_config=gen_config,
                        request_options={"timeout": 600}
                    )
                    
                    all_transcripts.append(response.text)
                    st.markdown(f"**{uploaded_file.name} 轉錄草稿：**")
                    st.write(response.text)
                    
                    status.update(label=f"✅ {uploaded_file.name} 處理完成", state="complete")
                    os.remove(temp_filename) # 清理

                except Exception as e:
                    error_str = str(e)
                    for code, msg in ERROR_MESSAGES.items():
                        if code in error_str:
                            error_str = msg
                            break
                    st.error(f"發生錯誤：{error_str}")
                    status.update(label="❌ 處理失敗", state="error")
            
            full_progress.progress((idx + 1) / len(sorted_files))

        # --- 第二階段：大一統整合 (當所有片段轉錄完成後) ---
        if all_transcripts:
            st.divider()
            with st.status("✨ 正在執行最終整合與摘要...", expanded=True) as status:
                full_raw_context = "\n\n--- 分段線 ---\n\n".join(all_transcripts)
                
                final_prompt = f"""
                以下是一份長達數小時的完整會議紀錄。
                請詳讀完整內容後，執行以下任務（請注意，不需要重寫逐字稿）：
                1. 【結構化摘要】：提供 300-500 字的高品質會議摘要。
                2. 【行動重點】：列出具體的後續待辦事項與負責人。

                待處理會議紀錄：
                {full_raw_context}
                """
                
                final_response = model.generate_content(final_prompt)
                
                st.subheader("📝 最終整合報告（下載報告前請確認分段逐字稿已經複製貼上，下載後記錄將清空）")
                st.markdown(final_response.text)
                status.update(label="✅ 全文處理完成！", state="complete")

                st.download_button(
                    label="📥 下載完整報告 (Markdown)",
                    data=final_response.text,
                    file_name="Final_Transcription_Report.md",
                    mime="text/markdown"
                )
