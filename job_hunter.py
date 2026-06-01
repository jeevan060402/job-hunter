#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  Job Hunter v4 — Daily Automated Pipeline for Jeevan Kumar  ║
║  AI Engine  : Groq (Llama 3.3-70b) — 100% FREE             ║
║  Schedule   : 9:30 AM IST via GitHub Actions cron           ║
║  Sources    : Remotive · RemoteOK · WeWorkRemotely          ║
║               Jobicy · Arbeitnow · TheMuse                  ║
║  New in v4  : seen-jobs dedup · retry logic · India source  ║
╚══════════════════════════════════════════════════════════════╝
"""

import json
import os
import smtplib
import datetime
import time
import requests
import logging
import sys
import re
import hashlib
import feedparser
from groq import Groq
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Set
from pathlib import Path


# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
CONFIG = {
    "groq_api_key":    os.getenv("GROQ_API_KEY",    ""),
    "email_sender":    os.getenv("EMAIL_SENDER",    "reddyjeevan936@gmail.com"),
    "email_password":  os.getenv("EMAIL_PASSWORD",  ""),
    "email_recipient": os.getenv("EMAIL_RECIPIENT", "reddyjeevan936@gmail.com"),
    "email_cc":        os.getenv("EMAIL_CC",        ""),
    "output_dir":      str(Path.home() / "job_reports"),

    # Path to the seen-jobs cache file (committed back to repo by GitHub Actions)
    "seen_jobs_path":  "seen_jobs.json",

    # How many days to remember a seen job before showing it again
    "seen_expiry_days": 14,

    "max_per_source": 25,

    "filter_keywords": [
        "python", "django", "fastapi", "flask", "backend",
        "devops", "kubernetes", "k8s", "docker", "platform engineer",
        "sre", "site reliability", "infrastructure", "cloud engineer",
        "microservices", "ci/cd", "devsecops",
    ],

    "block_keywords": [
        " ruby", "rails", " php", "laravel", "wordpress",
        "golang only", "java only", ".net only", "scala only",
        "business transformation", "revenue operations",
        "video editor", "cinemat", "motion graphic",
        "accountant", "buchhaltung", "comptable",
        "sales manager", "account executive", "copywriter",
        "android developer", "ios developer",
        "react developer", "angular developer", "vue developer",
        "data scientist", "ml engineer", "ai researcher",
        "embedded systems", "firmware",
    ],

    "tech_keywords": [
        "python", "devops", "kubernetes", "backend", "engineer",
        "developer", "infrastructure", "platform", "cloud", "sre",
        "docker", "microservice", "fastapi", "django",
    ],
}


# ─────────────────────────────────────────────
# CANDIDATE PROFILE + SCORING PROMPT
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """You are a senior technical recruiter assistant and job-fit analyst helping a backend + DevOps engineer find and prioritise the best job opportunities from a daily automated scrape.

=== CANDIDATE PROFILE ===
Name              : Maddur Jeevan Kumar Reddy
Current role      : SDE II — Backend & Cloud, FarmSetu Technologies
Total experience  : 3+ years
Location          : Hyderabad, India (open to remote or pan-India relocation)

Core backend stack : Python, Django, FastAPI, Flask, REST APIs, PostgreSQL, Redis, MySQL
DevOps / cloud     : Docker, Kubernetes (K8s), Jenkins, CI/CD, AWS, Azure, Shell scripting, Linux
Observability      : Prometheus, Grafana, logging, metrics monitoring
Notable work       : Built & published open-source package "setu-trafficmonitor" for real-time ingress/egress traffic monitoring — used in production microservices
Key achievements   : 25% PostgreSQL query optimisation via EXPLAIN ANALYZE; 40% system throughput improvement via ORM + Redis caching; AWS-to-Azure production migration with 100% data consistency
Education          : B.Tech ECE, KLEF (KL Hyderabad), CGPA 9.3/10

=== TARGET ROLES ===
ROLE A — Python Backend Engineer
  Experience bracket : 4+ years (candidate is strong 3+ with senior-level impact)
  Must-have          : Python, Django or FastAPI, REST APIs, PostgreSQL, AWS/Azure
  Good-to-have       : Microservices, Redis, Kubernetes, open-source contributions

ROLE B — DevOps / Platform / SRE / Infrastructure Engineer
  Experience bracket : 2+ years
  Must-have          : Docker, Kubernetes, CI/CD, Jenkins or GitHub Actions, Linux
  Good-to-have       : Prometheus/Grafana, AWS or Azure, Terraform, Helm

