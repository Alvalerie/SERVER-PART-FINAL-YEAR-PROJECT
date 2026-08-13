from torchvision import transforms
from PIL import Image, ImageOps

def pad_to_square(image):
    image = image.convert('RGB')
    gray = image.convert('L')
    bbox = ImageOps.invert(gray).getbbox()
    if bbox:
        image = image.crop(bbox)
    
    width, height = image.size
    max_dim = max(width, height)
    
    left = (max_dim - width) // 2
    right = max_dim - width - left
    top = (max_dim - height) // 2
    bottom = max_dim - height - top
    
    padded = ImageOps.expand(
        image, 
        border=(left, top, right, bottom), 
        fill=(255, 255, 255)
    )
    return padded

transform = transforms.Compose([
    transforms.Lambda(pad_to_square),
    transforms.Resize((224, 224)),
    transforms.Grayscale(num_output_channels=3),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])