"""
app/utils/image_io.py

Image loading and normalisation shared by the quality gate, the
embedding pipeline, and scripts/bulk_enroll.py.

Pure logic: no database, no HTTP, no FastAPI imports.

Why this module exists
----------------------
A phone camera does not rotate the pixels when you turn the phone. It
writes the pixels in sensor order and records an Orientation tag in the
EXIF header saying how to display them. Some readers honour that tag and
some do not, so the same file can be 1069x211 to one library and 211x1069
to another.

That breaks three things at once:

  1. The aspect-ratio check rejects perfectly good portrait captures.
  2. The model sees sideways handwriting and produces a meaningless
     embedding.
  3. Enrolment and identification can disagree if one path honours the
     tag and the other does not -- the worst case, because nothing
     errors, the accuracy just quietly drops.

So orientation is applied ONCE, here, at the edge. Everything downstream
works on upright pixels with no EXIF at all.
"""

import io

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError


class ImageDecodeError(ValueError):
    """Raised when bytes cannot be read as an image."""


# JPEG quality used when re-encoding after rotation. High enough that
# the re-encode does not measurably move the blur or contrast scores.
_REENCODE_QUALITY = 95


def normalise_orientation(image_bytes: bytes) -> bytes:
    """
    Apply the EXIF Orientation tag to the pixels and strip the metadata.

    Returns bytes that every downstream reader will agree on.

    Call this FIRST, before the quality gate and before embedding, and
    store the returned bytes -- not the original upload. If you store
    the original and normalise on read, you have simply moved the
    inconsistency rather than removed it.

    Stripping EXIF also drops GPS coordinates and device identifiers,
    which is worth having on file: handwriting samples are kept
    indefinitely, and there is no reason to keep where each one was
    taken.
    """
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            # exif_transpose returns a NEW image with the rotation baked
            # into the pixels. On a file with no EXIF it is a no-op.
            upright = ImageOps.exif_transpose(image)

            # Drop the alpha channel: handwriting on paper has no use
            # for transparency, and PNG uploads with alpha would
            # otherwise reach cv2 as 4 channels.
            if upright.mode != "RGB":
                upright = upright.convert("RGB")

            buffer = io.BytesIO()
            # No exif= argument, so the metadata does not come along.
            upright.save(buffer, format="JPEG", quality=_REENCODE_QUALITY)
            return buffer.getvalue()

    except UnidentifiedImageError as exc:
        raise ImageDecodeError("File could not be read as an image.") from exc
    except OSError as exc:
        # Truncated uploads land here -- an interrupted transfer over a
        # weak connection produces a file that opens but cannot be read
        # to the end.
        raise ImageDecodeError("Image file is incomplete or corrupt.") from exc


def decode_bgr(image_bytes: bytes) -> np.ndarray:
    """
    Decode to an OpenCV BGR array.

    Assumes orientation has already been normalised. Note that OpenCV
    does not reliably apply EXIF rotation on imdecode, which is exactly
    the inconsistency normalise_orientation exists to remove -- so do
    not call this on raw upload bytes.
    """
    buffer = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)

    if image is None:
        raise ImageDecodeError("File could not be decoded as an image.")

    return image


def to_pil(image_bytes: bytes) -> Image.Image:
    """
    Decode to a PIL image for the model transforms.

    The Siamese pipeline was built on PIL in Colab -- pad_to_square,
    Resize, Grayscale all operate on PIL images. Keeping the same
    library here avoids any chance of a subtle difference between how
    training saw an image and how inference does.
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()  # force full read now, so truncation raises here
        return image.convert("RGB")
    except UnidentifiedImageError as exc:
        raise ImageDecodeError("File could not be read as an image.") from exc
    except OSError as exc:
        raise ImageDecodeError("Image file is incomplete or corrupt.") from exc


def prepare_upload(image_bytes: bytes) -> tuple[bytes, np.ndarray]:
    """
    Convenience for the service layer: normalise once, then hand back
    both the bytes to store and the BGR array the quality gate needs.

    Decoding twice for one upload is wasteful and, more importantly,
    risks the gate and the stored file diverging.
    """
    normalised = normalise_orientation(image_bytes)
    return normalised, decode_bgr(normalised)