from dataclasses import dataclass
from typing import List

import numpy as np
from PIL import Image

LIMITE_BLOCOS = 10_000  # teto de segurança contra explosão do O(n²) em imagens grandes


@dataclass
class ParClonado:
    posicao_a: tuple  # (y, x) do canto superior esquerdo do bloco A
    posicao_b: tuple  # (y, x) do canto superior esquerdo do bloco B
    correlacao: float


def analisar(
    imagem: Image.Image,
    tamanho_bloco: int = 16,
    limiar: float = 0.995,
) -> List[ParClonado]:
    if tamanho_bloco < 8:
        raise ValueError(f"tamanho_bloco deve ser >= 8, recebido: {tamanho_bloco}")
    if not (0 < limiar <= 1):
        raise ValueError(f"limiar deve estar entre 0 e 1, recebido: {limiar}")

    img = np.array(imagem.convert("L"), dtype=float)
    h, w = img.shape
    passo = tamanho_bloco // 2          # sobreposição de 50% entre blocos consecutivos
    zona_exclusao = tamanho_bloco * 2   # distância mínima para ignorar blocos vizinhos

    blocos: list[tuple] = []
    for y in range(0, h - tamanho_bloco, passo):
        for x in range(0, w - tamanho_bloco, passo):
            vetor = img[y:y + tamanho_bloco, x:x + tamanho_bloco].flatten()
            if np.std(vetor) < 1e-6:  # descarta blocos uniformes (fundo branco, linhas)
                continue
            blocos.append((y, x, vetor))

    if len(blocos) > LIMITE_BLOCOS:
        raise ValueError(
            f"Imagem gerou {len(blocos)} blocos (limite: {LIMITE_BLOCOS}). "
            f"Aumente tamanho_bloco ou reduza a resolução da imagem."
        )

    pares: List[ParClonado] = []
    for i in range(len(blocos)):
        for j in range(i + 1, len(blocos)):
            y1, x1, v1 = blocos[i]
            y2, x2, v2 = blocos[j]

            if abs(y1 - y2) < zona_exclusao and abs(x1 - x2) < zona_exclusao:
                continue  # vizinhos sobrepostos — similaridade geométrica, não cópia

            correlacao = np.corrcoef(v1, v2)[0, 1]  # correlação de Pearson entre os dois blocos
            if np.isnan(correlacao):  # edge case: vetor com desvio efetivamente zero
                continue
            if correlacao > limiar:
                pares.append(ParClonado((y1, x1), (y2, x2), float(correlacao)))

    return pares
