import os, requests
from flask import Flask, render_template, request, jsonify, Response, stream_with_context

app = Flask(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
SHARE_CODE = os.getenv("SHARE_CODE", "").strip()
HF_TOKEN = os.getenv("HF_TOKEN", "").strip()

HF_MODEL = os.getenv("HF_MODEL", "black-forest-labs/FLUX.1-schnell").strip()
HF_API_BASE = os.getenv("HF_API_BASE", "https://router.huggingface.co/hf-inference").strip()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


@app.route("/")
def index():
    return render_template("index.html")


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


@app.route("/debug")
def debug():
    import socket, requests as req
    info = {
        "HF_TOKEN_SET": bool(HF_TOKEN),
        "HF_TOKEN_PREFIX": HF_TOKEN[:8] + "..." if HF_TOKEN else "N/A",
        "HF_MODEL": HF_MODEL,
        "GROQ_API_KEY_SET": bool(GROQ_API_KEY),
    }
    # DNS test
    hosts = ["router.huggingface.co", "api-inference.huggingface.co", "huggingface.co", "google.com"]
    for h in hosts:
        try:
            socket.getaddrinfo(h, 443)
            info[f"dns_{h}"] = True
        except Exception as e:
            info[f"dns_{h}"] = str(e)
    # Direct HTTP test to huggingface.co
    try:
        r = req.get("https://huggingface.co", timeout=10)
        info["http_huggingface"] = r.status_code
    except Exception as e:
        info["http_huggingface"] = str(e)[:100]
    # Test HF Inference API via direct IP or alternative
    try:
        r = req.post(
            f"https://api-inference.huggingface.co/models/runwayml/stable-diffusion-v1-5",
            json={"inputs": "test"},
            headers={"Authorization": f"Bearer {HF_TOKEN}"},
            timeout=15,
        )
        info["hf_api_status"] = r.status_code
        info["hf_api_response"] = r.text[:200]
    except Exception as e:
        info["hf_api_exception"] = str(e)[:200]
    return jsonify(info)


@app.route("/generate-image")
def generate_image():
    eng_prompt = request.args.get("prompt", "")
    seed = request.args.get("seed", "42")
    if not eng_prompt:
        return "Missing prompt", 400

    import time

    # Try Hugging Face Inference API
    if HF_TOKEN:
        headers = {
            "Authorization": f"Bearer {HF_TOKEN}",
        }
        payload = {"inputs": eng_prompt}
        models_to_try = [
            HF_MODEL,
            "runwayml/stable-diffusion-v1-5",
            "stabilityai/stable-diffusion-2-1",
        ]
        models_to_try = [HF_MODEL, "black-forest-labs/FLUX.1-schnell"]
        for model in models_to_try:
            try:
                url = f"{HF_API_BASE}/models/{model}"
                print(f"HF request: {url}")
                resp = requests.post(
                    url, json=payload, headers=headers, timeout=90,
                )
                if resp.status_code == 200:
                    ct = resp.headers.get("Content-Type", "")
                    if "image" in ct or len(resp.content) > 1000:
                        print(f"HF success: {model}, {len(resp.content)} bytes")
                        return Response(resp.content, mimetype=ct if "image" in ct else "image/jpeg")
                err = resp.text[:300] if resp.text else f"HTTP {resp.status_code}"
                print(f"  -> Failed: {err}")
            except Exception as e:
                print(f"  -> Exception: {e}")
    else:
        print("No HF_TOKEN configured")

    # Fallback: generate placeholder with prompt text
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io
        W, H = 512, 512
        img = Image.new("RGB", (W, H), (26, 26, 46))
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size=16)
        except Exception:
            font = ImageFont.load_default()
        lines = []
        line = ""
        for word in eng_prompt:
            test = f"{line}{word}"
            if d.textlength(test, font=font) > W - 40:
                lines.append(line)
                line = word
            else:
                line = test
        lines.append(line)
        y = (H - len(lines) * 24) // 2
        for line in lines:
            tw = d.textlength(line, font=font)
            d.text(((W - tw) // 2, y), line, fill=(180, 220, 255), font=font)
            y += 24
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return Response(buf.getvalue(), mimetype="image/png")
    except Exception as e:
        print(f"Pillow fallback failed: {e}")
        return jsonify({"error": "圖片生成服務忙碌，請稍後再試"}), 502


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
