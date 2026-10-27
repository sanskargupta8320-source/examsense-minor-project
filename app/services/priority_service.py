import json
from typing import List, Dict, Any


def calculate_topic_priority(
    frequency: int,
    total_marks: int,
    years_asked: List[int],
    all_subject_years: List[int],
    avg_marks_per_question: float = 7.0,
) -> Dict[str, Any]:
    """
    Computes a transparent priority score (0-100) and classification (High/Medium/Low)
    for an exam topic based on 4 key academic examination metrics:
    
    1. Frequency Weight (0-40 pts): Consistency across exam papers (10 pts per appearance, max 40).
    2. Marks Weight (0-25 pts): Total aggregate marks carried by questions in this topic.
    3. Recency Weight (0-15 pts): How recently the topic appeared in examinations.
    4. Gap Comeback Bonus (0-20 pts): University pattern bonus. Core frequent topics (>=2 appearances)
       that were skipped in the most recent 1-2 exam cycles have a statistically high return probability.
    
    Returns:
        dict containing:
            priority_score: float (0 - 100)
            priority_level: "High" | "Medium" | "Low"
            breakdown: detailed sub-scores and human-readable explanation
    """
    sorted_subject_years = sorted(list(set(all_subject_years)))
    latest_year = sorted_subject_years[-1] if sorted_subject_years else 2023
    sorted_topic_years = sorted(list(set(years_asked)))
    last_year_topic = sorted_topic_years[-1] if sorted_topic_years else 2020

    # 1. Frequency Score (up to 40 pts)
    # 1 appearance = 12 pts, 2 = 24 pts, 3 = 34 pts, 4+ = 40 pts
    freq_pts = min(40.0, frequency * 10.0 + (5.0 if frequency >= 2 else 0.0))

    # 2. Marks Score (up to 25 pts)
    # Relative to average question marks
    marks_factor = total_marks / max(1.0, avg_marks_per_question)
    marks_pts = min(25.0, marks_factor * 5.0)

    # 3. Recency Score (up to 15 pts)
    years_diff = latest_year - last_year_topic
    if years_diff <= 0:
        recency_pts = 15.0  # Asked in latest exam
    elif years_diff == 1:
        recency_pts = 10.0  # Asked 1 year ago
    elif years_diff == 2:
        recency_pts = 6.0   # Asked 2 years ago
    else:
        recency_pts = 3.0   # Older

    # 4. Gap Comeback Bonus (up to 20 pts)
    # Core observation in Indian state universities (RGPV, VTU, AKTU, etc.):
    # Highly frequent topics that professors skipped in the immediately preceding year
    # frequently rotate back into the question paper!
    gap_bonus = 0.0
    gap_reason = ""
    if frequency >= 2 and years_diff == 1:
        gap_bonus = 20.0
        gap_reason = f"High-frequency core topic ({frequency}x) was omitted in {latest_year}. High rotational comeback probability for next exam!"
    elif frequency >= 2 and years_diff == 2:
        gap_bonus = 15.0
        gap_reason = f"Frequent topic not asked for 2 cycles ({last_year_topic}-{latest_year}). Strong cyclical rebound likelihood."
    elif frequency >= 3 and years_diff == 0:
        gap_bonus = 10.0
        gap_reason = "Sustained high-yield evergreen topic tested consistently every year."
    else:
        gap_reason = "Standard rotation pattern."

    total_score = min(100.0, freq_pts + marks_pts + recency_pts + gap_bonus)

    # Classification
    if total_score >= 65.0:
        priority_level = "High"
    elif total_score >= 42.0:
        priority_level = "Medium"
    else:
        priority_level = "Low"

    breakdown = {
        "frequency_pts": round(freq_pts, 1),
        "marks_pts": round(marks_pts, 1),
        "recency_pts": round(recency_pts, 1),
        "gap_bonus": round(gap_bonus, 1),
        "total_score": round(total_score, 1),
        "priority_level": priority_level,
        "gap_reason": gap_reason,
        "latest_exam_year": latest_year,
        "last_asked_year": last_year_topic,
        "years_diff": years_diff,
        "formula": "Score = Frequency (40%) + Marks Weight (25%) + Recency (15%) + Gap Comeback Bonus (20%)",
        "disclaimer": "Trend-based prediction derived from historical examination patterns. Not an official guarantee by the university."
    }

    return {
        "priority_score": round(total_score, 1),
        "priority_level": priority_level,
        "breakdown": breakdown,
    }
