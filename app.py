import streamlit as st
import google.generativeai as genai
from streamlit_paste_button import paste_image_button
from PIL import Image
import time

# ==========================================
# 1. APIキーの設定
# ==========================================
try:
    if "GOOGLE_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    else:
        st.error("⚠️ APIキーが見つかりません。Secretsに 'GOOGLE_API_KEY' を設定してください。")
except Exception as e:
    st.error(f"設定エラー: {e}")

# ==========================================
# 2. エラーメッセージ変換ロジック
# ==========================================
def get_japanese_error_message(english_error_text):
    if not english_error_text: return "不明なエラーが発生しました。"
    lower_error = str(english_error_text).lower()

    if any(k in lower_error for k in ["limit", "quota", "exceeded", "429"]):
        return "回数制限の上限に達しました。\n※時間を置くか、設定を見直してください。"
    
    if any(k in lower_error for k in ["timeout", "network", "connection"]):
        return "通信がタイムアウトしました。\n通信環境を確認して再度お試しください。"

    if any(k in lower_error for k in ["server", "500", "unavailable"]):
        return "サーバーで一時的なエラーが発生しています。\n時間を置いてから再度お試しください。"

    if any(k in lower_error for k in ["image", "format", "size"]):
        return "画像の読み込みに失敗しました。\n画像の形式やサイズをご確認ください。"

    return f"予期せぬエラーが発生しました。\n(Error: {english_error_text})"

# ==========================================
# 3. アプリの画面構成
# ==========================================
st.title("AI OCRアプリ 🤖")

# --- セッション情報の初期化 ---
if 'pasted_images' not in st.session_state:
    st.session_state.pasted_images = []

st.write("---")

# ★★★ レイアウト修正箇所：ここから ★★★
# 2つのカラム（列）を作って、ボタンを横に並べます
col1, col2 = st.columns([1, 1])

with col1:
    st.write("##### 1. 画像を追加")
    # ペーストボタン
    paste_result = paste_image_button(
        label="📋 画像をペースト",
        background_color="#4CAF50",
        hover_background_color="#45a049",
    )
    # 画像追加処理
    if paste_result.image_data is not None:
        if len(st.session_state.pasted_images) == 0 or \
           st.session_state.pasted_images[-1] != paste_result.image_data:
            st.session_state.pasted_images.append(paste_result.image_data)

with col2:
    st.write(f"##### 2. 現在の枚数: {len(st.session_state.pasted_images)}枚")
    # クリアボタン
    if st.button("🗑️ 履歴をクリア", use_container_width=True):
        st.session_state.pasted_images = []
        st.rerun()
# ★★★ レイアウト修正箇所：ここまで ★★★

st.write("---")

# --- プレビューエリア（画像があるときだけ表示） ---
if st.session_state.pasted_images:
    st.write("##### ▼ 追加された画像リスト")
    st.image(st.session_state.pasted_images, width=120, caption=[f"No.{i+1}" for i in range(len(st.session_state.pasted_images))])

st.write("") # 余白

# --- OCR実行ボタン ---
st.write("##### 3. 読み取り実行")

if st.button("🚀 OCR開始 (テキスト化)", type="primary", use_container_width=True):
    if not st.session_state.pasted_images:
        st.warning("画像がありません。まずは「画像をペースト」してください。")
    else:
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        progress_bar = st.progress(0)
        total_images = len(st.session_state.pasted_images)
        all_results_text = "" # テキスト保存用

        for i, img in enumerate(st.session_state.pasted_images):
            try:
                with st.spinner(f"{i+1} / {total_images} 枚目を解析中..."):
                    response = model.generate_content([
                        "この画像に書かれている文字をすべて書き出してください。整形は不要です。", 
                        img
                    ])
                    text_result = response.text
                    
                    # 結果表示
                    st.success(f"✅ 画像 No.{i+1} の結果")
                    st.text_area(label=f"結果テキスト {i+1}", value=text_result, height=150)
                    
                    # テキスト結合
                    all_results_text += f"--- 画像 No.{i+1} の結果 ---\n{text_result}\n\n"
            
            except Exception as e:
                jp_msg = get_japanese_error_message(str(e))
                st.error(f"❌ {i+1}枚目でエラー: {jp_msg}")
                all_results_text += f"--- 画像 No.{i+1} (エラー) ---\n{jp_msg}\n\n"
            
            progress_bar.progress((i + 1) / total_images)

        st.success("🎉 すべての処理が完了しました！")
        
        # ダウンロードボタン
        st.download_button(
            label="📄 結果をテキストファイルでダウンロード",
            data=all_results_text,
            file_name="ocr_result.txt",
            mime="text/plain",
            use_container_width=True
        )
