"""Unit tests for Pydantic schema validation in LectureForge AI.

Tests verify:
- Complete StudyPackContent schema validation
- MCQ question constraints (exactly 4 options labeled A-D, correct_answer in A-D)
- Question difficulty enum validation and rejection of invalid values
- SourceReference validation
- EvaluationResult scoring bounds and integrity constraints
"""

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.study_pack import (
    Concept,
    DifficultyLevel,
    EvaluationResult,
    Formula,
    KeyTerm,
    MCQOption,
    PipelineMetadata,
    PracticeQuestion,
    QuestionType,
    SourceReference,
    StudyPackContent,
    StudyPackMetadata,
    Summary,
)

# ==============================================================================
# MCQ Option and PracticeQuestion Validation
# ==============================================================================


def test_mcq_question_valid():
    """Verify that a valid MCQ with 4 options (A, B, C, D) passes validation."""
    q = PracticeQuestion(
        id="mcq-1",
        question_text="Which of the following sorting algorithms has O(n log n) worst-case time?",
        question_type=QuestionType.MCQ,
        difficulty=DifficultyLevel.EASY,
        options=[
            MCQOption(label="A", text="Quicksort"),
            MCQOption(label="B", text="Mergesort"),
            MCQOption(label="C", text="Insertion Sort"),
            MCQOption(label="D", text="Bubble Sort"),
        ],
        correct_answer="B",
        explanation="Mergesort guarantees O(n log n) worst-case time complexity.",
        source_ref=SourceReference(page_numbers=[1]),
    )

    assert q.correct_answer == "B"
    assert len(q.options) == 4


def test_mcq_requires_exactly_four_options():
    """Verify that an MCQ with fewer or more than 4 options raises a ValidationError."""
    # Only 3 options
    with pytest.raises(ValidationError, match="must have exactly 4 options"):
        PracticeQuestion(
            id="mcq-invalid-3",
            question_text="Question with only 3 options?",
            question_type=QuestionType.MCQ,
            difficulty=DifficultyLevel.EASY,
            options=[
                MCQOption(label="A", text="Option A"),
                MCQOption(label="B", text="Option B"),
                MCQOption(label="C", text="Option C"),
            ],
            correct_answer="A",
            explanation="Explanation text",
        )

    # 5 options
    with pytest.raises(ValidationError, match="must have exactly 4 options"):
        PracticeQuestion(
            id="mcq-invalid-5",
            question_text="Question with 5 options?",
            question_type=QuestionType.MCQ,
            difficulty=DifficultyLevel.EASY,
            options=[
                MCQOption(label="A", text="Option A"),
                MCQOption(label="B", text="Option B"),
                MCQOption(label="C", text="Option C"),
                MCQOption(label="D", text="Option D"),
                MCQOption(label="A", text="Duplicate label A"),
            ],
            correct_answer="A",
            explanation="Explanation text",
        )


def test_mcq_missing_options():
    """Verify that an MCQ without options list raises a ValidationError."""
    with pytest.raises(ValidationError, match="MCQ questions must include options"):
        PracticeQuestion(
            id="mcq-no-options",
            question_text="Question without any options?",
            question_type=QuestionType.MCQ,
            difficulty=DifficultyLevel.MEDIUM,
            options=None,
            correct_answer="A",
            explanation="Explanation text",
        )


def test_mcq_invalid_option_labels():
    """Verify that options with invalid label letters raise a ValidationError."""
    with pytest.raises(ValidationError, match="MCQ option label must be 'A', 'B', 'C', or 'D'"):
        MCQOption(label="E", text="Invalid fifth option")

    with pytest.raises(ValidationError, match="MCQ option label must be 'A', 'B', 'C', or 'D'"):
        MCQOption(label="1", text="Numeric label")


def test_mcq_invalid_correct_answer():
    """Verify that MCQ correct_answer must be one of A, B, C, or D."""
    with pytest.raises(
        ValidationError, match="MCQ correct_answer must be one of 'A', 'B', 'C', or 'D'"
    ):
        PracticeQuestion(
            id="mcq-bad-answer",
            question_text="Question with invalid answer key?",
            question_type=QuestionType.MCQ,
            difficulty=DifficultyLevel.MEDIUM,
            options=[
                MCQOption(label="A", text="Option A"),
                MCQOption(label="B", text="Option B"),
                MCQOption(label="C", text="Option C"),
                MCQOption(label="D", text="Option D"),
            ],
            correct_answer="E",
            explanation="Explanation",
        )


