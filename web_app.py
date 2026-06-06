import os, requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
SHARE_CODE = os.getenv("SHARE_CODE", "")

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/optimize-prompt", methods=["POST"])
def optimize_prompt():
    data = request.get_json(force=True)
    if not GEMINI_API_KEY:
        return jsonify({"error": "伺服器未設定 GEMINI_API_KEY"}), 500
    if SHARE_CODE and data.get("code") != SHARE_CODE:
        return jsonify({"error": "共享密碼錯誤"}), 403

    prompt = data.get("prompt", "").strip()
    if not prompt:
        return jsonify({"error": "請輸入內容"}), 400

    payload = {
        "contents": [{
            "parts": [{
                "text": "You are a prompt engineer. Translate and expand the following user request into a detailed, cinematic English prompt for AI image generation. Output ONLY the final prompt text, nothing else. Request: " + prompt
            }]
        }]
    }
    try:
        resp = requests.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            json=payload,
            timeout=30,
        )
        if resp.status_code != 200:
            return jsonify({"error": f"Gemini 錯誤 ({resp.status_code})"}), 502
        result = resp.json()
        text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
        return jsonify({"optimized_prompt": text})
    except Exception as e:
        return jsonify({"error": str(e)[:200]}), 502


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
