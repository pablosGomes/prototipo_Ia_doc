from typing import Optional

import numpy as np
from PIL import Image

from src.domain.clone import ParClonado
from src.infrastructure import llm_client


def explicar(
    arquivo_original: str,
    ela_mapa: Optional[Image.Image] = None,
    noise_mapa: Optional[np.ndarray] = None,
    clone_pares: Optional[list[ParClonado]] = None,
) -> str:
    prompt = _montar_prompt(arquivo_original, ela_mapa, noise_mapa, clone_pares)
    return llm_client.gerar_texto(prompt)


def _montar_prompt(
    arquivo: str,
    ela_mapa: Optional[Image.Image],
    noise_mapa: Optional[np.ndarray],
    clone_pares: Optional[list[ParClonado]],
) -> str:
    secoes = [
        _secao_ela(ela_mapa),
        _secao_noise(noise_mapa),
        _secao_clone(clone_pares),
    ]
    relatorio = "\n\n".join(secoes)

    return f"""Você é um especialista em análise forense de imagens digitais, com foco em detecção \
de fraudes em documentos brasileiros (RG, CPF, CNH).

Analisei o documento "{arquivo}" pixel a pixel usando três métodos forenses independentes. \
Os resultados numéricos da análise estão abaixo:

{relatorio}

---

Com base estritamente nesses dados, escreva uma análise forense detalhada em português brasileiro \
seguindo exatamente esta estrutura, usando títulos em negrito:

**1. Veredito**
Em uma frase: o documento apresenta indícios de falsificação? Responda "sim", "não" ou "inconclusivo".

**2. Evidências encontradas**
Liste cada anomalia detectada, citando o método que a encontrou e a intensidade do sinal numérico.

**3. Tipo provável de manipulação**
Com base nos sinais, qual técnica de falsificação foi provavelmente usada? (edição em Photoshop, \
exportação do Canva, geração por IA, cópia interna de dígitos, etc.)

**4. Nível de confiança**
Alto, médio ou baixo. Justifique citando os números.

**5. Recomendações ao analista humano**
O que um perito deve verificar visualmente na imagem para confirmar ou descartar a suspeita.

Seja técnico mas acessível. Não invente evidências que não estão nos dados acima."""


def _secao_ela(mapa: Optional[Image.Image]) -> str:
    if mapa is None:
        return "## ELA (Error Level Analysis)\nNão executado."

    arr = np.array(mapa, dtype=float)
    brilho_medio = float(arr.mean())
    brilho_maximo = float(arr.max())
    pct_brilho_alto = float((arr > 50).mean()) * 100  # pixels claramente suspeitos no mapa ELA

    return f"""## ELA (Error Level Analysis) — detecta edição por Photoshop/GIMP
- Brilho médio do mapa de erro: {brilho_medio:.2f} (escala 0–255)
- Brilho máximo: {brilho_maximo:.2f}
- Pixels com brilho > 50 (suspeitos de edição): {pct_brilho_alto:.2f}% da imagem
- Interpretação: regiões com brilho alto indicam blocos JPEG recomprimidos com qualidade diferente, \
sinal típico de edição externa."""


def _secao_noise(mapa: Optional[np.ndarray]) -> str:
    if mapa is None:
        return "## Noise Inconsistency\nNão executado."

    media = float(mapa.mean())
    desvio = float(mapa.std())
    maximo = float(mapa.max())
    limiar = media + 2 * desvio
    blocos_anomalos = int((mapa > limiar).sum())
    total_pixels = mapa.size

    return f"""## Noise Inconsistency — detecta Canva, IA generativa, câmera diferente
- Desvio padrão médio do ruído: {media:.4f}
- Desvio padrão máximo (bloco mais anômalo): {maximo:.4f}
- Limiar de suspeita (média + 2σ): {limiar:.4f}
- Pixels acima do limiar: {blocos_anomalos} de {total_pixels} ({blocos_anomalos / total_pixels * 100:.2f}%)
- Interpretação: blocos com desvio muito acima da média indicam origem diferente do restante \
(outra câmera, exportação digital sem ruído de sensor, ou imagem gerada por IA)."""


def _secao_clone(pares: Optional[list[ParClonado]]) -> str:
    if pares is None:
        return "## Clone Detection (Copy-move)\nNão executado."

    if not pares:
        return """## Clone Detection (Copy-move) — detecta cópia interna de regiões
- Pares clonados detectados: 0
- Interpretação: nenhum bloco da imagem foi identificado como cópia de outro bloco da mesma imagem."""

    correlacao_max = max(p.correlacao for p in pares)
    correlacao_media = sum(p.correlacao for p in pares) / len(pares)
    amostras = "; ".join(
        f"({p.posicao_a[0]},{p.posicao_a[1]})↔({p.posicao_b[0]},{p.posicao_b[1]}) corr={p.correlacao:.4f}"
        for p in pares[:5]  # mostra até 5 amostras para não inflar o prompt
    )

    return f"""## Clone Detection (Copy-move) — detecta cópia interna de regiões
- Pares clonados detectados: {len(pares)}
- Correlação máxima entre pares: {correlacao_max:.4f}
- Correlação média entre pares: {correlacao_media:.4f}
- Amostras de pares (até 5): {amostras}
- Interpretação: regiões com altíssima correlação em posições distantes indicam que um trecho \
foi copiado e colado dentro do próprio documento — típico de alteração de dígitos ou datas."""



