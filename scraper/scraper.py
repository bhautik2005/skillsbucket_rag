import os
import re
import json
import requests
from bs4 import BeautifulSoup

# -----------------------------
# Configuration
# -----------------------------

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

OUTPUT_DIR = "output/json"

os.makedirs(OUTPUT_DIR, exist_ok=True)


# -----------------------------
# Helpers
# -----------------------------

def clean(text):
    if not text:
        return ""

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def safe_filename(name):

    name = clean(name)

    name = name.lower()

    name = re.sub(r'[<>:"/\\|?*]', "", name)

    name = name.replace(" ", "_")

    return name


# -----------------------------
# Main Scraper
# -----------------------------

def scrape(url):

    print("=" * 60)
    print("Downloading:", url)

    r = requests.get(url, headers=HEADERS, timeout=20)

    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")

    # -----------------------------
    # Course Name
    # -----------------------------

    title = ""

    if soup.title:

        title = soup.title.text

        title = title.replace("– Skillsbucket", "")

        title = title.replace("- Skillsbucket", "")

        title = clean(title)

    if not title:

        title = "unknown_course"

    print("Course:", title)

    data = {

        "course_name": title,

        "source": url,

        "category": "Soft Skills",

        "sections": []

    }

    # -----------------------------
    # Overview
    # -----------------------------

    overview = []

    paragraphs = soup.select("p.thin_font")

    for p in paragraphs:

        txt = clean(p.get_text())

        if len(txt) > 20:

            overview.append(txt)

    if overview:

        data["sections"].append({

            "section": "Overview",

            "content": " ".join(overview[:2])

        })

    # -----------------------------
    # Dynamic Sections
    # -----------------------------

    for heading in soup.find_all(["h2", "h3"]):

        heading_text = clean(heading.get_text())

        if len(heading_text) == 0:

            continue

        section = {

            "section": heading_text,

            "content": []

        }

        parent = heading.find_parent()

        if parent:

            # paragraphs

            for p in parent.find_all("p"):

                txt = clean(p.get_text())

                if txt and txt not in section["content"]:

                    section["content"].append(txt)

            # list items

            for li in parent.find_all("li"):

                txt = clean(li.get_text())

                if txt and txt not in section["content"]:

                    section["content"].append(txt)

            # figcaptions

            for fig in parent.find_all("figcaption"):

                txt = clean(fig.get_text())

                if txt and txt not in section["content"]:

                    section["content"].append(txt)

        if section["content"]:

            data["sections"].append(section)

    # -----------------------------
    # Remove duplicate sections
    # -----------------------------

    unique = []

    seen = set()

    for s in data["sections"]:

        if s["section"] not in seen:

            unique.append(s)

            seen.add(s["section"])

    data["sections"] = unique

    # -----------------------------
    # Save
    # -----------------------------

    filename = safe_filename(title)

    output = os.path.join(

        OUTPUT_DIR,

        filename + ".json"

    )

    with open(

        output,

        "w",

        encoding="utf-8"

    ) as f:

        json.dump(

            data,

            f,

            indent=4,

            ensure_ascii=False

        )

    print("Saved:", output)


# -----------------------------
# Read URL List
# -----------------------------

if __name__ == "__main__":

    if not os.path.exists("urls.txt"):

        print("urls.txt not found")

        exit()

    with open(

        "urls.txt",

        "r",

        encoding="utf-8"

    ) as f:

        urls = [

            i.strip()

            for i in f.readlines()

            if i.strip()

        ]

    print("Total URLs:", len(urls))

    for url in urls:

        try:

            scrape(url)

        except Exception as e:

            print("ERROR:", url)

            print(e)