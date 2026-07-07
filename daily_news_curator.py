import os
import time
import requests
import feedparser
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
import google.generativeai as genai

# 1. 설정
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

HN_KEYWORDS = ['game', 'unity', 'ai', 'llm', 'mcp']

RSS_FEEDS = [
    {"url": "https://blog.unity.com/feed", "source": "Unity Blog"},
    {"url": "https://openai.com/news/rss.xml", "source": "OpenAI News"},
    {"url": "https://deepmind.google/blog/rss.xml", "source": "DeepMind Blog"},
    {"url": "https://www.reddit.com/r/MachineLearning/top/.rss?t=day", "source": "r/MachineLearning"},
]

def get_hacker_news(limit=100):
    """Hacker News Top Stories에서 특정 키워드가 포함된 기사 추출"""
    print("Fetching Hacker News...")
    top_stories_url = "https://hacker-news.firebaseio.com/v0/topstories.json"
    
    try:
        story_ids = requests.get(top_stories_url, timeout=10).json()
    except Exception as e:
        print(f"Error fetching HN top stories: {e}")
        return []
    
    articles = []
    for story_id in story_ids[:limit]:
        item_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
        try:
            item = requests.get(item_url, timeout=5).json()
            if not item or 'title' not in item or 'url' not in item:
                continue
            
            title_lower = item['title'].lower()
            if any(keyword in title_lower for keyword in HN_KEYWORDS):
                articles.append({
                    "title": item['title'],
                    "link": item['url'],
                    "source": "Hacker News",
                    "content": "" # 내용을 직접 가져오지 못하므로 제목/링크 기반 요약 유도
                })
        except Exception as e:
            pass
            
    return articles

def get_rss_news():
    """RSS 피드에서 최신 기사 수집"""
    print("Fetching RSS feeds...")
    articles = []
    time_limit = datetime.now(timezone.utc) - timedelta(days=1)
    
    for feed_info in RSS_FEEDS:
        print(f" - {feed_info['source']}")
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:5]: # 피드당 최신 5개
                # 날짜 체크 (가급적 하루 이내)
                pub_date = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_date = datetime.fromtimestamp(time.mktime(entry.published_parsed), timezone.utc)
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    pub_date = datetime.fromtimestamp(time.mktime(entry.updated_parsed), timezone.utc)
                
                if pub_date and pub_date < time_limit:
                    continue
                
                content_raw = ""
                if hasattr(entry, 'content'):
                    content_raw = entry.content[0].value
                elif hasattr(entry, 'summary'):
                    content_raw = entry.summary
                elif hasattr(entry, 'description'):
                    content_raw = entry.description
                    
                soup = BeautifulSoup(content_raw, "html.parser")
                clean_content = soup.get_text(separator=" ", strip=True)[:2000] # 토큰 절약
                
                articles.append({
                    "title": entry.title,
                    "link": entry.link,
                    "source": feed_info["source"],
                    "content": clean_content
                })
        except Exception as e:
            print(f"Error fetching {feed_info['url']}: {e}")
            
    return articles

def summarize_with_gemini(article):
    """Gemini API를 사용하여 한국어로 3줄 요약 및 태그 생성"""
    if not GEMINI_API_KEY:
        return "API Key 설정 안됨", ["#Error"]
        
    genai.configure(api_key=GEMINI_API_KEY)
    
    # 무료 할당량이 넉넉한 gemini-2.5-flash 모델 사용
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
다음 기사 제목과 내용을 한국인 게임 프로그래머가 읽기 좋게 딱 3줄로 요약하고, 관련 핵심 기술 태그(예: #AI #Unity 등)를 달아주세요.
응답 형식은 반드시 다음과 같이 해주세요:
요약:
- 첫 번째 줄
- 두 번째 줄
- 세 번째 줄
태그: #태그1 #태그2

기사 제목: {article['title']}
내용: {article['content']}
"""
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Error calling Gemini API for {article['title']}: {e}")
        return "요약 실패", []

def main():
    print("Starting daily news collection...")
    
    hn_articles = get_hacker_news(limit=100)
    rss_articles = get_rss_news()
    
    all_articles = hn_articles + rss_articles
    if not all_articles:
        print("No articles found today.")
        return
        
    today_str = datetime.now().strftime("%Y-%m-%d")
    md_filename = f"{today_str}-daily-news.md"
    
    md_content = f"# {today_str} 게임 개발 & AI 데일리 뉴스\n\n"
    
    for i, article in enumerate(all_articles):
        print(f"[{i+1}/{len(all_articles)}] Summarizing: {article['title']}")
        if GEMINI_API_KEY:
            summary_text = summarize_with_gemini(article)
            time.sleep(4) # Rate limit 방지 (15 RPM 고려)
        else:
            summary_text = "(GEMINI_API_KEY가 설정되지 않아 요약을 생성하지 못했습니다.)"
            
        md_content += f"## [{article['source']}] {article['title']}\n"
        md_content += f"[원문 링크]({article['link']})\n\n"
        md_content += f"{summary_text}\n\n"
        md_content += "---\n\n"
        
    with open(md_filename, "w", encoding="utf-8") as f:
        f.write(md_content)
        
    print(f"Successfully created {md_filename}")

if __name__ == "__main__":
    main()