ROLE C — Remote US/Global (funded startups & product companies)
  Same stacks as A and B, but remote-friendly international roles
  Target             : Series A–C startups, YC-backed, well-funded product companies
  Must-have          : async-friendly, remote-first, Python/K8s/DevOps stack

=== SCORING RUBRIC ===
+3  Core stack match (Python/Django/FastAPI for backend; K8s/Docker/Jenkins for DevOps)
+2  Experience bracket fits (3–6 yr backend; 2–5 yr DevOps)
+1  Cloud platform match (AWS or Azure mentioned)
+1  Location fit (Remote / Hyderabad / pan-India / global-remote)
+1  Company quality (funded startup / MNC / YC-backed / strong brand)
+1  Compensation visible and in range (15–30 LPA or $60k–$150k USD)
-2  Hard mismatch (Java-only / .NET-only / no Python or DevOps context)
-1  Overleveled (requires 8+ years)
-1  Body-shopping / IT services with no product ownership

=== STRICT MISMATCH RULES ===
- Ruby / Rails / PHP / Laravel / WordPress → score MAX 3, SKIP always
- Non-engineering roles (business ops, sales, video, design) → score MAX 2, SKIP always
- Golang-only or Java-only with zero Python/K8s → score MAX 3, SKIP
- Roles requiring 8+ years → deduct -1 always

Priority:
  HIGH   = score 7–10  → apply same day
  MEDIUM = score 4–6   → apply with minor tweaks
  SKIP   = score 1–3   → do not apply

=== OUTPUT FORMAT ===
Return ONLY a valid JSON object — no markdown, no code fences.

{
  "run_date": "YYYY-MM-DD",
  "total_evaluated": <number>,
  "high_priority_count": <number>,
  "medium_priority_count": <number>,
  "jobs": [
    {
      "rank": 1,
      "title": "...",
      "company": "...",
      "location": "...",
      "experience_required": "...",
      "apply_url": "...",
      "source": "...",
      "score": <1-10>,
      "apply_priority": "HIGH | MEDIUM | SKIP",
      "fit_reason": "2-3 sentence plain-English explanation",
      "missing_keywords": ["keyword1", "keyword2"],
      "resume_tweak": "One specific line to add/highlight in resume (HIGH only, else empty string)"
    }
  ],
  "top_picks": ["Company A – Role Title", "Company B – Role Title"],
  "action_items": [
    "Apply to [Company] today — strong K8s + FastAPI match",
    "For [Company], add Helm chart deployment to the K8s bullet",
    "Avoid [Company] — IT services, no product context"
  ],
  "daily_summary": "2-3 sentence summary of today's batch and what to focus on."
}

Sort jobs array by score descending."""


# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(Path.home() / "job_hunter.log")),
    ],
)
log = logging.getLogger("job_hunter")


# ─────────────────────────────────────────────
# SEEN-JOBS CACHE  (prevents showing same jobs daily)
# ─────────────────────────────────────────────

def _job_hash(j: Dict) -> str:
    """Stable hash from URL, or company+title if URL is empty."""
    key = j.get("url") or f"{j.get('company','')}|{j.get('title','')}"
    return hashlib.md5(key.encode()).hexdigest()


def load_seen_jobs() -> Dict:
    """Load seen-jobs cache from disk. Returns {hash: date_str}."""
    path = Path(CONFIG["seen_jobs_path"])
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}
    return {}


def save_seen_jobs(seen: Dict):
    """Persist updated cache to disk."""
    Path(CONFIG["seen_jobs_path"]).write_text(
        json.dumps(seen, indent=2, ensure_ascii=False)
    )


def expire_seen_jobs(seen: Dict) -> Dict:
    """Remove entries older than seen_expiry_days."""
    cutoff = datetime.date.today() - datetime.timedelta(days=CONFIG["seen_expiry_days"])
    return {
        h: d for h, d in seen.items()
        if datetime.date.fromisoformat(d) >= cutoff
    }


def filter_seen(jobs: List[Dict], seen: Dict) -> List[Dict]:
    """Return only jobs NOT in the seen cache."""
    new_jobs = [j for j in jobs if _job_hash(j) not in seen]
    skipped  = len(jobs) - len(new_jobs)
    if skipped:
        log.info(f"Seen-jobs filter: removed {skipped} already-seen listings, {len(new_jobs)} new")
    return new_jobs


def mark_as_seen(jobs: List[Dict], seen: Dict) -> Dict:
    """Add today's jobs to the seen cache."""
    today = datetime.date.today().isoformat()
    for j in jobs:
        seen[_job_hash(j)] = today
    return seen


# ─────────────────────────────────────────────
# RETRY HELPER
# ─────────────────────────────────────────────

