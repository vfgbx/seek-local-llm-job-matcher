"""
seek_au_job_matcher.py

Automated SEEK Australia job-search assistant.

This script:
1. Opens a SEEK Australia search-results page with Selenium.
2. Collects job detail links from the search results.
3. Extracts job title, company, location, and job description.
4. Sends each job description to a local Ollama model for suitability screening.
5. Saves suitable jobs to CSV and all reviewed jobs to JSONL.

Important:
- This script uses a local Ollama endpoint by default.
- It does not apply for jobs automatically.
- It is intended for personal job-search workflow automation and human review.
- Always respect SEEK's terms of service and avoid aggressive scraping.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from typing import Any, Dict, List
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import pandas as pd
import requests
from bs4 import BeautifulSoup, NavigableString
from selenium import webdriver
from selenium.webdriver.safari.options import Options as SafariOptions


BASE_URL = "https://au.seek.com/deep-learning-jobs/in-New-South-Wales-NSW?sortmode=ListedDate"
SEEK_DOMAIN = "https://www.seek.com.au"

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gpt-oss:20b"

DEFAULT_LOCATION = "Australia"
DEFAULT_PAGES = 9999999
DEFAULT_PER_PAGE = 0
DEFAULT_OUT_CSV = "seek_au_matches.csv"
DEFAULT_OUT_JSONL = "seek_au_full_results.jsonl"

PAGE_DELAY_SECONDS = 1.0
JOB_DELAY_SECONDS = 0.5

LOCATION_REGEX = r"\b(NSW|VIC|QLD|WA|SA|ACT|TAS|NT)\b"

SYSTEM_PROMPT = 'You are a job-matching assistant.\n\nReturn ONLY one JSON object exactly like:\n{"suitable": true/false, "reason": "<中文一句话原因>"}\n\nCandidate facts (must assume true):\n- The candidate is a Chinese citizen.\n- The candidate holds an Australian Temporary Graduate visa (subclass 485) with full work rights.\n- The candidate is NOT an Australian citizen and NOT a permanent resident.\n\nRules:\n- Read the JOB description and the CANDIDATE profile.\n- Consider jobs related to computer science/software engineering, Python programming, algorithms, data engineering/analysis, machine learning (optional), computer vision (optional), automation/control systems, embedded systems, electronics, robotics, and interdisciplinary roles combining these areas.\n- WORK RIGHTS FILTER IS STRICT: If the job explicitly requires Australian Citizen / Permanent Resident (PR) / Citizenship / PR Only, then set "suitable": false.\n- YEARS OF EXPERIENCE REQUIREMENTS ARE STRICT. If the job explicitly requires X+ years of professional experience and the candidate does not have that experience, then set "suitable": false.\n- DEFENCE FILTER IS STRICT: If the job is related to defence, military, weapons, munitions, battlefield systems, intelligence, national security, surveillance for defence use, government defence contractors, or requires security clearance / NV1 / NV2 / Baseline / defence clearance, then set "suitable": false.\n- If the job does NOT explicitly require years of experience, then evaluate whether the candidate can reasonably perform the responsibilities based on skills, academic background, internships, and projects.\n- Consider required skills, technical stack if explicitly stated.\n- Output MUST be valid JSON only, with exactly two keys: "suitable" and "reason".\n- The "reason" must be in Chinese, concise (<= 20 Chinese characters preferred, <= 30 max), and mention the main deciding factor.\n- No extra fields, no markdown, no chit-chat.'

PROMPT_TEMPLATE = """[JOB]
Title: {title}
Company: {company}
Location: {job_location}
Description:
{description}

[CANDIDATE - ABOUT ME]
{about_me}

