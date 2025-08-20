# duplicate_checker.py
import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
import openai
import yaml
import re

logger = logging.getLogger(__name__)

def load_config(path="config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def clean_response_text(text: str) -> str:
    text = re.sub(r'^\s*```(?:json)?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```\s*$', '', text, flags=re.IGNORECASE)
    return text.strip()

def get_recent_results(base_folder="pages", exclude_hash: Optional[str] = None, hours_back=48, limit=50) -> List[str]:
    """
    Load up to `limit` results from the last 48 hours (or specified hours),
    excluding the provided hash if specified.
    """
    cutoff_time = datetime.now() - timedelta(hours=hours_back)
    entries = []
    
    base_path = Path(base_folder)
    if not base_path.exists():
        return []
    
    for folder in base_path.iterdir():
        if not folder.is_dir():
            continue
            
        # Check if folder is recent enough
        try:
            folder_time = datetime.fromtimestamp(folder.stat().st_mtime)
            if folder_time < cutoff_time:
                continue
        except:
            continue
        
        # Look for ready_candidates.json in this folder
        candidates_path = folder / "ready_candidates.json"
        if not candidates_path.exists():
            continue
            
        try:
            with open(candidates_path, "r", encoding="utf-8") as f:
                candidates = json.load(f)
                
            for candidate in candidates:
                # Skip excluded hash
                if exclude_hash and candidate.get("hash") == exclude_hash:
                    continue
                    
                # Get the result if available
                result = candidate.get("result")
                if result and result.strip() and result.strip() != "X":
                    # Use modification time of the folder for sorting
                    folder_mtime = folder.stat().st_mtime
                    entries.append((folder_mtime, result))
                    
        except Exception as e:
            logger.warning(f"Error reading {candidates_path}: {e}")
            continue
    
    # Sort by most recent (descending)
    entries.sort(reverse=True, key=lambda x: x[0])
    # Return only content of top `limit` entries
    return [content for _, content in entries[:limit]]

async def is_duplicate(new_text: str, new_hash: Optional[str] = None) -> bool:
    """
    Returns True if the new_text is semantically duplicative of recent results.
    """
    if not new_text or new_text.strip() == "X":
        return False  # Don't waste GPT calls on non-substantive filings

    old_texts = get_recent_results(exclude_hash=new_hash, hours_back=48, limit=50)
    if not old_texts:
        return False

    # If we have too many old texts, truncate to fit token limits
    total_length = sum(len(text) for text in old_texts)
    max_old_texts_length = 15000  # Rough token estimate
    
    if total_length > max_old_texts_length:
        # Truncate oldest texts first (they're at the end since we sorted reverse)
        truncated_texts = []
        current_length = 0
        for text in reversed(old_texts):
            if current_length + len(text) > max_old_texts_length:
                break
            truncated_texts.append(text)
            current_length += len(text)
        old_texts = list(reversed(truncated_texts))

    prompt = f"""
You are a financial analyst reviewing summaries of investment opportunities for potential duplication.

You are given a **NEW investment summary** and a list of **OLD investment summaries** from the past 48 hours.

Determine if the new summary is **semantically duplicative** of any previous ones — meaning it describes essentially the same investment opportunity, company, deal structure, terms, or parties.

Summaries may differ in wording or formatting, but if they describe the same investment opportunity or closely related deals, they are considered duplicates.

Reply ONLY with one word:
- "YES" if it's a duplicate
- "NO" if it's materially different or substantively unique

NEW SUMMARY:
{new_text}

OLD SUMMARIES:
{"\n\n---\n\n".join(old_texts)}
"""

    config = load_config()
    api_key = config.get("openai", {}).get("api_key")
    if not api_key:
        logger.error("Missing OpenAI API key in config.yaml")
        return False

    openai.api_key = api_key

    try:
        logger.info("🤖 Checking for semantic duplicates with GPT...")
        response = openai.chat.completions.create(
            model="gpt-4o-mini",  # Use cheaper model for this check
            messages=[
                {"role": "system", "content": "You are a helpful assistant that checks for semantic duplication in investment summaries."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=10,
            temperature=0.1,
        )
        raw_output = response.choices[0].message.content
        cleaned_output = clean_response_text(raw_output)
        
        is_dup = cleaned_output.strip().lower().startswith("yes")
        logger.info(f"✅ Duplicate check result: {'DUPLICATE' if is_dup else 'UNIQUE'}")
        return is_dup
        
    except Exception as e:
        logger.error(f"❌ Error in duplicate check: {e}")
        # On error, assume it's not a duplicate to avoid false positives
        return False