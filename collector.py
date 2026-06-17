import feedparser
import requests
import json
import os
import time
from datetime import datetime, timedelta
import re
import sys
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("Error: GEMINI_API_KEY is not set.")
    sys.exit(1)

FALLBACK_SUMMARY = "요약을 가져오지 못했습니다. 원본 링크를 확인해주세요."

def get_best_model():
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            names = [
                m['name'] for m in resp.json().get('models', [])
                if "generateContent" in m.get('supportedGenerationMethods', [])
                and "embedding" not in m['name']
            ]
            # 무료 한도가 더 넉넉한 모델 우선 (flash-lite > flash). 없으면 가용한 첫 모델.
            for pref in ("gemini-2.5-flash-lite", "gemini-2.0-flash-lite",
                         "gemini-2.5-flash", "gemini-2.0-flash"):
                for n in names:
                    if pref in n:
                        return n
            if names:
                return names[0]
    except Exception:
        pass
    return "models/gemini-2.5-flash"

MODEL_NAME = get_best_model()

FEEDS = [
    {"url": "https://gamedevdigest.com/feed.xml", "default_tag": "GameDev"},
    {"url": "https://aigamechangers.substack.com/feed", "default_tag": "AI"},
    {"url": "https://aiplaybook.substack.com/feed", "default_tag": "AI"},
    {"url": "https://blog.unity.com/feed", "default_tag": "Unity"},
    {"url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCFK6NCbuRICzA6xTq1uVD0w", "default_tag": "Unity"},
    {"url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCbfYPyITQ-7l4upoX8nvctg", "default_tag": "AI"},
    {"url": "https://80.lv/rss", "default_tag": "GameDev"},
    {"url": "https://www.gamedeveloper.com/rss.xml", "default_tag": "News"},
    {"url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCX_b3NNQN5bzExm-22-NVVg", "default_tag": "Unity"},
    {"url": "https://huggingface.co/blog/feed.xml", "default_tag": "AI"},
    {"url": "https://openai.com/news/rss.xml", "default_tag": "AI"},
    {"url": "https://deepmind.google/blog/rss.xml", "default_tag": "AI"},
    {"url": "https://www.deeplearning.ai/the-batch/feed/", "default_tag": "AI"},
]

def strip_html(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    return soup.get_text(separator=" ", strip=True)

def analyze_content(title, content):
    prompt = f"""
You are an expert technical editor. Read the following article/video title and content snippet.
Original Title: {title}
Content: {content[:2000]} # Limit length to save tokens/time

Task:
1. Translate the Original Title into natural Korean.
2. Summarize the key points in 2-3 short bullet points (in Korean).
3. Suggest 1 to 3 relevant tags from this list if applicable, or create short new ones: Unity, GameDev, AI, Tutorial, News, Research.

Format your response strictly as valid JSON like this:
{{
    "translated_title": "번역된 한국어 제목",
    "summary": ["point 1", "point 2"],
    "tags": ["tag1", "tag2"]
}}
"""
    url = f"https://generativelanguage.googleapis.com/v1beta/{MODEL_NAME}:generateContent?key={API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    delay = 8  # 429일 때 지수 backoff 시작 간격(초)
    for attempt in range(5):
        try:
            response = requests.post(url, json=payload, timeout=60)

            # 레이트리밋: 더 오래 기다렸다 재시도. 본문 메시지로 쿼터 종류(분당/일일) 로깅.
            if response.status_code == 429:
                wait = delay
                ra = response.headers.get("Retry-After", "")
                if ra.isdigit():
                    wait = max(wait, int(ra))
                quota_hint = ""
                try:
                    quota_hint = response.json().get("error", {}).get("message", "")[:170]
                except Exception:
                    pass
                print(f"  429 rate limit ({wait}s 대기, {attempt+1}/5) {quota_hint}")
                time.sleep(wait)
                delay = min(delay * 2, 120)
                continue

            response.raise_for_status()
            data = response.json()
            text_response = data['candidates'][0]['content']['parts'][0]['text']
            # Extract JSON if markdown wrapped
            if "```json" in text_response:
                text_response = text_response.split("```json")[1].split("```")[0].strip()
            elif "```" in text_response:
                text_response = text_response.split("```")[1].split("```")[0].strip()

            result = json.loads(text_response)
            return result.get("translated_title", title), result.get("summary", []), result.get("tags", [])
        except Exception as e:
            msg = str(e).split("?key=")[0]  # 에러 메시지에 API 키가 섞여 들어가지 않게 제거
            print(f"  Attempt {attempt+1} failed for '{title[:50]}': {msg}")
            time.sleep(delay)
            delay = min(delay * 2, 120)

    print(f"All attempts failed for '{title[:50]}'.")
    return title, [FALLBACK_SUMMARY], []

def load_existing_by_link():
    """기존 data/articles.js를 link -> 기사 dict 로 읽어 캐시로 사용."""
    path = 'data/articles.js'
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding='utf-8') as f:
            txt = f.read()
        s, e = txt.find('['), txt.rfind(']')
        if s == -1 or e == -1:
            return {}
        arr = json.loads(txt[s:e + 1])
        return {a['link']: a for a in arr if a.get('link')}
    except Exception as ex:
        print(f"기존 데이터 로드 실패(무시): {ex}")
        return {}

