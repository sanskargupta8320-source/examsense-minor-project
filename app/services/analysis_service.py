import re
import json
import logging
from typing import List, Dict, Any, Tuple
from collections import defaultdict
from app.services.priority_service import calculate_topic_priority

logger = logging.getLogger("examsense.analysis")

# Attempt scikit-learn import
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn not available. Fallback to Jaccard token similarity.")


STOP_WORDS = {
    "what", "is", "are", "explain", "define", "discuss", "with", "suitable",
    "illustrative", "examples", "example", "describe", "how", "why", "the",
    "and", "for", "in", "of", "to", "a", "an", "short", "notes", "write",
    "brief", "detail", "different", "differentiate", "between", "state"
}


def clean_question_text_for_nlp(text: str) -> str:
    """Removes exam noise like question labels ('Q1.', '(a)', marks indicators) for clean similarity analysis."""
    # Remove question numbers e.g. "Q.1", "Q 1", "Question 2", "1(a)", "(b)", etc.
    cleaned = re.sub(r"^(Q(?:uestion)?\s*\.?\s*\d+\s*[\.\:\-\)]?|\d+[\.\)]\s*(?:\([a-zA-Z0-9]+\))?|\([a-zA-Z0-9]+\))\s*", "", text, flags=re.IGNORECASE)
    # Remove trailing marks indicators e.g. "[7]", "(10 Marks)", "7M"
    cleaned = re.sub(r"\[\s*\d+\s*(?:marks|m)?\s*\]|\(\s*\d+\s*(?:marks|m)?\s*\)|\d+\s*marks", "", cleaned, flags=re.IGNORECASE)
    # Lowercase & normalize spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    return cleaned


def extract_keywords(text: str) -> set:
    """Extracts informative semantic keywords after stripping common examination noise words."""
    cleaned = clean_question_text_for_nlp(text)
    words = re.findall(r"\b[a-zA-Z0-9]{2,}\b", cleaned)
    return set(w for w in words if w not in STOP_WORDS)


def compute_keyword_similarity(text1: str, text2: str) -> float:
    """
    Computes semantic similarity based on Szymkiewicz-Simpson overlap coefficient
    and Jaccard token matching for resilient fallback when scikit-learn is absent.
    """
    k1 = extract_keywords(text1)
    k2 = extract_keywords(text2)
    if not k1 or not k2:
        return 0.0
    intersection = len(k1.intersection(k2))
    overlap_coeff = intersection / min(len(k1), len(k2))
    jaccard = intersection / len(k1.union(k2))
    # Harmonic mean of overlap coefficient and Jaccard
    return (0.7 * overlap_coeff) + (0.3 * jaccard)


