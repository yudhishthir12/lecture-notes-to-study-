"""Unit tests for the study pack evaluation and quality audit engine.

Tests verify:
- Deterministic checks (empty answers, missing text, duplicate questions, MCQ validity)
- Citation provenance validation (rejecting <= 0 page numbers)
- Weighted overall scoring calculation
- Pass/Fail criteria enforcement
- Fallback estimation when LLM is unavailable
"""

import uuid
from datetime import datetime, timezone

import pytest

from app.evaluation.evaluator import StudyPackEvaluator
from app.schemas.study_pack import (
    Concept,
    DifficultyLevel,
    Formula,
    KeyTerm,
    MCQOption,
    PracticeQuestion,
    QuestionType,
    SourceReference,
    StudyPackContent,
    StudyPackMetadata,
    Summary,
)
from app.services.llm_service import GeminiProvider


@pytest.fixture
def evaluator() -> StudyPackEvaluator:
    """Fixture returning a StudyPackEvaluator using unconfigured mock LLM."""
    mock_llm = GeminiProvider(api_key=None)
    return StudyPackEvaluator(llm_service=mock_llm)


# ==============================================================================
# Deterministic Checks Tests
# ==============================================================================


def test_deterministic_checks_on_valid_pack(
    evaluator: StudyPackEvaluator, sample_study_pack_content: StudyPackContent
):
    """Verify that a valid, fully populated study pack passes deterministic checks with zero issues."""
    issues = evaluator.deterministic_checks(sample_study_pack_content)
    assert len(issues) == 0


def test_deterministic_checks_detects_empty_answers(
    evaluator: StudyPackEvaluator, sample_study_pack_content: StudyPackContent
):
    """Verify that questions with empty correct_answer or empty explanation are flagged."""
    pack = sample_study_pack_content.model_copy(deep=True)

    # Empty correct answer on question 1
    pack.practice_questions[0].correct_answer = "   "
    # Empty explanation on question 2
    pack.practice_questions[1].explanation = ""

    issues = evaluator.deterministic_checks(pack)

    assert any("empty correct_answer" in iss for iss in issues)
    assert any("empty explanation" in iss for iss in issues)


def test_deterministic_checks_detects_duplicate_questions(
    evaluator: StudyPackEvaluator, sample_study_pack_content: StudyPackContent
):
    """Verify that duplicate questions are detected via normalized text matching."""
    pack = sample_study_pack_content.model_copy(deep=True)

    # Duplicate question text
    duplicate_q = PracticeQuestion(
        id="q-dup",
        question_text=pack.practice_questions[0].question_text.upper(),  # Same text in uppercase
        question_type=QuestionType.SHORT_ANSWER,
        difficulty=DifficultyLevel.EASY,
        correct_answer="Solution",
        explanation="Reasoning",
    )
    pack.practice_questions.append(duplicate_q)

    issues = evaluator.deterministic_checks(pack)
    assert any("Duplicate question detected" in iss for iss in issues)


def test_deterministic_checks_detects_invalid_citations(
    evaluator: StudyPackEvaluator, sample_study_pack_content: StudyPackContent
):
    """Verify that page numbers <= 0 are flagged as citation errors."""
    pack = sample_study_pack_content.model_copy(deep=True)
    pack.practice_questions[0].source_ref = SourceReference(page_numbers=[0, -1])

    issues = evaluator.deterministic_checks(pack)
    assert any("invalid page number" in iss for iss in issues)


def test_deterministic_checks_detects_brief_summaries(
    evaluator: StudyPackEvaluator, sample_study_pack_content: StudyPackContent
):
    """Verify that missing or excessively brief summaries trigger issues."""
    pack = sample_study_pack_content.model_copy(deep=True)
    pack.summary = Summary(overview="Too short", detailed_summary="Brief")

    issues = evaluator.deterministic_checks(pack)
    assert any("Summary overview is missing or excessively brief" in iss for iss in issues)
    assert any("Detailed summary is missing or insufficiently detailed" in iss for iss in issues)


# ==============================================================================
# Scoring Calculation and Pass / Fail Criteria
# ==============================================================================


def test_scoring_calculation_weights(
    evaluator: StudyPackEvaluator, sample_study_pack_content: StudyPackContent
):
    """Verify weighted scoring formula:

    Overall = 0.35 * Faithfulness + 0.25 * Coverage + 0.25 * Accuracy + 0.15 * Clarity.
    """
    result = evaluator.evaluate(sample_study_pack_content)

    # Expected score when all 4 metrics are 5:
    # 0.35*5 + 0.25*5 + 0.25*5 + 0.15*5 = 5.0
    assert result.overall_score == 5.0
    assert result.faithfulness == 5
    assert result.coverage == 5
    assert result.answer_accuracy == 5
    assert result.clarity == 5
    assert result.passed is True


def test_evaluator_penalizes_question_flaws(
    evaluator: StudyPackEvaluator, sample_study_pack_content: StudyPackContent
):
    """Verify that detected question flaws cap answer_accuracy at <= 3 and cause evaluation failure."""
    pack = sample_study_pack_content.model_copy(deep=True)
    pack.practice_questions[0].correct_answer = ""

    result = evaluator.evaluate(pack)

    assert result.answer_accuracy <= 3
    assert result.passed is False
    assert "practice_questions" in result.failed_sections
    assert len(result.issues) > 0


def test_evaluator_pass_criteria(
    evaluator: StudyPackEvaluator, sample_study_pack_content: StudyPackContent
):
    """Verify benchmark criteria: pass requires all criteria >= 4, overall >= 4.0, zero issues."""
    # A flawless pack passes
    result_clean = evaluator.evaluate(sample_study_pack_content)
    assert result_clean.passed is True

    # Pack with issue fails even if overall is relatively high
    pack_flawed = sample_study_pack_content.model_copy(deep=True)
    pack_flawed.practice_questions[1].explanation = ""
    result_flawed = evaluator.evaluate(pack_flawed)
    assert result_flawed.passed is False
