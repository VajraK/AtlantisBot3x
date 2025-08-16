import re
import json
import os
import openai
import yaml
import logging
from typing import List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_config(path="config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def clean_json_response(text: str) -> str:
    """
    Remove markdown code fences (``` or ```json) wrapping the JSON.
    Also strip any leading/trailing whitespace.
    """
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text, flags=re.IGNORECASE)
    return text.strip()

def format_prompt(entries: List[dict]) -> str:
    config = load_config()
    base_prompt = config.get("prompt0", "")
    prompt = base_prompt + "\n\nItems:\n"
    for entry in entries:
        prompt += (
            f"\nHash: {entry['hash']}\n"
            f"Title: {entry['name']}\n"
            f"Description: {entry['description']}\n"
            f"URL: {entry['url']}\n"
        )
    return prompt

async def rate_entries_with_gpt(entries: List[dict], batch_size=10, model="gpt-4o", temperature=0.2):
    config = load_config()
    api_key = config.get("openai", {}).get("api_key")
    if not api_key:
        raise ValueError("Missing OpenAI API key in config.yaml")

    openai.api_key = api_key
    results = {}

    for i in range(0, len(entries), batch_size):
        batch = entries[i:i + batch_size]
        prompt = format_prompt(batch)

        try:
            logger.info(f"⏳ Sending batch {i // batch_size + 1} to OpenAI...")
            response = openai.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful financial analyst."},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=1000
            )
            raw_content = response.choices[0].message.content
            cleaned_content = clean_json_response(raw_content)
            parsed = json.loads(cleaned_content)
            results.update(parsed)
            logger.info(f"✅ Got results for batch {i // batch_size + 1}")

        except json.JSONDecodeError as jde:
            logger.error(f"❌ JSON decode error on batch {i // batch_size + 1}: {jde}")
            logger.error(f"Raw response was:\n{raw_content}")
        except Exception as e:
            logger.error(f"❌ Error processing batch {i // batch_size + 1}: {e}")

    return results
