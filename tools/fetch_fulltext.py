#!/usr/bin/env python3
"""Download and parse paper full text (anti-hallucination v3 — solid evidence).

Why this tool is needed:
- The old check_numerical_claims.py only anchored numerical values in the summary/abstract of retrieval_log
- But abstracts do not contain specific numbers, experimental details, or conclusions — the real numerical claims are in the full text
- When the LLM writes sections it makes up values like "58.6%", "N=24, RCT" from memory; these must be anchored in the full text
- No full text = no basis = any claim is a potential hallucination

Workflow:
1. Given a cite_key + arxiv_id/doi/pdf_url, download the PDF
2. Parse to plain text using pdfminer.six (preferred) or PyPDF2
3. Save to paper/fulltext/<cite_key>.txt
4. Return the path for use by check_numerical_claims/check_factual_claims/verify_conclusions

Dependencies:
- pip install pdfminer.six  # Pure Python, no system dependencies, recommended
- or PyPDF2 (fallback)
- Network access to arxiv.org / publisher DOI URL

No-dependency fallback:
- If PDF parsing fails, mark fulltext_status=failed, forcing Gate 1.6 to fail
- We do not allow "cannot parse PDF, just let it pass" — that is a breeding ground for hallucinations
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from retrieval_log import read_log, find_by_doi, find_by_source_id  # noqa: E402

FULLTEXT_DIRNAME = "fulltext"


def _fulltext_path(task_dir: Path, cite_key: str) -> Path:
    d = task_dir / "paper" / FULLTEXT_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{cite_key}.txt"


def _fulltext_meta_path(task_dir: Path, cite_key: str) -> Path:
    d = task_dir / "paper" / FULLTEXT_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{cite_key}.meta.json"


def _extract_pdf_url(rec: dict) -> str | None:
    """Extract the PDF URL from a retrieval_log record.

    Priority: extra.pdf_url > url (if it ends with .pdf)
    Note: record.url may be an abs URL, not a PDF; check extra.pdf_url first.
    """
    pdf = rec.get("extra", {}).get("pdf_url", "")
    if pdf:
        return pdf
    url = rec.get("url", "")
    # Only return url when it is a pdf URL
    if url and (url.endswith(".pdf") or "/pdf/" in url):
        return url
    return None


def _find_pdf_url(cite_key: str, task_dir: Path) -> str | None:
    """Reverse-lookup pdf_url from retrieval_log (used when there is no cite_key association)."""
    for rec in read_log(task_dir):
        url = _extract_pdf_url(rec)
        if url:
            return url
    return None


def _find_pdf_url_for_cite_key(cite_key: str, task_dir: Path, citation_plan: Path) -> str | None:
    """Find source_id in citation_plan.jsonl, then reverse-lookup retrieval_log for pdf_url."""
    if citation_plan.exists():
        for line in citation_plan.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                plan = json.loads(line)
            except json.JSONDecodeError:
                continue
            if plan.get("key") != cite_key:
                continue
            sid = plan.get("source_id", "")
            if not sid:
                continue
            # Reverse-lookup retrieval_log via source_id
            rec = find_by_source_id(task_dir, sid)
            if rec:
                url = _extract_pdf_url(rec)
                if url:
                    return url
            # Fallback: source_id of the form "doi:xxx" → look up via doi
            if sid.startswith("doi:"):
                doi = sid[4:]
                rec = find_by_doi(task_dir, doi)
                if rec:
                    url = _extract_pdf_url(rec)
                    if url:
                        return url
            # arxiv source_id → construct PDF URL directly
            if sid.startswith("arxiv:"):
                aid = sid.split(":", 1)[1]
                # Strip version suffix
                aid_clean = re.sub(r"v\d+$", "", aid)
                return f"http://arxiv.org/pdf/{aid_clean}"
    return None


def download_pdf(url: str, dest_pdf: Path, timeout: int = 60) -> bool:
    """Download PDF to dest_pdf."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AutoResearch/2.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        if len(data) < 1000:
            return False
        dest_pdf.write_bytes(data)
        return True
    except Exception:
        return False


def parse_pdf_pdfminer(pdf_path: Path) -> str | None:
    """Parse PDF to plain text using pdfminer.six."""
    try:
        from pdfminer.high_level import extract_text
        text = extract_text(str(pdf_path))
        if text and len(text) > 100:
            return text
    except ImportError:
        pass
    except Exception:
        pass
    return None


def parse_pdf_pypdf2(pdf_path: Path) -> str | None:
    """Parse PDF using PyPDF2 (fallback)."""
    try:
        import PyPDF2  # type: ignore
        reader = PyPDF2.PdfReader(str(pdf_path))
        text = ""
        for page in reader.pages:
            try:
                text += page.extract_text() or ""
            except Exception:
                continue
        if text and len(text) > 100:
            return text
    except ImportError:
        pass
    except Exception:
        pass
    return None


