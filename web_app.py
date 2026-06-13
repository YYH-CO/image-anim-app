import os, requests, io, base64, traceback
from flask import Flask, render_template, request, jsonify, Response, stream_with_context

app = Flask(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
SHARE_CODE = os.getenv("SHARE_CODE", "").strip()
HF_TOKEN = os.getenv("HF_TOKEN", "").strip()

HF_MODEL = os.getenv("HF_MODEL", "black-forest-labs/FLUX.1-schnell").strip()
HF_API_BASE = os.getenv("HF_API_BASE", "https://router.huggingface.co/hf-inference").strip()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# In-memory history (max 20)
HISTORY = []


def add_history(zh_prompt, eng_prompt, mode, style, image_b64):
    import time
    entry = {
        "zh": zh_prompt[:200],
        "en": eng_prompt[:200],
        "mode": mode,
        "style": style,
        "image": image_b64,
        "time": int(time.time()),
    }
    HISTORY.append(entry)
    if len(HISTORY) > 20:
        HISTORY.pop(0)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/optimize-prompt", methods=["POST"])
def optimize_prompt():
    data = request.get_json(force=True)
    if not GROQ_API_KEY:
        return jsonify({"error": "伺服器未設定 GROQ_API_KEY"}), 500

    prompt = data.get("prompt", "").strip()
    mode = data.get("mode", "single").strip()
    style = data.get("style", "realistic").strip()
    code = data.get("code", "").strip()
    if not prompt:
        return jsonify({"error": "請輸入內容"}), 400
    if SHARE_CODE and code != SHARE_CODE:
        return jsonify({"error": "共享密碼錯誤"}), 403

    style_map = {
        "realistic": "photorealistic, highly detailed, cinematic lighting",
        "anime": "anime style, cel shaded, vibrant colors, Japanese animation",
        "watercolor": "watercolor painting style, soft edges, paper texture",
        "oilpainting": "oil painting on canvas, thick brushstrokes, impasto",
        "sketch": "pencil sketch, black and white, hand-drawn, cross-hatching",
        "pixel": "pixel art style, 8-bit retro game graphics, blocky pixels",
    }
    style_instruction = style_map.get(style, style_map["realistic"])

    if mode == "storyboard4":
        format_instruction = (
            "Generate a prompt for a 4-panel comic storyboard arranged in a 2x2 grid. "
            "Describe the entire layout first, then each panel sequentially: "
            "Panel 1 (top-left): ..., Panel 2 (top-right): ..., "
            "Panel 3 (bottom-left): ..., Panel 4 (bottom-right): .... "
            "Each panel should show a different scene or moment from the story. "
            "Include clear panel borders. Style: " + style_instruction
        )
    else:
        format_instruction = (
            "Generate a highly descriptive, vivid, detailed prompt for a single image. "
            "Style: " + style_instruction
        )

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "system",
                "content": "You are an expert AI image prompt engineer. Translate the user input into English and expand it into a detailed image generation prompt. " + format_instruction + " Output ONLY the raw final expanded prompt text. No explanations, markdown, or chat text."
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
    size_str = request.args.get("size", "1024x1024")
    negative_prompt = request.args.get("negative", "")
    zh_prompt = request.args.get("zh", "")  # original Chinese prompt
    mode = request.args.get("mode", "single")
    style_arg = request.args.get("style", "realistic")
    if not eng_prompt:
        return "Missing prompt", 400

    import time, base64

    parts = size_str.split("x")
    try:
        W, H = int(parts[0]), int(parts[1])
    except Exception:
        W, H = 1024, 1024

    # Try Pollinations (free, no key needed)
    try:
        from urllib.parse import quote
        poll_url = f"https://image.pollinations.ai/prompt/{quote(eng_prompt, safe='')}"
        params = {
            "width": str(W),
            "height": str(H),
            "seed": str(seed),
        }
        if negative_prompt:
            params["negative_prompt"] = negative_prompt
        print(f"Pollinations request: {poll_url} params={params}")
        resp = requests.get(poll_url, params=params, timeout=90)
        if resp.status_code == 200 and len(resp.content) > 1000:
            ct = resp.headers.get("Content-Type", "")
            if "image" in ct or len(resp.content) > 2000:
                print(f"Pollinations success: {len(resp.content)} bytes")
                b64 = base64.b64encode(resp.content).decode()
                add_history(zh_prompt, eng_prompt, mode, style_arg, b64)
                return Response(resp.content, mimetype=ct if "image" in ct else "image/jpeg")
        err_body = resp.text[:500] if resp.text else "empty"
        print(f"Pollinations failed: HTTP {resp.status_code}, {err_body}")
        return jsonify({"error": f"Pollinations: HTTP {resp.status_code}", "detail": err_body}), 502
    except Exception as e:
        print(f"Pollinations exception: {e}")
        return jsonify({"error": f"Pollinations 連線失敗", "detail": str(e)[:300]}), 502

    # Try Hugging Face Inference API (if credits remaining)
    hf_error = ""
    if HF_TOKEN:
        headers = {
            "Authorization": f"Bearer {HF_TOKEN}",
        }
        payload = {"inputs": eng_prompt}
        if negative_prompt:
            payload["parameters"] = {"negative_prompt": negative_prompt}

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
                        b64 = base64.b64encode(resp.content).decode()
                        add_history(zh_prompt, eng_prompt, mode, style_arg, b64)
                        return Response(resp.content, mimetype=ct if "image" in ct else "image/jpeg")
                err_text = resp.text[:500] if resp.text else f"HTTP {resp.status_code}"
                hf_error += f"[{model}] {err_text}\n"
                print(f"  -> Failed: {err_text}")
            except Exception as e:
                hf_error += f"[{model}] {str(e)[:200]}\n"
                print(f"  -> Exception: {e}")

    # Fallback: return error
    print(f"All providers failed.")
    return jsonify({"error": "所有圖片服務皆無法使用，請稍後再試"}), 502


@app.route("/history")
def history():
    return jsonify(list(reversed(HISTORY)))


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    msg = data.get("message", "").strip()
    history = data.get("history", [])
    if not msg:
        return jsonify({"error": "請輸入內容"}), 400
    if not GROQ_API_KEY:
        return jsonify({"error": "未設定 GROQ_API_KEY"}), 500

    messages = [{"role": "system", "content": "你是一個有用的 AI 助手。用繁體中文回答。"}]
    for h in history[-10:]:
        messages.append(h)
    messages.append({"role": "user", "content": msg})

    try:
        resp = requests.post(GROQ_URL, json={
            "model": "llama-3.3-70b-versatile",
            "messages": messages,
            "temperature": 0.7,
            "stream": True,
        }, headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }, timeout=30, stream=True)

        def generate():
            for line in resp.iter_lines():
                if line:
                    try:
                        d = line.decode().strip()
                        if d.startswith("data: "):
                            import json
                            j = json.loads(d[6:])
                            if "choices" in j and j["choices"]:
                                delta = j["choices"][0].get("delta", {}).get("content", "")
                                if delta:
                                    yield delta
                    except Exception:
                        continue

        return Response(stream_with_context(generate()), mimetype="text/plain")
    except Exception as e:
        return jsonify({"error": str(e)[:200]}), 502


