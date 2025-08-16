const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const RecaptchaPlugin = require('puppeteer-extra-plugin-recaptcha');
const readline = require('readline');
const fs = require('fs');
const yaml = require('js-yaml');
const path = require('path');

const config = yaml.load(fs.readFileSync('./config.yaml', 'utf8'));

puppeteer.use(StealthPlugin());
puppeteer.use(
  RecaptchaPlugin({
    provider: {
      id: '2captcha',
      token: config.twoCaptchaApiKey
    },
    visualFeedback: true,
    solveScoreBased: true,
    solveInactiveChallenges: true,
    solveInViewportOnly: false,
    solveTimeout: 300000
  })
);

async function delay(ms, reason = '') {
  if (reason) console.error(`⏳ Waiting ${ms / 1000}s - ${reason}`);
  return new Promise(resolve => setTimeout(resolve, ms));
}

function buildSearchUrl(query, start = 0) {
  return `https://www.google.com/search?q=${encodeURIComponent(query)}&hl=en-GB&tbs=qdr:d&start=${start}`;
}

async function scrapeGoogleResults(query, pagesLimitFromInput, folderPath) {
  // Ensure the target folder exists
  fs.mkdirSync(folderPath, { recursive: true });

  const browser = await puppeteer.launch({
    headless: false,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-blink-features=AutomationControlled',
      '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    ],
    defaultViewport: null,
    slowMo: 50
  });

  const page = await browser.newPage();
  await page.setUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36");

  page.setDefaultNavigationTimeout(180000);
  page.setDefaultTimeout(60000);

  const results = [];
  let currentPage = 0;

  // Use pagesLimitFromInput or fallback to config.maxPages or default 3
  const maxPages = pagesLimitFromInput || config.maxPages || 3;

  let keepGoing = true;

  try {
    while (keepGoing) {
      if (currentPage >= maxPages) {
        console.error(`🛑 Reached max page limit from input/config (${maxPages}), stopping.`);
        break;
      }

      const url = buildSearchUrl(query, currentPage * 10);
      console.error(`🌐 Navigating to page ${currentPage + 1}: ${url}`);

      await page.goto(url, { waitUntil: 'networkidle2', timeout: 180000 });
      await delay(5000, 'Initial page load');

      // 🔁 CAPTCHA loop
      let captchaLoopCount = 0;
      const captchaMaxRetries = 5;

      while (captchaLoopCount < captchaMaxRetries) {
        const captchaVisible = await page.$('iframe[src*="recaptcha"]') !== null;

        if (!captchaVisible) {
          console.error('🔓 No CAPTCHA detected, continuing...');
          break;
        }

        console.error(`🔒 CAPTCHA detected. Solving attempt ${captchaLoopCount + 1}/${captchaMaxRetries}...`);
        const { solved, error } = await page.solveRecaptchas().catch(err => ({ solved: [], error: err }));

        if (solved?.length > 0) {
          console.error(`✅ Solved ${solved.length} CAPTCHA(s)`);
          await delay(8000, 'Waiting after solving CAPTCHA');
          // Optionally reload to re-trigger content
          await page.reload({ waitUntil: 'networkidle2' });
        } else {
          console.error(`⚠️ CAPTCHA solve failed: ${error?.message || 'unknown error'}`);
          await delay(10000, 'Waiting before retry');
        }

        captchaLoopCount++;
      }

      if (captchaLoopCount >= captchaMaxRetries) {
        console.error('❌ Too many CAPTCHA loops, skipping this page.');
        await page.screenshot({ path: path.join(folderPath, `captcha-failure-page-${currentPage + 1}.png`) });
        currentPage++;
        continue;
      }

      // 🍪 Accept cookie banner if present
      try {
        const acceptSelectors = [
          'div.QS5gu.sy4vM',
          'div[role="button"]:has-text("Accept all")',
          'button:has-text("Accept all")',
          'button:has-text("I agree")',
          'div[role="button"]:has-text("Akceptuję")',
          'button[aria-label="Accept all"]',
        ];

        for (const selector of acceptSelectors) {
          const btn = await page.$(selector);
          if (btn) {
            await btn.click();
            console.error('🍪 Clicked "Accept all" consent button');
            await delay(3000, 'Waiting after accepting cookies');
            break;
          }
        }
      } catch (err) {
        console.error('⚠️ Cookie consent handling failed:', err.message);
      }

      // 📝 Save HTML content
      try {
        const safeFilename = `google-results-page-${currentPage + 1}.html`;
        const filePath = path.join(folderPath, safeFilename);

        const htmlContent = await page.content();
        fs.writeFileSync(filePath, htmlContent, 'utf8');

        console.error(`✅ Saved HTML to ${filePath}`);
        results.push(filePath);
      } catch (err) {
        console.error(`❌ Failed to save HTML: ${err.message}`);
      }

      // ⏭️ Go to next page if available
      const nextButton = await page.$('a#pnnext');
      if (nextButton) {
        currentPage++;
        await delay(2000, 'Waiting before next page');
      } else {
        console.error('ℹ️ No Next button found, ending pagination.');
        keepGoing = false;
      }
    }
  } catch (err) {
    console.error(`❌ Critical error during scraping: ${err.message}`);
    await page.screenshot({ path: path.join(folderPath, 'error-screenshot.png') });
  } finally {
    await browser.close();
  }

  return results;
}

// 🧠 CLI entrypoint for Python integration
async function main() {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false
  });

  let inputData = '';
  for await (const line of rl) {
    inputData += line;
  }

  try {
    const { query, pages_limit, folder_path } = JSON.parse(inputData);
    const results = await scrapeGoogleResults(query, pages_limit, folder_path);
    console.log(JSON.stringify({ success: true, results }));
  } catch (err) {
    console.log(JSON.stringify({ success: false, error: err.message }));
    process.exit(1);
  }
}

if (require.main === module) {
  main().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

module.exports = { scrapeGoogleResults };