def _get(url: str, headers: Dict = None, params: Dict = None,
         timeout: int = 15, retries: int = 2) -> requests.Response:
    """requests.get with automatic retry on 429 / 5xx."""
    h = headers or {"User-Agent": "JobHunterBot/1.0"}
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=h, params=params, timeout=timeout)
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 10))
                log.warning(f"Rate limited by {url} — waiting {wait}s")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r
        except requests.exceptions.Timeout:
            log.warning(f"Timeout on {url} (attempt {attempt+1})")
            if attempt < retries:
                time.sleep(3)
        except requests.exceptions.RequestException as e:
            log.warning(f"Request error {url}: {e}")
            if attempt < retries:
                time.sleep(3)
    return None


# ─────────────────────────────────────────────
# JOB FETCHERS
# ─────────────────────────────────────────────

def fetch_remotive() -> List[Dict]:
    """Remotive — category search + keyword search for full coverage."""
    jobs, seen_urls = [], set()
    h = {"User-Agent": "JobHunterBot/1.0 (personal; reddyjeevan936@gmail.com)"}

    for cat in ["software-dev", "devops-sysadmin", "backend"]:
        r = _get(f"https://remotive.com/api/remote-jobs?category={cat}&limit={CONFIG['max_per_source']}", headers=h)
        if r:
            for j in r.json().get("jobs", []):
                if j.get("url") not in seen_urls:
                    seen_urls.add(j.get("url"))
                    jobs.append(_remotive_item(j))
        time.sleep(1)

    for kw in ["python", "devops", "kubernetes"]:
        r = _get(f"https://remotive.com/api/remote-jobs?search={kw}&limit=10", headers=h)
        if r:
            for j in r.json().get("jobs", []):
                if j.get("url") not in seen_urls:
                    seen_urls.add(j.get("url"))
                    jobs.append(_remotive_item(j))
        time.sleep(1)

    log.info(f"Remotive: {len(jobs)} listings")
    return jobs


def _remotive_item(j: Dict) -> Dict:
    return {
        "source":      "Remotive",
        "title":       j.get("title", ""),
        "company":     j.get("company_name", ""),
        "location":    j.get("candidate_required_location", "Remote"),
        "url":         j.get("url", ""),
        "description": _clean(j.get("description", ""), 800),
        "tags":        ", ".join(j.get("tags", [])),
        "salary":      j.get("salary", ""),
        "posted":      j.get("publication_date", ""),
    }


