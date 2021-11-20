import feedparser
import httpx
import json
import pathlib
import re
import os
import datetime

blog_feed_url = "https://ssscode.com/atom.xml"
# wakatime_raw_url = "https://gist.githubusercontent.com/JS-banana/b4b79e0deb0164edaae772ecbc5bd8bc/raw/"

root = pathlib.Path(__file__).parent.resolve()


def replace_chunk(content, marker, chunk, inline=False):
    r = re.compile(
        r"<!\-\- {} starts \-\->.*<!\-\- {} ends \-\->".format(marker, marker),
        re.DOTALL,
    )
    if not inline:
        chunk = "\n{}\n".format(chunk)
    chunk = "<!-- {} starts -->{}<!-- {} ends -->".format(
        marker, chunk, marker)
    return r.sub(chunk, content)


def fetch_code_time():
    timeTxt = root / "packages/wakatime/time.txt"
    timeTxt_contents = readme.open(encoding='UTF-8').read()
    return timeTxt_contents


def fetch_blog_entries():
    entries = feedparser.parse(blog_feed_url)["entries"]
    return [
        {
            "title": entry["title"],
            "url": entry["link"].split("#")[0],
            "published": entry["published"].split("T")[0],
        }
        for entry in entries
    ]


if __name__ == "__main__":
    readme = root / "README.md"
    readme_contents = readme.open(encoding='UTF-8').read()

    code_time_text = "\n```text\n"+fetch_code_time()+"\n```\n"
    rewritten = replace_chunk(readme_contents, "code_time", code_time_text)

    entries = fetch_blog_entries()[:5]
    entries_md = "\n".join(
        ["* <a href='{url}' target='_blank'>{title}</a> - {published}".format(
            **entry) for entry in entries]
    )
    rewritten = replace_chunk(rewritten, "blog", entries_md)

    readme.open("w", encoding='UTF-8').write(rewritten)
