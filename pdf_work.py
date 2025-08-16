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


async def download_pdf(session, url, save_path, timeout_secs=TIMEOUT_SECS):
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/pdf,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": url,
        "Connection": "keep-alive",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1"
    }

    try:
        async with async_timeout.timeout(timeout_secs):
            async with session.get(url, headers=headers, allow_redirects=True, ssl=False) as resp:
                if resp.status == 200 and "application/pdf" in resp.content_type:
                    content = await resp.read()
                    with open(save_path, "wb") as f:
                        f.write(content)
                    logger.info(f"✅ Downloaded PDF: {save_path}")
                else:
                    logger.error(f"❌ Failed to download {url}, HTTP {resp.status}, Content-Type: {resp.content_type}")
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


async def download_with_retries(url, save_path, session, semaphore):
    async with semaphore:
        for attempt in range(RETRY_ATTEMPTS):
            try:
                await asyncio.sleep(random.uniform(1, 3))  # random delay between attempts
                await download_pdf(session, url, save_path)
                return
            except Exception:
                logger.warning(f"🔁 Retry {attempt + 1} for {url}")
        logger.error(f"❌ All retries failed for {url}")


async def download_pdfs_from_ready_candidates(ready_candidates_path, base_pages_folder="pages"):
    with open(ready_candidates_path, "r", encoding="utf-8") as f:
        candidates = json.load(f)

    pdf_candidates = [c for c in candidates if c.get("url", "").strip().lower().endswith(".pdf")]
    if not pdf_candidates:
        logger.info("ℹ️ No PDF URLs found in ready_candidates.json")
        return

    latest_folder = os.path.dirname(ready_candidates_path)
    pdf_folder = os.path.join(latest_folder, "pdf")
    os.makedirs(pdf_folder, exist_ok=True)

    semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)

    async with aiohttp.ClientSession() as session:
        tasks = []
        for entry in pdf_candidates:
            url = entry["url"]
            filename = f"{entry['hash']}.pdf"
            save_path = os.path.join(pdf_folder, filename)
            tasks.append(download_with_retries(url, save_path, session, semaphore))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"⚠️ Download task {i} raised an exception: {repr(result)}")

    logger.info(f"📥 Attempted to download {len(pdf_candidates)} PDFs into {pdf_folder}")


def convert_pdfs_to_text(base_folder):
    pdf_folder = os.path.join(base_folder, "pdf")
    txt_folder = os.path.join(base_folder, "txt")
    os.makedirs(txt_folder, exist_ok=True)

    pdf_files = list(Path(pdf_folder).glob("*.pdf"))
    if not pdf_files:
        logger.info("ℹ️ No PDFs found to convert.")
        return

    for pdf_file in pdf_files:
        try:
            text = extract_text(str(pdf_file))
            txt_path = os.path.join(txt_folder, f"{pdf_file.stem}.txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(text)
            logger.info(f"📝 Converted {pdf_file.name} to text.")
        except Exception as e:
            logger.error(f"❌ Error converting {pdf_file.name} to text: {repr(e)}\n{traceback.format_exc()}")
