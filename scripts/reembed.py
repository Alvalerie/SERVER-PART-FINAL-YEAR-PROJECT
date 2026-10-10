"""
scripts/reembed.py

Recompute every stored embedding with the current checkpoint.

Run after replacing ml/best_model.pth AND bumping MODEL_VERSION in .env:

    python -m scripts.reembed            # re-embed everything stale
    python -m scripts.reembed --dry-run  # only report how many are stale

Embeddings from different checkpoints are not comparable, and
search_similar only ranks rows whose model_version matches the current
one -- so until this runs, students enrolled under the old version are
invisible to identification. The source images in IMAGES_DIR are the
real asset; embeddings are derived from them.
"""

from __future__ import annotations

import argparse
import logging

from app.config.settings import settings
from app.dependencies.database import SessionLocal
from app.repositories.handwriting_sample import HandwritingSampleRepository
from app.utils.image_io import to_pil

# Import every model so SQLAlchemy can resolve relationships.
import app.models  # noqa: F401
from ml.model import get_embedding_from_image

logger = logging.getLogger("reembed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch", type=int, default=200)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    version = settings.MODEL_VERSION
    done = missing = failed = 0
    failed_ids: set[int] = set()

    with SessionLocal() as db:
        repo = HandwritingSampleRepository(db)

        if args.dry_run:
            stale = repo.stale_embeddings(version, limit=1_000_000)
            logger.info("%d sample(s) not embedded with %s", len(stale), version)
            return

        while True:
            # Rows that fail stay stale; skip them so the loop ends.
            batch = [
                s for s in repo.stale_embeddings(version, limit=args.batch + len(failed_ids))
                if s.id not in failed_ids
            ][: args.batch]
            if not batch:
                break

            for sample in batch:
                path = settings.IMAGES_DIR / sample.path
                if not path.is_file():
                    logger.warning("missing file for sample %s: %s", sample.id, path)
                    missing += 1
                    failed_ids.add(sample.id)
                    continue
                try:
                    embedding = get_embedding_from_image(to_pil(path.read_bytes()))
                    repo.update_embedding(sample, embedding, version)
                    done += 1
                except Exception:
                    logger.exception("failed to re-embed sample %s", sample.id)
                    failed += 1
                    failed_ids.add(sample.id)

            logger.info("re-embedded %d so far", done)

    logger.info("done: %d re-embedded, %d missing file, %d failed (version %s)",
                done, missing, failed, version)


if __name__ == "__main__":
    main()