def is_translated_ok(a):
    """이미 성공적으로 번역된 기사인지 (fallback 요약이 아니면 성공으로 간주)."""
    summ = a.get('summary') or []
    return bool(summ) and summ[0] != FALLBACK_SUMMARY

def collect_news():
    existing = load_existing_by_link()
    articles = []
    seen = set()
    reused = 0
    new_ok = 0
    consecutive_fail = 0
    quota_exhausted = False
    time_limit = datetime.now() - timedelta(days=7)

    print(f"데이터 수집 시작... (모델: {MODEL_NAME}, 기존 캐시 {len(existing)}건)")

    for feed_info in FEEDS:
        print(f"Fetching: {feed_info['url']}")
        try:
            feed = feedparser.parse(feed_info["url"])
        except Exception as ex:
            print(f"  피드 파싱 실패, 건너뜀: {ex}")
            continue

        for entry in feed.entries[:5]:
            link = getattr(entry, 'link', None)
            title = getattr(entry, 'title', None)
            if not link or not title or link in seen:
                continue

            pub_date = None
            if getattr(entry, 'published_parsed', None):
                pub_date = datetime.fromtimestamp(time.mktime(entry.published_parsed))
            elif getattr(entry, 'updated_parsed', None):
                pub_date = datetime.fromtimestamp(time.mktime(entry.updated_parsed))
            if not pub_date:
                pub_date = datetime.now()
            if pub_date < time_limit:
                continue

            seen.add(link)
            source = feed.feed.title if hasattr(feed.feed, 'title') else "Unknown Source"

            # 1) 이미 번역 성공한 글은 그대로 재사용 → Gemini 호출/쿼터 절약, 번역이 사라지지 않음
            prev = existing.get(link)
            if prev and is_translated_ok(prev):
                articles.append(prev)
                reused += 1
                continue

            # 2) 쿼터 소진으로 판단되면 신규 글은 영어 원문으로 임시 저장(다음 실행에서 재시도)
            if quota_exhausted:
                articles.append({
                    "title": title, "translated_title": title, "link": link,
                    "date": pub_date.strftime("%Y-%m-%d"), "summary": [FALLBACK_SUMMARY],
                    "tags": list(set([feed_info["default_tag"]])), "source": source,
                })
                continue

            content_raw = ""
            if hasattr(entry, 'content'):
                content_raw = entry.content[0].value
            elif hasattr(entry, 'summary'):
                content_raw = entry.summary
            elif hasattr(entry, 'description'):
                content_raw = entry.description
            clean_content = strip_html(content_raw)

            print(f" - Analyzing: {title[:60]}")
            translated_title, summary, ai_tags = analyze_content(title, clean_content)
            failed = (summary == [FALLBACK_SUMMARY])

            if failed:
                consecutive_fail += 1
                # 연속 실패 = 일일 쿼터 소진 신호. 남은 신규 글은 호출 없이 다음 실행으로 미룸.
                if consecutive_fail >= 3:
                    quota_exhausted = True
                    print("연속 실패 3회 — 쿼터 소진으로 판단, 남은 신규 번역은 다음 실행으로 미룹니다.")
            else:
                consecutive_fail = 0
                new_ok += 1

            articles.append({
                "title": title,
                "translated_title": translated_title,
                "link": link,
                "date": pub_date.strftime("%Y-%m-%d"),
                "summary": summary,
                "tags": list(set([feed_info["default_tag"]] + ai_tags)),
                "source": source,
            })

            if not failed:
                time.sleep(12)  # 성공 호출 사이 간격 → 무료 RPM 한도 회피(여유 있게)

    articles.sort(key=lambda x: x["date"], reverse=True)

    # 안전장치: 한 건도 못 모았으면 기존 데이터를 절대 덮어쓰지 않음
    if not articles:
        print("수집 0건 — 기존 데이터를 보존하고 종료합니다.")
        return

    os.makedirs('data', exist_ok=True)
    with open('data/articles.js', 'w', encoding='utf-8') as f:
        f.write("const allArticlesData = ")
        json.dump(articles, f, ensure_ascii=False, indent=2)
        f.write(";")

    print(f"\n완료! 총 {len(articles)}건 (재사용 {reused}, 신규 번역 {new_ok}, "
          f"미번역 {len(articles) - reused - new_ok}).")

if __name__ == "__main__":
    collect_news()
