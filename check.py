"""每天檢查各校官網，偵測 116 學年度碩士班「考試入學」簡章是否公告，並試著從簡章 PDF 抓報名與筆試日期。

只處理 data.json 裡 status 還不是 "out" 的學校；已公告的資料不動（那些是人工核對過的）。
"""
import io
import json
import re
import sys
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from playwright.sync_api import sync_playwright
from pypdf import PdfReader

DATA = Path(__file__).with_name("data.json")
TW = timezone(timedelta(hours=8))
TLJ = "https://adms.site.nthu.edu.tw/p/412-1207-3107.php?Lang=zh-tw"  # 台聯大聯招（清大、陽明交大資工類走這裡）

# 每校要掃的頁面
PAGES = {
    "ntust": ["https://www.admission.ntust.edu.tw/"],
    "nsysu": ["https://oaa.nsysu.edu.tw/"],
    "ntut": ["https://graduate.ntut.edu.tw/"],
    "ntu": ["https://exam.aca.ntu.edu.tw/graf/brochure/"],
    "nthu": [TLJ, "https://adms.site.nthu.edu.tw/p/412-1207-3106.php?Lang=zh-tw"],
    "nycu": [TLJ, "https://exam.nycu.edu.tw/ma-me.html"],
    "ncku": ["https://adms-acad.ncku.edu.tw/p/406-1044-227148,r3265.php?Lang=zh-tw"],
    "ccu": ["https://exams.ccu.edu.tw/"],
}

EXCLUDE = re.compile(r"甄試|在職|博士|產業|僑|陸生|外國|境外|轉學|特殊選才|學士|遞補|榜單|名單|錄取|統計|人數|日程|預定|延長|退費|QA")
ROC_DATE = re.compile(r"(1[01]\d)[年./-](\d{1,2})[月./-](\d{1,2})日?")


def norm(s):
    # NFKC：PDF 常用相容字元（例如 U+F98E 的「年」），也順便把全形括號轉半形
    s = re.sub(r"\s+", "", unicodedata.normalize("NFKC", s))
    # 「碩士班(含在職專班)」這種寫法不算在職專班
    return re.sub(r"\(?[含及暨與、]碩?士?在職專班\)?", "", s)


def is_target(text):
    t = norm(text)
    return "116" in t and "碩士" in t and re.search(r"考試|簡章|聯合招生", t) and not EXCLUDE.search(t)


def roc(y, m, d):
    try:
        return date(int(y) + 1911, int(m), int(d))
    except ValueError:
        return None


def find_dates(window):
    out = []
    for m in ROC_DATE.finditer(window):
        d = roc(*m.groups())
        if d:
            out.append((d, m.end()))
    return out


def extract_dates(text):
    t = norm(text)
    reg = exam = None
    for kw in re.finditer(r"網路報名|報名期間|報名日期|報名時間", t):
        ds = find_dates(t[kw.start(): kw.start() + 160])
        if len(ds) >= 2:
            a, b = ds[0][0], ds[1][0]
            if date(2026, 10, 15) <= a <= date(2027, 1, 31) and 0 <= (b - a).days <= 40:
                reg = [a.isoformat(), b.isoformat()]
                break
    for kw in re.finditer(r"筆試", t):
        win = t[kw.start(): kw.start() + 80]
        ds = find_dates(win)
        if ds and date(2027, 1, 10) <= ds[0][0] <= date(2027, 3, 15):
            d1, end = ds[0]
            exam = [d1.isoformat()]
            # 「116年1月29日至30日」這種同月連續兩天
            more = re.match(r"(\(.\))?[至~～-](\d{1,2})日", win[end:])
            if more:
                d2 = d1.replace(day=int(more.group(2)))
                if d2 > d1:
                    exam.append(d2.isoformat())
            break
    return reg, exam


def pdf_text(url):
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    reader = PdfReader(io.BytesIO(r.content))
    return "\n".join((p.extract_text() or "") for p in reader.pages[:12])


def goto(page, url):
    # 有些校網一直有背景連線，等不到 networkidle，改成 load 後多等 3 秒讓 JS 把公告載出來
    page.goto(url, wait_until="load", timeout=60000)
    page.wait_for_timeout(3000)


def anchors(page):
    return page.evaluate("() => [...document.querySelectorAll('a')].map(a => [a.innerText || a.title || '', a.href])")


def find_pdf(page, href):
    """候選連結本身是 PDF 就直接用；不是的話打開那頁找簡章 PDF。"""
    if ".pdf" in href.lower():
        return href
    goto(page, href)
    pdfs = [(t, h) for t, h in anchors(page) if ".pdf" in h.lower() and "甄試" not in t]
    pdfs.sort(key=lambda x: ("簡章" not in x[0], "全" not in x[0]))
    return pdfs[0][1] if pdfs else None


def check_school(page, sid):
    for url in PAGES[sid]:
        goto(page, url)
        if sid == "ntu":
            # 台大簡章頁是分區塊列連結，看有沒有出現「碩士班考試」區塊
            body = norm(page.inner_text("body"))
            if re.search(r"碩士班(招生)?考試", body):
                return {"link": url, "reg": None, "exam": None}
            continue
        for text, href in anchors(page):
            if href and is_target(text):
                link = urljoin(url, href)
                reg = exam = None
                try:
                    pdf = find_pdf(page, link)
                    if pdf:
                        reg, exam = extract_dates(pdf_text(pdf))
                        link = pdf
                except Exception as e:  # 抓日期失敗不影響「已公告」的判定
                    print(f"  {sid} 抓日期失敗：{e}")
                return {"link": link, "reg": reg, "exam": exam, "title": norm(text)}
    return None


def main():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    now = datetime.now(TW)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for s in data["schools"]:
            if s["status"] == "out" or s["id"] not in PAGES:
                continue
            try:
                found = check_school(page, s["id"])
                s.pop("error", None)
            except Exception as e:
                print(f"{s['name']}：檢查失敗 {e}")
                s["error"] = now.date().isoformat()
                continue
            if not found:
                print(f"{s['name']}：尚未公告")
                continue
            print(f"{s['name']}：偵測到簡章 {found}")
            got_dates = bool(found["reg"] or found["exam"])
            s.update({
                "status": "out", "auto": True, "announce": now.date().isoformat(), "announceText": None,
                "annNote": "（自動偵測日）", "link": found["link"],
                "reg": found["reg"] or s.get("reg"), "exam": found["exam"] or s.get("exam"),
                "datesUnverified": not (found["reg"] and found["exam"]),
            })
            s["note"] = (f"{now:%m/%d} 自動偵測到簡章公告。"
                         + ("日期由程式從簡章擷取，請以簡章為準。" if got_dates else "日期還沒擷取到，請看簡章。"))
        browser.close()
    data["checked_at"] = now.isoformat(timespec="seconds")
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
