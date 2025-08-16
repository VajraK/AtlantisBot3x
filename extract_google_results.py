import os
import glob
import json
import yaml
from bs4 import BeautifulSoup
import hashlib

def generate_hash(name, url, description):
    # Combine fields into one string
    combined = f"{name}|{url}|{description}"
    # Create SHA-256 hash and return as hex string (shortened if you want)
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()[:16]  # 16 chars for brevity

def extract_results_from_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    results = []

    containers = soup.select('div.tF2Cxc')

    for g in containers:
        title_tag = g.select_one('h3')
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)

        link_tag = g.select_one('a')
        if not link_tag or not link_tag.has_attr('href'):
            continue
        url = link_tag['href']

        # Attempt snippet extraction using multiple fallback methods:
        description = ''

        # 1. Try known class selectors first
        snippet_tag = g.select_one('div.IsZvec') or g.select_one('span.aCOpRe')
        if snippet_tag:
            description = snippet_tag.get_text(separator=' ', strip=True)
        else:
            # 2. As fallback, get all text in container excluding title and link text
            full_text = g.get_text(separator=' ', strip=True)
            # Remove title text from full_text
            description = full_text.replace(title, '').strip()

            # If link text appears inside full_text, also remove it
            link_text = link_tag.get_text(strip=True)
            if link_text:
                description = description.replace(link_text, '').strip()

            # Optionally, trim description length to avoid clutter
            if len(description) > 300:
                description = description[:300] + '...'

        # Generate hash for this entry
        entry_hash = generate_hash(title, url, description)

        results.append({
            'hash': entry_hash,
            'name': title,
            'url': url,
            'description': description
        })

    return results

def load_all_html_files(folder_path):
    pattern = os.path.join(folder_path, '**', '*.html')
    return glob.glob(pattern, recursive=True)

def extract_all_results(
    html_folder='./pages',
    output_file='extracted_results.yaml',
    output_format='yaml'
):
    all_results = []

    html_files = load_all_html_files(html_folder)

    for html_file in html_files:
        with open(html_file, 'r', encoding='utf-8') as f:
            content = f.read()
            extracted = extract_results_from_html(content)
            all_results.extend(extracted)

    # Deduplicate by URL
    unique_results = list({r['url']: r for r in all_results}.values())

    if output_format.lower() == 'json':
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(unique_results, f, indent=2, ensure_ascii=False)
    else:
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(unique_results, f, allow_unicode=True)

    return unique_results
