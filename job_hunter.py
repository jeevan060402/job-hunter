#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  Job Hunter — Daily Automated Pipeline for Jeevan Kumar     ║
║  AI Engine : Google Gemini Flash (100% FREE)                ║
║  Schedule  : 9:30 AM IST via GitHub Actions cron            ║
║  Sources   : Remotive · RemoteOK · Arbeitnow · Naukri RSS   ║
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
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict
from pathlib import Path

import google.generativeai as genai

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
CONFIG = {
    # Free Gemini API key — get from https://aistudio.google.com (no card needed)
    "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),

    # Gmail settings — use an App Password, not your account password
    # Create one at: https://myaccount.google.com/apppasswords
    "email_sender":    os.getenv("EMAIL_SENDER",    "reddyjeevan936@gmail.com"),
    "email_password":  os.getenv("EMAIL_PASSWORD",  ""),
    "email_recipient": os.getenv("EMAIL_RECIPIENT", "reddyjeevan936@gmail.com"),
    "email_cc":        os.getenv("EMAIL_CC",        ""),

    # Local archive folder
    "output_dir": str(Path.home() / "job_reports"),

    # Max listings fetched per source before filtering
    "max_per_source": 15,

    # Keep jobs that contain at least one of these (case-insensitive)
    "filter_keywords": [
        "python", "django", "fastapi", "backend", "devops", "kubernetes",
        "k8s", "docker", "platform", "sre", "site reliability",
        "infrastructure", "cloud", "flask", "microservices",
    ],

    # Drop jobs whose title/description contains any of these
    "block_keywords": [
        "java only", ".net only", "ruby on rails", "php developer",
        "android developer", "ios developer", "react developer",
        "angular developer", "data scientist", "machine learning engineer",
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

Priority:
  HIGH   = score 7–10, strong stack match, apply same day
  MEDIUM = score 4–6, partial match, worth applying with tweaks
  SKIP   = score 1–3, mismatch or overleveled

=== OUTPUT FORMAT ===
Return ONLY a valid JSON object. No markdown, no code fences, no explanation outside the JSON.

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
      "resume_tweak": "One specific line to add or highlight in resume (HIGH only, else empty string)"
    }
  ],
  "top_picks": ["Company A – Role Title", "Company B – Role Title"],
  "action_items": [
    "Apply to [Company] today — strong K8s + FastAPI match",
    "For [Company], add Helm chart deployment to the K8s bullet",
    "Avoid [Company] — IT services, no product ownership context"
  ],
  "daily_summary": "2-3 sentence summary of today's batch quality and what to focus on."
}

