import os
import json
import logging
import aiohttp
import asyncio
import async_timeout
import traceback
import random
from pathlib import Path
from pdfminer.high_level import extract_text
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.198 Safari/537.36",
]

SEMAPHORE_LIMIT = 5
RETRY_ATTEMPTS = 3
TIMEOUT_SECS = 20

async def download_file(session, url, save_path, only_pdf=False, timeout_secs=TIMEOUT_SECS):
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": url,
        "Connection": "keep-alive",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1"
    }

    try:
        async with async_timeout.timeout(timeout_secs):
            async with session.get(url, headers=headers, allow_redirects=True, ssl=False) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    content_type = resp.content_type.lower()

                    if only_pdf:
                        if "pdf" not in content_type:
                            logger.warning(f"❌ Skipping non-PDF {url}")
                            return
                        final_path = save_path if save_path.endswith(".pdf") else save_path + ".pdf"
                    else:
                        if "pdf" in content_type or url.lower().endswith(".pdf"):
                            final_path = save_path if save_path.endswith(".pdf") else save_path + ".pdf"
                        else:
                            final_path = save_path if save_path.endswith(".html") else save_path + ".html"

                    with open(final_path, "wb") as f:
                        f.write(content)

                    logger.info(f"✅ Downloaded {final_path} ({content_type})")
                else:
                    logger.error(f"❌ Failed to download {url}, HTTP {resp.status}")
                    raise aiohttp.ClientResponseError(
                        resp.request_info,
                        resp.history,
                        status=resp.status,
                        message=f"Unexpected content type: {resp.content_type}",
                        headers=resp.headers
                    )
    except asyncio.TimeoutError:
        logger.error(f"⏱️ Timeout when downloading {url}")
        raise
    except Exception as e:
        logger.error(f"❌ Error downloading {url}: {repr(e)}\n{traceback.format_exc()}")
        raise

async def download_with_retries(url, save_path, session, semaphore, only_pdf=False):
    async with semaphore:
        for attempt in range(RETRY_ATTEMPTS):
            try:
                await asyncio.sleep(random.uniform(1, 3))
                await download_file(session, url, save_path, only_pdf=only_pdf)
                return
            except Exception:
                logger.warning(f"🔁 Retry {attempt + 1} for {url}")
        logger.error(f"❌ All retries failed for {url}")

async def download_files_from_ready_candidates(ready_candidates_path, base_pages_folder="pages", only_pdf=False):
    with open(ready_candidates_path, "r", encoding="utf-8") as f:
        candidates = json.load(f)

    file_candidates = [c for c in candidates if c.get("url", "").strip()]

    if not file_candidates:
        logger.info("ℹ️ No file URLs found in ready_candidates.json")
        return

    latest_folder = os.path.dirname(ready_candidates_path)
    download_folder = os.path.join(latest_folder, "downloads")
    os.makedirs(download_folder, exist_ok=True)

    semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)

    async with aiohttp.ClientSession() as session:
        tasks = []
        for entry in file_candidates:
            url = entry["url"]
            ext = ".pdf" if url.lower().endswith(".pdf") else ".html"
            filename = f"{entry['hash']}{ext}"
            save_path = os.path.join(download_folder, filename)
            tasks.append(download_with_retries(url, save_path, session, semaphore, only_pdf=only_pdf))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"⚠️ Download task {i} raised an exception: {repr(result)}")

    logger.info(f"📥 Attempted to download {len(file_candidates)} files into {download_folder}")

def convert_files_to_text(base_folder, only_pdf=False):
    download_folder = os.path.join(base_folder, "downloads")
    txt_folder = os.path.join(base_folder, "txt")
    os.makedirs(txt_folder, exist_ok=True)

    if only_pdf:
        files = list(Path(download_folder).glob("*.pdf"))
    else:
        files = list(Path(download_folder).glob("*.*"))

    if not files:
        logger.info("ℹ️ No files found to convert.")
        return

    for file_path in files:
        try:
            text = ""
            if file_path.suffix.lower() == ".pdf":
                text = extract_text(str(file_path))
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    soup = BeautifulSoup(f, "html.parser")
                    # Optional: extract main content container if exists
                    main_div = soup.find("div", class_="main-container container-fluid")
                    text = main_div.get_text(separator="\n", strip=True) if main_div else soup.get_text(separator="\n", strip=True)

            txt_path = os.path.join(txt_folder, f"{file_path.stem}.txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(text)

            logger.info(f"📝 Converted {file_path.name} to text.")
        except Exception as e:
            logger.error(f"❌ Error converting {file_path.name} to text: {repr(e)}\n{traceback.format_exc()}")
