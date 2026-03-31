import feedparser
import json
import os
import re
import hashlib
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))

RSS_FEEDS = [
    {"url": "https://www.mext.go.jp/rss/news.xml",        "source": "文部科学省", "domain": "mext.go.jp"},
    {"url": "https://www.kyoiku-shimbun.net/rss/",         "source": "教育新聞",   "domain": "kyoiku-shimbun.net"},
    {"url": "https://edtechzine.jp/rss/",                  "source": "EdTechZine", "domain": "edtechzine.jp"},
]

CATEGORIES = {
    "法改正":     ["法改正","制度改正","通知","給特法","個人情報","労働時間","規制","条例","法律","告示","文部科学省令","指針"],
    "ICT・AI":    ["AI","ICT","デジタル","GIGA","タブレット","プログラミング","EdTech","生成AI","ChatGPT","DX","ロボット","アプリ","システム"],
    "研修・イベント": ["研修","セミナー","講演","イベント","講座","開催","募集","シンポジウム","フォーラム","説明会","参加無料"],
    "書籍・論文": ["書籍","書評","論文","研究報告","著書","刊行","出版","図書","レポート","調査結果"],
    "授業アイデア": ["授業","指導","学習","探究","実践","教材","ワーク","単元","教育方法","学び","カリキュラム"],
}

def categorize(title, summary=""):
    text = title + " " + (summary or "")
    for cat, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw in text:
                return cat
    return "授業アイデア"

def parse_date(entry):
    for attr in ["published_parsed", "updated_parsed"]:
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6]).strftime("%Y-%m-%d")
            except Exception:
                pass
    return datetime.now(JST).strftime("%Y-%m-%d")

def make_id(url):
    return int(hashlib.md5(url.encode()).hexdigest()[:8], 16) % 10000000

def fetch_all():
    articles = []
    seen_urls = set()
    for feed_info in RSS_FEEDS:
        try:
            print(f"Fetching: {feed_info[\"url\"]}")
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:30]:
                url = entry.get("link", "").strip()
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                title = entry.get("title", "").strip()
                if not title:
                    continue
                raw_summary = entry.get("summary", entry.get("description", ""))
                summary = re.sub(r"<[^>]+>", "", raw_summary).strip()
                summary = re.sub(r"\s+", " ", summary)[:200]
                date = parse_date(entry)
                cat = categorize(title, summary)
                articles.append({
                    "id":      make_id(url),
                    "cat":     cat,
                    "isNew":   False,
                    "title":   title,
                    "summary": summary,
                    "source":  feed_info["source"],
                    "domain":  feed_info["domain"],
                    "date":    date,
                    "url":     url,
                })
            print(f"  -> {len(feed.entries)} entries found")
        except Exception as e:
            print(f"Error fetching {feed_info[\"url\"]}: {e}")

    articles.sort(key=lambda x: x["date"], reverse=True)
    for a in articles[:3]:
        a["isNew"] = True
    return articles[:60]

def main():
    os.makedirs("data", exist_ok=True)
    articles = fetch_all()
    with open("data/news.json", "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"
Saved {len(articles)} articles to data/news.json")

if __name__ == "__main__":
    main()

