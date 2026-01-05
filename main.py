import os
import requests
import base64
import json
import sys
import google.generativeai as genai
from PIL import Image
from io import BytesIO

# 設定読み込み
REFRESH_TOKEN = os.environ["CANVA_REFRESH_TOKEN"]
CLIENT_ID = os.environ["CANVA_CLIENT_ID"]
CLIENT_SECRET = os.environ["CANVA_CLIENT_SECRET"]
DESIGN_ID = os.environ["CANVA_DESIGN_ID"]
LINE_TOKEN = os.environ["LINE_TOKEN"]
LINE_USER_ID = os.environ["LINE_USER_ID"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

genai.configure(api_key=GEMINI_API_KEY)

def get_new_tokens():
    """新しいアクセストークンとリフレッシュトークンを取得"""
    url = "https://api.canva.com/rest/v1/oauth/token"
    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    b64_auth = base64.b64encode(auth_str.encode()).decode()
    headers = {
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {"grant_type": "refresh_token", "refresh_token": REFRESH_TOKEN}
    
    resp = requests.post(url, headers=headers, data=data)
    if resp.status_code != 200:
        print(f"★トークン更新エラー: {resp.text}")
        return None, None
    
    tokens = resp.json()
    return tokens.get("access_token"), tokens.get("refresh_token")

def analyze_image_with_gemini(image_bytes):
    print("Gemini: 解析中...")
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        image = Image.open(BytesIO(image_bytes))
        prompt = """
        このエクセル画像の表の内容を読み取り、LINEで見やすいテキストにまとめてください。
        タイトルを明確にし、データは箇条書きで見やすく整理して。
        """
        response = model.generate_content([prompt, image])
        return response.text
    except Exception as e:
        print(f"Geminiエラー: {e}")
        return "読み取り失敗"

def main():
    # 1. トークン更新
    access_token, new_refresh_token = get_new_tokens()
    if not access_token: sys.exit(1)

    # ★重要：新しいリフレッシュトークンをGitHub Actionsに渡す処理
    if new_refresh_token:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f"new_refresh_token={new_refresh_token}\n")
        print("★新しいリフレッシュトークンを取得しました（自動保存待機中）")

    # 2. 画像情報取得
    url = f"https://api.canva.com/rest/v1/designs/{DESIGN_ID}"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(url, headers=headers)
    thumbnail_url = resp.json().get("design", {}).get("thumbnail", {}).get("url")

    if not thumbnail_url: 
        print("サムネイルなし")
        sys.exit(1)

    # 3. 画像ダウンロード & Gemini解析
    img_resp = requests.get(thumbnail_url)
    text_msg = analyze_image_with_gemini(img_resp.content)
    print("Gemini解析完了")

    # 4. LINE送信
    line_url = "https://api.line.me/v2/bot/message/push"
    headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "to": LINE_USER_ID,
        "messages": [
            {"type": "image", "originalContentUrl": thumbnail_url, "previewImageUrl": thumbnail_url},
            {"type": "text", "text": text_msg}
        ]
    }
    requests.post(line_url, headers=headers, json=payload)
    print("送信成功")

if __name__ == "__main__":
    main()
