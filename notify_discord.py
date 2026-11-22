"""比對 HEAD 與工作區的 data.json，有學校資料變動就用 Discord Webhook 通知。"""
import json
import os
import subprocess
import sys

import requests

PAGE = "https://currywarrior.github.io/grad-exam-116/"


def load_old():
    out = subprocess.run(["git", "show", "HEAD:data.json"], capture_output=True, text=True, encoding="utf-8", check=True)
    return {s["id"]: s for s in json.loads(out.stdout)["schools"]}


def clean(s):
    # error 欄位只是當天檢查失敗的標記，不算「資料變動」
    return {k: v for k, v in s.items() if k != "error"}


def fmt_range(r):
    if not r:
        return "未定"
    return r[0] if len(r) == 1 or r[0] == r[-1] else f"{r[0]} ~ {r[-1]}"


def main():
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not url:
        print("沒有設定 DISCORD_WEBHOOK_URL，略過通知")
        return
    old = load_old()
    new = json.load(open("data.json", encoding="utf-8"))["schools"]
    embeds = []
    for s in new:
        if clean(s) == clean(old.get(s["id"], {})):
            continue
        label = s.get("examLabel", "筆試")
        embeds.append({
            "title": f"{s['name']} 簡章資料有更新",
            "url": s.get("link") or PAGE,
            "color": 0x2346A8,
            "fields": [
                {"name": "報名", "value": fmt_range(s.get("reg")), "inline": True},
                {"name": label, "value": fmt_range(s.get("exam")), "inline": True},
            ],
        })
    if not embeds:
        print("沒有變動，不通知")
        return
    # 一則訊息最多 10 個 embed，最後一個留給時程表預覽圖
    count = len(embeds)
    embeds = embeds[:9]
    embeds.append({
        "title": "116 碩考報名時程",
        "url": PAGE,
        "description": "日期由程式從簡章擷取，請以簡章為準。",
        "color": 0xC4362B,
        "image": {"url": PAGE + "og-image.png"},
    })
    r = requests.post(url, json={"content": "碩考時程表偵測到變動", "embeds": embeds}, timeout=15)
    r.raise_for_status()
    print(f"已通知 {count} 校")


if __name__ == "__main__":
    sys.exit(main())
