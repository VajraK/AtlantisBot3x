import os
import re
import yaml
import logging
import tiktoken
import openai
from datetime import datetime
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_INPUT_TOKENS = 25000
CHUNK_TOKENS = 10000
MAX_CHUNKS = 5

def load_config(path="config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def clean_response_text(text: str) -> str:
    text = re.sub(r'^\s*```(?:json)?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```\s*$', '', text, flags=re.IGNORECASE)
    return text.strip()

def chunk_text(text, max_chunk_tokens=CHUNK_TOKENS, model="gpt-4o-mini"):
    encoding = tiktoken.encoding_for_model(model)
    tokens = encoding.encode(text)
    chunks = []
    for i in range(0, len(tokens), max_chunk_tokens):
        chunk_tokens = tokens[i:i+max_chunk_tokens]
        chunk_text = encoding.decode(chunk_tokens)
        chunks.append(chunk_text)
    return chunks[:MAX_CHUNKS]

async def analyze_txt_file(filepath: str) -> str:
    config = load_config()
    api_key = config.get("openai", {}).get("api_key")
    prompt_template = config.get("prompt")

    if not api_key:
        logger.error("OpenAI API key not found.")
        return None
    if not prompt_template:
        logger.error("Prompt not found in config.yaml.")
        return None

    openai.api_key = api_key

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
            text = soup.get_text(separator="\n").strip()
    except Exception as e:
        logger.error(f"Error reading file {filepath}: {e}")
        return None

    encoding = tiktoken.encoding_for_model("gpt-4o-mini")
    tokens = encoding.encode(text)

    current_date = datetime.now().strftime("%Y-%m-%d")
    prompt_filled = prompt_template.replace("{{current_date}}", current_date)

    if len(tokens) <= MAX_INPUT_TOKENS:
        # Small enough to go directly to GPT-4.1
        full_prompt = prompt_filled + "\n\nHere is the document:\n\n" + text
        try:
            logger.info(f"📤 Sending full document to GPT-4.1: {filepath}")
            response = openai.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": full_prompt}
                ],
                max_tokens=1000,
                temperature=0.2,
            )
            return clean_response_text(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"OpenAI API error (GPT-4.1): {e}")
            return None

    # Too big — summarize chunks with mini model
    chunks = chunk_text(text)
    summaries = []

    for i, chunk in enumerate(chunks, 1):
        summary_prompt = (
            f"Summarize this document chunk (part {i}/{len(chunks)}) "
            f"with a focus on private investment opportunities:\n\n{chunk}"
        )
        try:
            logger.info(f"🧩 Summarizing chunk {i}/{len(chunks)} with gpt-4o-mini...")
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant specialized in summarizing financial documents."},
                    {"role": "user", "content": summary_prompt}
                ],
                max_tokens=500,
                temperature=0.3,
            )
            summaries.append(clean_response_text(response.choices[0].message.content))
        except Exception as e:
            logger.error(f"Error summarizing chunk {i}: {e}")
            summaries.append(f"❌ Error summarizing chunk {i}")

    combined = "\n\n".join(summaries)
    final_prompt = prompt_filled + "\n\nHere is the combined summary:\n\n" + combined

    try:
        logger.info(f"📤 Sending combined summary to GPT-4.1 for final analysis...")
        final_response = openai.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": "You are a halpful assistant."},
                {"role": "user", "content": final_prompt}
            ],
            max_tokens=1000,
            temperature=0.2,
        )
        return clean_response_text(final_response.choices[0].message.content)
    except Exception as e:
        logger.error(f"OpenAI API error (final summary): {e}")
        return None
