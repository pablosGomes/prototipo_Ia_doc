import numpy as np
from scipy import ndimage
from PIL import Image


def _extrair_ruido(img_cinza: np.ndarray, sigma: float) -> np.ndarray:
    suavizada = ndimage.gaussian_filter(img_cinza, sigma=sigma)  # remove conteúdo visual preservando ruído de sensor
    return img_cinza - suavizada  # isola o ruído subtraindo o conteúdo suavizado


def analisar(imagem: Image.Image, sigma: float = 2.0, tamanho_bloco: int = 64) -> np.ndarray:
    if not (0 < sigma <= 10):
        raise ValueError(f"sigma deve estar entre 0 e 10, recebido: {sigma}")
    if tamanho_bloco < 8:
        raise ValueError(f"tamanho_bloco deve ser >= 8, recebido: {tamanho_bloco}")

    img = np.array(imagem.convert("L"), dtype=float)  # converte para escala de cinza
    ruido = _extrair_ruido(img, sigma)

    h, w = ruido.shape
    mapa = np.zeros((h, w), dtype=float)

    for y in range(0, h, tamanho_bloco):
        for x in range(0, w, tamanho_bloco):
            bloco = ruido[y:y + tamanho_bloco, x:x + tamanho_bloco]
            if bloco.shape != (tamanho_bloco, tamanho_bloco):  # pula blocos parciais nas bordas
                continue
            mapa[y:y + tamanho_bloco, x:x + tamanho_bloco] = np.std(bloco)  # desvio padrão do ruído no bloco

    return mapa
