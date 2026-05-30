# SEEK Local LLM Job Matcher

A Python-based job-search automation project that collects job listings from SEEK Australia and SEEK New Zealand, extracts job descriptions, and uses a local Ollama language model to evaluate whether each role is suitable for a specific candidate profile.

This project is designed as a personal workflow automation tool and portfolio project. It demonstrates practical skills in browser automation, web data extraction, prompt engineering, local LLM integration, structured output validation, CSV/JSONL reporting, and human-in-the-loop job-search decision support.

---

## Recommended GitHub Repository Name

Recommended:

```text
seek-local-llm-job-matcher
```

Other good options:

```text
seek-job-matching-automation
local-llm-job-search-assistant
seek-ai-job-screening-pipeline
job-search-automation-with-ollama
```

My strongest recommendation is:

```text
seek-local-llm-job-matcher
```

This name is clear, professional, and directly describes the purpose of the project without exaggerating what it does.

---

## Suggested GitHub Description

```text
Selenium and Ollama-based job-search assistant for extracting SEEK job ads and screening role suitability with structured local LLM prompts.
```

A shorter version:

```text
Local LLM job-matching automation for SEEK Australia and New Zealand.
```

---

## Project Structure

A clean repository structure can look like this:

```text
seek-local-llm-job-matcher/
├── README.md
├── requirements.txt
├── scripts/
│   ├── seek_au_job_matcher.py
│   └── seek_nz_job_matcher.py
└── outputs/
    └── .gitkeep
```

The `scripts/` folder contains the source code. The `outputs/` folder can store generated CSV and JSONL files, but most output files should usually be ignored by Git unless you intentionally want to publish examples.

---

## What This Project Does

This project automates the first stage of job searching.

Instead of manually opening every job listing and reading every description, the script:

1. Opens a SEEK search page with Selenium.
2. Scrolls the page to trigger dynamic content loading.
3. Collects job-detail links.
4. Opens each job page.
5. Extracts the title, company, location, and job description.
6. Sends the structured job information to a local Ollama model.
7. Asks the model to return a strict JSON decision.
8. Saves suitable jobs to a CSV file.
9. Saves all reviewed jobs to a JSONL audit file.

The final output is not meant to replace human judgement. It is a filtering assistant that reduces repetitive manual reading and helps the user focus on roles that are more likely to be relevant.

---

## Files

### `seek_au_job_matcher.py`

This script targets SEEK Australia.

It assumes the candidate:

- Is a Chinese citizen
- Holds an Australian Temporary Graduate visa, subclass 485
- Has full work rights in Australia
- Is not an Australian citizen
- Is not an Australian permanent resident

The model is instructed to reject jobs that explicitly require:

- Australian citizenship
- Permanent residency
- Citizen-only or PR-only eligibility
- Defence clearance or national security clearance
- Professional experience beyond the candidate's early-career level

The default search URL is configured for deep-learning-related jobs in New South Wales, but this can be changed in the script or through command-line arguments.

---

### `seek_nz_job_matcher.py`

This script targets SEEK New Zealand.

It assumes the candidate:

- Is a Chinese citizen
- Does not currently hold New Zealand work rights
- Would require employer sponsorship to work full-time in New Zealand
- Is not a New Zealand citizen
- Is not a New Zealand permanent resident

The model is instructed to reject jobs that explicitly require:

- Current New Zealand work rights
- New Zealand citizenship
- New Zealand permanent residency
- No sponsorship
- Defence clearance or national security clearance
- Professional experience beyond the candidate's early-career level

This version is stricter on work-rights filtering because the candidate would need sponsorship for New Zealand roles.

---

## Core Workflow

The workflow can be visualised as:

```text
SEEK search page
        ↓
Collect job links
        ↓
Open each job-detail page
        ↓
Extract job information
        ↓
Build structured prompt
        ↓
Send prompt to local Ollama model
        ↓
Parse JSON response
        ↓
Save matched jobs and full review log
```

---

## Why a Local LLM?

