import yaml
import os
import asyncio
import json
import logging
import shutil
import hashlib
import random
import string
from datetime import datetime
from logging.handlers import RotatingFileHandler
from telegram_sender import TelegramSender
from pathlib import Path
from google_scraper import scrape_google_links
from extract_google_results import extract_all_results
from ai_api import rate_entries_with_gpt
from file_work import download_files_from_ready_candidates, convert_files_to_text
from pdf_work import download_pdfs_from_ready_candidates, convert_pdfs_to_text
from ai_api_final import analyze_txt_file

# ------------------- Logging Setup -------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

for handler in logger.handlers[:]:
    logger.removeHandler(handler)

formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
file_handler = RotatingFileHandler("main.log", maxBytes=5_000_000, backupCount=5, encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

# ------------------- Config Loader -------------------
def load_config(path="config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)

# ------------------- Analysis -------------------
async def analyze_all_txts(base_folder):
    txt_folder = os.path.join(base_folder, "txt")
    ready_json_path = os.path.join(base_folder, "ready_candidates.json")

    with open(ready_json_path, "r", encoding="utf-8") as f:
        candidates = json.load(f)
        hash_entry_map = {item["hash"]: item for item in candidates}

    sender = TelegramSender()

    for txt_file in Path(txt_folder).glob("*.txt"):
        hash_name = txt_file.stem
        logger.info(f"🔍 Analyzing: {hash_name}.txt")

        entry = hash_entry_map.get(hash_name)
        if not entry:
            logger.warning(f"⚠️ No matching entry in ready_candidates.json for hash: {hash_name}")
            continue

        try:
            result = await analyze_txt_file(str(txt_file))
            if result:
                entry["result"] = result
                await sender.send_filing_result(result, entry["url"])
        except Exception as e:
            logger.error(f"❌ Error processing {txt_file.name}: {e}")

    with open(ready_json_path, "w", encoding="utf-8") as f:
        json.dump(list(hash_entry_map.values()), f, indent=2, ensure_ascii=False)

    logger.info(f"💾 Updated ready_candidates.json with analysis results")

# ------------------- Ready Candidates -------------------
def save_ready_candidates(combined_results_path, ratings_path, output_path, threshold=5):
    with open(combined_results_path, "r", encoding="utf-8") as f:
        combined_results = json.load(f)
    with open(ratings_path, "r", encoding="utf-8") as f:
        ratings = json.load(f)
    ready_candidates = [
        entry for entry in combined_results
        if ratings.get(entry.get("hash"), 0) >= threshold
    ]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(ready_candidates, f, indent=2, ensure_ascii=False)
    logger.info(f"✅ Saved {len(ready_candidates)} ready candidates with rating >= {threshold} to {output_path}")

# ------------------- Main Async -------------------
# ------------------- Main Async -------------------
async def async_main():
    config = load_config()
    queries = config.get("google", {}).get("queries")
    if not queries:
        default_query = config.get("google", {}).get("query", 'site:*.com filetype:pdf investment memo')
        queries = [default_query]

    download_type = config.get("download_type", "pdf")  # 'pdf' or 'page'

    # Generate a single hash for this run
    import hashlib
    import random
    import string

    random_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    run_hash = hashlib.md5(random_str.encode()).hexdigest()[:8]

    logger.info(f"🔍 Running Google search for queries: {queries} with download_type='{download_type}' and hash={run_hash}")

    pages_limit = config.get("google", {}).get("pages_limit", 1)
    per_query_folders = []

    # ------------------- Process Each Query -------------------
    for query in queries:
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        query_folder = Path("pages") / f"{timestamp}-{run_hash}"
        query_folder.mkdir(parents=True, exist_ok=True)
        per_query_folders.append(query_folder)

        logger.info(f"\n🔍 Searching Google for: '{query}' -> saving to {query_folder}")
        try:
            html_files = await scrape_google_links(query=query, pages_limit=pages_limit, folder_path=str(query_folder))
            if html_files:
                logger.info(f"✅ Saved {len(html_files)} HTML page(s) to {query_folder}")
            else:
                logger.info(f"❌ No pages saved for query: '{query}'")
        except Exception as e:
            logger.error(f"❌ Error running query '{query}': {e}")

    # ------------------- Combine All Queries Into Single Run Folder -------------------
    combined_folder = Path("pages") / run_hash
    combined_folder.mkdir(parents=True, exist_ok=True)
    all_html_paths = []

    for folder in per_query_folders:
        for file_path in folder.glob("*"):
            if file_path.is_file():
                unique_name = f"{file_path.stem}_{random.randint(0,9999)}{file_path.suffix}"
                shutil.copy(file_path, combined_folder / unique_name)
                all_html_paths.append(combined_folder / unique_name)

    if not all_html_paths:
        logger.info("ℹ️ No new HTML files generated.")
        return

    logger.info(f"🆕 Combined {len(all_html_paths)} HTML file(s) into {combined_folder}")

    # ------------------- Extraction and Processing -------------------
    combined_json_path = combined_folder / "combined_results.json"
    extracted = extract_all_results(html_folder=combined_folder, output_file=combined_json_path, output_format='json')
    logger.info(f"✅ Extracted {len(extracted)} unique results into {combined_json_path}")

    logger.info("🤖 Sending results to OpenAI for investment relevance rating...")
    ratings = await rate_entries_with_gpt(extracted)

    ratings_file = combined_folder / "ratings.json"
    with open(ratings_file, "w", encoding="utf-8") as f:
        json.dump(ratings, f, indent=2, ensure_ascii=False)
    logger.info(f"📊 Saved ratings to {ratings_file}")

    ready_candidates_file = combined_folder / "ready_candidates.json"
    save_ready_candidates(combined_json_path, ratings_file, ready_candidates_file)

    # Download and convert depending on type
    if download_type == "pdf":
        await download_pdfs_from_ready_candidates(str(ready_candidates_file))
        convert_pdfs_to_text(combined_folder)
    else:  # any page
        await download_files_from_ready_candidates(str(ready_candidates_file))
        convert_files_to_text(combined_folder)

    await analyze_all_txts(combined_folder)

# ------------------- Entry Point -------------------
def main():
    asyncio.run(async_main())

if __name__ == "__main__":
    main()
