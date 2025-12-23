import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
import numpy as np
from streamlit_paste_button import paste_image_button

# --- ページ設定 ---
st.set_page_config(page_title="AI OCR App", layout="wide")

# --- タイトル ---
st.title("Ai OCR App")
st.write("サイドバーからモデルを選択し、画像をアップロードしてください。")

# --- セッションステート初期化（ペースト履歴用） ---
if 'pasted_images' not in st.session_state:
    st.session_state.pasted_images = []

# --- APIキーの設定 ---
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except:
    st.error("APIキーが見つかりません。Secretsの設定を確認してください。")
    st.stop()

# ==========================================
# サイドバー (設定エリア)
# ==========================================
with st.sidebar:
    st.header("⚙️ 設定")
    
    # モデル選択
    model_options = [
        "gemini-1.5-flash",          # 推奨
        "gemini-flash-lite-latest",  # 軽量
        "gemini-1.5-flash-8b",       # 超高速
        "gemini-1.5-pro",            # 高精度
        "gemini-2.0-flash-exp",      # 実験版
    ]
    
    selected_model_name = st.selectbox(
        "使用するAIモデル",
        model_options,
        index=0
    )

    try:
        model = genai.GenerativeModel(selected_model_name)
    except Exception as e:
        st.error(f"モデル設定エラー: {e}")

    st.divider()
    
    st.header("📤 画像入力")

    # 1. ファイルアップロード
    st.subheader("1. ファイルから選択")
    uploaded_files_from_pc = st.file_uploader(
        "画像を選択 (複数可)",
        type=['png', 'jpg', 'jpeg', 'webp'],
        accept_multiple_files=True,
        key="file_uploader"
    )

    st.divider()

    # 2. クリップボードからペースト（複数対応版）
    st.subheader("2. クリップボード")
    st.caption("画像をコピーし、ボタンを押すたびに追加されます。")
    
    # ペーストボタン
    paste_result = paste_image_button(
        label="📋 画像をペースト (追加)",
        background_color="#7E9469",
        hover_background_color="#6A8055",
        key="paste_btn"
    )

    # --- 履歴追加ロジック ---
    if paste_result.image_data is not None:
        # 重複追加を防ぐため、リストが空か、または最後の画像と違う場合のみ追加
        # (注: 画像データの比較は簡易的に行います)
        is_new_image = False
        
        if len(st.session_state.pasted_images) == 0:
            is_new_image = True
        else:
            # 最新の履歴と比較（同じ画像を連続で貼ろうとした場合は無視する設定）
            # ※完全に厳密な比較は重くなるため、簡易的なチェック
            last_img = st.session_state.pasted_images[-1]
            if paste_result.image_data != last_img:
                is_new_image = True
        
        if is_new_image:
            st.session_state.pasted_images.append(paste_result.image_data)
            # 追加した瞬間に通知
            st.toast("画像を追加しました！", icon="📋")

    # --- ペースト履歴の表示とクリア ---
    if len(st.session_state.pasted_images) > 0:
        st.write(f"**現在のペースト枚数: {len(st.session_state.pasted_images)}枚**")
        
        # 履歴クリアボタン
        if st.button("🗑️ ペースト履歴をクリア"):
            st.session_state.pasted_images = []
            st.rerun()

        # 小さくサムネイル表示
        st.caption("追加済みリスト:")
        cols = st.columns(3)
        for i, img in enumerate(st.session_state.pasted_images):
            with cols[i % 3]:
                st.image(img, use_container_width=True)

# ==========================================
# メイン処理
# ==========================================
target_images = []

# 1. アップロード画像の追加
if uploaded_files_from_pc:
    for up_file in uploaded_files_from_pc:
        target_images.append((Image.open(up_file), up_file.name))

# 2. ペースト履歴画像の追加（ここが変更点）
if st.session_state.pasted_images:
    for i, p_img in enumerate(st.session_state.pasted_images):
        # 名前は自動的に連番を振る
        target_images.append((p_img, f"📋 ペースト画像_{i+1}"))

# --- 画像があれば処理開始ボタンを表示 ---
if target_images:
    st.divider()
    st.subheader(f"📸 読み取り対象: 合計 {len(target_images)} 枚 (モデル: {selected_model_name})")

    # メインエリアにプレビュー
    cols = st.columns(min(len(target_images), 6))
    for idx, (img, name) in enumerate(target_images):
        with cols[idx % len(cols)]:
             st.image(img, use_container_width=True, caption=f"{idx+1}")

    st.divider()

    if st.button('まとめてOCR開始', type="primary"):
        progress_bar = st.progress(0)
        total_files = len(target_images)

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
                        st.success("完了")
                        st.text_area(f"読み取り結果 ({name})", response.text, height=200)
                    except Exception as e:
                        st.error(f"エラーが発生しました: {e}")
                        st.warning("⚠️ モデルを変更して再試行してください。")
            
            st.divider()
            progress_bar.progress((i + 1) / total_files)
        
        st.success("🎉 すべて完了しました！")
