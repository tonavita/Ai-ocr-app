import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
import numpy as np
from streamlit_paste_button import paste_image_button
from datetime import datetime

# --- ページ設定 ---
st.set_page_config(page_title="AI OCR App", layout="wide")

# ==========================================
# 0. エラーメッセージの日本語変換関数
# ==========================================
def get_japanese_error_message(english_error_text):
    """英語のエラーを日本語の案内文に変換する"""
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

# --- タイトル ---
st.title("Ai OCR App")
st.write("サイドバーからモデルを選択し、画像をアップロードしてください。")

# --- セッションステート初期化 ---
if 'pasted_images' not in st.session_state:
    st.session_state.pasted_images = []

if 'ocr_result_text' not in st.session_state:
    st.session_state.ocr_result_text = ""

if 'ocr_filename_default' not in st.session_state:
    st.session_state.ocr_filename_default = ""

# --- APIキーの設定 ---
try:
    if "GOOGLE_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    else:
        st.error("⚠️ APIキーが見つかりません。Secretsの設定を確認してください。")
        st.stop()
except Exception as e:
    st.error(f"API設定エラー: {e}")
    st.stop()

# ==========================================
# サイドバー (設定エリア)
# ==========================================
with st.sidebar:
    st.header("⚙️ 設定")
    
    # ★★★ モデルリストを「使えるもの」だけに厳選 ★★★
    model_options = [
        "gemini-flash-lite-latest",  # 【デフォルト】最も制限が緩く軽量
        "gemini-1.5-flash",          # 標準的でバランスが良い
        "gemini-1.5-flash-8b",       # 超高速
        "gemini-2.0-flash-exp",      # 最新の実験版（性能高い）
    ]
    
    selected_model_name = st.selectbox(
        "使用するAIモデル",
        model_options,
        index=0  # 一番上（Lite）をデフォルトにする
    )

    try:
        model = genai.GenerativeModel(selected_model_name)
    except Exception as e:
        st.error(f"モデル設定エラー: {e}")

    st.divider()
    
    st.header("📤 画像入力")

    st.subheader("1. ファイルから選択")
    uploaded_files_from_pc = st.file_uploader(
        "画像を選択 (複数可)",
        type=['png', 'jpg', 'jpeg', 'webp'],
        accept_multiple_files=True,
        key="file_uploader"
    )

    st.divider()

    st.subheader("2. クリップボード")
    st.caption("画像をコピーし、ボタンを押すたびに追加されます。")
    
    paste_result = paste_image_button(
        label="📋 画像をペースト (追加)",
        background_color="#7E9469",
        hover_background_color="#6A8055",
        key="paste_btn"
    )

    if paste_result.image_data is not None:
        is_new_image = False
        if len(st.session_state.pasted_images) == 0:
            is_new_image = True
        else:
            last_img = st.session_state.pasted_images[-1]
            if paste_result.image_data != last_img:
                is_new_image = True
        
        if is_new_image:
            st.session_state.pasted_images.append(paste_result.image_data)
            st.toast("画像を追加しました！", icon="📋")

    if len(st.session_state.pasted_images) > 0:
        st.write(f"**現在のペースト枚数: {len(st.session_state.pasted_images)}枚**")
        
        if st.button("🗑️ ペースト履歴をクリア"):
            st.session_state.pasted_images = []
            st.session_state.ocr_result_text = ""
            st.session_state.ocr_filename_default = ""
            st.rerun()

        st.caption("追加済みリスト:")
        cols = st.columns(3)
        for i, img in enumerate(st.session_state.pasted_images):
            with cols[i % 3]:
                st.image(img, use_container_width=True)

# ==========================================
# メイン処理
# ==========================================
target_images = []

if uploaded_files_from_pc:
    for up_file in uploaded_files_from_pc:
        target_images.append((Image.open(up_file), up_file.name))

if st.session_state.pasted_images:
    for i, p_img in enumerate(st.session_state.pasted_images):
        target_images.append((p_img, f"📋 ペースト画像_{i+1}"))

if target_images:
    st.divider()
    st.subheader(f"📸 読み取り対象: 合計 {len(target_images)} 枚 (モデル: {selected_model_name})")

    cols = st.columns(min(len(target_images), 6))
    for idx, (img, name) in enumerate(target_images):
        with cols[idx % len(cols)]:
             st.image(img, use_container_width=True, caption=f"{idx+1}")

    st.divider()

    if st.button('まとめてOCR開始', type="primary"):
        # 前回の結果をクリア
        st.session_state.ocr_result_text = ""
        
        progress_bar = st.progress(0)
        total_files = len(target_images)
        current_results = ""

        for i, (image, name) in enumerate(target_images):
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.markdown(f"**📄 {i+1}枚目: {name}**")
                st.image(image, use_container_width=True)
            
            with col2:
                with st.spinner(f'{selected_model_name} で解析中...'):
                    try:
                        prompt = "この画像の手書き文字をすべてテキスト化してください。誤字脱字を修正せず、そのまま読み取ってください。"
                        response = model.generate_content([prompt, image])
                        
                        text_result = response.text
                        st.success("完了")
                        st.text_area(f"読み取り結果 ({name})", text_result, height=200)
                        
                        current_results += f"--- {name} の結果 ---\n{text_result}\n\n"

                    except Exception as e:
                        jp_msg = get_japanese_error_message(str(e))
                        st.error(f"エラーが発生しました: {jp_msg}")
                        st.warning("⚠️ モデルを変更するか、時間を置いて再試行してください。")
                        current_results += f"--- {name} (エラー) ---\n{jp_msg}\n\n"
            
            st.divider()
            progress_bar.progress((i + 1) / total_files)
        
        # 結果を保存
        st.session_state.ocr_result_text = current_results
        
        # ファイル名を一度だけ生成
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        st.session_state.ocr_filename_default = f"ocr_result_{timestamp}.txt"
        
        st.success("🎉 すべて完了しました！下にダウンロードボタンが表示されます。")

# ==========================================
# ダウンロードエリア
# ==========================================
if st.session_state.ocr_result_text:
    st.markdown("### 💾 結果の保存")
    st.info("ファイル名を変更する場合は、入力後に Enter キーを押して確定してください。")
    
    col_dl1, col_dl2 = st.columns([1, 1])
    
    with col_dl1:
        # 保存された固定のファイル名を初期値として使う
        file_name_input = st.text_input(
            "ファイル名を入力してください", 
            value=st.session_state.ocr_filename_default
        )
        
        if not file_name_input.endswith(".txt"):
            file_name_input += ".txt"
            
    with col_dl2:
        st.write("") 
        st.write("") 
        
        st.download_button(
            label="📄 結果をテキストファイルでダウンロード",
            data=st.session_state.ocr_result_text,
            file_name=file_name_input, 
            mime="text/plain",
            type="primary"
        )
