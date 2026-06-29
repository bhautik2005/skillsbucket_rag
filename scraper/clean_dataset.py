import json
import re
import os

INPUT_FILE = "output/training_dataset.json"
OUTPUT_FILE = "output/cleaned_dataset.json"


def clean_text(text):
    """Clean text by removing extra spaces and formatting."""
    if not text:
        return ""

    text = re.sub(r"\s+", " ", text)
    text = text.replace("\n", " ")
    text = text.replace("\t", " ")
    text = re.sub(r",+", ",", text)

    return text.strip()


# Check if input file exists
if not os.path.exists(INPUT_FILE):
    print(f"Error: {INPUT_FILE} not found!")
    print("Run scrape_course_details.py first.")
    exit()

# Load raw dataset
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    dataset = json.load(f)

cleaned = []

for course in dataset:

    item = {
        "title": clean_text(course.get("title", "")),
        "url": course.get("url", ""),
        "sections": {}
    }

    sections = course.get("sections", {})

    for heading, values in sections.items():

        heading = clean_text(heading)

        cleaned_values = []

        for value in values:

            value = clean_text(value)

            if value and value not in cleaned_values:
                cleaned_values.append(value)

        item["sections"][heading] = cleaned_values

    cleaned.append(item)

# Create output folder if it doesn't exist
os.makedirs("output", exist_ok=True)

# Save cleaned dataset
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(cleaned, f, indent=4, ensure_ascii=False)

print("✅ Dataset cleaned successfully!")
print(f"Saved to: {OUTPUT_FILE}")