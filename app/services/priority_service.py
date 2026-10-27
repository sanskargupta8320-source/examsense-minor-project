import json
from typing import List, Dict, Any


def calculate_topic_priority(
    frequency: int,
    total_marks: int,
    years_asked: List[int],
    all_subject_years: List[int],
    avg_marks_per_question: float = 7.0,
    has_notes_bonus: bool = False,
    total_subject_questions: int = 0,
    total_subject_marks: int = 0,
) -> Dict[str, Any]:
    """
    Computes a smart multi-factor priority score (0-100) and classification (High/Medium/Low):
    
    Priority Score = (Topic Frequency Ratio * 0.45) + (Normalized Marks Weightage * 0.35) + (Cross-Year Recency/Repeat Bonus * 0.20)
    
    1. Topic Frequency Ratio (0 - 45 pts):
       Reflects consistency across exam cycles or relative share of questions.
    2. Normalized Marks Weightage (0 - 35 pts):
       Aggregate exam marks carried by questions in this topic relative to total paper weightage.
    3. Cross-Year Recency / Repeat Bonus (0 - 20 pts):
       Considers how recently the topic was asked, cross-year appearances, and gap comeback rotation.
    4. Optional Notes Source Bonus (+5 pts):
       Granted if verified study notes or teacher lecture materials reinforce this topic.
    """
    sorted_subject_years = sorted(list(set(all_subject_years)))
    latest_year = sorted_subject_years[-1] if sorted_subject_years else 2023
    sorted_topic_years = sorted(list(set(years_asked)))
    last_year_topic = sorted_topic_years[-1] if sorted_topic_years else 2020

    # 1. Topic Frequency Ratio (0 - 45 pts)
    # If total_subject_questions is known, use true ratio; otherwise use scale relative to typical paper
    if total_subject_questions and total_subject_questions > 0:
        freq_ratio = frequency / total_subject_questions
        # A topic having 25%+ of questions is dominant; scale smoothly
        freq_pts = min(45.0, (freq_ratio / 0.25) * 45.0 if freq_ratio < 0.25 else 45.0)
    else:
        # 1 appearance = 16 pts, 2 = 30 pts, 3 = 39 pts, 4+ = 45 pts
        freq_pts = min(45.0, frequency * 12.0 + (6.0 if frequency >= 2 else 4.0))

    # 2. Normalized Marks Weightage (0 - 35 pts)
    if total_subject_marks and total_subject_marks > 0:
        marks_ratio = total_marks / total_subject_marks
        marks_pts = min(35.0, (marks_ratio / 0.25) * 35.0 if marks_ratio < 0.25 else 35.0)
    else:
        # Relative to average question marks
        marks_factor = total_marks / max(1.0, avg_marks_per_question)
        marks_pts = min(35.0, marks_factor * 7.0)

    # 3. Cross-Year Recency / Repeat Bonus (0 - 20 pts)
    years_diff = latest_year - last_year_topic
    recency_base = 10.0 if years_diff <= 0 else (7.0 if years_diff == 1 else (4.0 if years_diff == 2 else 2.0))
    
    # Gap Comeback Bonus: core recurring topic omitted in the most recent cycle rotates back
    gap_bonus = 0.0
    gap_reason = ""
    if frequency >= 2 and years_diff == 1:
        gap_bonus = 10.0
        gap_reason = f"Core topic ({frequency}x) was omitted in {latest_year}. High rotational comeback probability for upcoming exam!"
    elif frequency >= 2 and years_diff == 2:
        gap_bonus = 7.0
        gap_reason = f"Frequent topic not asked for 2 cycles ({last_year_topic}-{latest_year}). Strong cyclical rebound likelihood."
    elif frequency >= 3 and years_diff == 0:
        gap_bonus = 8.0
        gap_reason = "Sustained evergreen high-yield topic tested consistently every exam cycle."
    elif frequency >= 2:
        gap_bonus = 5.0
        gap_reason = f"Tested multiple times across exam cycles ({frequency} appearances)."
    else:
        gap_reason = "Standard curriculum topic."

    recency_repeat_pts = min(20.0, recency_base + gap_bonus)

    # Combine with weights (45% + 35% + 20%) + notes bonus
    notes_bonus = 5.0 if has_notes_bonus else 0.0
    total_score = min(100.0, freq_pts + marks_pts + recency_repeat_pts + notes_bonus)

    # Standard threshold classification
    if total_score >= 65.0:
        priority_level = "High"
    elif total_score >= 42.0:
        priority_level = "Medium"
    else:
        priority_level = "Low"

    breakdown = {
        "frequency_pts": round(freq_pts, 1),
        "marks_pts": round(marks_pts, 1),
        "recency_repeat_pts": round(recency_repeat_pts, 1),
        "gap_bonus": round(gap_bonus, 1),
        "notes_bonus": notes_bonus,
        "total_score": round(total_score, 1),
        "priority_level": priority_level,
        "gap_reason": gap_reason,
        "latest_exam_year": latest_year,
        "last_asked_year": last_year_topic,
        "years_diff": years_diff,
        "formula": "Score = Frequency Ratio (45%) + Marks Weightage (35%) + Cross-Year Recency/Repeat Bonus (20%)",
        "disclaimer": "Trend-based prediction derived from historical examination patterns. Not an official guarantee by the exam board or authority."
    }

    return {
        "priority_score": round(total_score, 1),
        "priority_level": priority_level,
        "breakdown": breakdown,
    }


