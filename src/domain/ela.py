import io
import numpy as np
from PIL import Image


def analisar(imagem: Image.Image, qualidade: int = 90, amplificacao: int = 15) -> Image.Image:
    original = imagem.convert("RGB")

    buffer = io.BytesIO()
    original.save(buffer, "JPEG", quality=qualidade)
    buffer.seek(0)
    recomprimida = Image.open(buffer).convert("RGB")

    # int16 evita underflow: uint8 - uint8 negativo vira 255 silenciosamente.
    diff = np.abs(
        np.array(original, dtype=np.int16) -
        np.array(recomprimida, dtype=np.int16)
    )
    
    mapa = (diff * amplificacao).clip(0, 255).astype(np.uint8)
    return Image.fromarray(mapa)
