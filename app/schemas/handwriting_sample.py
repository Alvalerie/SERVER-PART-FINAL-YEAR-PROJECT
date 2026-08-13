"""
app/schemas/handwriting_sample.py

Request/response shapes for handwriting enrolment and identification.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------
# Quality configuration
# ---------------------------------------------------------------------

class QualityConfigOut(BaseModel):
    """
    Served by GET /config/sample-quality.

    The mobile app enforces these locally so a bad capture is caught
    while the paper is still on the desk. Because the numbers come from
    the server, the two sides cannot drift apart and the blur threshold
    can be retuned without an app release.
    """

    min_width: int
    min_height: int
    max_aspect_ratio: float
    min_blur_score: float
    min_contrast: float
    min_ink_ratio: float
    max_ink_ratio: float

    # False while the blur threshold is still being calibrated: the
    # server reports blur but does not reject on it.
    enforce_blur_check: bool

    min_samples_per_student: int


# ---------------------------------------------------------------------
# Samples
# ---------------------------------------------------------------------

class SampleOut(BaseModel):
    """
    A stored sample, as returned by the read routes.

    Read directly off the ORM object, so it contains only real columns.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    student_no: str
    path: str
    model_version: str | None = None
    created_at: datetime


class EnrolledSampleOut(SampleOut):
    """
    A sample that was just accepted.

    Carries the extra context the operator needs at capture time and
    which does NOT exist as a column -- hence a separate schema. Putting
    these on SampleOut would make every read route fail validation.
    """

    sample_count: int = Field(description="Total samples now held for this student")
    is_enrolled: bool = Field(description="Whether the minimum has been reached")

    # width, height, aspect_ratio, blur_score, contrast, ink_ratio.
    # Values are floats and ints mixed, so left loosely typed.
    quality_metrics: dict = Field(default_factory=dict)


class RejectedSample(BaseModel):
    """
    One file that did not make it in.

    `code` is the contract -- the app switches on it. `message` is for
    display only and must never be parsed.
    """

    filename: str | None = None
    code: str
    message: str


class BulkEnrolResult(BaseModel):
    """
    Result of uploading a batch of samples.

    Partial success is normal, not an error: an operator uploads
    fourteen photos and two are blurry. Each file is reported
    separately and the accepted ones are kept, so the whole batch never
    has to be redone.
    """

    accepted: list[EnrolledSampleOut]
    rejected: list[RejectedSample]

    sample_count: int
    is_enrolled: bool
    samples_needed: int = Field(
        description="How many more are required before this student counts "
                    "as enrolled. Zero once the minimum is met."
    )


# ---------------------------------------------------------------------
# Identification
# ---------------------------------------------------------------------

class WriterCandidate(BaseModel):
    """
    One suggested writer. A suggestion, never a decision.
    """

    rank: int
    student_no: str

    # The closest sample for this student, so the UI can show the actual
    # handwriting side by side with the script being reviewed. That is
    # what makes the confirm step a real check rather than a rubber stamp.
    sample_id: int

    # Cosine distance. Lower is closer. Range is [0, 2] for unit-length
    # embeddings, so no upper bound of 1 here.
    distance: float = Field(ge=0.0)

    # 1 - distance, purely as a display aid. NOT a probability and NOT a
    # confidence percentage -- the UI must not present it as one. Can be
    # negative when two embeddings point in opposing directions.
    score: float


class WriterSuggestions(BaseModel):
    candidates: list[WriterCandidate]

    # How many students were searched. None means every enrolled student
    # was searched, which is a testing mode -- in real use this should be
    # the size of the marking session's roster.
    searched_pool_size: int | None = None

    # Set when the crop passed but scored poorly. The lecturer is told
    # the suggestions may be unreliable rather than being refused: a
    # script cannot be recaptured the way an enrolment photo can.
    quality_warning: str | None = None