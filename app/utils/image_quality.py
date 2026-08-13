"""
app/utils/image_quality.py

Quality checks for enrolled handwriting samples.

Pure logic: no database, no HTTP, no FastAPI imports. Callable from the
service layer, from scripts/bulk_enroll.py, and from tests.

The service layer decides what a rejection means (422). This module only
reports.
"""

from dataclasses import dataclass, field

import cv2
import numpy as np


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class QualityThresholds:
    """
    Thresholds are injected, never hardcoded here, so that:
      - settings.py owns the values and .env can override them
      - GET /config/sample-quality can serve the same numbers to the app
      - tests can construct extreme values without touching settings
    """

    min_width: int = 150
    min_height: int = 150

    # Rejects the thin horizontal strips that cost you two writers.
    # 411x27 is an aspect ratio of 15.2.
    max_aspect_ratio: float = 4.0

    # Laplacian variance. THIS NUMBER IS A PLACEHOLDER.
    # It is scale- and content-dependent and must be calibrated on your
    # own images before you enable rejection. Ship it as a warning first.
    min_blur_score: float = 100.0

    # Standard deviation of grayscale pixel values. Catches the
    # dark-background / washed-out samples.
    min_contrast: float = 30.0

    # Fraction of pixels that are ink after Otsu thresholding.
    # Low  -> blank or near-blank page.
    # High -> the crop is mostly a dark background, not writing.
    min_ink_ratio: float = 0.01
    max_ink_ratio: float = 0.50


@dataclass(frozen=True)
class QualityResult:
    accepted: bool
    code: str | None = None
    message: str | None = None
    # Always populated, even on acceptance. Log these: they are what you
    # will use to calibrate the thresholds.
    metrics: dict = field(default_factory=dict)


# Codes the mobile app can switch on. Never parse the message string.
UNREADABLE = "UNREADABLE"
TOO_SMALL = "TOO_SMALL"
BAD_ASPECT_RATIO = "BAD_ASPECT_RATIO"
TOO_BLURRY = "TOO_BLURRY"
LOW_CONTRAST = "LOW_CONTRAST"
NOT_ENOUGH_WRITING = "NOT_ENOUGH_WRITING"
MOSTLY_BACKGROUND = "MOSTLY_BACKGROUND"


# ---------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------

def _blur_score(gray: np.ndarray) -> float:
    """
    Variance of the Laplacian. Sharp edges produce a wide spread of
    second-derivative values; blur flattens them.

    Note this is resolution-sensitive: the same photo downscaled scores
    differently. Measure on the image as uploaded, and keep the app and
    server measuring at the same size, or the two will disagree.
    """
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _contrast(gray: np.ndarray) -> float:
    return float(gray.std())


def _ink_ratio(gray: np.ndarray) -> float:
    """
    Otsu picks the threshold between paper and ink automatically, which
    is what makes this work across different lighting.

    THRESH_BINARY_INV so ink becomes 255 and paper 0, then the mean over
    255 is the fraction of the image that is ink.
    """
    _, binary = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    return float(binary.mean() / 255.0)


# ---------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------

def check_sample_quality(
    image: np.ndarray,
    thresholds: QualityThresholds | None = None,
    tolerance: float = 1.0,
) -> QualityResult:
    """
    Decide whether a handwriting sample is good enough to enrol.

    tolerance: multiplier applied to the score-based thresholds only.
        The server should pass something like 0.9 so it is very slightly
        more permissive than what it advertises to the app. JPEG
        re-encoding on upload shifts blur and contrast scores a little,
        and a borderline image that the app accepted must not then be
        rejected by the server -- that is the one failure mode users
        find genuinely infuriating.

    Checks run cheapest-first and return on the first failure, so a
    50x50 image never gets a Laplacian computed over it.
    """
    t = thresholds or QualityThresholds()


    if image is None:
        return QualityResult(
            accepted=False,
            code=UNREADABLE,
            message="This file could not be read as an image.",
        )

    height, width = image.shape[:2]

    # --- dimensions ---
    if width < t.min_width or height < t.min_height:
        return QualityResult(
            accepted=False,
            code=TOO_SMALL,
            message=(
                f"Image is {width}x{height}. It must be at least "
                f"{t.min_width}x{t.min_height}. Move closer to the paper."
            ),
            metrics={"width": width, "height": height},
        )

    # --- aspect ratio ---
    aspect = max(width / height, height / width)
    if aspect > t.max_aspect_ratio:
        return QualityResult(
            accepted=False,
            code=BAD_ASPECT_RATIO,
            message=(
                "This looks like a narrow strip rather than a block of "
                "writing. Capture two or three full lines together."
            ),
            metrics={"width": width, "height": height, "aspect_ratio": aspect},
        )

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    blur = _blur_score(gray)
    contrast = _contrast(gray)
    ink = _ink_ratio(gray)

    metrics = {
        "width": width,
        "height": height,
        "aspect_ratio": round(aspect, 2),
        "blur_score": round(blur, 2),
        "contrast": round(contrast, 2),
        "ink_ratio": round(ink, 4),
    }

    # --- blur ---
    if blur < t.min_blur_score * tolerance:
        return QualityResult(
            accepted=False,
            code=TOO_BLURRY,
            message="The writing is out of focus. Hold steady and retake.",
            metrics=metrics,
        )

    # --- contrast ---
    if contrast < t.min_contrast * tolerance:
        return QualityResult(
            accepted=False,
            code=LOW_CONTRAST,
            message=(
                "The writing does not stand out from the background. Use "
                "white paper in good light, and avoid shadows."
            ),
            metrics=metrics,
        )

    # --- ink coverage ---
    if ink < t.min_ink_ratio:
        return QualityResult(
            accepted=False,
            code=NOT_ENOUGH_WRITING,
            message="Almost no writing detected. Capture more of the text.",
            metrics=metrics,
        )

    if ink > t.max_ink_ratio:
        return QualityResult(
            accepted=False,
            code=MOSTLY_BACKGROUND,
            message=(
                "Most of this image is dark. Place the paper on a plain "
                "light surface and retake."
            ),
            metrics=metrics,
        )

    return QualityResult(accepted=True, metrics=metrics)