This project uses a local Ollama model instead of a cloud API.

The advantages are:

- The candidate profile stays local.
- Job-screening prompts can be customised freely.
- The workflow can run without paid API calls.
- The script can be adjusted for different countries, visa conditions, job types, or filtering rules.
- The local model can be used as a repeatable decision-support component.

The default endpoint is:

```text
http://localhost:11434/api/generate
```

The default model name is:

```text
gpt-oss:20b
```

You can change the model name in the code or through command-line arguments.

---

## Local LLM Decision Format

The model is required to return one JSON object only:

```json
{"suitable": true, "reason": "技能匹配"}
```

or:

```json
{"suitable": false, "reason": "需要PR"}
```

The strict JSON format makes the output easy to parse automatically.

The script stores two versions of the model output:

1. `model_json`  
   A cleaned version containing `suitable` and `reason`.

2. `model_raw`  
   The original raw model response, useful for debugging and auditing.

---

## Prompt Design

Each job is sent to the model using this structure:

```text
[JOB]
Title: ...
Company: ...
Location: ...
Description:
...

[CANDIDATE - ABOUT ME]
...

Only output the JSON as specified, nothing else.
```

The system prompt defines strict rules for:

- Work rights
- Citizenship and permanent residency requirements
- Years of experience
- Defence-related roles
- Technical skill matching
- Candidate background assumptions
- Output format

This is an example of structured prompt engineering for decision automation.

---

## Suitability Rules

The model evaluates job suitability based on several criteria.

### Technical relevance

The scripts prioritise roles related to:

- Python programming
- Software engineering
- Data analysis
- Data engineering
- Machine learning
- Deep learning
- Computer vision
- Automation
- Robotics
- Control systems
- Embedded systems
- Electrical or mechatronics engineering
- Interdisciplinary engineering technology roles

### Work-rights filtering

The Australia script allows roles where full Australian work rights are acceptable, but rejects citizen-only or PR-only roles.

The New Zealand script rejects roles requiring current New Zealand work rights or roles that state no sponsorship is available.

### Experience-level filtering

If a job explicitly requires several years of professional experience beyond the candidate's background, the script instructs the model to reject it.

This helps reduce applications to unrealistic senior roles.

### Defence filtering

The scripts reject defence, military, weapons, national-security, intelligence, or clearance-required roles.

This is especially useful because many technical roles in Australia and New Zealand may require citizenship or security clearance.

---

## SEEK Page Extraction Logic

SEEK job pages contain dynamic content, buttons, repeated navigation text, and safety notices.

The scripts use a combination of Selenium and BeautifulSoup:

- Selenium opens the page and scrolls it to trigger lazy loading.
- BeautifulSoup parses the final page source.
- CSS selectors extract job links, title, company, and location.
- A custom text-extraction function attempts to capture the main job description.
- Repeated "Save" sections and "Be careful" safety notices are removed.

The main extraction steps are:

```text
Find Apply / Quick Apply / Save area
        ↓
Collect visible text after that point
        ↓
Stop near the "Be careful" safety section
        ↓
Fallback to SEEK's jobAdDetails container if extraction is too short
```

This makes the scraper more robust against messy page layouts.

---

## Outputs

### Matched jobs CSV

The matched CSV contains jobs that the model marked as suitable.

Example files:

```text
seek_au_matches.csv
seek_nz_matches.csv
```

Typical fields include:

```text
url
title
company
location
reason
```

This file is useful for quick manual review and deciding which roles to apply for.

---

### Full results JSONL

The JSONL file stores every reviewed job, including unsuitable jobs.

Example files:

```text
seek_au_full_results.jsonl
seek_nz_full_results.jsonl
```

Each line is one JSON object.

This file is useful for:

- Debugging model decisions
- Reviewing rejected jobs
- Improving prompts
- Auditing the search process
- Checking whether the model is too strict or too loose

---

## Installation

Install Python dependencies:

```bash
pip install pandas requests beautifulsoup4 lxml selenium
```

Install and run Ollama:

```bash
ollama serve
```

