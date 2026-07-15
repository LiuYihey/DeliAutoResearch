#!/usr/bin/env python3
"""Stage 2-4 pipeline: LQS scoring + citation_plan.jsonl + references.bib generation.

Reads literature_raw_*.json, enriches with venue_tier/institution_tier, computes LQS,
filters irrelevant candidates, auto-classifies A/B/C/D, assigns sections, and generates
bib entries from retrieval_log.jsonl anchors (never from LLM memory).

Usage:
    python tools/stage234_pipeline.py tasks/affective-eeg-bci-v2
"""
from __future__ import annotations
import json, re, sys, hashlib
from pathlib import Path
from datetime import datetime

# ---------- LQS scoring (mirrors lqs_score.py) ----------
def score_recency(year: int, month: int = 6) -> float:
    now = datetime.now()
    age = (now.year - year) * 12 + (now.month - month)
    if age <= 6: return 10.0
    if age <= 12: return 8.0
    if age <= 24: return 5.0
    if age <= 36: return 3.0
    return 1.0

def score_cites(cpm: float) -> float:
    if cpm >= 50: return 10.0
    if cpm >= 10: return 8.0
    if cpm >= 3: return 6.0
    if cpm >= 1: return 4.0
    return 2.0

def score_venue(vt: str) -> float:
    return {"top":10.0,"strong":7.0,"workshop":4.0,"arxiv":3.0,"unknown":2.0}.get(vt.lower(),2.0)

def compute_lqs(p: dict) -> float:
    r = score_recency(int(p.get("year",2020) or 2020), int(p.get("month",6) or 6))
    c = score_cites(float(p.get("cites_per_month",0) or 0))
    v = score_venue(p.get("venue_tier","unknown"))
    i = {"top_lab":10.0,"top_uni":9.0,"strong":7.0,"other":5.0}.get(p.get("institution_tier","other").lower(),5.0)
    a = {"accepted":10.0,"under_review":5.0,"none":3.0}.get(p.get("acceptance","none").lower(),3.0)
    return round(0.30*r + 0.25*c + 0.20*v + 0.10*i + 0.15*a, 2)

# ---------- Relevance filtering ----------
# Core brain-signal keywords (at least one required)
CORE_KW = [
    "eeg","electroencephal","bci","brain-computer","neurofeedback","erp","p300",
    "deap","seed","amigos","fnirs","fmri","brain signal","neural interface",
    "valence","arousal","frontal alpha","event-related potential","motor imagery",
]
# Affect/emotion keywords (at least one required for relevance)
AFFECT_KW = [
    "emotion","affective","valence","arousal","mood","stress","anxiety","depression",
    "neurofeedback","feeling","sentiment","affect recognition","emotion recognition",
    "emotion regulation","mental health","affective computing","emotional bci",
]

def is_relevant(p: dict) -> bool:
    text = (str(p.get("title","")) + " " + str(p.get("summary","")) + " " + str(p.get("venue",""))).lower()
    has_core = any(kw in text for kw in CORE_KW)
    has_affect = any(kw in text for kw in AFFECT_KW)
    return has_core and has_affect

# ---------- Venue tier ----------
TOP_VENUES = ["transactions on affective computing","ieee trans","tbme","tnsre","neuroimage",
    "nature","science","neurips","nips","icml","iclr","cvpr","nature machine","j. neural eng",
    "journal of neural engineering","neurobiology","ieee reviews"]
STRONG_VENUES = ["ieee","acm","elsevier","springer","embs","icassp","embc","ismir","ijcnn",
    "congress","conference","workshop on","proceedings","frontiers","plos"]

def classify_venue(venue: str, source: str) -> str:
    v = (venue or "").lower()
    if not v and source == "arxiv":
        return "arxiv"
    if any(t in v for t in TOP_VENUES):
        return "top"
    if any(s in v for s in STRONG_VENUES):
        return "strong"
    if "workshop" in v:
        return "workshop"
    return "unknown"

# ---------- Section assignment ----------
def assign_section(p: dict) -> str:
    t = (str(p.get("title","")) + " " + str(p.get("summary",""))).lower()
    if any(k in t for k in ["deap","seed","amigos","dataset","benchmark"]):
        return "03_benchmarks"
    if any(k in t for k in ["neurofeedback","closed-loop","closed loop","real-time","real time","feedback","adaptive","latency","regulation"]):
        return "06_closed_loop"
    if any(k in t for k in ["subject-independent","cross-subject","domain adaptation","generalization","transfer","online","offline","degradation","short window","causal"]):
        return "05_transition_gap"
    if any(k in t for k in ["clinical","translational","validation","readiness","deploy","field study"]):
        return "07_validation"
    if any(k in t for k in ["survey","review","affective computing","emotional bci","definition","landscape"]):
        return "02_foundations"
    if any(k in t for k in ["deep learning","cnn","rnn","transformer","gnn","attention","classification","decoding","recognition","lstm","gru","autoencoder","contrastive"]):
        return "04_algorithms"
    if any(k in t for k in ["stress","anxiety","depression","mental health","application"]):
        return "06_closed_loop"
    if any(k in t for k in ["challenge","future","outlook","open problem"]):
        return "08_challenges"
    return "04_algorithms"

