from pathlib import Path
from PIL import Image


def carregar(caminho: Path) -> Image.Image:
    """Carrega uma imagem de disco e retorna um PIL.Image convertida para RGB.

    Lança FileNotFoundError se o caminho não existir.
    """
    caminho = Path(caminho)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")
    img = Image.open(caminho)
    return img.convert("RGB")