Pull or prepare the local model you want to use:

```bash
ollama pull gpt-oss:20b
```

If using another model, update:

```python
MODEL = "your-model-name"
```

or pass it as a command-line argument.

---

## Safari WebDriver Requirement

The scripts use Safari WebDriver by default.

On macOS, enable Safari WebDriver with:

```bash
safaridriver --enable
```

You may also need to allow remote automation in Safari:

```text
Safari → Develop → Allow Remote Automation
```

If you want to use Chrome or Firefox instead, replace the `start_safari()` function with a ChromeDriver or GeckoDriver setup.

---

## Example Usage

### Run the Australia script

```bash
python scripts/seek_au_job_matcher.py
```

With custom options:

```bash
python scripts/seek_au_job_matcher.py   --location "Sydney NSW"   --pages 3   --per-page 10   --out-csv outputs/seek_au_matches.csv   --out-jsonl outputs/seek_au_full_results.jsonl
```

---

### Run the New Zealand script

```bash
python scripts/seek_nz_job_matcher.py
```

With custom options:

```bash
python scripts/seek_nz_job_matcher.py   --location "Auckland"   --pages 3   --per-page 10   --out-csv outputs/seek_nz_matches.csv   --out-jsonl outputs/seek_nz_full_results.jsonl
```

---

## Important Configuration Fields

### Search URL

```python
BASE_URL = "..."
```

Change this to target different job categories.

Examples:

```text
Python jobs
Machine learning jobs
Computer vision jobs
Automation jobs
Graduate software jobs
Robotics jobs
Data analyst jobs
```

### Ollama endpoint

```python
OLLAMA_URL = "http://localhost:11434/api/generate"
```

Use this if Ollama is running locally.

### Model name

```python
MODEL = "gpt-oss:20b"
```

Change this to the model available in your Ollama environment.

### Candidate profile

The `DEFAULT_ABOUT_ME` section contains the candidate's background.

This is one of the most important parts of the workflow because it gives the model the facts needed to evaluate suitability.

You can customise this section for different career targets, including:

- Software engineering
- Data analysis
- Machine learning
- Robotics
- Embedded systems
- Automation
- Computer vision
- Graduate roles
- Internship roles

---

## Human-in-the-Loop Design

The script does not send applications automatically.

It only filters job ads and produces review files.

A safe workflow is:

```text
Run script
    ↓
Open matched CSV
    ↓
Manually review each job
    ↓
Check work-rights and experience requirements again
    ↓
Customise CV and cover letter
    ↓
Apply manually
```

This helps avoid careless mass applications and keeps the final decision under human control.

---

## Limitations

This project has important limitations:

1. SEEK page structures may change.
2. Web scraping may fail if pages load differently.
3. The model may make mistakes.
4. The script does not verify facts outside the job ad.
5. Some job descriptions may omit work-rights requirements.
6. Local LLM output may occasionally be invalid JSON.
7. The suitability decision should always be reviewed manually.
8. The script does not submit applications.
9. Users should respect SEEK's terms of service and use conservative request rates.

---

## Ethical and Practical Notes

This project is intended for personal productivity and workflow automation.

Recommended use:

- Keep request rates low.
- Do not overload websites.
- Do not collect unnecessary personal data.
- Manually verify results before applying.
- Use the tool as decision support, not as an automatic application bot.

---

## Portfolio Value

This project demonstrates several practical engineering skills:

- Browser automation with Selenium
- HTML parsing with BeautifulSoup
- Dynamic web-page handling
- Local LLM integration with Ollama
- Prompt engineering
- Structured JSON output validation
- CSV and JSONL reporting
- Rule-based filtering logic
- Workflow automation
- Practical software design for a real personal productivity problem

It is a compact example of using AI agents and automation to reduce repetitive work while keeping human review in the loop.

---

## Disclaimer

This project is for educational, research, and personal productivity purposes only.

It is not affiliated with SEEK, Ollama, or any employer.

The user is responsible for complying with the terms of service of any website accessed by the script.
