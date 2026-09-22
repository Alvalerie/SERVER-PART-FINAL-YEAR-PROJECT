import torch
import torch.nn as nn
from torchvision import models
from PIL import Image
from pathlib import Path

from ml.transforms import get_eval_crops, tensorize_crop
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
            nn.Linear(512, embedding_dim),
            nn.BatchNorm1d(embedding_dim),
        )

    def forward(self, x):
        x = self.backbone(x)
        x = x.view(x.size(0), -1)
        x = self.embedding_head(x)
        return nn.functional.normalize(x, p=2, dim=1)


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
    model = _get_model()
    crops = get_eval_crops(image)
    batch = torch.stack([tensorize_crop(c) for c in crops]).to(device)
    with torch.no_grad():
        embs = model.get_embedding(batch)
        vec = nn.functional.normalize(embs.mean(0, keepdim=True), p=2, dim=1)
    return vec.squeeze(0).cpu().numpy().tolist()


def get_embedding_from_path(image_path: str) -> list:
    return get_embedding_from_image(Image.open(image_path).convert("RGB"))