@app.route("/tts")
def tts():
    # Backend TTS is unreliable via router; frontend uses browser Web Speech API
    # This endpoint is kept as fallback
    return jsonify({"error": "前端的瀏覽器語音 API 更穩定，請直接使用播放按鈕"}), 501


@app.route("/img2img", methods=["POST"])
def img2img():
    data = request.get_json(force=True)
    prompt = data.get("prompt", "").strip()
    image_b64 = data.get("image", "")
    if not prompt or not image_b64:
        return jsonify({"error": "需要 prompt 和圖片"}), 400
    if not HF_TOKEN:
        return jsonify({"error": "未設定 HF_TOKEN"}), 500

    import base64
    try:
        image_bytes = base64.b64decode(image_b64)
    except Exception:
        return jsonify({"error": "圖片格式錯誤"}), 400

    try:
        resp = requests.post(
            f"{HF_API_BASE}/models/stabilityai/stable-diffusion-2-1",
            json={"inputs": prompt, "image": image_b64},
            headers={"Authorization": f"Bearer {HF_TOKEN}"},
            timeout=60,
        )
        if resp.status_code == 200:
            ct = resp.headers.get("Content-Type", "")
            if "image" in ct or len(resp.content) > 1000:
                return Response(resp.content, mimetype=ct if "image" in ct else "image/jpeg")
        return jsonify({"error": resp.text[:200]}), 502
    except Exception as e:
        return jsonify({"error": str(e)[:200]}), 502