def calibrate_priorities_percentile(topics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Dynamically calibrates topic priorities so that High Priority Topics is NEVER 0
    when topics exist (e.g. when only a single question paper is uploaded).
    
    If no topic reached the absolute 'High' threshold (65.0):
    - Top 30-35% of topics (at least the top 1 or 2 topics) become 'High' Priority (Must Study)
    - Next 40% become 'Medium' Priority (Important)
    - Remainder stay 'Low' Priority (Good to Know)
    
    Adjusts priority_score accordingly so ordering and thresholds remain consistent.
    """
    if not topics:
        return topics

    # Check if any topic is already High
    has_high = any(t.get("priority_level") == "High" for t in topics)
    if has_high:
        return topics

    # Sort descending by current score
    sorted_topics = sorted(topics, key=lambda t: t.get("priority_score", 0), reverse=True)
    n = len(sorted_topics)

    # Determine boundaries
    high_count = max(1, int(round(n * 0.35))) if n >= 3 else 1
    med_count = max(1, int(round(n * 0.40))) if n - high_count >= 1 else 0

    for idx, t in enumerate(sorted_topics):
        if not isinstance(t.get("priority_breakdown"), dict):
            t["priority_breakdown"] = {}

        if idx < high_count:
            t["priority_level"] = "High"
            # Ensure score is in High range [70, 95]
            boost = max(70.0, min(95.0, 75.0 + (high_count - idx) * 5.0))
            t["priority_score"] = round(boost, 1)
            t["priority_breakdown"]["priority_level"] = "High"
            t["priority_breakdown"]["total_score"] = t["priority_score"]
            t["priority_breakdown"]["calibrated"] = True
            t["priority_breakdown"]["calibration_note"] = "Dynamically prioritized as Top Predicted Exam Topic based on relative question frequency and marks weightage."
        elif idx < high_count + med_count:
            t["priority_level"] = "Medium"
            # Ensure score in Medium range [48, 64]
            t["priority_score"] = round(max(48.0, min(64.0, t.get("priority_score", 50.0))), 1)
            t["priority_breakdown"]["priority_level"] = "Medium"
            t["priority_breakdown"]["total_score"] = t["priority_score"]
        else:
            t["priority_level"] = "Low"
            t["priority_score"] = round(min(41.0, t.get("priority_score", 35.0)), 1)
            t["priority_breakdown"]["priority_level"] = "Low"
            t["priority_breakdown"]["total_score"] = t["priority_score"]

    return sorted_topics