Sort the jobs array by score descending."""


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
# JOB FETCHERS
# ─────────────────────────────────────────────

def fetch_remotive() -> List[Dict]:
    """Remotive.com — free API, best for remote startup + product company roles."""
    jobs = []
    categories = ["software-dev", "devops-sysadmin", "backend"]
    headers = {"User-Agent": "JobHunterBot/1.0 (personal; reddyjeevan936@gmail.com)"}
    for cat in categories:
        try:
            r = requests.get(
                f"https://remotive.com/api/remote-jobs?category={cat}&limit={CONFIG['max_per_source']}",
                headers=headers, timeout=15,
            )
            r.raise_for_status()
            for j in r.json().get("jobs", []):
                jobs.append({
                    "source":      "Remotive",
                    "title":       j.get("title", ""),
                    "company":     j.get("company_name", ""),
                    "location":    j.get("candidate_required_location", "Remote"),
                    "url":         j.get("url", ""),
                    "description": _clean(j.get("description", ""), 800),
                    "tags":        ", ".join(j.get("tags", [])),
                    "salary":      j.get("salary", ""),
                    "posted":      j.get("publication_date", ""),
                })
            log.info(f"Remotive [{cat}]: {len(jobs)} total so far")
            time.sleep(1)
        except Exception as e:
            log.warning(f"Remotive [{cat}]: {e}")
    return jobs


def fetch_remoteok() -> List[Dict]:
    """RemoteOK — free JSON feed, lots of US startup remote roles with salary."""
    jobs = []
    try:
        r = requests.get(
            "https://remoteok.com/api",
            headers={"User-Agent": "Mozilla/5.0 (compatible; JobHunterBot/1.0)"},
            timeout=20,
        )
        r.raise_for_status()
        listings = [j for j in r.json() if isinstance(j, dict) and j.get("position")]
        for j in listings[:CONFIG["max_per_source"]]:
            tags = j.get("tags", [])
            jobs.append({
                "source":      "RemoteOK",
                "title":       j.get("position", ""),
                "company":     j.get("company", ""),
                "location":    "Remote",
                "url":         j.get("url", ""),
                "description": _clean(j.get("description", ""), 800),
                "tags":        ", ".join(tags) if isinstance(tags, list) else "",
                "salary":      f"{j.get('salary_min','')}-{j.get('salary_max','')}".strip("-"),
                "posted":      j.get("date", ""),
            })
        log.info(f"RemoteOK: {len(jobs)} listings")
    except Exception as e:
        log.warning(f"RemoteOK: {e}")
    return jobs


def fetch_arbeitnow() -> List[Dict]:
    """Arbeitnow — free API, global remote jobs, many EU + US startups."""
    jobs = []
    try:
        r = requests.get(
            "https://www.arbeitnow.com/api/job-board-api",
            headers={"User-Agent": "JobHunterBot/1.0"},
            params={"tags": "python,devops,kubernetes,django,fastapi"},
            timeout=15,
        )
        r.raise_for_status()
        for j in r.json().get("data", [])[:CONFIG["max_per_source"]]:
            jobs.append({
                "source":      "Arbeitnow",
                "title":       j.get("title", ""),
                "company":     j.get("company_name", ""),
                "location":    j.get("location", "") + (" [Remote]" if j.get("remote") else ""),
                "url":         j.get("url", ""),
                "description": _clean(j.get("description", ""), 800),
                "tags":        ", ".join(j.get("tags", [])),
                "salary":      "",
                "posted":      j.get("created_at", ""),
            })
        log.info(f"Arbeitnow: {len(jobs)} listings")
    except Exception as e:
        log.warning(f"Arbeitnow: {e}")
    return jobs


def fetch_naukri_rss() -> List[Dict]:
    """Naukri RSS — India-focused Python + DevOps listings."""
    import xml.etree.ElementTree as ET
    jobs = []
    feeds = [
        "https://www.naukri.com/rss/jobs/python-developer-jobs-in-hyderabad.rss",
        "https://www.naukri.com/rss/jobs/devops-engineer-jobs-in-hyderabad.rss",
        "https://www.naukri.com/rss/jobs/python-developer-jobs-in-india.rss",
        "https://www.naukri.com/rss/jobs/kubernetes-engineer-jobs-in-india.rss",
    ]
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
    for url in feeds:
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.content)
            channel = root.find("channel")
            if channel is None:
                continue
            for item in channel.findall("item")[:8]:
                jobs.append({
                    "source":      "Naukri",
                    "title":       item.findtext("title", ""),
                    "company":     "",
                    "location":    "India",
                    "url":         item.findtext("link", ""),
                    "description": _clean(item.findtext("description", ""), 600),
                    "tags":        "",
                    "salary":      "",
                    "posted":      item.findtext("pubDate", ""),
                })
            time.sleep(1)
        except Exception as e:
            log.warning(f"Naukri RSS {url}: {e}")
    log.info(f"Naukri RSS: {len(jobs)} listings")
    return jobs


# ─────────────────────────────────────────────
# FILTERING
# ─────────────────────────────────────────────

def filter_jobs(jobs: List[Dict]) -> List[Dict]:
    filtered, seen = [], set()
    for j in jobs:
        url = j.get("url", "")
        if url in seen:
            continue
        seen.add(url)

        hay = (j.get("title", "") + " " + j.get("description", "") + " " + j.get("tags", "")).lower()

        if any(kw in hay for kw in CONFIG["block_keywords"]):
            continue
        if any(kw in hay for kw in CONFIG["filter_keywords"]):
            filtered.append(j)

    log.info(f"After filtering: {len(filtered)} / {len(jobs)} jobs kept")
    return filtered


# ─────────────────────────────────────────────
# GEMINI SCORING  (100% FREE)
# ─────────────────────────────────────────────

def score_jobs_with_gemini(jobs):
    from groq import Groq

    if not CONFIG["GROQ_API_KEY"]:
        raise ValueError("GROQ_API_KEY is not set.")

    client = Groq(api_key=CONFIG["GROQ_API_KEY"])  # reusing same config key

    today   = datetime.date.today().isoformat()
    payload = json.dumps(jobs, indent=2, ensure_ascii=False)
    prompt  = f"Today is {today}.\n\nHere are today's scraped job listings:\n\n{payload}"

    log.info(f"Sending {len(jobs)} jobs to Groq (Llama 3.3) for scoring…")

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
    raw = re.sub(r"\s*```$", "", raw)

    result = json.loads(raw)
    log.info(f"Groq returned: {result.get('total_evaluated','?')} evaluated, "
             f"{result.get('high_priority_count','?')} HIGH")
    return result

# ─────────────────────────────────────────────
# HTML EMAIL REPORT
# ─────────────────────────────────────────────

P_COLOR = {"HIGH": "#16a34a", "MEDIUM": "#d97706", "SKIP": "#9ca3af"}
P_BG    = {"HIGH": "#f0fdf4", "MEDIUM": "#fffbeb", "SKIP": "#f9fafb"}


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
    tweak_html = (
        f"<p style='margin:6px 0 0;font-size:12px;background:#eff6ff;"
        f"border-left:3px solid #3b82f6;padding:6px 10px;border-radius:4px'>"
        f"<b>📝 Resume tweak:</b> {tw}</p>"
    ) if tw and p == "HIGH" else ""

    return f"""
    <div style="border:1px solid #e5e7eb;border-radius:8px;margin:10px 0;padding:14px 16px;
                background:{P_BG.get(p,'#fff')};">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:6px;">
        <div>
          <span style="font-weight:700;font-size:15px;color:#111827">{j.get('rank','')}.&nbsp;{j.get('title','')}</span><br>
          <span style="color:#6b7280;font-size:13px">{j.get('company','Unknown')} · {j.get('location','')}</span>
        </div>
        <div style="display:flex;gap:8px;align-items:center;flex-shrink:0;">
          <span style="font-weight:700;font-size:17px;color:{_score_color(sc)}">{sc}/10</span>
          <span style="background:{P_COLOR.get(p,'#6b7280')};color:#fff;border-radius:4px;
                       padding:2px 10px;font-size:12px;font-weight:600">{p}</span>
        </div>
      </div>
      <p style="margin:8px 0 4px;color:#374151;font-size:13px;line-height:1.5">{j.get('fit_reason','')}</p>
      <p style="margin:4px 0;font-size:12px;color:#6b7280">
        <b>Exp required:</b> {j.get('experience_required','N/A')} &nbsp;|&nbsp;
        <b>Missing keywords:</b> {kw}
      </p>
      {tweak_html}
      <div style="margin-top:10px;display:flex;align-items:center;gap:12px;">
        <a href="{j.get('apply_url','#')}"
           style="background:#2563eb;color:#fff;padding:6px 16px;border-radius:4px;
                  text-decoration:none;font-size:13px;font-weight:600">Apply →</a>
        <span style="font-size:11px;color:#9ca3af">via {src}</span>
      </div>
    </div>"""


def build_html_email(result: Dict) -> str:
    today   = result.get("run_date", datetime.date.today().isoformat())
    high    = result.get("high_priority_count", 0)
    medium  = result.get("medium_priority_count", 0)
    summary = result.get("daily_summary", "")
    picks   = result.get("top_picks", [])
    actions = result.get("action_items", [])
    jobs    = result.get("jobs", [])

    apply_jobs = [j for j in jobs if j.get("apply_priority") != "SKIP"]
    skip_jobs  = [j for j in jobs if j.get("apply_priority") == "SKIP"]

    cards_html   = "".join(_job_card(j) for j in apply_jobs)
    picks_html   = "".join(f"<li>⭐ {p}</li>" for p in picks)
    actions_html = "".join(f"<li>→ {a}</li>" for a in actions)
    skip_html    = "".join(
        f"<li style='color:#9ca3af;font-size:12px'>"
        f"{j.get('rank','')}.&nbsp;{j.get('title','')} — {j.get('company','')} "
        f"(Score: {j.get('score',0)})</li>"
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

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#1e3a5f,#2563eb);padding:22px 26px;">
    <h1 style="margin:0;color:#fff;font-size:21px">🎯 Daily Job Report</h1>
    <p style="margin:4px 0 0;color:#bfdbfe;font-size:13px">
      {today} · Jeevan Kumar Reddy · Powered by Gemini Flash (free)
    </p>
  </div>

  <!-- Stats -->
  <div style="display:flex;border-bottom:1px solid #e5e7eb;">
    <div style="flex:1;text-align:center;padding:14px;border-right:1px solid #e5e7eb;">
      <div style="font-size:26px;font-weight:700;color:#111827">{result.get('total_evaluated',0)}</div>
      <div style="font-size:12px;color:#6b7280;margin-top:2px">Evaluated</div>
    </div>
    <div style="flex:1;text-align:center;padding:14px;border-right:1px solid #e5e7eb;">
      <div style="font-size:26px;font-weight:700;color:#16a34a">{high}</div>
      <div style="font-size:12px;color:#6b7280;margin-top:2px">HIGH Priority</div>
    </div>
    <div style="flex:1;text-align:center;padding:14px;">
      <div style="font-size:26px;font-weight:700;color:#d97706">{medium}</div>
      <div style="font-size:12px;color:#6b7280;margin-top:2px">MEDIUM Priority</div>
    </div>
  </div>

  <div style="padding:22px 26px;">

    <!-- Summary -->
    <div style="background:#f0f9ff;border-left:4px solid #0ea5e9;padding:12px 14px;
                border-radius:4px;margin-bottom:18px;">
      <b style="color:#0369a1;font-size:12px">📊 TODAY'S SUMMARY</b>
      <p style="margin:5px 0 0;color:#374151;font-size:13px;line-height:1.5">{summary}</p>
    </div>

    <!-- Top picks -->
    {"<div style='background:#f0fdf4;border-radius:8px;padding:12px 14px;margin-bottom:18px;'><b style='color:#16a34a;font-size:12px'>⭐ TOP PICKS TODAY</b><ul style='margin:6px 0 0;padding-left:16px;font-size:13px;color:#374151'>" + picks_html + "</ul></div>" if picks else ""}

    <!-- Action items -->
    {"<div style='background:#fefce8;border-radius:8px;padding:12px 14px;margin-bottom:18px;'><b style='color:#a16207;font-size:12px'>✅ ACTION ITEMS</b><ul style='margin:6px 0 0;padding-left:16px;font-size:13px;color:#374151'>" + actions_html + "</ul></div>" if actions else ""}

    <!-- Job cards -->
    <h2 style="font-size:15px;color:#111827;margin:0 0 4px">Apply Today & This Week</h2>
    <p style="font-size:12px;color:#6b7280;margin:0 0 14px">Sorted by fit score ↓</p>
    {cards_html or "<p style='color:#9ca3af;font-size:14px'>No strong matches today — check back tomorrow.</p>"}

    <!-- Skipped -->
    {"<details style='margin-top:18px'><summary style='cursor:pointer;color:#6b7280;font-size:13px'>Show " + str(len(skip_jobs)) + " skipped / mismatched roles</summary><ul style='margin:6px 0 0;padding-left:16px'>" + skip_html + "</ul></details>" if skip_jobs else ""}

  </div>

  <!-- Footer -->
  <div style="background:#f9fafb;padding:14px 26px;border-top:1px solid #e5e7eb;
              text-align:center;font-size:11px;color:#9ca3af;">
    Auto-generated · Python + Gemini Flash (free tier) · GitHub Actions
    <br>Sources: Remotive · RemoteOK · Arbeitnow · Naukri RSS
  </div>
</div>
</body>
</html>"""