Only output the JSON as specified, nothing else.
"""

DEFAULT_ABOUT_ME = 'I am a recent Master of Computing and Innovation graduate from the University of Adelaide, with full Australian work rights on a Temporary Graduate visa subclass 485 valid until October 2028. I am based in Adelaide and open to relocate Australia-wide immediately, including Sydney, Melbourne, Brisbane, Perth and regional locations. I am also open to remote and hybrid roles. My technical background combines computing, data analysis, artificial intelligence, automation, and electrical engineering. I have hands-on experience in Python programming, data processing, API-based data collection, automation scripts, data cleaning, data validation, time-series analysis, statistical reporting, machine learning, deep learning, computer vision, image processing, model evaluation, debugging, technical documentation, and reproducible workflow development. My programming and technical skills include Python, Pandas, NumPy, Matplotlib, PyTorch, TensorFlow, OpenCV, MATLAB, Simulink, C, embedded C, PLC ladder logic, STM32, ATmega16, LabVIEW, Git, Visual Studio Code, CSV/Excel processing, API integration, structured reporting, data quality checks, sensor feedback analysis, PID control, control-system modelling, hardware/software troubleshooting, and engineering documentation. My key projects include an automated ASX market data collection and update pipeline using Python, Pandas and the Interactive Brokers API; a quantitative analysis and reporting workflow for time-series market data; a local LLM-powered evaluation assistant using structured prompts, scoring logic and human-in-the-loop review; a Transformer-based financial time-series modelling workflow; an end-to-end computer vision detection system using PyTorch, Faster R-CNN, ResNet-50 FPN, active learning, hard-negative mining and reproducible training scripts; and a PLC-based self-service pricing and heating control system involving ladder logic, ATmega16 integration, sensor handling, safety logic, simulation and hardware testing. My internships included engineering and robotics R&D environments where I supported control-system modelling, embedded validation, sensor feedback testing, PID control improvement, MATLAB/Simulink modelling, LabVIEW-assisted data review, STM32-based validation, system testing, troubleshooting, documentation, and collaboration with R&D, hardware, production and engineering teams. I am suitable for early-career technical roles that use my existing skills in Python, data analysis, automation, AI/ML, computer vision, software workflows, technical documentation, embedded systems, control systems, or engineering technology.'


def start_safari() -> webdriver.Safari:
    """Start a Safari WebDriver session.

    On macOS, run `safaridriver --enable` before using Safari automation.
    In Safari, you may also need to enable Develop -> Allow Remote Automation.
    """
    options = SafariOptions()
    driver = webdriver.Safari(options=options)
    driver.set_page_load_timeout(30)
    return driver


def build_search_url(location: str, page: int = 1, base_url: str = BASE_URL) -> str:
    """Build a SEEK search URL with page and location query parameters."""
    parsed = urlsplit(base_url)
    query = dict(parse_qsl(parsed.query))
    query["page"] = str(page)

    if location and location.strip():
        query["where"] = location.strip()

    return urlunsplit(parsed._replace(query=urlencode(query)))


def collect_job_links(driver: webdriver.Safari, search_url: str, limit_per_page: int) -> List[str]:
    """Collect job-detail links from one search-results page.

    SEEK pages load some content dynamically. The scroll loop triggers lazy
    loading before BeautifulSoup parses the final HTML snapshot.
    """
    driver.get(search_url)
    time.sleep(PAGE_DELAY_SECONDS)

    for _ in range(5):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(0.2)

    soup = BeautifulSoup(driver.page_source, "lxml")

    links: List[str] = []
    for anchor in soup.select("a[data-automation='jobTitle']"):
        href = anchor.get("href")
        if not href:
            continue

        full_url = urljoin(SEEK_DOMAIN, href)
        if full_url not in links:
            links.append(full_url)

        if limit_per_page > 0 and len(links) >= limit_per_page:
            break

    return links


def canonical_job_url(url: str) -> str:
    """Convert SEEK job URLs into stable /job/{id} URLs where possible."""
    match = re.search(r"jobId=(\d+)", url)
    if match:
        return f"{SEEK_DOMAIN}/job/{match.group(1)}"

    match = re.search(r"/job/(\d+)", url)
    if match:
        return f"{SEEK_DOMAIN}/job/{match.group(1)}"

    return url


def node_text(node: Any) -> str:
    """Return cleaned visible text from a BeautifulSoup node."""
    return node.get_text("\n", strip=True) if node else ""


def is_visible_text_element(element: Any) -> bool:
    """Remove script/style/no-script elements while allowing visible text nodes."""
    if isinstance(element, NavigableString):
        return True

    if getattr(element, "name", None) in {"script", "style", "noscript"}:
        return False

    return True


def extract_description_between_markers(soup: BeautifulSoup) -> str:
    """Extract the main job description from a SEEK job page.

    The function searches for text after Apply/Quick Apply/Save areas and stops
    around SEEK's "Be careful" safety notice. If the result is too short, it
    falls back to the standard jobAdDetails container.
    """
    start_candidates = []
    start_candidates.extend(
        soup.select("[data-automation*='apply'], [data-automation*='quick'], [data-automation*='save']")
    )
    start_candidates.extend(
        [
            button
            for button in soup.find_all(["button", "a"])
            if re.search(r"\b(quick\s*apply|apply now|apply|save)\b", node_text(button), re.I)
        ]
    )

    start_node = None
    for node in start_candidates:
        if node and getattr(node, "name", None) and node.get_text(strip=True):
            start_node = node
            break

    if not start_node:
        fallback = (
            soup.select_one("[data-automation='jobAdDetails']")
            or soup.select_one("div[data-automation='jobAdDetails']")
            or soup.select_one("article")
        )
        return node_text(fallback) if fallback else ""

    end_candidates = [
        node
        for node in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "strong", "b"])
        if re.search(r"\bbe\s+careful\b", node_text(node), re.I)
    ]
    end_node = end_candidates[0] if end_candidates else None

    allowed_tags = {"p", "li", "ul", "ol", "div", "section", "article", "span"}
    buffer: List[str] = []

    for element in start_node.next_elements:
        if element is end_node:
            break

        name = getattr(element, "name", None)
        if name in allowed_tags and is_visible_text_element(element):
            text = node_text(element)
            if text:
                buffer.append(text)

    description = "\n".join(buffer).strip()

    if len(description) < 300:
        fallback = (
            soup.select_one("[data-automation='jobAdDetails']")
            or soup.select_one("div[data-automation='jobAdDetails']")
            or soup.select_one("article")
        )
        if fallback:
            description = node_text(fallback)

    return description


def clean_job_description(description: str) -> str:
    """Remove repeated Save blocks and SEEK safety notice text."""
    save_lines = list(re.finditer(r"(?im)^[ \t]*save[ \t]*$", description))
    if save_lines:
        description = description[save_lines[-1].end():].lstrip()
    else:
        save_mentions = list(re.finditer(r"(?i)\bsave\b", description))
        if save_mentions:
            description = description[save_mentions[-1].end():].lstrip()

    careful_match = re.search(r"(?is)\bbe\s*careful\b", description)
    if careful_match:
        description = description[:careful_match.start()].rstrip()

    return description.strip()


def extract_job_detail(driver: webdriver.Safari, job_url: str, debug: bool = False) -> Dict[str, str]:
    """Open one job-detail page and extract structured information."""
    job_url = canonical_job_url(job_url)
    driver.get(job_url)
    time.sleep(JOB_DELAY_SECONDS)

    for _ in range(6):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(0.15)

    soup = BeautifulSoup(driver.page_source, "lxml")

    title = ""
    h1 = soup.select_one("h1[data-automation='job-detail-title']") or soup.select_one("h1")
    if h1:
        title = node_text(h1)

    if not title:
        meta_title = soup.select_one("meta[property='og:title']")
        if meta_title and meta_title.get("content"):
            title = meta_title["content"].strip()

    company = node_text(soup.select_one("[data-automation='advertiser-name']"))
    if not company and h1 and h1.parent:
        for line in h1.parent.get_text("\n", strip=True).split("\n")[1:4]:
            candidate = line.strip()
            if candidate and candidate != title and len(candidate) < 80:
                if not re.search(LOCATION_REGEX, candidate, re.I):
                    company = candidate
                    break

    location = node_text(soup.select_one("[data-automation='job-detail-location']"))
    if not location and h1 and h1.parent:
        for line in h1.parent.get_text("\n", strip=True).split("\n")[1:6]:
            if re.search(LOCATION_REGEX, line, re.I) or ("," in line and len(line) <= 60):
                location = line.strip()
                break

    description = clean_job_description(extract_description_between_markers(soup))

    if debug:
        preview = (description[:500] + ("..." if len(description) > 500 else "")).replace("\n", " ")
        print(f"\n[DEBUG] {job_url}")
        print(f"[DEBUG] title={title}")
        print(f"[DEBUG] company={company}")
        print(f"[DEBUG] location={location}")
        print(f"[DEBUG] desc_len={len(description)}")
        print(f"[DEBUG] desc_preview={preview}")

    return {
        "url": job_url,
        "title": title,
        "company": company,
        "location": location,
        "description": description,
    }


def judge_one_job_stateless(
    job: Dict[str, str],
    about_text: str,
    ollama_url: str = OLLAMA_URL,
    model: str = MODEL,
    debug_prompt: bool = False,
) -> Dict[str, Any]:
    """Send one job to a local Ollama model and parse its JSON decision."""
    prompt = PROMPT_TEMPLATE.format(
        title=job.get("title") or "(no title)",
        company=job.get("company") or "(unknown)",
        job_location=job.get("location") or "(unknown)",
        description=job.get("description") or "",
        about_me=(about_text or "").strip() or "(no additional info)",
    )

    if debug_prompt:
        print("\n===== PROMPT SENT TO MODEL =====\n")
        print(prompt)
        print("\n===== END PROMPT =====\n")

    payload = {
        "model": model,
        "system": SYSTEM_PROMPT,
        "prompt": prompt,
        "stream": False,
        "think": "high",
        "options": {"temperature": 0.0, "seed": 1234},
    }

    response = requests.post(ollama_url, json=payload, timeout=800)
    response.raise_for_status()

    raw_text = response.json().get("response", "").strip()

    try:
        parsed = json.loads(raw_text)
    except Exception:
        parsed = {"suitable": False, "reason": "bad-json"}

    return {
        "suitable": bool(parsed.get("suitable", False)),
        "reason": str(parsed.get("reason", ""))[:300],
        "raw": raw_text,
    }


def parse_args() -> argparse.Namespace:
    """Parse command-line options while keeping practical defaults."""
    parser = argparse.ArgumentParser(
        description="Filter SEEK Australia jobs with Selenium and a local Ollama model."
    )
    parser.add_argument("--location", default=DEFAULT_LOCATION, help="Search location.")
    parser.add_argument("--pages", type=int, default=DEFAULT_PAGES, help="Number of search-result pages to scan.")
    parser.add_argument("--per-page", type=int, default=DEFAULT_PER_PAGE, help="Jobs per page to scan. Use 0 for all collected jobs.")
    parser.add_argument("--about", default=DEFAULT_ABOUT_ME, help="Candidate profile used by the matching model.")
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV, help="CSV output path for suitable jobs.")
    parser.add_argument("--out-jsonl", default=DEFAULT_OUT_JSONL, help="JSONL output path for all reviewed jobs.")
    parser.add_argument("--base-url", default=BASE_URL, help="SEEK search URL.")
    parser.add_argument("--ollama-url", default=OLLAMA_URL, help="Local Ollama API endpoint.")
    parser.add_argument("--model", default=MODEL, help="Ollama model name.")
    parser.add_argument("--debug", action="store_true", help="Print extraction and prompt debug information.")
    return parser.parse_args()


def main() -> None:
    """Run the full job-search and local-LLM matching workflow."""
    args = parse_args()

    driver = start_safari()
    all_records: List[Dict[str, Any]] = []
    matched_records: List[Dict[str, Any]] = []

    try:
        for page in range(1, args.pages + 1):
            search_url = build_search_url(args.location, page, args.base_url)
            print(f"[INFO] page {page}: {search_url}")

            links = collect_job_links(driver, search_url, args.per_page)
            print(f"[INFO] collected {len(links)} links")

            if not links:
                print("[INFO] No links found on this page. Stopping early.")
                break

            for url in links:
                try:
                    job = extract_job_detail(driver, url, debug=args.debug)
                    result = judge_one_job_stateless(
                        job,
                        about_text=args.about,
                        ollama_url=args.ollama_url,
                        model=args.model,
                        debug_prompt=args.debug,
                    )

                    job_without_description = dict(job)
                    job_without_description.pop("description", None)

                    record = {
                        **job_without_description,
                        "model_json": {
                            "suitable": result["suitable"],
                            "reason": result["reason"],
                        },
                        "model_raw": result["raw"],
                    }
                    all_records.append(record)

                    if result["suitable"]:
                        matched_records.append({**job_without_description, "reason": result["reason"]})

                    title_preview = (job.get("title") or "(no title)")[:60]
                    print(f"  - {title_preview} | suitable={result['suitable']} | reason={result['reason']}")

                except Exception as exc:
                    print(f"[WARN] job failed: {url} -> {type(exc).__name__}: {exc}")

    finally:
        try:
            driver.quit()
        except Exception:
            pass

    if matched_records:
        pd.DataFrame(matched_records).to_csv(args.out_csv, index=False)
        print(f"[SAVE] suitable matches -> {args.out_csv}")
    else:
        print("[INFO] No suitable matches found. CSV not created.")

    with open(args.out_jsonl, "w", encoding="utf-8") as file:
        for record in all_records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"[SAVE] all reviewed jobs -> {args.out_jsonl}")
    print("[DONE]")


if __name__ == "__main__":
    main()
