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
    lines = []
    for s in new:
        if clean(s) == clean(old.get(s["id"], {})):
            continue
        label = s.get("examLabel", "筆試")
        lines.append(f"**{s['name']}** 簡章資料有更新\n報名：{fmt_range(s.get('reg'))}\n{label}：{fmt_range(s.get('exam'))}\n簡章：{s.get('link', '')}")
    if not lines:
        print("沒有變動，不通知")
        return
    content = "碩考時程表偵測到變動（日期由程式擷取，請以簡章為準）\n\n" + "\n\n".join(lines) + f"\n\n完整時程表：{PAGE}"
    r = requests.post(url, json={"content": content[:1900]}, timeout=15)
    r.raise_for_status()
    print(f"已通知 {len(lines)} 校")


if __name__ == "__main__":
    sys.exit(main())
