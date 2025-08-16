# Atlantis Bot 3x

![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![Node.js](https://img.shields.io/badge/node.js-16+-green.svg)

An automated investment opportunity finder that scans Google for PDF documents containing potential private investment opportunities, analyzes them using AI, and delivers actionable results via Telegram.

## Features

- **Automated Google Search**: Scrapes Google results for PDFs matching financial opportunity keywords
- **AI-Powered Analysis**: Uses OpenAI's GPT models to:
  - Pre-filter potentially relevant documents
  - Analyze document content for investment opportunities
- **Smart Processing**:
  - Handles large documents with chunking and summarization
  - Deduplicates results
  - Converts PDFs to text for analysis
- **Telegram Integration**: Sends formatted results directly to Telegram
- **Scheduled Operation**: Runs daily at configured times

## Components

| File                        | Description                                     |
| --------------------------- | ----------------------------------------------- |
| `main.py`                   | Main orchestration script                       |
| `ai_api.py`                 | Initial document relevance rating with GPT      |
| `ai_api_final.py`           | Detailed document analysis with GPT             |
| `google_scraper.js`         | Node.js Google scraping with CAPTCHA solving    |
| `google_scraper.py`         | Python wrapper for the Node.js scraper          |
| `extract_google_results.py` | Extracts and processes search results from HTML |
| `pdf_work.py`               | Handles PDF downloading and text conversion     |
| `telegram_sender.py`        | Manages Telegram notifications                  |
| `start.py`                  | Scheduled execution controller                  |
| `config.yaml`               | Configuration file (see example below)          |

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/VajraK/AtlantisBot2
   cd AtlantisBot2
   ```

2. **Install Python dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Install Node.js dependencies:**

   ```bash
   npm install puppeteer puppeteer-extra puppeteer-extra-plugin-stealth puppeteer-extra-plugin-recaptcha js-yaml
   ```

4. **Set up configuration:**
   - Copy `config_example.yaml` to `config.yaml`
   - Fill in all required API keys and settings

## Configuration

Example `config.yaml`:

```yaml
telegram_bot_token: "your_bot_token"
telegram_chat_id: "your_chat_id"

google:
  queries:
    - '("seeking funding" OR "raising capital" OR ...) filetype:pdf'
  pages_limit: 3

openai:
  api_key: "your_openai_key"

twoCaptchaApiKey: "your_2captcha_key"

schedule:
  hour: 6 # 6 AM
  minute: 0

prompt: |
  Analyze the following former-PDF for any private investment opportunities...
```

### Required services:

- OpenAI API key
- Telegram bot token and chat ID
- 2Captcha API key (for CAPTCHA solving)

## Usage

### Manual Run

```bash
python main.py
```

### Scheduled Execution

```bash
python start.py
```

The bot will run daily at the time specified in `config.yaml`.

## Workflow

1. **Search Phase:**

   - Executes Google searches with configured queries
   - Solves CAPTCHAs automatically
   - Saves HTML results

2. **Processing Phase:**

   - Extracts search results from HTML
   - Uses GPT to rate initial relevance (YES/NO)
   - Downloads PDFs of promising candidates

3. **Analysis Phase:**
   - Converts PDFs to text
   - Uses GPT to analyze content for investment opportunities
   - Sends formatted results to Telegram

## Requirements

- Python 3.9+
- Node.js 16+
- Supported platforms: Linux, macOS, Windows

## Troubleshooting

- Check `main.log` for detailed operation logs. Common issues:
  - CAPTCHA solving failures: Ensure your 2Captcha API key is valid and has balance
  - API limits: Check your OpenAI quota if analysis fails
  - PDF download issues: Some servers may block automated downloads

## License

MIT License

<3
