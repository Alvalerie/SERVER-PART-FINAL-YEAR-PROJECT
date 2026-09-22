from torchvision import transforms
from PIL import Image, ImageOps
import numpy as np

TARGET_H = 224
CROP_SIZE = 224


def prepare_handwriting(image, target_height=TARGET_H, min_width=CROP_SIZE):
    """Crop ink, scale HEIGHT to 224, keep aspect ratio.

    Replaces the old pad-to-square approach, which squeezed wide
    handwriting lines into a thin strip with almost no visible ink.
    """
    image = image.convert('RGB')
    gray = image.convert('L')
    bbox = ImageOps.invert(gray).getbbox()
    if bbox:
        image = image.crop(bbox)
    width, height = image.size
    height = max(height, 1)
    new_w = max(min_width, int(round(width * target_height / height)))
    image = image.resize((new_w, target_height), Image.BILINEAR)
    if new_w < min_width:
        pad = min_width - new_w
        left = pad // 2
        image = ImageOps.expand(image, border=(left, 0, pad - left, 0), fill=(255, 255, 255))
    return image


def tensorize_crop(pil_img):
    """Turn one already-224x224 PIL crop into a normalized tensor."""
    img = pil_img.convert('RGB')
    img = transforms.Grayscale(num_output_channels=3)(img)
    tensor = transforms.ToTensor()(img)
    return transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225],
    )(tensor)


def get_eval_crops(image, n_crops=4):
    """Prepare an image, then return a list of horizontal 224x224 crops
    spanning its width. Matches Colab's embed_image() so enrolment and
    identification see the same thing the model was evaluated on.
    """
    prepared = prepare_handwriting(image)
    width, height = prepared.size
    if width <= CROP_SIZE:
        return [prepared.crop((0, 0, CROP_SIZE, CROP_SIZE))]
    xs = np.linspace(0, width - CROP_SIZE, num=n_crops)
    return [prepared.crop((int(x), 0, int(x) + CROP_SIZE, CROP_SIZE)) for x in xs]


eval_transform = transforms.Compose([
    transforms.Lambda(prepare_handwriting),
    transforms.CenterCrop(CROP_SIZE),
    transforms.Grayscale(num_output_channels=3),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])