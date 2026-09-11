#!/usr/bin/env python3
"""Download every source the plan relies on and extract text LOCALLY.

Same rule as ~/teardowns/fetch.py: a fetch summary is never evidence. We keep the
bytes, extract text here, and search that text with verify.py.
"""
import html, io, os, re, sys, time, urllib.request

UA = "Vedant Tigade research your-email@example.com"
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "sources")

# key -> (url, tier). tier: primary = the company/regulator/court itself.
SOURCES = {
    "wf-10q-2026q2": ("https://www.sec.gov/Archives/edgar/data/72971/000007297126000302/wfc-20260630.htm", "primary"),
    "wf-10q-2026q1": ("https://www.sec.gov/Archives/edgar/data/72971/000007297126000217/wfc-20260331.htm", "primary"),
    "wf-10k-2025":   ("https://www.sec.gov/Archives/edgar/data/72971/000007297126000133/wfc-20251231_d2.htm", "primary"),
    "wf-8k-2026q2-release": ("https://www.sec.gov/Archives/edgar/data/72971/000007297126000288/wfc2qer07-14x26ex991xrelea.htm", "primary"),
    "wf-8k-2026q1-release": ("https://www.sec.gov/Archives/edgar/data/72971/000007297126000213/wfc1qer04-14x26ex991xrelea.htm", "primary"),
    "wf-newsroom-fed-order-terminated": ("https://newsroom.wf.com/news-releases/news-details/2026/Wells-Fargo-2018-Federal-Reserve-Consent-Order-Terminated/default.aspx", "primary"),
    "wf-job-tech-intern-2027": ("https://www.wellsfargojobs.com/en/jobs/r-557386/2027-technology-program-intern/", "primary"),
    "sec-tricolor-2026-77": ("https://www.sec.gov/newsroom/press-releases/2026-77-sec-charges-former-executives-fraud-connection-19-billion-collapse-subprime-auto-lender-tricolor", "primary"),
    "doj-tricolor": ("https://www.justice.gov/usao-sdny/pr/ceo-cfo-coo-charged-connection-billion-dollar-collapse-tricolor-auto", "primary"),
    "doj-first-brands": ("https://www.justice.gov/usao-sdny/pr/first-brands-executives-charged-multibillion-dollar-fraud", "primary"),
    "setpoint-pledgecheck": ("https://www.setpoint.io/setpoint-launches-industry-standard-to-stop-double-pledging-after-tricolor-and-first-brands-collapse/", "primary"),
    "fool-wf-2026q1-call": ("https://www.fool.com/earnings/call-transcripts/2026/04/14/wells-fargo-wfc-q1-2026-earnings-call-transcript/", "secondary"),
    "cnbc-mfs": ("https://www.cnbc.com/2026/05/18/mfs-private-credit-insolvency-banks-failure-collapse-barclays-mortgage.html", "secondary"),
    "seekingalpha-mfs": ("https://seekingalpha.com/news/4558063-barclays-santander-wells-fargo-in-street-lenders-exposed-to-failed-uk-based-mfs---report", "secondary"),
    "yahoo-collateral-checkers": ("https://finance.yahoo.com/small-business/articles/tricolor-fallout-fuels-boom-business-090000623.html", "secondary"),
    "gtr-first-brands": ("https://www.gtreview.com/news/americas/first-brands-faces-investigation-into-double-financing-of-receivables-inventory/", "secondary"),
    "tps-first-brands": ("https://www.truckpartsandservice.com/business/finance/article/15820570/prosecutors-reveal-details-of-multibillion-dollar-fraud-at-first-brands", "secondary"),
    "gleif-level2": ("https://www.gleif.org/en/lei-data/access-and-use-lei-data/level-2-data-who-owns-whom", "primary"),
    "courtlistener-api": ("https://www.courtlistener.com/help/api/rest/", "primary"),
    "sec-absee-interps": ("https://www.sec.gov/divisions/corpfin/guidance/form-abs-ee-interps.htm", "primary"),
    # --- added after Vedant's review: stack, model approach, training resources ---
    "wf-job-backend-kafka-ai": ("https://www.wellsfargojobs.com/en/jobs/r-552636/software-engineer-backend-java-spring-boot-microservices-kafka-ai-ml-gen-ai/", "primary"),
    "wf-job-data-engineer-ai": ("https://www.wellsfargojobs.com/en/jobs/r-570930/data-engineer-ai/", "primary"),
    "wf-job-lead-data-engineer": ("https://www.wellsfargojobs.com/en/jobs/r-451826/lead-data-engineer/", "primary"),
    "venturebeat-fargo": ("https://venturebeat.com/ai/wells-fargos-ai-assistant-just-crossed-245-million-interactions-with-zero-humans-in-the-loop-and-zero-pii-to-the-llm", "secondary"),
    "ciodive-wf-agentspace": ("https://www.ciodive.com/news/wells-fargo-google-cloud-agentic-AI/756872/", "secondary"),
    "hf-zerogpu-docs": ("https://huggingface.co/docs/hub/spaces-zerogpu", "primary"),
    "kaggle-gpu-docs": ("https://www.kaggle.com/docs/efficient-gpu-usage", "primary"),
    "hf-cord-v2": ("https://huggingface.co/datasets/naver-clova-ix/cord-v2", "primary"),
    "funsd": ("https://guillaumejaume.github.io/FUNSD/", "primary"),
}


def fetch(url):
    ua = UA if "sec.gov" in url else BROWSER_UA
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "text/html,application/pdf,*/*"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def to_text(raw):
    if raw[:4] == b"%PDF":
        from pypdf import PdfReader
        return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(raw)).pages)
    s = raw.decode("utf-8", errors="replace")
    s = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def main(force=False):
    os.makedirs(SRC, exist_ok=True)
    for key, (url, tier) in SOURCES.items():
        raw_path = os.path.join(SRC, key + ".raw")
        txt_path = os.path.join(SRC, key + ".txt")
        if os.path.exists(txt_path) and not force:
            print(f"cached  {key}")
            continue
        try:
            raw = fetch(url)
            open(raw_path, "wb").write(raw)
            t = to_text(raw)
            open(txt_path, "w").write(f"SOURCE: {url}\nTIER: {tier}\nFETCHED: {time.strftime('%Y-%m-%d')}\n\n{t}")
            print(f"ok      {key:34} {len(t):>8} chars")
        except Exception as e:
            print(f"FAILED  {key:34} {type(e).__name__}: {e}")
        time.sleep(0.4)
    # local PDF already on disk (downloaded earlier this session from occ.gov)
    pdf = os.path.join(SRC, "occ-formal-agreement-2024-72.pdf")
    if os.path.exists(pdf):
        t = to_text(open(pdf, "rb").read())
        open(os.path.join(SRC, "occ-formal-agreement-2024-72.txt"), "w").write(
            "SOURCE: https://www.occ.gov/static/enforcement-actions/eaAA-ENF-2024-72.pdf\nTIER: primary\n\n" + t)
        print(f"ok      occ-formal-agreement-2024-72       {len(t):>8} chars")


if __name__ == "__main__":
    main(force="--force" in sys.argv)