def fetch_remoteok() -> List[Dict]:
    """RemoteOK — tag-filtered for Python/DevOps/K8s roles."""
    jobs, seen_urls = [], set()
    for tag in ["python", "devops", "kubernetes", "backend"]:
        r = _get(
            f"https://remoteok.com/api?tags={tag}",
            headers={"User-Agent": "Mozilla/5.0 (compatible; JobHunterBot/1.0)"},
            timeout=20,
        )
        if r:
            listings = [j for j in r.json() if isinstance(j, dict) and j.get("position")]
            for j in listings[:12]:
                url = j.get("url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                tags   = j.get("tags", [])
                s_min  = j.get("salary_min", "")
                s_max  = j.get("salary_max", "")
                salary = f"${s_min}–${s_max}" if s_min and s_max else ""
                jobs.append({
                    "source":      "RemoteOK",
                    "title":       j.get("position", ""),
                    "company":     j.get("company", ""),
                    "location":    "Remote",
                    "url":         url,
                    "description": _clean(j.get("description", ""), 800),
                    "tags":        ", ".join(tags) if isinstance(tags, list) else "",
                    "salary":      salary,
                    "posted":      j.get("date", ""),
                })
        time.sleep(2)

    log.info(f"RemoteOK: {len(jobs)} listings")
    return jobs


def fetch_weworkremotely() -> List[Dict]:
    """We Work Remotely — highest quality remote US startup jobs via RSS."""
    jobs = []
    feeds = [
        ("https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss",  "Backend"),
        ("https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",       "DevOps"),
        ("https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss","Full-Stack"),
    ]
    for url, label in feeds:
        r = _get(url, timeout=10)
        if r:
            feed = feedparser.parse(r.content)
            for entry in feed.entries[:12]:
                title = entry.get("title", "")
                company, job_title = (title.split(": ", 1) if ": " in title else ("", title))
                jobs.append({
                    "source":      "WeWorkRemotely",
                    "title":       job_title.strip(),
                    "company":     company.strip(),
                    "location":    "Remote (Worldwide)",
                    "url":         entry.get("link", ""),
                    "description": _clean(entry.get("summary", ""), 800),
                    "tags":        label,
                    "salary":      "",
                    "posted":      entry.get("published", ""),
                })
            log.info(f"WeWorkRemotely [{label}]: {len(feed.entries)} entries")
        time.sleep(1)

    log.info(f"WeWorkRemotely total: {len(jobs)}")
    return jobs


def fetch_jobicy() -> List[Dict]:
    """Jobicy — free API, good salary data, Python/DevOps/Backend tags."""
    jobs, seen_urls = [], set()
    for tag, label in [("python-developer","Python"), ("devops-engineer","DevOps"),
                        ("backend-developer","Backend")]:
        r = _get(
            "https://jobicy.com/api/v2/remote-jobs",
            params={"count": 15, "tag": tag},
        )
        if r:
            for j in r.json().get("jobs", []):
                url = j.get("url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                s_min  = j.get("annualSalaryMin", "")
                s_max  = j.get("annualSalaryMax", "")
                cur    = j.get("salaryCurrency", "USD")
                salary = f"{cur} {s_min}–{s_max}" if s_min and s_max else ""
                jobs.append({
                    "source":      "Jobicy",
                    "title":       j.get("jobTitle", ""),
                    "company":     j.get("companyName", ""),
                    "location":    j.get("jobGeo", "Remote"),
                    "url":         url,
                    "description": _clean(j.get("jobDescription", ""), 800),
                    "tags":        label,
                    "salary":      salary,
                    "posted":      j.get("pubDate", ""),
                })
        time.sleep(1)

    log.info(f"Jobicy: {len(jobs)} listings")
    return jobs


def fetch_arbeitnow() -> List[Dict]:
    """Arbeitnow — remote filter + non-English skip."""
    jobs = []
    non_en = ["gmbh","co. kg","s.r.o","s.a.","b.v.","s.p.a",
              "kaufmännisch","mitarbeiter","buchhaltung",
              "développeur","comptable","ingénieur","développement"]
    r = _get(
        "https://www.arbeitnow.com/api/job-board-api",
        params={"tags": "python,devops,kubernetes,django,fastapi", "remote": "true"},
    )
    if r:
        for j in r.json().get("data", [])[:CONFIG["max_per_source"]]:
            hay = (j.get("title","") + " " + j.get("company_name","") + " " +
                   j.get("description","")).lower()
            if any(w in hay for w in non_en):
                continue
            jobs.append({
                "source":      "Arbeitnow",
                "title":       j.get("title", ""),
                "company":     j.get("company_name", ""),
                "location":    j.get("location","") + (" [Remote]" if j.get("remote") else ""),
                "url":         j.get("url", ""),
                "description": _clean(j.get("description", ""), 800),
                "tags":        ", ".join(j.get("tags", [])),
                "salary":      "",
                "posted":      j.get("created_at", ""),
            })

    log.info(f"Arbeitnow: {len(jobs)} listings")
    return jobs


def fetch_themuse() -> List[Dict]:
    """The Muse — free API, no auth, engineering-only post-filter."""
    jobs = []
    searches = [
        ("Software Engineer",  "Mid Level"),
        ("Software Engineer",  "Senior Level"),
        ("DevOps & SysAdmin",  "Mid Level"),
        ("DevOps & SysAdmin",  "Senior Level"),
    ]
    for cat, level in searches:
        r = _get(
            "https://www.themuse.com/api/public/jobs",
            params={"category": cat, "level": level, "page": 1, "descending": "true"},
        )
        if r:
            for j in r.json().get("results", [])[:8]:
                check = (j.get("name","") + " " + j.get("contents","")).lower()
                if not any(k in check for k in CONFIG["tech_keywords"]):
                    continue
                locs = j.get("locations", [])
                loc  = ", ".join(l.get("name","") for l in locs) or "Remote"
                jobs.append({
                    "source":      "TheMuse",
                    "title":       j.get("name", ""),
                    "company":     j.get("company", {}).get("name", ""),
                    "location":    loc,
                    "url":         j.get("refs", {}).get("landing_page", ""),
                    "description": _clean(j.get("contents", ""), 800),
                    "tags":        cat,
                    "salary":      "",
                    "posted":      j.get("publication_date", ""),
                })
        time.sleep(1)

    log.info(f"TheMuse: {len(jobs)} listings")
    return jobs


def fetch_hn_jobs() -> List[Dict]:
    """
    HackerNews 'Who is Hiring' monthly thread — best source for
    YC-backed & funded startup jobs. Parsed via Algolia + HN Firebase API.
    Only runs if today is in the first 7 days of the month (when the thread is fresh).
    """
    jobs = []
    today = datetime.date.today()
    if today.day > 7:
        log.info("HackerNews Who's Hiring: skipping (only runs on days 1–7 of month)")
        return jobs

    try:
        # Find the latest "Ask HN: Who is hiring?" post
        r = _get(
            "https://hn.algolia.com/api/v1/search_by_date",
            params={"query": "Ask HN: Who is hiring?", "tags": "ask_hn", "hitsPerPage": 1},
        )
        if not r:
            return jobs

        hits = r.json().get("hits", [])
        if not hits:
            return jobs

        post_id = hits[0].get("objectID")
        month   = hits[0].get("title", "")
        log.info(f"HackerNews: parsing '{month}' (id={post_id})")

        # Fetch top-level comment IDs
        r2 = _get(f"https://hacker-news.firebaseio.com/v0/item/{post_id}.json")
        if not r2:
            return jobs

        kids = r2.json().get("kids", [])[:150]   # top 150 comments

        # Fetch each comment and filter for Python/DevOps mentions
        kw = ["python", "django", "fastapi", "devops", "kubernetes",
              "k8s", "backend", "remote", "docker", "flask"]
        count = 0
        for kid_id in kids:
            if count >= 20:    # cap at 20 HN items
                break
            r3 = _get(f"https://hacker-news.firebaseio.com/v0/item/{kid_id}.json", timeout=8)
            if not r3:
                continue
            item = r3.json()
            if item.get("dead") or item.get("deleted"):
                continue

            text = _clean(item.get("text", ""), 1000)
            if not any(k in text.lower() for k in kw):
                continue

            # Extract company name from first line (most HN posts start with "Company | Role | ...")
            first_line = text.split("\n")[0][:120] if text else ""
            jobs.append({
                "source":      "HackerNews",
                "title":       first_line or "Software Engineer (HN Hiring)",
                "company":     first_line.split("|")[0].strip() if "|" in first_line else "Unknown",
                "location":    "Remote" if "remote" in text.lower() else "See listing",
                "url":         f"https://news.ycombinator.com/item?id={kid_id}",
                "description": text,
                "tags":        "HN Who is Hiring",
                "salary":      "",
                "posted":      today.isoformat(),
            })
            count += 1
            time.sleep(0.2)

        log.info(f"HackerNews: {len(jobs)} relevant listings")

    except Exception as e:
        log.warning(f"HackerNews fetch error: {e}")

    return jobs


# ─────────────────────────────────────────────
# FILTERING & DEDUPLICATION
# ─────────────────────────────────────────────

def filter_jobs(jobs: List[Dict]) -> List[Dict]:
    filtered    = []
    seen_urls   = set()
    seen_titles = set()

    for j in jobs:
        url = j.get("url", "")

        if url in seen_urls:
            continue
        seen_urls.add(url)

        title_key = f"{j.get('company','').lower().strip()}|{j.get('title','').lower().strip()[:60]}"
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)

        hay = (j.get("title","") + " " + j.get("description","") + " " + j.get("tags","")).lower()

        if any(kw in hay for kw in CONFIG["block_keywords"]):
            continue
        if not any(kw in hay for kw in CONFIG["filter_keywords"]):
            continue

        filtered.append(j)

    log.info(f"After keyword filter: {len(filtered)} / {len(jobs)} kept")
    return filtered


# ─────────────────────────────────────────────
# GROQ SCORING
# ─────────────────────────────────────────────

def score_jobs_with_groq(jobs: List[Dict]) -> Dict:
    if not CONFIG["groq_api_key"]:
        raise ValueError(
            "GROQ_API_KEY not set. Get a free key at https://console.groq.com"
        )

    client  = Groq(api_key=CONFIG["groq_api_key"])
    today   = datetime.date.today().isoformat()
    payload = json.dumps(jobs, indent=2, ensure_ascii=False)
    prompt  = f"Today is {today}.\n\nHere are today's NEW job listings:\n\n{payload}"

    log.info(f"Sending {len(jobs)} jobs to Groq (Llama 3.3-70b)…")

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        temperature=0.2,
        max_tokens=4096,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$",          "", raw)

    result = json.loads(raw)
    log.info(
        f"Groq done: {result.get('total_evaluated','?')} evaluated | "
        f"{result.get('high_priority_count','?')} HIGH | "
        f"{result.get('medium_priority_count','?')} MEDIUM"
    )
    return result


# ─────────────────────────────────────────────
# HTML EMAIL REPORT
# ─────────────────────────────────────────────

P_COLOR = {"HIGH": "#16a34a", "MEDIUM": "#d97706", "SKIP": "#9ca3af"}
P_BG    = {"HIGH": "#f0fdf4", "MEDIUM": "#fffbeb", "SKIP": "#f9fafb"}
SRC_BADGE = {
    "Remotive":       "#dbeafe",
    "RemoteOK":       "#fce7f3",
    "WeWorkRemotely": "#d1fae5",
    "Jobicy":         "#fef3c7",
    "Arbeitnow":      "#e0e7ff",
    "TheMuse":        "#ffe4e6",
    "HackerNews":     "#fff3cd",
}


def _score_color(s: int) -> str:
    if s >= 8: return "#16a34a"
    if s >= 5: return "#d97706"
    return "#dc2626"


def _job_card(j: Dict) -> str:
    p   = j.get("apply_priority", "SKIP")
    sc  = j.get("score", 0)
    kw  = ", ".join(j.get("missing_keywords", [])) or "None"
    tw  = j.get("resume_tweak", "")
    src = j.get("source", "")
    sal = j.get("salary", "")
    src_color = SRC_BADGE.get(src, "#f3f4f6")

    tweak_html = (
        f"<p style='margin:6px 0 0;font-size:12px;background:#eff6ff;"
        f"border-left:3px solid #3b82f6;padding:6px 10px;border-radius:0 4px 4px 0'>"
        f"<b>📝 Resume tweak:</b> {tw}</p>"
    ) if tw and p == "HIGH" else ""

    salary_html = (
        f"<span style='font-size:11px;background:#f0fdf4;color:#166534;"
        f"padding:1px 7px;border-radius:4px;margin-left:6px'>{sal}</span>"
    ) if sal else ""

    return f"""
    <div style="border:1px solid #e5e7eb;border-radius:8px;margin:10px 0;padding:14px 16px;
                background:{P_BG.get(p,'#fff')};">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;
                  flex-wrap:wrap;gap:6px;">
        <div>
          <span style="font-weight:700;font-size:15px;color:#111827">
            {j.get('rank','')}.&nbsp;{j.get('title','')}
          </span>{salary_html}<br>
          <span style="color:#6b7280;font-size:13px">
            {j.get('company','Unknown')} · {j.get('location','')}
          </span>
        </div>
        <div style="display:flex;gap:8px;align-items:center;flex-shrink:0;">
          <span style="font-weight:700;font-size:17px;color:{_score_color(sc)}">{sc}/10</span>
          <span style="background:{P_COLOR.get(p,'#6b7280')};color:#fff;border-radius:4px;
                       padding:2px 10px;font-size:12px;font-weight:600">{p}</span>
        </div>
      </div>
      <p style="margin:8px 0 4px;color:#374151;font-size:13px;line-height:1.5">
        {j.get('fit_reason','')}
      </p>
      <p style="margin:4px 0;font-size:12px;color:#6b7280">
        <b>Exp:</b> {j.get('experience_required','N/A')} &nbsp;|&nbsp;
        <b>Missing:</b> {kw}
      </p>
      {tweak_html}
      <div style="margin-top:10px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
        <a href="{j.get('apply_url','#')}"
           style="background:#2563eb;color:#fff;padding:6px 16px;border-radius:4px;
                  text-decoration:none;font-size:13px;font-weight:600">Apply →</a>
        <span style="font-size:11px;background:{src_color};color:#374151;
                     padding:2px 8px;border-radius:4px">via {src}</span>
      </div>
    </div>"""


def build_html_email(result: Dict, new_count: int, total_raw: int) -> str:
    today   = result.get("run_date", datetime.date.today().isoformat())
    high    = result.get("high_priority_count", 0)
    medium  = result.get("medium_priority_count", 0)
    summary = result.get("daily_summary", "")
    picks   = result.get("top_picks", [])
    actions = result.get("action_items", [])
    jobs    = result.get("jobs", [])

    apply_jobs   = [j for j in jobs if j.get("apply_priority") != "SKIP"]
    skip_jobs    = [j for j in jobs if j.get("apply_priority") == "SKIP"]
    cards_html   = "".join(_job_card(j) for j in apply_jobs)
    picks_html   = "".join(f"<li>⭐ {p}</li>" for p in picks)
    actions_html = "".join(f"<li>→ {a}</li>" for a in actions)
    skip_html    = "".join(
        f"<li style='color:#9ca3af;font-size:12px'>"
        f"{j.get('rank','')}.&nbsp;{j.get('title','')} — "
        f"{j.get('company','')} (Score: {j.get('score',0)})</li>"
        for j in skip_jobs
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>Daily Job Report — {today}</title>
</head>
<body style="margin:0;padding:0;background:#f3f4f6;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<div style="max-width:680px;margin:24px auto;background:#fff;border-radius:12px;
            box-shadow:0 1px 4px rgba(0,0,0,.1);overflow:hidden;">

  <div style="background:linear-gradient(135deg,#1e3a5f,#2563eb);padding:22px 26px;">
    <h1 style="margin:0;color:#fff;font-size:21px">🎯 Daily Job Report</h1>
    <p style="margin:4px 0 0;color:#bfdbfe;font-size:13px">
      {today} · Jeevan Kumar Reddy · Groq + Llama 3.3 (free) · v4
    </p>
  </div>

  <div style="display:flex;border-bottom:1px solid #e5e7eb;">
    <div style="flex:1;text-align:center;padding:12px 8px;border-right:1px solid #e5e7eb;">
      <div style="font-size:22px;font-weight:700;color:#111827">{total_raw}</div>
      <div style="font-size:11px;color:#6b7280;margin-top:2px">Scraped</div>
    </div>
    <div style="flex:1;text-align:center;padding:12px 8px;border-right:1px solid #e5e7eb;">
      <div style="font-size:22px;font-weight:700;color:#2563eb">{new_count}</div>
      <div style="font-size:11px;color:#6b7280;margin-top:2px">New today</div>
    </div>
    <div style="flex:1;text-align:center;padding:12px 8px;border-right:1px solid #e5e7eb;">
      <div style="font-size:22px;font-weight:700;color:#16a34a">{high}</div>
      <div style="font-size:11px;color:#6b7280;margin-top:2px">HIGH</div>
    </div>
    <div style="flex:1;text-align:center;padding:12px 8px;">
      <div style="font-size:22px;font-weight:700;color:#d97706">{medium}</div>
      <div style="font-size:11px;color:#6b7280;margin-top:2px">MEDIUM</div>
    </div>
  </div>

  <div style="padding:22px 26px;">
    <div style="background:#f0f9ff;border-left:4px solid #0ea5e9;padding:12px 14px;
                border-radius:0 4px 4px 0;margin-bottom:18px;">
      <b style="color:#0369a1;font-size:12px">📊 TODAY'S SUMMARY</b>
      <p style="margin:5px 0 0;color:#374151;font-size:13px;line-height:1.5">{summary}</p>
    </div>

    {"<div style='background:#f0fdf4;border-radius:8px;padding:12px 14px;margin-bottom:18px;'><b style='color:#16a34a;font-size:12px'>⭐ TOP PICKS TODAY</b><ul style='margin:6px 0 0;padding-left:16px;font-size:13px;color:#374151'>" + picks_html + "</ul></div>" if picks else ""}
    {"<div style='background:#fefce8;border-radius:8px;padding:12px 14px;margin-bottom:18px;'><b style='color:#a16207;font-size:12px'>✅ ACTION ITEMS</b><ul style='margin:6px 0 0;padding-left:16px;font-size:13px;color:#374151'>" + actions_html + "</ul></div>" if actions else ""}

    <h2 style="font-size:15px;color:#111827;margin:0 0 4px">Apply Today & This Week</h2>
    <p style="font-size:12px;color:#6b7280;margin:0 0 14px">Sorted by fit score — new listings only</p>
    {cards_html or "<p style='color:#9ca3af;font-size:14px'>No new matches today — all recent listings already seen. Check back tomorrow.</p>"}

    {"<details style='margin-top:18px'><summary style='cursor:pointer;color:#6b7280;font-size:13px'>Show " + str(len(skip_jobs)) + " skipped / mismatched roles</summary><ul style='margin:6px 0 0;padding-left:16px'>" + skip_html + "</ul></details>" if skip_jobs else ""}
  </div>

  <div style="background:#f9fafb;padding:14px 26px;border-top:1px solid #e5e7eb;
              text-align:center;font-size:11px;color:#9ca3af;">
    Auto-generated · Groq Llama 3.3-70b (free) · GitHub Actions · v4
    <br>Sources: Remotive · RemoteOK · WeWorkRemotely · Jobicy · Arbeitnow · TheMuse · HackerNews
  </div>
</div>
</body>
</html>"""


# ─────────────────────────────────────────────
# EMAIL SENDER
# ─────────────────────────────────────────────

def send_email(html_body: str, result: Dict):
    if not CONFIG["email_password"]:
        log.warning("EMAIL_PASSWORD not set — skipping email.")
        return

    today   = result.get("run_date", datetime.date.today().isoformat())
    high    = result.get("high_priority_count", 0)
    emoji   = "🔥" if high >= 3 else ("⭐" if high >= 1 else "📋")
    subject = f"{emoji} Job Report {today} — {high} HIGH priority role(s)"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = CONFIG["email_sender"]
    msg["To"]      = CONFIG["email_recipient"]
    if CONFIG["email_cc"]:
        msg["Cc"] = CONFIG["email_cc"]
    msg.attach(MIMEText(html_body, "html"))

    recipients = [CONFIG["email_recipient"]]
    if CONFIG["email_cc"]:
        recipients.append(CONFIG["email_cc"])

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
        server.login(CONFIG["email_sender"], CONFIG["email_password"])
        server.sendmail(CONFIG["email_sender"], recipients, msg.as_string())

    log.info(f"✅ Email sent → {CONFIG['email_recipient']}")


# ─────────────────────────────────────────────
# DISK ARCHIVE
# ─────────────────────────────────────────────

def save_report(result: Dict, html: str) -> Path:
    out_dir = Path(CONFIG["output_dir"]) / result.get("run_date", "unknown")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    html_path = out_dir / "report.html"
    html_path.write_text(html, encoding="utf-8")
    log.info(f"📁 Saved → {out_dir}")
    return html_path


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _clean(text: str, limit: int) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] + ("…" if len(text) > limit else "")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def run():
    log.info("═" * 55)
    log.info("🚀 Job Hunter v4 started")
    log.info("═" * 55)

    # 1. Load seen-jobs cache
    seen = load_seen_jobs()
    seen = expire_seen_jobs(seen)
    log.info(f"Seen-jobs cache: {len(seen)} entries (last {CONFIG['seen_expiry_days']} days)")

    # 2. Fetch from all 7 sources
    raw: List[Dict] = []
    raw.extend(fetch_remotive())
    raw.extend(fetch_remoteok())
    raw.extend(fetch_weworkremotely())
    raw.extend(fetch_jobicy())
    raw.extend(fetch_arbeitnow())
    raw.extend(fetch_themuse())
    raw.extend(fetch_hn_jobs())
    total_raw = len(raw)
    log.info(f"Total raw listings: {total_raw}")

    if not raw:
        log.error("No jobs fetched — check network or API sources")
        sys.exit(1)

    # 3. Keyword filter + company-title dedup
    jobs = filter_jobs(raw)

    # 4. Remove already-seen jobs — only score NEW ones
    jobs = filter_seen(jobs, seen)
    new_count = len(jobs)

    if not jobs:
        log.info("No new jobs today — all listings already seen. Sending 'no new jobs' email.")
        result = {
            "run_date": datetime.date.today().isoformat(),
            "total_evaluated": 0, "high_priority_count": 0, "medium_priority_count": 0,
            "jobs": [], "top_picks": [], "action_items": [],
            "daily_summary": "No new job listings today — all sources returned listings already seen in the past 14 days. Try again tomorrow.",
        }
        html = build_html_email(result, 0, total_raw)
        save_report(result, html)
        try:
            send_email(html, result)
        except Exception as e:
            log.error(f"Email failed: {e}")
        return

    # Cap at 40 for Groq
    jobs = jobs[:40]
    log.info(f"Sending {len(jobs)} new jobs to Groq")

    # 5. Score with Groq
    result = score_jobs_with_groq(jobs)

    # 6. Mark ALL fetched jobs as seen (not just the ones sent to Groq)
    all_filtered = filter_jobs(raw)
    seen = mark_as_seen(all_filtered, seen)
    save_seen_jobs(seen)
    log.info(f"Seen-jobs cache updated: {len(seen)} total entries")

    # 7. Build + save report
    html      = build_html_email(result, new_count, total_raw)
    html_path = save_report(result, html)

    # 8. Email
    try:
        send_email(html, result)
    except Exception as e:
        log.error(f"Email failed: {e}")

    # 9. Console summary
    print("\n" + "═" * 55)
    print(f"  DATE         : {result.get('run_date')}")
    print(f"  RAW SCRAPED  : {total_raw}")
    print(f"  NEW TODAY    : {new_count}")
    print(f"  EVALUATED    : {result.get('total_evaluated', 0)}")
    print(f"  HIGH         : {result.get('high_priority_count', 0)}")
    print(f"  MEDIUM       : {result.get('medium_priority_count', 0)}")
    print(f"  REPORT       : {html_path}")
    print("═" * 55)
    for p in result.get("top_picks", []):
        print(f"  ⭐ {p}")
    for a in result.get("action_items", []):
        print(f"  • {a}")
    print()
    log.info("✅ Done")


if __name__ == "__main__":
    run()