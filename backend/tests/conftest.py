"""Pytest configuration and shared fixtures for LectureForge AI test suite."""

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.models.document import (
    Document,
    DocumentStatus,
    FileType,
    StudyPack,
    StudyPackStatus,
)
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
from app.services.llm_service import LLMService

# Test SQLite in-memory database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def async_db_engine():
    """Create an in-memory SQLite async engine for test isolation."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(async_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Yield an independent async database session per test."""
    session_factory = async_sessionmaker(
        bind=async_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(
    db_session: AsyncSession, tmp_path: Path
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """HTTPX AsyncClient configured with FastAPI app and database dependency override."""
    # Direct uploads/exports to temporary paths during testing
    original_upload_dir = settings.UPLOAD_DIR
    original_export_dir = settings.EXPORT_DIR
    settings.UPLOAD_DIR = str(tmp_path / "uploads")
    settings.EXPORT_DIR = str(tmp_path / "exports")

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()
    settings.UPLOAD_DIR = original_upload_dir
    settings.EXPORT_DIR = original_export_dir


@pytest.fixture
def sample_source_ref() -> SourceReference:
    """Fixture providing a standard traceable SourceReference."""
    return SourceReference(
        page_numbers=[1, 2],
        section_title="Introduction to Sorting",
        slide_numbers=[3, 4],
    )


@pytest.fixture
def sample_study_pack_content(sample_source_ref: SourceReference) -> StudyPackContent:
    """Fixture providing a complete, schema-valid StudyPackContent artifact."""
    doc_id = uuid.uuid4()
    return StudyPackContent(
        metadata=StudyPackMetadata(
            topic="Sorting Algorithms and Big-O Complexity",
            document_id=doc_id,
            source_pages=[1, 2, 3],
            generated_at=datetime.now(timezone.utc),
        ),
        summary=Summary(
            overview="Comprehensive analysis of comparison-based sorting algorithms and lower bounds.",
            detailed_summary=(
                "### Comparison-based Sorts\n\n"
                "Comparison-based sorting models operate by repeatedly querying pairwise elements. "
                "The theoretical lower bound is Omega(n log n) comparisons in the worst case.\n\n"
                "### Quicksort & Mergesort\n\n"
                "Mergesort provides deterministic O(n log n) runtime via divide-and-conquer, "
                "while Quicksort achieves O(n log n) expected time with low constant memory overhead."
            ),
        ),
        concepts=[
            Concept(
                name="Divide and Conquer",
                description="A recursive problem-solving paradigm that breaks problems into smaller subproblems.",
                source_ref=sample_source_ref,
            ),
            Concept(
                name="Asymptotic Lower Bound",
                description="The theoretical minimum number of comparisons necessary to sort n elements.",
                source_ref=sample_source_ref,
            ),
            Concept(
                name="Logarithmic Time Complexity",
                description="Algorithms whose running time scales with the logarithm of input size.",
                source_ref=sample_source_ref,
            ),
        ],
        key_terms=[
            KeyTerm(
                term="Stable Sort",
                definition="A sorting algorithm that preserves the relative order of duplicate keys.",
                source_ref=sample_source_ref,
            ),
            KeyTerm(
                term="In-Place",
                definition="An algorithm that requires O(1) auxiliary space beyond the input buffer.",
                source_ref=sample_source_ref,
            ),
        ],
        formulas=[
            Formula(
                expression="T(n) = 2T(n/2) + O(n) \\implies T(n) = O(n \\log n)",
                description="Master Theorem Case 2 recurrence relation for Mergesort",
                source_ref=sample_source_ref,
            ),
        ],
        practice_questions=[
            PracticeQuestion(
                id="q-001",
                question_text="What is the worst-case time complexity of standard Quicksort with first-element pivot?",
                question_type=QuestionType.MCQ,
                difficulty=DifficultyLevel.MEDIUM,
                options=[
                    MCQOption(label="A", text="O(n)"),
                    MCQOption(label="B", text="O(n log n)"),
                    MCQOption(label="C", text="O(n^2)"),
                    MCQOption(label="D", text="O(log n)"),
                ],
                correct_answer="C",
                explanation="When the array is already sorted and the first element is selected as pivot, partitions are unbalanced resulting in O(n^2) operations.",
                source_ref=sample_source_ref,
            ),
            PracticeQuestion(
                id="q-002",
                question_text="Explain why comparison-based sorting has a lower bound of Omega(n log n).",
                question_type=QuestionType.CONCEPTUAL,
                difficulty=DifficultyLevel.HARD,
                options=None,
                correct_answer="Any comparison-based algorithm corresponds to a decision tree with n! leaves. A binary tree with n! leaves must have depth at least log2(n!) = Omega(n log n).",
                explanation="The decision tree must distinguish between all possible n! permutations of input elements.",
                source_ref=sample_source_ref,
            ),
            PracticeQuestion(
                id="q-003",
                question_text="What auxiliary space complexity does standard top-down Mergesort require?",
                question_type=QuestionType.SHORT_ANSWER,
                difficulty=DifficultyLevel.EASY,
                options=None,
                correct_answer="O(n) auxiliary space",
                explanation="Mergesort allocates temporary buffers during the merge step to store partitioned subarrays.",
                source_ref=sample_source_ref,
            ),
        ],
        evaluation=EvaluationResult(
            faithfulness=5,
            coverage=5,
            answer_accuracy=5,
            clarity=5,
            overall_score=5.0,
            passed=True,
            issues=[],
            failed_sections=[],
        ),
        pipeline_metadata=PipelineMetadata(
            prompt_version="v1.0",
            model_name="gemini-2.0-flash",
            retry_count=0,
            processing_time_seconds=1.42,
        ),
    )


@pytest.fixture
def sample_document_data() -> dict:
    """Fixture providing sample dictionary for document creation."""
    return {
        "id": uuid.uuid4(),
        "filename": "Algorithms_Lecture_01.pdf",
        "file_type": "pdf",
        "file_path": "/tmp/Algorithms_Lecture_01.pdf",
        "file_size": 204800,
        "status": DocumentStatus.UPLOADED,
    }


@pytest.fixture
def mock_llm_service() -> MagicMock:
    """Provide a mock LLM service that simulates structured LLM responses without external API calls."""
    mock = MagicMock(spec=LLMService)
    mock.is_configured.return_value = True
    mock.generate.return_value = {
        "faithfulness": 5,
        "coverage": 5,
        "answer_accuracy": 5,
        "clarity": 5,
        "issues": [],
        "failed_sections": [],
    }
    return mock
