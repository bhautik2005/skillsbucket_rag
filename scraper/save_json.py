import json
import pandas as pd
import os

INPUT = "output/cleaned_dataset.json"

CSV_OUTPUT = "output/training_dataset.csv"

MARKDOWN_FOLDER = "output/markdown"

os.makedirs(MARKDOWN_FOLDER, exist_ok=True)

with open(INPUT, "r", encoding="utf8") as f:
    dataset = json.load(f)

rows = []

for course in dataset:

    title = course["title"]

    url = course["url"]

    md = f"# {title}\n\n"

    md += f"Source: {url}\n\n"

    for heading, content in course["sections"].items():

        md += f"## {heading}\n\n"

        for line in content:

            md += f"- {line}\n"

            rows.append({
                "Course": title,
                "Section": heading,
                "Content": line,
                "URL": url
            })

        md += "\n"

    filename = title.lower().replace(" ", "_")

    with open(
        f"{MARKDOWN_FOLDER}/{filename}.md",
        "w",
        encoding="utf8"
    ) as f:

        f.write(md)

df = pd.DataFrame(rows)

df.to_csv(CSV_OUTPUT, index=False)

print("CSV Saved")
print("Markdown Files Saved")