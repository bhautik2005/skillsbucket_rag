import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json

BASE_URL = "https://skillsbucket.in/"
URL = urljoin(BASE_URL, "training-program.htm")

headers = {
    "User-Agent":
    "Mozilla/5.0"
}

response = requests.get(URL, headers=headers)
response.raise_for_status()

soup = BeautifulSoup(response.text, "lxml")

courses = []

for a in soup.find_all("a", href=True):

    text = a.get_text(strip=True)

    if text.lower() == "learn more":

        href = urljoin(BASE_URL, a["href"])

        card = a.find_parent()

        title = ""

        description = ""

        if card:

            h = card.find(["h2", "h3", "h4"])

            if h:
                title = h.get_text(" ", strip=True)

            p = card.find("p")

            if p:
                description = p.get_text(" ", strip=True)

        courses.append({
            "title": title,
            "description": description,
            "url": href
        })

print(courses)

with open("course_links.json","w",encoding="utf8") as f:
    json.dump(courses,f,indent=4,ensure_ascii=False)