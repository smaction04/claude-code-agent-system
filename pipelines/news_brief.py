#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
아침 뉴스 브리핑 봇 (B1 무인 자동화) — 경제/부동산/AI 뉴스 수집 → 텔레그램 전송.

원칙(기존 규칙 간섭 0):
  - 무인은 "수집·전송"만. 판단/생성/발행 가공은 사람 세션에서 (knowledge_crawl 패턴).
  - 사실(뉴스 제목·링크)만 그대로 전달. LLM 요약/주장 없음 → 정직성 검수 불필요.
의존성 0 (Python 표준 라이브러리만) — Windows 작업 스케줄러로 헤드리스 실행.

토큰 미설정 시 = dry-run (전송 없이 콘솔 출력만). 수집 검증용.
설정: 00_Director/_config/news_brief_config.json
"""
import json, os, ssl, sys, urllib.request, urllib.parse, io
from xml.etree import ElementTree as ET
from datetime import datetime, timezone, timedelta
from html import unescape
import re

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    import certifi
    _SSL = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSL = ssl.create_default_context()

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)                      # 00_Director
CONFIG = os.path.join(ROOT, "_config", "news_brief_config.json")
LOGFILE = os.path.join(ROOT, "_config", "news_brief.log")


def _log(line):
    try:
        with open(LOGFILE, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat(timespec='seconds')} {line}\n")
    except Exception:
        pass

# 카테고리별 RSS 후보 (dry-run으로 생존 검증 후 죽은 건 교체)
DEFAULT_SOURCES = {
    "경제": [
        ("연합뉴스 경제", "https://www.yna.co.kr/rss/economy.xml"),
        ("매일경제", "https://www.mk.co.kr/rss/30000001/"),
        ("한겨레 경제", "https://www.hani.co.kr/rss/economy/"),
    ],
    "부동산": [
        ("매경 부동산", "https://www.mk.co.kr/rss/50300009/"),
        ("연합 경제(부동산필터)", "https://www.yna.co.kr/rss/economy.xml"),
    ],
    "AI": [
        ("AI타임스", "https://www.aitimes.com/rss/allArticle.xml"),
    ],
}

# 카테고리별 제목 키워드 필터 (지정 시 제목에 키워드 포함된 것만 수집)
DEFAULT_FILTERS = {
    "부동산": ["부동산", "아파트", "분양", "전세", "매매", "재건축", "재개발",
               "청약", "주택", "집값", "임대", "토지", "전셋값", "월세", "오피스텔"],
    "AI": ["AI", "인공지능", "GPT", "LLM", "챗봇", "생성형", "오픈AI", "OpenAI",
           "엔비디아", "반도체", "로봇", "머신러닝", "딥러닝", "앤트로픽", "클로드",
           "제미나이", "코파일럿", "데이터센터", "자율주행", "알고리즘", "GPU", "양자"],
}

DEFAULT_CFG = {
    "telegram_token": "",
    "chat_id": "",
    "per_category": 5,
    "hours": 36,
    "sources": DEFAULT_SOURCES,
    "filters": DEFAULT_FILTERS,
}


def load_cfg():
    c = dict(DEFAULT_CFG)
    if os.path.exists(CONFIG):
        try:
            with open(CONFIG, "r", encoding="utf-8") as f:
                disk = json.load(f)
            for k, v in disk.items():
                c[k] = v
        except Exception as e:
            sys.stderr.write(f"[news_brief] config 읽기 실패 → 기본값: {e}\n")
    # 환경변수 우선(GitHub Actions Secrets) — 있으면 로컬 config보다 우선
    c["telegram_token"] = os.environ.get("TELEGRAM_TOKEN") or c.get("telegram_token", "")
    c["chat_id"] = os.environ.get("CHAT_ID") or c.get("chat_id", "")
    return c


def fetch(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (news_brief)"})
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL) as r:
        return r.read()


def parse_rss(raw):
    """RSS/Atom 공통 파싱 → [(title, link, dt)]."""
    out = []
    try:
        root = ET.fromstring(raw)
    except Exception:
        return out
    # RSS 2.0
    for item in root.iter("item"):
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        pub = item.findtext("pubDate", "") or item.findtext("{http://purl.org/dc/elements/1.1/}date", "")
        dt = _parse_date(pub)
        if title:
            out.append((unescape(title), link, dt))
    # Atom
    if not out:
        ns = "{http://www.w3.org/2005/Atom}"
        for e in root.iter(f"{ns}entry"):
            title = (e.findtext(f"{ns}title") or "").strip()
            link_el = e.find(f"{ns}link")
            link = link_el.get("href") if link_el is not None else ""
            pub = (e.findtext(f"{ns}updated") or e.findtext(f"{ns}published") or "")
            dt = _parse_date(pub)
            if title:
                out.append((unescape(title), link, dt))
    return out


def _parse_date(s):
    s = (s or "").strip()
    if not s:
        return None
    fmts = ["%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
            "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"]
    for f in fmts:
        try:
            d = datetime.strptime(s, f)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return d
        except Exception:
            continue
    return None


def collect(cfg):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=cfg["hours"])
    result = {}
    diag = {}
    filters = cfg.get("filters", {})
    for cat, feeds in cfg["sources"].items():
        seen = set()
        items = []
        kw = filters.get(cat)
        for name, url in feeds:
            try:
                raw = fetch(url)
                parsed = parse_rss(raw)
                live = len(parsed)
                kept = 0
                for title, link, dt in parsed:
                    if dt and dt < cutoff:
                        continue
                    if kw and not any(k.lower() in title.lower() for k in kw):
                        continue
                    key = re.sub(r"\s+", "", title)[:40]
                    if key in seen:
                        continue
                    seen.add(key)
                    items.append((title, link))
                    kept += 1
                diag[f"{cat}/{name}"] = f"OK live={live} kept={kept}"
            except Exception as e:
                diag[f"{cat}/{name}"] = f"FAIL {type(e).__name__}"
        result[cat] = items[: cfg["per_category"]]
    return result, diag


def format_message(result):
    today = datetime.now().strftime("%Y-%m-%d (%a)")
    lines = [f"📰 아침 브리핑 — {today}\n"]
    icons = {"경제": "💹", "부동산": "🏠", "AI": "🤖"}
    for cat, items in result.items():
        lines.append(f"\n{icons.get(cat, '•')} {cat}")
        if not items:
            lines.append("  (신규 없음)")
        for title, link in items:
            lines.append(f"• {title}\n  {link}")
    return "\n".join(lines)


def send_telegram(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id, "text": text,
        "disable_web_page_preview": "true",
    }).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=15, context=_SSL) as r:
        return json.loads(r.read())


def main():
    cfg = load_cfg()
    result, diag = collect(cfg)

    sys.stderr.write("[news_brief] 수집 진단:\n")
    for k, v in diag.items():
        sys.stderr.write(f"  {k}: {v}\n")

    msg = format_message(result)

    diag_summary = " | ".join(f"{k}:{v}" for k, v in diag.items())
    if cfg["telegram_token"] and cfg["chat_id"]:
        try:
            resp = send_telegram(cfg["telegram_token"], cfg["chat_id"], msg)
            ok = resp.get("ok")
            desc = resp.get("description", "")
            sys.stderr.write(f"[news_brief] 텔레그램 전송: {'성공' if ok else '실패'} {desc}\n")
            _log(f"{'SENT' if ok else 'SEND_FAIL'} desc={desc} | {diag_summary}")
            return 0 if ok else 1
        except Exception as e:
            sys.stderr.write(f"[news_brief] 전송 오류: {e}\n")
            _log(f"SEND_EXC {type(e).__name__}: {e} | {diag_summary}")
            return 1
    else:
        sys.stderr.write("[news_brief] 토큰 미설정 → dry-run (전송 생략, 아래 미리보기)\n")
        _log(f"DRYRUN | {diag_summary}")
        print("=" * 50)
        print(msg)
        print("=" * 50)
        return 0


if __name__ == "__main__":
    sys.exit(main())
