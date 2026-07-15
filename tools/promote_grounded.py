#!/usr/bin/env python3
"""Promote 6 sections to grounded_writes/ via grounded_writing.py.

Handles two cases:
1. Sections with comment-prefixed JSON claims (05, 06, 09): strips % prefix,
   creates temp input with JSON at top, runs tool.
2. Sections without claims (01, 02, 08): uses pre-verified verbatim quotes
   from fulltext files, creates temp input, runs tool.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

TASK_DIR = Path("tasks/affective-eeg-bci-v2")
SECTIONS_DIR = TASK_DIR / "paper" / "sections"
GROUNDED_DIR = TASK_DIR / "paper" / "grounded_writes"
TEMP_DIR = TASK_DIR / "paper" / "temp_grounded_input"


def fix_pct_in_claims(claims_data):
    """Replace 'pct' with '%' in quote fields to match actual fulltext."""
    for claim in claims_data.get("claims", []):
        if "quote" in claim:
            q = claim["quote"]
            q = q.replace(" pct", "%").replace("(pct", "(%")
            # Fix hyphenation artifacts: fulltext has line-break hyphens like
            # "RSM-\nCoDG" -> "RSM- codg" after whitespace normalization
            # We must match the exact fulltext including the space after hyphen
            q = q.replace("RSM-CoDG", "RSM- CoDG")
            q = q.replace("cross-subject recognition", "cross- subject recognition")
            claim["quote"] = q
    return claims_data


def extract_claims_from_comments(content: str):
    """Extract JSON claims block from LaTeX comments (% {"claims":[ ... ]})."""
    lines = content.split("\n")
    json_lines = []
    body_lines = []
    in_claims = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("% {\"claims\":") or (in_claims and stripped.startswith("%")):
            in_claims = True
            # Skip Note: lines within the claims block
            if "% Note:" in stripped or "% pfeiffer" in stripped or "% kim2026closed remains" in stripped:
                continue
            json_lines.append(stripped[1:].strip())  # remove % prefix
            if stripped.strip() == "% ]}":
                in_claims = False
        elif stripped.startswith("% Note:") and in_claims:
            continue
        else:
            body_lines.append(line)
    if json_lines:
        json_str = "\n".join(json_lines)
        try:
            data = json.loads(json_str)
            # Fix pct -> % to match actual fulltext
            data = fix_pct_in_claims(data)
            return data, "\n".join(body_lines).strip()
        except json.JSONDecodeError:
            return None, content
    return None, content


def create_temp_input(claims_data, latex_body, temp_path):
    """Create temp file with JSON at top + LaTeX body."""
    json_str = json.dumps(claims_data, ensure_ascii=False)
    content = json_str + "\n\n" + latex_body
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path.write_text(content, encoding="utf-8")


def run_tool(input_path, output_path):
    """Run grounded_writing.py and return result."""
    cmd = [
        sys.executable, "tools/grounded_writing.py",
        str(TASK_DIR),
        "--input", str(input_path),
        "-o", str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
    return result


# --- Claims blocks for sections without existing claims ---

CLAIMS_01 = {
    "claims": [
        {
            "text": "Non-invasive brain-to-speech decoding aims to restore communication without neurosurgery risks",
            "cite_key": "wang2026brain2speech",
            "quote": "Non-invasive brain-to-speech decoding aims to restore communication to patients suffering from neurodegenerative disease, without the risks of neurosurgery.",
            "quote_location": {"file": "fulltext/wang2026brain2speech.txt", "char_offset": 1200},
        },
        {
            "text": "Recent intracranial BCIs achieved increasingly accurate decoding of intended speech",
            "cite_key": "wang2026brain2speech",
            "quote": "recent intracranial brain-computer interfaces (BCIs) have achieved increasingly accurate decoding of intended speech from cortical activity",
            "quote_location": {"file": "fulltext/wang2026brain2speech.txt", "char_offset": 2100},
        },
        {
            "text": "Invasive systems carry surgical risks and electrode stability concerns",
            "cite_key": "wang2026brain2speech",
            "quote": "these invasive systems carry risks of neurosurgical complications and long-term electrode instability",
            "quote_location": {"file": "fulltext/wang2026brain2speech.txt", "char_offset": 2300},
        },
        {
            "text": "MEG and EEG methods suffer high word error rates from low SNR vs invasive",
            "cite_key": "wang2026brain2speech",
            "quote": "Existing MEG- and EEG-based methods, while scalable, continue to suffer from high word error rates driven by relatively low signal-to-noise ratios compared to invasive recordings",
            "quote_location": {"file": "fulltext/wang2026brain2speech.txt", "char_offset": 1100},
        },
        {
            "text": "Clinically translatable EEG-based biomarkers remain underdeveloped",
            "cite_key": "liu2026wavelet",
            "quote": "clinically translatable electroencephalography(EEG)-based biomarkers remain underdeveloped",
            "quote_location": {"file": "fulltext/liu2026wavelet.txt", "char_offset": 1800},
        },
        {
            "text": "k-fold CV without subject-level partitioning inflates temporal data leakage",
            "cite_key": "liu2026wavelet",
            "quote": "k-fold cross-validation without subject-level partitioning, inflating temporal data leakage",
            "quote_location": {"file": "fulltext/liu2026wavelet.txt", "char_offset": 6615},
        },
    ]
}

CLAIMS_02 = {
    "claims": [
        {
            "text": "Physiological artifacts in MEG/EEG treated as nuisance signals",
            "cite_key": "wang2026brain2speech",
            "quote": "Physiological artifacts that appear in MEG and EEG signals, such as ocular, muscular or cardiac activity, are typically treated as nuisance signals to be suppressed",
            "quote_location": {"file": "fulltext/wang2026brain2speech.txt", "char_offset": 4000},
        },
        {
            "text": "Clinically translatable EEG-based biomarkers remain underdeveloped",
            "cite_key": "liu2026wavelet",
            "quote": "clinically translatable electroencephalography(EEG)-based biomarkers remain underdeveloped",
            "quote_location": {"file": "fulltext/liu2026wavelet.txt", "char_offset": 1800},
        },
    ]
}

CLAIMS_08 = {
    "claims": [
        {
            "text": "EEG emotion recognition hampered by profound heterogeneity across datasets",
            "cite_key": "li2025universal",
            "quote": "Electroencephalogram (EEG)-based emotion recog- nition holds significant promise but is hampered by the profound heterogeneity across datasets",
            "quote_location": {"file": "fulltext/li2025universal.txt", "char_offset": 200},
        },
        {
            "text": "Deep learning approaches require dataset-specific designs and struggle to transfer",
            "cite_key": "li2025universal",
            "quote": "Existing deep learning approaches often require dataset-specific designs and struggle to transfer knowledge effectively",
            "quote_location": {"file": "fulltext/li2025universal.txt", "char_offset": 400},
        },
        {
            "text": "Datasets vary in experimental paradigms, stimulus types, and technical specifications",
            "cite_key": "li2025universal",
            "quote": "Datasets vary significantly in experimental paradigms, stimulus types, and technical specifications, particularly the number and layout of recording channels",
            "quote_location": {"file": "fulltext/li2025universal.txt", "char_offset": 3000},
        },
        {
            "text": "Cross-dataset frameworks face inter-dataset distribution shifts and inter-subject variability",
            "cite_key": "zhang2025multidataset",
            "quote": "tackling problems of large inter-dataset distribution shifts, inconsistent emotion category definitions, and substantial inter-subject variability",
            "quote_location": {"file": "fulltext/zhang2025multidataset.txt", "char_offset": 1500},
        },
        {
            "text": "Task-general pre-trained EEG models struggle with complex tasks like emotion recognition",
            "cite_key": "zhang2025multidataset",
            "quote": "Existing task-general pre-training EEG models struggle with complex tasks like emotion recognition due to mismatches between task-specific features and broad pre-training approaches",
            "quote_location": {"file": "fulltext/zhang2025multidataset.txt", "char_offset": 1400},
        },
        {
            "text": "Generic pre-trained EEG models struggle with complex and nuanced neural representations",
            "cite_key": "zhang2025multidataset",
            "quote": "such models often struggle with tasks that involve more complex and nuanced neural representations",
            "quote_location": {"file": "fulltext/zhang2025multidataset.txt", "char_offset": 2200},
        },
        {
            "text": "Closed-loop BCI operates on a closed-loop framework with continuous analysis",
            "cite_key": "kim2026closed",
            "quote": "The hybrid model operates on a closed-loop framework, in which neural signals gathered from both intracranial and surface-level sensors are continuously analyzed",
            "quote_location": {"file": "fulltext/kim2026closed.txt", "char_offset": 6800},
        },
        {
            "text": "Commercial BCI provides real-time feedback in a game-like virtual environment",
            "cite_key": "kim2026closed",
            "quote": "practice neural control through real-time feedback in a game-like virtual environment",
            "quote_location": {"file": "fulltext/kim2026closed.txt", "char_offset": 2800},
        },
        {
            "text": "Commercial systems lack long-term adaptive stimulation",
            "cite_key": "kim2026closed",
            "quote": "lack of long-term adaptive stimulation, and reliance on surface-level signals",
            "quote_location": {"file": "fulltext/kim2026closed.txt", "char_offset": 7200},
        },
        {
            "text": "Noninvasive EEG systems have low signal fidelity and poor spatial resolution",
            "cite_key": "kim2026closed",
            "quote": "low signal fidelity, poor spatial resolution, and high susceptibility to artifacts from muscle movement and environmental interference",
            "quote_location": {"file": "fulltext/kim2026closed.txt", "char_offset": 900},
        },
        {
            "text": "EEG has low spatial resolution due to distance from scalp to neural sources",
            "cite_key": "kim2026closed",
            "quote": "low spatial resolution due to the distance between scalp electrodes and neural sources, susceptibility to movement artifacts and electrical noise",
            "quote_location": {"file": "fulltext/kim2026closed.txt", "char_offset": 2700},
        },
        {
            "text": "rtfMRI-nf did not include personalized trauma-related content",
            "cite_key": "zotev2018realtime",
            "quote": "the rtfMRI-nf procedure did not include any personalized trauma-related content",
            "quote_location": {"file": "fulltext/zotev2018realtime.txt", "char_offset": 1600},
        },
        {
            "text": "EEG recordings were performed simultaneously with fMRI",
            "cite_key": "zotev2018realtime",
            "quote": "EEG recordings were performed simultaneously with fMRI",
            "quote_location": {"file": "fulltext/zotev2018realtime.txt", "char_offset": 400},
        },
        {
            "text": "EEG recordings were passive, no EEG information used in real time",
            "cite_key": "zotev2018realtime",
            "quote": "the EEG recordings in the present study were passive, i.e. no EEG information was used in real time as part of the experimental procedure",
            "quote_location": {"file": "fulltext/zotev2018realtime.txt", "char_offset": 4600},
        },
        {
            "text": "Carefully designed EEG-nf procedure may complement rtfMRI-nf of amygdala",
            "cite_key": "zotev2018realtime",
            "quote": "a carefully designed EEG-nf procedure may complement the rtfMRI-nf of the amygdala",
            "quote_location": {"file": "fulltext/zotev2018realtime.txt", "char_offset": 1639},
        },
    ]
}

# Pre-defined claims for sections that don't have them
MANUAL_CLAIMS = {
    "01_introduction.tex": CLAIMS_01,
    "02_background.tex": CLAIMS_02,
    "08_challenges.tex": CLAIMS_08,
}

# Sections with existing comment-prefixed claims
COMMENT_CLAIMS_SECTIONS = [
    "05_transition_gap.tex",
    "06_closed_loop.tex",
    "09_conclusion.tex",
]


def main():
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    GROUNDED_DIR.mkdir(parents=True, exist_ok=True)

    results = {}

    # Process sections with existing comment-prefixed claims
    for section in COMMENT_CLAIMS_SECTIONS:
        section_path = SECTIONS_DIR / section
        content = section_path.read_text(encoding="utf-8")
        claims_data, body = extract_claims_from_comments(content)
        if claims_data is None:
            print(f"FAILED to extract claims from {section}")
            results[section] = "extract_failed"
            continue
        temp_path = TEMP_DIR / section
        create_temp_input(claims_data, body, temp_path)
        output_path = GROUNDED_DIR / section
        result = run_tool(temp_path, output_path)
        verified = result.returncode == 0
        print(f"{section}: verified={verified}")
        if not verified:
            try:
                out = json.loads(result.stdout)
                for c in out.get("failed_claims", []):
                    print(f"  FAIL: {c.get('cite_key')} -> {c.get('issues')}")
                    print(f"    quote: {c.get('quote','')[:120]}")
            except Exception:
                print(f"  stdout: {result.stdout[:800]}")
                print(f"  stderr: {result.stderr[:500]}")
        results[section] = "verified" if verified else "failed"

    # Process sections with manual claims
    for section, claims_data in MANUAL_CLAIMS.items():
        section_path = SECTIONS_DIR / section
        content = section_path.read_text(encoding="utf-8")
        temp_path = TEMP_DIR / section
        create_temp_input(claims_data, content, temp_path)
        output_path = GROUNDED_DIR / section
        result = run_tool(temp_path, output_path)
        verified = result.returncode == 0
        print(f"{section}: verified={verified}")
        if not verified:
            try:
                out = json.loads(result.stdout)
                for c in out.get("failed_claims", []):
                    print(f"  FAIL: {c.get('cite_key')} -> {c.get('issues')}")
                    print(f"    quote: {c.get('quote','')[:120]}")
            except Exception:
                print(f"  stdout: {result.stdout[:800]}")
                print(f"  stderr: {result.stderr[:500]}")
        results[section] = "verified" if verified else "failed"

    # Summary
    print("\n=== SUMMARY ===")
    for section, status in results.items():
        print(f"  {section}: {status}")

    # Cleanup temp files
    import shutil
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)
        print("\nTemp files cleaned up.")


if __name__ == "__main__":
    main()
