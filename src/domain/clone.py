from dataclasses import dataclass
from typing import List

import numpy as np
from PIL import Image

LIMITE_BLOCOS = 10_000  # teto de seguranca contra explosao do O(n^2) em imagens grandes


@dataclass
class ParClonado:
    posicao_a: tuple  # (y, x) do canto superior esquerdo do bloco A
    posicao_b: tuple  # (y, x) do canto superior esquerdo do bloco B
    correlacao: float


def analisar(
    imagem: Image.Image,
    tamanho_bloco: int = 16,
    limiar: float = 0.995,
    limite_blocos: int = LIMITE_BLOCOS,
) -> List[ParClonado]:
    if tamanho_bloco < 8:
        raise ValueError(f"tamanho_bloco deve ser >= 8, recebido: {tamanho_bloco}")
    if not (0 < limiar <= 1):
        raise ValueError(f"limiar deve estar entre 0 e 1, recebido: {limiar}")
    if limite_blocos < 1:
        raise ValueError(f"limite_blocos deve ser >= 1, recebido: {limite_blocos}")

    img = np.array(imagem.convert("L"), dtype=float)
    h, w = img.shape
    tamanho_bloco = tamanho_bloco_efetivo(
        largura=w,
        altura=h,
        tamanho_bloco=tamanho_bloco,
        limite_blocos=limite_blocos,
    )
    passo = tamanho_bloco // 2          # sobreposicao de 50% entre blocos consecutivos
    zona_exclusao = tamanho_bloco * 2   # distancia minima para ignorar blocos vizinhos

    blocos: list[tuple] = []
    for y in range(0, h - tamanho_bloco, passo):
        for x in range(0, w - tamanho_bloco, passo):
            vetor = img[y:y + tamanho_bloco, x:x + tamanho_bloco].flatten()
            if np.std(vetor) < 1e-6:  # descarta blocos uniformes (fundo branco, linhas)
                continue
            blocos.append((y, x, vetor))

    if len(blocos) > limite_blocos:
        raise ValueError(
            f"Imagem gerou {len(blocos)} blocos (limite: {limite_blocos}). "
            f"Aumente tamanho_bloco ou reduza a resolucao da imagem."
        )

    pares: List[ParClonado] = []
    for i in range(len(blocos)):
        for j in range(i + 1, len(blocos)):
            y1, x1, v1 = blocos[i]
            y2, x2, v2 = blocos[j]

            if abs(y1 - y2) < zona_exclusao and abs(x1 - x2) < zona_exclusao:
                continue  # vizinhos sobrepostos: similaridade geometrica, nao copia

            correlacao = np.corrcoef(v1, v2)[0, 1]  # correlacao de Pearson entre os dois blocos
            if np.isnan(correlacao):  # edge case: vetor com desvio efetivamente zero
                continue
            if correlacao > limiar:
                pares.append(ParClonado((y1, x1), (y2, x2), float(correlacao)))

    return pares


def tamanho_bloco_efetivo(
    largura: int,
    altura: int,
    tamanho_bloco: int = 16,
    limite_blocos: int = LIMITE_BLOCOS,
) -> int:
    """Aumenta o bloco automaticamente para imagens grandes."""
    if tamanho_bloco < 8:
        raise ValueError(f"tamanho_bloco deve ser >= 8, recebido: {tamanho_bloco}")
    if limite_blocos < 1:
        raise ValueError(f"limite_blocos deve ser >= 1, recebido: {limite_blocos}")
    if largura <= tamanho_bloco or altura <= tamanho_bloco:
        return tamanho_bloco

    bloco = tamanho_bloco
    while _estimar_total_blocos(largura, altura, bloco) > limite_blocos:
        bloco += 2
    return bloco


def _estimar_total_blocos(largura: int, altura: int, tamanho_bloco: int) -> int:
    passo = max(1, tamanho_bloco // 2)
    total_y = len(range(0, altura - tamanho_bloco, passo))
    total_x = len(range(0, largura - tamanho_bloco, passo))
    return total_y * total_x
