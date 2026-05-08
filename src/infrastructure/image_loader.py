from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

FORMATOS_SUPORTADOS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
MAX_PIXELS = 25_000_000  # ~5000x5000 — limite para evitar consumo abusivo de memória


class ImagemInvalidaError(Exception):
    pass


class FormatoNaoSuportadoError(Exception):
    pass


class ImagemMuitoGrandeError(Exception):
    pass


def carregar(caminho: str | Path) -> Image.Image:
    caminho = Path(caminho)

    if not caminho.is_file():  # rejeita diretórios e caminhos inexistentes
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

    if caminho.suffix.lower() not in FORMATOS_SUPORTADOS:
        raise FormatoNaoSuportadoError(
            f"Formato '{caminho.suffix}' não suportado. "
            f"Use: {', '.join(sorted(FORMATOS_SUPORTADOS))}"
        )

    try:
        imagem = Image.open(caminho)
        imagem.load()  # força leitura completa — PIL abre arquivos de forma lazy por padrão
    except UnidentifiedImageError:
        raise ImagemInvalidaError(f"O arquivo não é uma imagem válida: {caminho}")
    except OSError as e:
        raise ImagemInvalidaError(f"Erro ao ler arquivo {caminho}: {e}")

    if imagem.width * imagem.height > MAX_PIXELS:
        raise ImagemMuitoGrandeError(
            f"Imagem com {imagem.width}x{imagem.height} excede o limite de {MAX_PIXELS} pixels"
        )

    imagem = ImageOps.exif_transpose(imagem)  # aplica rotação EXIF para evitar análise em imagem girada
    return imagem