# ==============================================================================
# Difficulty and Question Type Enum Tests
# ==============================================================================


def test_invalid_difficulty_level_rejected():
    """Verify that an unrecognized difficulty level string raises a ValidationError."""
    with pytest.raises(ValidationError):
        PracticeQuestion(
            id="q-diff",
            question_text="What is P vs NP?",
            question_type=QuestionType.CONCEPTUAL,
            difficulty="impossible",  # Invalid enum value
            correct_answer="An unsolved computational complexity problem.",
            explanation="Explanation text.",
        )


def test_valid_difficulty_levels():
    """Verify all valid difficulty levels (easy, medium, hard) are accepted."""
    for level in (DifficultyLevel.EASY, DifficultyLevel.MEDIUM, DifficultyLevel.HARD):
        q = PracticeQuestion(
            id=f"q-{level.value}",
            question_text="Sample question",
            question_type=QuestionType.SHORT_ANSWER,
            difficulty=level,
            correct_answer="Model solution",
            explanation="Detailed explanation",
        )
        assert q.difficulty == level


# ==============================================================================
# SourceReference Validation
# ==============================================================================


def test_source_reference_fields():
    """Verify SourceReference correctly stores pages, sections, and slide numbers."""
    ref = SourceReference(
        page_numbers=[3, 4],
        section_title="4.2 Relational Algebra",
        slide_numbers=[12, 13],
    )
    assert ref.page_numbers == [3, 4]
    assert ref.section_title == "4.2 Relational Algebra"
    assert ref.slide_numbers == [12, 13]


def test_source_reference_defaults():
    """Verify SourceReference defaults to empty page numbers and None for section/slides."""
    ref = SourceReference()
    assert ref.page_numbers == []
    assert ref.section_title is None
    assert ref.slide_numbers is None


# ==============================================================================
# EvaluationResult Scoring Bounds
# ==============================================================================


def test_evaluation_result_valid():
    """Verify a valid EvaluationResult passes validation."""
    ev = EvaluationResult(
        faithfulness=4,
        coverage=5,
        answer_accuracy=4,
        clarity=5,
        overall_score=4.45,
        passed=True,
        issues=[],
        failed_sections=[],
    )
    assert ev.faithfulness == 4
    assert ev.overall_score == 4.45
    assert ev.passed is True


def test_evaluation_result_out_of_bounds_scores():
    """Verify scores below 1 or above 5 are rejected by Pydantic."""
    # Score 0 (below min 1)
    with pytest.raises(ValidationError):
        EvaluationResult(
            faithfulness=0,
            coverage=5,
            answer_accuracy=5,
            clarity=5,
            overall_score=3.75,
            passed=False,
        )

    # Score 6 (above max 5)
    with pytest.raises(ValidationError):
        EvaluationResult(
            faithfulness=5,
            coverage=6,
            answer_accuracy=5,
            clarity=5,
            overall_score=5.0,
            passed=True,
        )

    # overall_score > 5.0
    with pytest.raises(ValidationError):
        EvaluationResult(
            faithfulness=5,
            coverage=5,
            answer_accuracy=5,
            clarity=5,
            overall_score=5.5,
            passed=True,
        )


# ==============================================================================
# Full StudyPackContent Validation
# ==============================================================================


def test_study_pack_content_complete(sample_study_pack_content: StudyPackContent):
    """Verify that a complete StudyPackContent instance is fully schema-compliant."""
    assert sample_study_pack_content.metadata.topic == "Sorting Algorithms and Big-O Complexity"
    assert len(sample_study_pack_content.concepts) == 3
    assert len(sample_study_pack_content.key_terms) == 2
    assert len(sample_study_pack_content.formulas) == 1
    assert len(sample_study_pack_content.practice_questions) == 3
    assert sample_study_pack_content.evaluation is not None
    assert sample_study_pack_content.pipeline_metadata is not None