@app.route("/batch-generate")
def batch_generate():
    eng_prompt = request.args.get("prompt", "")
    count = int(request.args.get("count", "4"))
    size_str = request.args.get("size", "512x512")
    if not eng_prompt:
        return "Missing prompt", 400
    count = min(max(count, 1), 8)
    import base64, concurrent.futures, requests as req

    def fetch_one(seed):
        try:
            r = req.post(
                f"{HF_API_BASE}/models/{HF_MODEL}",
                json={"inputs": eng_prompt},
                headers={"Authorization": f"Bearer {HF_TOKEN}"},
                timeout=90,
            )
            if r.status_code == 200 and len(r.content) > 1000:
                return {"seed": seed, "image": base64.b64encode(r.content).decode()}
        except Exception:
            pass
        return None

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futures = [ex.submit(fetch_one, i) for i in range(count)]
        for f in concurrent.futures.as_completed(futures):
            r = f.result()
            if r:
                results.append(r)

    return jsonify({"images": results})


@app.route("/storyboard", methods=["POST"])
def storyboard():
    data = request.get_json(force=True)
    theme = data.get("theme", "").strip()
    style = data.get("style", "realistic").strip()
    code = data.get("code", "").strip()
    if not theme:
        return jsonify({"error": "請輸入故事主題"}), 400
    if SHARE_CODE and code != SHARE_CODE:
        return jsonify({"error": "共享密碼錯誤"}), 403
    if not GROQ_API_KEY:
        return jsonify({"error": "未設定 GROQ_API_KEY"}), 500

    style_map = {
        "realistic": "photorealistic style",
        "anime": "anime style, cel shaded",
        "watercolor": "watercolor painting style",
        "oilpainting": "oil painting style",
        "sketch": "pencil sketch style",
        "pixel": "pixel art style",
    }
    style_inst = style_map.get(style, style_map["realistic"])

    prompt = (
        f"你是一個 AI 故事作家。請以「{theme}」為主題，創作一個簡短的故事。\n\n"
        f"請輸出純 JSON（不要 markdown 格式），格式如下：\n"
        f'{{"title": "故事標題", "scenes": [{{"paragraph": "第一段文字", "prompt": "這段故事的英文圖像描述（{style_inst}）"}}, ...]}}\n\n'
        "要求：\n"
        "- 故事要有 3~4 個場景\n"
        "- paragraph 用繁體中文寫\n"
        "- prompt 用英文寫，是給 AI 繪圖用的詳細描述，包含角色、場景、氛圍\n"
        "- 只輸出 JSON，不要任何其他文字"
    )

    try:
        resp = requests.post(GROQ_URL, json={
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.8,
            "response_format": {"type": "json_object"},
        }, headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }, timeout=30)

        if resp.status_code != 200:
            return jsonify({"error": f"Groq 連線失敗 ({resp.status_code})"}), 502

        result = resp.json()
        text = result["choices"][0]["message"]["content"].strip()
        import json as json_mod
        try:
            parsed = json_mod.loads(text)
        except Exception:
            # try to extract JSON from markdown
            import re
            m = re.search(r'\{.*\}', text, re.DOTALL)
            if m:
                parsed = json_mod.loads(m.group())
            else:
                return jsonify({"error": "JSON 解析失敗", "raw": text[:500]}), 502
        return jsonify(parsed)
    except Exception as e:
        return jsonify({"error": str(e)[:200]}), 502


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
