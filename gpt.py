import json
import os
from flask import Flask, request, Response
import requests
from waitress import serve

CFG = {
    "bind_host": "0.0.0.0",
    "bind_port": 5550,
    "openai_api_key": "",
    "openai_base": "https://api.openai.com",
    "default_model": "gpt-4o-mini",
    "request_timeout_sec": 60,
}

def load_cfg():
    path = os.path.join(os.path.dirname(__file__), "config.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            user = json.load(f)
            CFG.update(user)
    except Exception as e:
        print("[CFG] Не удалось прочитать config.json:", e)
    print("[CFG] base:", CFG["openai_base"], "model:", CFG["default_model"])

load_cfg()

app = Flask(__name__)

def to_cp1251_json(obj) -> bytes:
    """
    Превращает Python-объект в JSON и кодирует в Windows-1251.
    Не представляющиеся символы заменяются на '?'
    """
    txt = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return txt.encode("cp1251", errors="replace")

def upstream_headers():
    return {
        "Authorization": f"Bearer {CFG['openai_api_key']}",
        "Content-Type": "application/json; charset=utf-8",
    }

def make_resp_bytes(data_obj, status=200):
    body = to_cp1251_json(data_obj)
    return Response(
        body,
        status=status,
        content_type="application/json; charset=windows-1251",
    )

@app.get("/ping")
def ping():
    info = {
        "ok": True,
        "base": CFG["openai_base"],
        "model": CFG["default_model"],
        "charset": "windows-1251"
    }
    return make_resp_bytes(info, 200)

@app.post("/v1/chat/completions")
def chat_completions():

    try:
        incoming = request.get_json(force=True, silent=False)
    except Exception as e:
        return make_resp_bytes({"error": f"Bad JSON: {e}"}, 400)


    payload = {
        "model": incoming.get("model") or CFG["default_model"],
        "messages": incoming.get("messages", []),
        "temperature": incoming.get("temperature", 0.7),
        "max_tokens": incoming.get("max_tokens"),
        "top_p": incoming.get("top_p"),
        "presence_penalty": incoming.get("presence_penalty"),
        "frequency_penalty": incoming.get("frequency_penalty"),
        "stop": incoming.get("stop"),
        "n": incoming.get("n"),
        # добавь нужные поля при необходимости
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    url = CFG["openai_base"].rstrip("/") + "/v1/chat/completions"

    try:
        r = requests.post(
            url,
            headers=upstream_headers(),
            json=payload,
            timeout=CFG["request_timeout_sec"],
        )
    except requests.RequestException as e:
        return make_resp_bytes({"error": f"upstream failed: {e}"}, 502)

    if r.status_code // 100 != 2:
        try:
            err = r.json()
        except Exception:
            err = {"error": r.text}
        return make_resp_bytes(err, r.status_code)

    try:
        data = r.json()
    except Exception:
        # крайний случай: текст → генерируем совместимый JSON
        data = {"text": r.text}

    return make_resp_bytes(data, 200)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5550)
