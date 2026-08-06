from sqlalchemy.orm import Session

from ..models.image_model import Image


class ImageRepository:
    """
    Handles all direct database interactions for Image.
    No business logic lives here — only queries and mutations.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(self) -> list[Image]:
        return self.db.query(Image).all()

    def get_by_id(self, image_id: int) -> Image | None:
        return self.db.query(Image).filter(Image.id == image_id).first()

    def get_by_student(self, student_id: str) -> list[Image]:
        return self.db.query(Image).filter(Image.student_id == student_id).all()

    def get_all_with_vectors(self) -> list[Image]:
        """Return every image that has a stored vector (used for similarity search)."""
        return self.db.query(Image).filter(Image.vector.isnot(None)).all()

    def create(self, student_id: str, path: str, vector: str) -> Image:
        image = Image(
            student_id=student_id,
            path=path,
            vector=vector,
        )
        self.db.add(image)
        self.db.commit()
        self.db.refresh(image)
        return image

    def delete(self, image: Image) -> None:
        self.db.delete(image)
        self.db.commit()