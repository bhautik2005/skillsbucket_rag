import requests
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin

headers = {
    "User-Agent":
    "Mozilla/5.0"
}


with open("course_links.json","r",encoding="utf8") as f:
    links = json.load(f)

dataset=[]

for course in links:

    print("Scraping :",course["title"])

    html = requests.get(course["url"],headers=headers)

    soup = BeautifulSoup(html.text,"lxml")

    data = {
        "title": course["title"],
        "url": course["url"],
        "sections":{}
    }

    current_heading = None

    for tag in soup.find_all(["h1","h2","h3","strong","b","p","ul"]):

        text = tag.get_text(" ",strip=True)

        if len(text)==0:
            continue

        if tag.name in ["h1","h2","h3"]:

            current_heading=text

            data["sections"][current_heading]=[]

        else:

            if current_heading:

                data["sections"][current_heading].append(text)

    dataset.append(data)

# with open("training_dataset.json","w",encoding="utf8") as f:

#     json.dump(dataset,f,indent=4,ensure_ascii=False)
import os

os.makedirs("output", exist_ok=True)

with open(
    "output/raw_dataset.json",
    "w",
    encoding="utf-8"
) as f:
    json.dump(dataset, f, indent=4, ensure_ascii=False)

print("Saved output/raw_dataset.json")