def fetch_fulltext_for_cite_key(
    cite_key: str,
    task_dir: Path,
    *,
    pdf_url: str = None,
    citation_plan: Path = None,
    cache_only: bool = False,
) -> dict:
    """Fetch and parse full text for a cite_key.

    Returns:
        {
            "cite_key": str,
            "status": "ok" | "cached" | "no_pdf_url" | "download_failed" | "parse_failed",
            "fulltext_path": str | None,
            "char_count": int,
            "source_url": str,
        }
    """
    out_path = _fulltext_path(task_dir, cite_key)
    meta_path = _fulltext_meta_path(task_dir, cite_key)
    # Cache hit
    if out_path.exists() and out_path.stat().st_size > 100:
        text = out_path.read_text(encoding="utf-8", errors="ignore")
        return {
            "cite_key": cite_key, "status": "cached",
            "fulltext_path": str(out_path), "char_count": len(text),
            "source_url": "",
        }
    if cache_only:
        return {"cite_key": cite_key, "status": "not_cached",
                "fulltext_path": None, "char_count": 0, "source_url": ""}

    # Find PDF URL
    url = pdf_url
    if not url:
        plan_path = citation_plan or (task_dir / "paper" / "citation_plan.jsonl")
        url = _find_pdf_url_for_cite_key(cite_key, task_dir, plan_path)
    if not url:
        # Fallback: walk the entire retrieval_log for the first record with pdf_url
        url = _find_pdf_url(cite_key, task_dir)
    if not url:
        return {"cite_key": cite_key, "status": "no_pdf_url",
                "fulltext_path": None, "char_count": 0, "source_url": ""}

    # Download
    tmp_pdf = out_path.with_suffix(".pdf")
    if not download_pdf(url, tmp_pdf):
        return {"cite_key": cite_key, "status": "download_failed",
                "fulltext_path": None, "char_count": 0, "source_url": url}

    # Parse
    text = parse_pdf_pdfminer(tmp_pdf) or parse_pdf_pypdf2(tmp_pdf)
    if not text:
        # Clean up PDF even if parsing fails
        tmp_pdf.unlink(missing_ok=True)
        return {"cite_key": cite_key, "status": "parse_failed",
                "fulltext_path": None, "char_count":  0, "source_url": url}

    out_path.write_text(text, encoding="utf-8")
    tmp_pdf.unlink(missing_ok=True)  # Delete PDF, keep only the txt
    meta = {
        "cite_key": cite_key,
        "source_url": url,
        "char_count": len(text),
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"cite_key": cite_key, "status": "ok",
            "fulltext_path": str(out_path), "char_count": len(text),
            "source_url": url}


def fetch_all_in_plan(task_dir: Path, *, max_papers: int = 200) -> dict:
    """Batch-fetch full text for A/B-grade citations from citation_plan.jsonl (C/D-grade not needed)."""
    plan_path = task_dir / "paper" / "citation_plan.jsonl"
    if not plan_path.exists():
        return {"fetched": 0, "ok": 0, "failed": [], "plan_path": str(plan_path)}
    keys = []
    for line in plan_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            plan = json.loads(line)
        except json.JSONDecodeError:
            continue
        if plan.get("depth") in ("A", "B"):  # C/D-grade fulltext not needed
            keys.append(plan.get("key", ""))
    results = []
    failed = []
    ok = 0
    for k in keys[:max_papers]:
        if not k:
            continue
        r = fetch_fulltext_for_cite_key(k, task_dir, citation_plan=plan_path)
        results.append(r)
        if r["status"] in ("ok", "cached"):
            ok += 1
        else:
            failed.append({"cite_key": k, "status": r["status"]})
        time.sleep(1.0)  # Be friendly to arxiv rate limits
    return {"fetched": len(results), "ok": ok, "failed": failed, "plan_path": str(plan_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and parse paper full text (anti-hallucination v3)")
    parser.add_argument("task_dir", type=Path)
    parser.add_argument("--key", default=None, help="Only fetch the specified cite_key")
    parser.add_argument("--all", action="store_true", help="Batch-fetch A/B-grade from citation_plan.jsonl")
    parser.add_argument("--url", default=None, help="Provide PDF URL directly (used with --key)")
    parser.add_argument("-o", "--output", type=Path, default=None)
    args = parser.parse_args()
    if args.all:
        result = fetch_all_in_plan(args.task_dir)
    elif args.key:
        result = fetch_fulltext_for_cite_key(args.key, args.task_dir, pdf_url=args.url)
    else:
        parser.error("Need --key or --all")
    out = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