# ---------- Year extraction ----------
def extract_year(p: dict) -> int:
    if p.get("year"):
        return int(p["year"])
    raw = p.get("raw", {})
    dp = raw.get("published", {}).get("date-parts", [[]])
    if dp and dp[0] and dp[0][0]:
        return int(dp[0][0])
    dp2 = raw.get("issued", {}).get("date-parts", [[]])
    if dp2 and dp2[0] and dp2[0][0]:
        return int(dp2[0][0])
    return 2020

# ---------- Bib key ----------
def make_key(authors, year, title):
    fam = ""
    if authors:
        a0 = authors[0]
        if "," in a0:
            fam = a0.split(",")[0].strip()
        else:
            parts = a0.split()
            fam = parts[-1] if parts else ""
    fam = re.sub(r"[^A-Za-z]", "", fam).lower()[:15] or "anon"
    words = re.findall(r"[A-Za-z]{3,}", title or "")
    tw = words[0].lower() if words else "untitled"
    return f"{fam}{year}{tw}"

# ---------- Main pipeline ----------
def main():
    task_dir = Path(sys.argv[1])
    paper = task_dir / "paper"

    # Load retrieval_log anchors — index by source_id AND by doi for flexible matching
    log_recs = {}
    doi_to_rec = {}
    for line in (paper / "retrieval_log.jsonl").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
            log_recs[r.get("source_id","")] = r
            rdoi = (r.get("doi","") or "").lower()
            if rdoi:
                doi_to_rec[rdoi] = r
        except json.JSONDecodeError:
            continue
    print(f"Loaded {len(log_recs)} retrieval_log anchors ({len(doi_to_rec)} with DOI)")

    def find_anchor(p):
        """Find retrieval_log anchor by source_id, then by doi fallback."""
        sid = p.get("source_id","")
        if sid and sid in log_recs:
            return sid
        # Fallback: match by DOI
        doi = (p.get("doi","") or "").lower()
        if doi and doi in doi_to_rec:
            rec = doi_to_rec[doi]
            return rec.get("source_id","")
        return ""

    # Stage 2: read + enrich + score
    all_papers = []
    for f in sorted(paper.glob("literature_raw_*.json")):
        try:
            arr = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for p in arr:
            p["year"] = extract_year(p)
            p["venue_tier"] = classify_venue(p.get("venue",""), p.get("source",""))
            p["institution_tier"] = "other"
            p["acceptance"] = "accepted" if p.get("venue") and p["venue_tier"] != "arxiv" else "none"
            p["cites_per_month"] = p.get("cites_per_month", 0)
            p["lqs"] = compute_lqs(p)
            p["lqs_class"] = "must_cite" if p["lqs"]>=7.0 else ("conditional" if p["lqs"]>=5.0 else "drop")
            p["relevant"] = is_relevant(p)
            p["section"] = assign_section(p)
            # source_id — try to find anchor via DOI fallback
            if p.get("doi"):
                p["source_id"] = f"doi:{p['doi']}"
            elif p.get("arxiv_id"):
                p["source_id"] = f"arxiv:{p['arxiv_id']}"
            else:
                p["source_id"] = ""
            # Resolve to actual retrieval_log anchor (may be dblp:... format)
            p["anchor_source_id"] = find_anchor(p)
            all_papers.append(p)

    # Dedup by anchor_source_id (prefer anchored records)
    seen = set()
    deduped = []
    for p in all_papers:
        sid = p.get("anchor_source_id","") or p.get("source_id","")
        if sid and sid in seen:
            continue
        seen.add(sid)
        deduped.append(p)
    all_papers = deduped

    # Sort: relevant first, then by LQS
    all_papers.sort(key=lambda x: (x.get("relevant",False), x["lqs"]), reverse=True)

    # Write literature_scored.json
    (paper / "literature_scored.json").write_text(
        json.dumps(all_papers, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    relevant = [p for p in all_papers if p.get("relevant") and p.get("anchor_source_id")]
    print(f"Total: {len(all_papers)}, Relevant+anchored: {len(relevant)}")

    # Build source_id -> enriched paper lookup (for year extraction)
    sid_to_paper = {}
    for p in all_papers:
        sid = p.get("anchor_source_id","") or p.get("source_id","")
        if sid:
            sid_to_paper[sid] = p

    # Build DOI -> authors fallback (CrossRef has authors when DBLP doesn't)
    doi_to_authors = {}
    for p in all_papers:
        doi = (p.get("doi","") or "").lower()
        auths = p.get("authors", [])
        if doi and auths:
            doi_to_authors[doi] = auths

    # Stage 3: build citation_plan.jsonl
    plan_entries = []
    used_keys = set()
    for p in relevant:
        sid = p["anchor_source_id"]
        # Use DOI-to-authors fallback for key generation when authors empty
        auths = p.get("authors", [])
        if not auths and p.get("doi"):
            auths = doi_to_authors.get(p["doi"].lower(), [])
        key = make_key(auths, p["year"], p.get("title",""))
        if key in used_keys:
            key = key + "x"
        used_keys.add(key)
        # Depth classification
        vt = p["venue_tier"]
        if p["lqs"] >= 7.0 and vt in ("top","strong"):
            depth = "A"
        elif p["lqs"] >= 5.0 or vt in ("top","strong"):
            depth = "B"
        elif p["lqs"] >= 3.0:
            depth = "C"
        else:
            depth = "D"
        if depth == "D":
            continue
        plan_entries.append({
            "key": key, "depth": depth, "section": p["section"],
            "source_id": sid,
            "rationale": f"LQS={p['lqs']}, venue={vt}, section={p['section']}"
        })

    with (paper / "citation_plan.jsonl").open("w", encoding="utf-8") as f:
        for e in plan_entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    # Stage 4: generate references.bib from retrieval_log anchors
    bib_parts = []
    for e in plan_entries:
        sid = e["source_id"]
        rec = log_recs.get(sid, {})
        enriched = sid_to_paper.get(sid, {})
        key = e["key"]
        authors = rec.get("authors", []) or enriched.get("authors", [])
        title = rec.get("title", "") or enriched.get("title", "")
        # Use enriched year (extracted from raw.published.date-parts) over retrieval_log year
        year = enriched.get("year") or rec.get("year") or ""
        venue = rec.get("venue", "") or enriched.get("venue", "")
        doi = rec.get("doi", "") or enriched.get("doi", "")
        url = rec.get("url", "")
        extra = rec.get("extra", {})

        # Fallback: if authors empty, try DOI cross-reference from CrossRef records
        if not authors and doi:
            authors = doi_to_authors.get(doi.lower(), [])

        # Format authors
        if authors:
            auth_str = " and ".join(authors)
        else:
            auth_str = "Unknown"

        # Determine entry type — check for journal keywords
        venue_lower = (venue or "").lower()
        is_arxiv = sid.startswith("arxiv:") or venue_lower in ("corr", "arxiv")
        has_venue = bool(venue and venue_lower not in ("", "corr", "arxiv"))
        is_journal = any(k in venue_lower for k in ["journal","transactions","trans.","ieee access","proceedings of the ieee"])

        if is_arxiv and not has_venue:
            # Extract arxiv_id from source_id or DOI or enriched data
            arxiv_id = ""
            if sid.startswith("arxiv:"):
                arxiv_id = sid.split(":",1)[1]
            elif doi and "arxiv" in doi.lower():
                # DOI format: 10.48550/arxiv.2510.22197
                m = re.search(r"arxiv\.(\d+\.\d+)", doi, re.IGNORECASE)
                if m:
                    arxiv_id = m.group(1)
            if not arxiv_id:
                arxiv_id = enriched.get("arxiv_id", "")
            arxiv_clean = re.sub(r"v\d+$","",arxiv_id)
            entry = f"@article{{{key},\n"
            entry += f"  author = {{{auth_str}}},\n"
            entry += f"  title = {{{{{title}}}}},\n"
            entry += f"  journal = {{arXiv preprint arXiv:{arxiv_clean}}},\n"
            entry += f"  year = {{{year}}},\n"
            entry += f"  eprint = {{{arxiv_clean}}},\n"
            if doi:
                entry += f"  doi = {{{doi}}},\n"
            entry += "\n}"
        elif is_journal:
            vol = enriched.get("volume","")
            iss = enriched.get("issue","")
            pg = enriched.get("page","")
            entry = f"@article{{{key},\n"
            entry += f"  author = {{{auth_str}}},\n"
            entry += f"  title = {{{{{title}}}}},\n"
            entry += f"  journal = {{{venue}}},\n"
            entry += f"  year = {{{year}}},\n"
            if vol: entry += f"  volume = {{{vol}}},\n"
            if iss: entry += f"  number = {{{iss}}},\n"
            if pg: entry += f"  pages = {{{pg}}},\n"
            if doi:
                entry += f"  doi = {{{doi}}},\n"
            entry += "\n}"
        else:
            pg = enriched.get("page","")
            entry = f"@inproceedings{{{key},\n"
            entry += f"  author = {{{auth_str}}},\n"
            entry += f"  title = {{{{{title}}}}},\n"
            entry += f"  booktitle = {{{venue or 'Unknown Conference'}}},\n"
            entry += f"  year = {{{year}}},\n"
            if pg: entry += f"  pages = {{{pg}}},\n"
            if doi:
                entry += f"  doi = {{{doi}}},\n"
            entry += "\n}"
        bib_parts.append(entry)

    (paper / "references.bib").write_text("\n\n".join(bib_parts) + "\n", encoding="utf-8")

    # Summary
    depths = {}
    for e in plan_entries:
        depths[e["depth"]] = depths.get(e["depth"],0) + 1
    print(f"citation_plan: {len(plan_entries)} entries, depths={depths}")
    print(f"references.bib: {len(bib_parts)} entries")
    print(f"literature_scored.json: {len(all_papers)} entries")

if __name__ == "__main__":
    main()
