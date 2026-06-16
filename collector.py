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

def get_best_model():
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
    try:
        resp = requests.get(url)
        if resp.status_code == 200:
            models = resp.json().get('models', [])
            # Priority 1: gemini-1.5-flash
            for m in models:
                if "gemini-1.5-flash" in m['name'] and "generateContent" in m.get('supportedGenerationMethods', []):
                    return m['name']
            # Priority 2: any model that supports generateContent
            for m in models:
                if "generateContent" in m.get('supportedGenerationMethods', []) and "embedding" not in m['name']:
                    return m['name']
    except Exception:
        pass
    return "models/gemini-1.5-flash"

MODEL_NAME = get_best_model()

FEEDS = [
    {"url": "https://gamedevdigest.com/feed.xml", "default_tag": "GameDev"},
    {"url": "https://aigamechangers.substack.com/feed", "default_tag": "AI"},
    {"url": "https://aiplaybook.substack.com/feed", "default_tag": "AI"},
    {"url": "https://blog.unity.com/feed", "default_tag": "Unity"},
    {"url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCFK6NCbuRICzA6xTq1uVD0w", "default_tag": "Unity"},
    {"url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCbfYPyITQ-7l4upoX8nvctg", "default_tag": "AI"},
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
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    try:
        response = requests.post(url, json=payload)
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
        print(f"Error analyzing content for '{title}': {e}")
        return title, ["요약을 가져오지 못했습니다. 원본 링크를 확인해주세요."], []

def collect_news():
    articles = []
    time_limit = datetime.now() - timedelta(days=7)
    
    print(f"데이터 수집을 시작합니다... (사용 모델: {MODEL_NAME})")
    
    for feed_info in FEEDS:
        print(f"Fetching: {feed_info['url']}")
        feed = feedparser.parse(feed_info["url"])
        
        for entry in feed.entries[:5]:
            pub_date = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                pub_date = datetime.fromtimestamp(time.mktime(entry.published_parsed))
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                pub_date = datetime.fromtimestamp(time.mktime(entry.updated_parsed))
            
            if not pub_date:
                pub_date = datetime.now()
                
            if pub_date < time_limit:
                continue
                
            title = entry.title
            link = entry.link
            
            content_raw = ""
            if hasattr(entry, 'content'):
                content_raw = entry.content[0].value
            elif hasattr(entry, 'summary'):
                content_raw = entry.summary
            elif hasattr(entry, 'description'):
                content_raw = entry.description
                
            clean_content = strip_html(content_raw)
            
            print(f" - Analyzing: {title}")
            translated_title, summary, ai_tags = analyze_content(title, clean_content)
            
            tags = list(set([feed_info["default_tag"]] + ai_tags))
            
            articles.append({
                "title": title,
                "translated_title": translated_title,
                "link": link,
                "date": pub_date.strftime("%Y-%m-%d"),
                "summary": summary,
                "tags": tags,
                "source": feed.feed.title if hasattr(feed.feed, 'title') else "Unknown Source"
            })
            
            time.sleep(1.5)
            
    articles.sort(key=lambda x: x["date"], reverse=True)
    
    os.makedirs('data', exist_ok=True)
    output_file = 'data/articles.js'
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("const allArticlesData = ")
        json.dump(articles, f, ensure_ascii=False, indent=2)
        f.write(";")
        
    print(f"\n완료! 총 {len(articles)}개의 기사를 저장했습니다.")

if __name__ == "__main__":
    collect_news()
