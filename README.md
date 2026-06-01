# 🎯 Job Hunter — Daily Automated Pipeline

Fetches Python/DevOps/Remote jobs from 4 sources, scores them via Claude API,
and emails you a colour-coded HTML report every morning at **9:30 AM IST**.

---

## Quick Start

```bash
# 1. Clone / copy this folder to your machine
cd job_hunter

# 2. Run setup (creates venv, installs deps, schedules cron)
bash setup.sh

# 3. Fill in your secrets
nano .env          # Add ANTHROPIC_API_KEY + Gmail App Password

# 4. Test it immediately
bash run_daily.sh
```

---

## What You Get Every Morning

An HTML email with:

| Section | Details |
|---|---|
| **Stats bar** | Total evaluated · HIGH count · MEDIUM count |
| **Daily summary** | 2-3 sentences from Claude on today's batch |
| **Top picks** | Best 2–3 roles to apply to first |
| **Action items** | Specific apply/tweak/avoid instructions |
| **Job cards** | Score /10 · priority badge · fit reason · missing keywords · resume tweak |
| **Skipped roles** | Collapsed list of mismatches (Java-only, overleveled etc.) |

---

## Job Sources

| Source | Type | Best for |
|---|---|---|
| **Remotive** | Free API | Remote startup & product company roles globally |
| **RemoteOK** | Free API | Remote US startup roles, often salary-visible |
| **Arbeitnow** | Free API | European + global remote, Python/K8s tags |
| **Naukri RSS** | Public RSS | India-specific Python + DevOps, Hyderabad |

---

## Scoring Rubric (Claude applies this)

| Signal | Points |
|---|---|
| Core stack match (Python/Django/FastAPI or K8s/Docker) | +3 |
| Experience bracket fits (3–6 yr backend; 2–5 yr DevOps) | +2 |
| Cloud platform match (AWS or Azure) | +1 |
| Location fit (Remote / Hyderabad / pan-India / global-remote) | +1 |
| Company quality (funded startup / MNC / YC-backed) | +1 |
| Compensation visible and in range | +1 |
| Hard mismatch (Java-only / .NET-only) | -2 |
| Overleveled (8+ years required) | -1 |
| Body-shopping / IT services | -1 |

**HIGH = 7–10** · **MEDIUM = 4–6** · **SKIP = 1–3**

---

## Environment Variables

```bash
export ANTHROPIC_API_KEY="sk-ant-..."         # console.anthropic.com
export EMAIL_SENDER="you@gmail.com"
export EMAIL_PASSWORD="xxxx xxxx xxxx xxxx"   # Gmail App Password (not account pw)
export EMAIL_RECIPIENT="you@gmail.com"
export EMAIL_CC=""                             # optional
```

### Gmail App Password setup
1. Go to https://myaccount.google.com/security
2. Enable 2-Step Verification
3. Search "App passwords" → create one for "Mail"
4. Paste the 16-char password into EMAIL_PASSWORD

---

## Cron Schedule

```
0 4 * * *   →   04:00 UTC   =   09:30 AM IST
```

View/edit: `crontab -e`
Remove: `crontab -l | grep -v job_hunter | crontab -`

---

## Logs & Archives

```
~/job_hunter.log              ← daily run log
~/job_reports/
  └── 2025-06-01/
        ├── report.json       ← raw Claude output
        └── report.html       ← email-style HTML report
```

Open any `report.html` in browser to re-read old reports.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ANTHROPIC_API_KEY not set` | Run `source .env` or check cron wrapper |
| Email not arriving | Check spam; verify Gmail App Password; check `~/job_hunter.log` |
| 0 jobs fetched | Check network; one of the APIs may be down; run manually to see error |
| Claude JSON parse error | Rare; re-run manually; usually a transient API issue |
| Cron not firing | `grep CRON /var/log/syslog` or `journalctl -u cron` |

---

## Customisation

Open `job_hunter.py` and edit the `CONFIG` dict at the top:

```python
"filter_keywords": [...]    # add more tech keywords
"block_keywords":  [...]    # add more job titles to skip
"max_per_source":  15       # increase to fetch more per source
```

To add a new job source, add a `fetch_xxx()` function and call it in `run()`.

---

## Cost Estimate

~30–40 job listings/day × ~1500 tokens each = ~50k tokens/run
Claude Sonnet 4 input: ~$0.003/run · output: ~$0.012/run
**Total: ≈ $0.45/month** for daily runs
