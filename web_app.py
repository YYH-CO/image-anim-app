import os, requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
SHARE_CODE = os.getenv("SHARE_CODE", "").strip()
POLLINATIONS_KEY = os.getenv("POLLINATIONS_KEY", "").strip()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


@app.route("/")
def index():
    return render_template("index.html", poll_key=POLLINATIONS_KEY)


@app.route("/optimize-prompt", methods=["POST"])
def optimize_prompt():
    data = request.get_json(force=True)
    if not GROQ_API_KEY:
        return jsonify({"error": "伺服器未設定 GROQ_API_KEY"}), 500
    if SHARE_CODE and data.get("code") != SHARE_CODE:
        return jsonify({"error": "共享密碼錯誤"}), 403

    prompt = data.get("prompt", "").strip()
    if not prompt:
        return jsonify({"error": "請輸入內容"}), 400

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "system",
                "content": "You are an expert AI image prompt engineer. Translate the user input into English and expand it into a highly descriptive, vivid, detailed prompt for image generation. Output ONLY the raw final expanded prompt text. No explanations, markdown, or chat text."
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
    }
    try:
        resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=20)
        if resp.status_code != 200:
            print(f"Groq Error: {resp.text}")
            return jsonify({"error": f"Groq 連線失敗 ({resp.status_code})"}), 502
        result = resp.json()
        text = result["choices"][0]["message"]["content"].strip()
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1].strip()
        return jsonify({"optimized_prompt": text})
    except Exception as e:
        return jsonify({"error": f"連線異常: {str(e)[:200]}"}), 502


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