def find_repeated_questions(
    questions: List[Dict[str, Any]], similarity_threshold: float = 0.48
) -> List[Dict[str, Any]]:
    """
    Detects repeated or near-duplicate questions across different exam years using
    TF-IDF Vectorization and Cosine Similarity (scikit-learn).
    
    If scikit-learn is unavailable, falls back to tokenized keyword overlap similarity.
    
    Returns:
        List of repeated question groups with canonical text, years, and similarity scores.
    """
    if len(questions) < 2:
        return []

    cleaned_texts = [clean_question_text_for_nlp(q["question_text"]) for q in questions]

    # Compute similarity matrix
    n = len(questions)
    sim_matrix = [[0.0] * n for _ in range(n)]

    if SKLEARN_AVAILABLE and len(set(cleaned_texts)) > 1:
        try:
            vectorizer = TfidfVectorizer(
                stop_words="english",
                ngram_range=(1, 2),
                min_df=1,
                lowercase=True,
                token_pattern=r"(?u)\b\w+\b",
            )
            tfidf_mat = vectorizer.fit_transform(cleaned_texts)
            cos_sim = cosine_similarity(tfidf_mat)
            for i in range(n):
                for j in range(n):
                    sim_matrix[i][j] = float(cos_sim[i][j])
        except Exception as e:
            logger.warning(f"TF-IDF similarity failed, using fallback: {e}")
            for i in range(n):
                for j in range(n):
                    sim_matrix[i][j] = compute_keyword_similarity(cleaned_texts[i], cleaned_texts[j])
    else:
        for i in range(n):
            for j in range(n):
                if i == j:
                    sim_matrix[i][j] = 1.0
                else:
                    sim_matrix[i][j] = compute_keyword_similarity(cleaned_texts[i], cleaned_texts[j])

    # If questions share identical topic and strong keywords, boost similarity
    for i in range(n):
        for j in range(i + 1, n):
            topic_i = questions[i].get("unit_or_topic_guess")
            topic_j = questions[j].get("unit_or_topic_guess")
            if topic_i and topic_j and topic_i == topic_j:
                if sim_matrix[i][j] >= 0.35:
                    sim_matrix[i][j] = min(0.98, sim_matrix[i][j] + 0.15)
                    sim_matrix[j][i] = sim_matrix[i][j]

    # Graph adjacency / Connected components to cluster duplicate questions
    adj = defaultdict(list)
    pair_scores = {}

    for i in range(n):
        for j in range(i + 1, n):
            score = sim_matrix[i][j]
            if score >= similarity_threshold:
                adj[i].append(j)
                adj[j].append(i)
                pair_scores[(min(i, j), max(i, j))] = score

    visited = set()
    groups = []

    for i in range(n):
        if i not in visited and adj[i]:
            # BFS to find connected component
            cluster = []
            queue = [i]
            visited.add(i)

            while queue:
                curr = queue.pop(0)
                cluster.append(curr)
                for neighbor in adj[curr]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)

            if len(cluster) >= 2:
                # Group questions in this cluster
                cluster_questions = [questions[idx] for idx in cluster]
                
                # Check years involved
                cluster_years = sorted(list(set(q["year"] for q in cluster_questions)))
                
                # Calculate average similarity score among the cluster pairs
                cluster_scores = []
                for idx_a in cluster:
                    for idx_b in cluster:
                        if idx_a < idx_b and (idx_a, idx_b) in pair_scores:
                            cluster_scores.append(pair_scores[(idx_a, idx_b)])
                avg_sim = sum(cluster_scores) / max(1, len(cluster_scores))

                # Pick canonical question (the one with longest descriptive text)
                canonical = max(cluster_questions, key=lambda q: len(q["question_text"]))

                groups.append({
                    "canonical_question": canonical["question_text"],
                    "similarity_score": round(avg_sim, 2),
                    "years": cluster_years,
                    "question_ids": [q.get("id") for q in cluster_questions if q.get("id") is not None],
                    "questions": [
                        {
                            "id": q.get("id"),
                            "year": q["year"],
                            "marks": q.get("marks", 7),
                            "question_text": q["question_text"],
                        }
                        for q in cluster_questions
                    ],
                    "repeat_count": len(cluster_questions),
                })

    # Sort groups by repeat count and then similarity score descending
    groups.sort(key=lambda g: (g["repeat_count"], g["similarity_score"]), reverse=True)
    return groups


def aggregate_topics_and_priorities(
    questions: List[Dict[str, Any]], all_subject_years: List[int]
) -> List[Dict[str, Any]]:
    """
    Groups questions by normalized topic name and calculates:
    - Frequency
    - Total marks
    - Years asked
    - Last year asked
    - Priority score and level
    - Formula breakdown
    
    Returns:
        List of topic dicts sorted by priority_score descending.
    """
    topic_map = defaultdict(lambda: {
        "questions": [],
        "years": set(),
        "total_marks": 0,
    })

    for q in questions:
        topic_name = q.get("unit_or_topic_guess") or "General Fundamentals"
        # Capitalize/Clean topic name
        clean_topic = topic_name.strip()
        topic_map[clean_topic]["questions"].append(q)
        topic_map[clean_topic]["years"].add(q.get("year", 2023))
        topic_map[clean_topic]["total_marks"] += int(q.get("marks", 7))

    total_q_count = len(questions)
    total_q_marks = sum(q.get("marks", 7) for q in questions)
    avg_marks = (total_q_marks / max(1, total_q_count)) if total_q_count else 7.0

    aggregated_topics = []

    for name, data in topic_map.items():
        years_list = sorted(list(data["years"]))
        frequency = len(data["questions"])
        total_marks = data["total_marks"]
        last_year = years_list[-1] if years_list else 2023

        p_result = calculate_topic_priority(
            frequency=frequency,
            total_marks=total_marks,
            years_asked=years_list,
            all_subject_years=all_subject_years,
            avg_marks_per_question=avg_marks,
        )

        aggregated_topics.append({
            "name": name,
            "frequency": frequency,
            "total_marks": total_marks,
            "years_asked": years_list,
            "last_year_asked": last_year,
            "priority_score": p_result["priority_score"],
            "priority_level": p_result["priority_level"],
            "priority_breakdown": p_result["breakdown"],
            "questions": data["questions"],
        })

    # Sort topics by priority_score descending
    aggregated_topics.sort(key=lambda t: t["priority_score"], reverse=True)
    return aggregated_topics
