import torch
import torch.nn as nn
from torchvision import models
from PIL import Image
from pathlib import Path

from ml.transforms import transform
from app.config.settings import settings


class EmbeddingNetwork(nn.Module):
    def __init__(self, embedding_dim=256):
        super(EmbeddingNetwork, self).__init__()

        resnet = models.resnet18(weights='IMAGENET1K_V1')
        self.backbone = nn.Sequential(*list(resnet.children())[:-1])

        for param in self.backbone.parameters():
            param.requires_grad = False

        for param in self.backbone[7].parameters():
            param.requires_grad = True

        self.embedding_head = nn.Sequential(
            nn.Linear(512, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(p=0.3),
        )

    def forward(self, x):
        x = self.backbone(x)
        x = x.view(x.size(0), -1)
        x = self.embedding_head(x)
        return x


class SiameseNetwork(nn.Module):
    def __init__(self, embedding_dim=256):
        super(SiameseNetwork, self).__init__()
        self.embedding_network = EmbeddingNetwork(embedding_dim)

    def forward(self, img1, img2):
        emb1 = self.embedding_network(img1)
        emb2 = self.embedding_network(img2)
        return emb1, emb2

    def get_embedding(self, img):
        return self.embedding_network(img)


device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Loaded on first use, not at import. A missing or broken checkpoint
# then disables handwriting only, rather than stopping the whole API --
# the CSV trunk does not depend on the model.
_model: SiameseNetwork | None = None


def _get_model() -> SiameseNetwork:
    global _model
    if _model is None:
        path = Path(settings.MODEL_CHECKPOINT_PATH)
        if not path.is_file():
            raise RuntimeError(f"Model checkpoint not found at {path}")

        m = SiameseNetwork(embedding_dim=256).to(device)
        m.load_state_dict(torch.load(path, map_location=device))
        m.eval()
        _model = m
    return _model


def get_embedding_from_image(image: Image.Image) -> list:
    """Embed a PIL image already loaded in memory (enrolment upload,
    identification crop)."""
    model = _get_model()
    tensor = transform(image).unsqueeze(0).to(device)
    with torch.no_grad():
        return model.get_embedding(tensor).cpu().numpy().tolist()[0]


def get_embedding_from_path(image_path: str) -> list:
    """Embed an image on disk. Used by scripts/bulk_enroll.py."""
    return get_embedding_from_image(Image.open(image_path).convert("RGB"))