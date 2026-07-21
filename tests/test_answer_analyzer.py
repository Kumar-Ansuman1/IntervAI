from backend.interview.answer_analyzer import analyze_answer,calculate_overall_score


def test_answer_analyzer() -> None:
    question = (
        "What is the difference between a Python list and a tuple?"
    )

    candidate_answer = (
    "A list is an ordered mutable collection, while a tuple is "
    "ordered and immutable. Lists are useful when values need to "
    "change dynamically. Tuples are suitable for fixed records and "
    "can be used as dictionary keys when all their elements are "
    "hashable. Tuples also generally have less memory overhead."
)

    analysis = analyze_answer(
        question=question,
        candidate_answer=candidate_answer,
        skill="Python",
        topic="Data structures",
        difficulty="easy"
    )

    overall_score = calculate_overall_score(analysis)

    print("\nANSWER ANALYSIS")
    print("-" * 50)

    print(f"Correctness: {analysis.correctness_score}/10")
    print(f"Completeness: {analysis.completeness_score}/10")
    print(f"Clarity: {analysis.clarity_score}/10")
    print(
        "Practical understanding: "
        f"{analysis.practical_understanding_score}/10"
    )

    print(f"Overall score: {overall_score}/10")
    print(f"Strengths: {analysis.strengths}")
    print(f"Missing concepts: {analysis.missing_concepts}")
    print(f"Misconceptions: {analysis.misconceptions}")
    print(f"Feedback: {analysis.feedback}")

    print(
        "Recommended action: "
        f"{analysis.recommended_action}"
    )

    print(
        "Recommended difficulty: "
        f"{analysis.recommended_difficulty}"
    )

    print(f"Follow-up focus: {analysis.follow_up_focus}")


if __name__ == "__main__":
    test_answer_analyzer()