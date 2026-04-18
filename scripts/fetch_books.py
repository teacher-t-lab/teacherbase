import json
import os
import re
import time
import urllib.request
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))

# Amazon アソシエイトタグ（後で本物に差し替えてください）
AMAZON_TAG = "teacherbase-22"

JSON_PATH = "data/books.json"


def isbn13_to_isbn10(isbn13):
    """ISBN-13 を ISBN-10 に変換してAmazonリンク用に使用"""
    if not isbn13 or len(isbn13) < 12:
        return None
    # 978 または 979 プレフィックスを除いた 9 桁
    core = isbn13[3:12]
    total = sum((10 - i) * int(d) for i, d in enumerate(core))
    check = (11 - (total % 11)) % 11
    check_char = "X" if check == 10 else str(check)
    return core + check_char


def make_buy_links(isbn):
    """ISBN から Amazon・楽天の購入リンクを生成"""
    isbn10 = isbn13_to_isbn10(isbn)
    if isbn10:
        amazon_url = "https://www.amazon.co.jp/dp/" + isbn10 + "?tag=" + AMAZON_TAG
    else:
        amazon_url = "https://www.amazon.co.jp/s?k=" + isbn
    rakuten_url = "https://books.rakuten.co.jp/search?sitem=" + isbn
    return amazon_url, rakuten_url


def fetch_google_books(isbn):
    """Google Books API から書誌情報を取得"""
    api_key = os.environ.get("GOOGLE_BOOKS_API_KEY", "")
    api_url = "https://www.googleapis.com/books/v1/volumes?q=isbn:" + isbn
    if api_key:
        api_url += "&key=" + api_key
    try:
        req = urllib.request.Request(
            api_url,
            headers={"User-Agent": "TeacherBase-BookFetcher/1.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as res:
            data = json.load(res)

        if data.get("totalItems", 0) == 0 or not data.get("items"):
            print("  Not found on Google Books: " + isbn)
            return None

        info = data["items"][0].get("volumeInfo", {})

        # 著者（複数の場合は「・」で結合）
        authors = info.get("authors", [])
        author = "・".join(authors) if authors else "不明"

        # 表紙画像（HTTP → HTTPS に変換）
        image_links = info.get("imageLinks", {})
        cover_url = image_links.get("thumbnail") or image_links.get("smallThumbnail") or ""
        cover_url = cover_url.replace("http://", "https://")

        # 出版年（publishedDate は "2020-05-01" や "2020" など）
        published = info.get("publishedDate", "")
        year = int(published[:4]) if len(published) >= 4 and published[:4].isdigit() else None

        # ページ数
        pages = info.get("pageCount") or None

        # あらすじ（HTMLタグ除去・300文字で切り捨て）
        description = info.get("description", "")
        description = re.sub(r"<[^>]+>", "", description).strip()
        description = re.sub(r"\s+", " ", description)
        if len(description) > 300:
            description = description[:300] + "…"

        return {
            "title":       info.get("title", ""),
            "author":      author,
            "cover_url":   cover_url,
            "description": description,
            "pages":       pages,
            "year":        year,
        }

    except Exception as e:
        print("  Error fetching " + isbn + ": " + str(e))
        return None


def main():
    if not os.path.exists(JSON_PATH):
        print("ERROR: " + JSON_PATH + " not found")
        return

    with open(JSON_PATH, encoding="utf-8") as f:
        books = json.load(f)

    fetched_count = 0
    updated_count = 0

    for book in books:
        isbn = book.get("isbn", "").strip()
        if not isbn:
            continue

        # 購入リンクを常に最新化（タグ変更に対応）
        amazon_url, rakuten_url = make_buy_links(isbn)
        book["amazon_url"] = amazon_url
        book["rakuten_url"] = rakuten_url
        updated_count += 1

        # title が既に入っている場合は API 取得をスキップ
        if book.get("title"):
            print("Skip (already fetched): " + isbn + " - " + book["title"])
            continue

        # Google Books API で書誌情報を取得
        print("Fetching: " + isbn)
        api_data = fetch_google_books(isbn)

        if api_data:
            # 管理者が手動で入力した comment・category・tags は上書きしない
            for key, val in api_data.items():
                if val:  # 空でない値のみ反映
                    book[key] = val
            book["fetched_at"] = datetime.now(JST).strftime("%Y-%m-%d")
            fetched_count += 1
            print("  -> " + book.get("title", "(no title)"))
        else:
            print("  -> Could not fetch data")

        time.sleep(0.5)  # API レート制限対策

    # 書き戻し
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(books, f, ensure_ascii=False, indent=2)

    print("")
    print("Done. Fetched: " + str(fetched_count) + " / Updated links: " + str(updated_count) + " / Total: " + str(len(books)))


if __name__ == "__main__":
    main()