# ─────────────────────────────────────────────
# EMAIL SENDER
# ─────────────────────────────────────────────

def send_email(html_body: str, result: Dict):
    if not CONFIG["email_password"]:
        log.warning("EMAIL_PASSWORD not set — skipping email, report saved to disk only.")
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
    log.info("🚀 Job Hunter started")
    log.info("═" * 55)

    # 1. Fetch from all sources
    raw: List[Dict] = []
    raw.extend(fetch_remotive())
    raw.extend(fetch_remoteok())
    raw.extend(fetch_arbeitnow())
    raw.extend(fetch_naukri_rss())
    log.info(f"Raw listings: {len(raw)}")

    if not raw:
        log.error("No jobs fetched — check network or API sources")
        sys.exit(1)

    # 2. Filter + deduplicate
    jobs = filter_jobs(raw)
    if not jobs:
        log.warning("Nothing passed keyword filter — using first 20 raw as fallback")
        jobs = raw[:20]

    jobs = jobs[:40]   # cap to keep Gemini prompt manageable

    # 3. Score with Gemini (free)
    result = score_jobs_with_gemini(jobs)

    # 4. Build HTML
    html = build_html_email(result)

    # 5. Save to disk
    html_path = save_report(result, html)

    # 6. Email
    try:
        send_email(html, result)
    except Exception as e:
        log.error(f"Email failed: {e}")

    # 7. Console summary
    print("\n" + "═" * 55)
    print(f"  DATE         : {result.get('run_date')}")
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