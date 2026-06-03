from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from src.domain import clone, ela, noise
from src.domain.clone import ParClonado
from src.infrastructure import image_loader, result_writer
from src.infrastructure.result_writer import ResultadoSalvo


@dataclass
class ConfiguracaoPipeline:
    executar_ela: bool = True
    executar_noise: bool = True
    executar_clone: bool = True

    ela_qualidade: int = 90
    ela_amplificacao: float = 15.0

    noise_sigma: float = 2.0
    noise_tamanho_bloco: int = 64

    clone_tamanho_bloco: int = 16
    clone_limiar: float = 0.995

    # Heurísticas de suspeita — calibradas empiricamente, configuráveis para experimentação
    suspeita_ela_limiar_brilho: float = 25.0
    suspeita_noise_fator_desvio: float = 2.0


@dataclass
class ResultadoAnalise:
    id: str
    arquivo_original: str
    ela_mapa: Optional[Image.Image]
    noise_mapa: Optional[np.ndarray]
    clone_pares: Optional[list[ParClonado]]
    clone_tamanho_bloco_efetivo: Optional[int]
    salvo: ResultadoSalvo
    config: ConfiguracaoPipeline

    @property
    def tem_suspeitas(self) -> bool:
        ela_suspeito = self.ela_mapa is not None and _mapa_ela_tem_anomalia(
            self.ela_mapa, self.config.suspeita_ela_limiar_brilho
        )
        noise_suspeito = self.noise_mapa is not None and _mapa_noise_tem_anomalia(
            self.noise_mapa, self.config.suspeita_noise_fator_desvio
        )
        clone_suspeito = bool(self.clone_pares)
        return ela_suspeito or noise_suspeito or clone_suspeito

    @property
    def metodos_executados(self) -> list[str]:
        executados = []
        if self.ela_mapa is not None:
            executados.append("ela")
        if self.noise_mapa is not None:
            executados.append("noise")
        if self.clone_pares is not None:
            executados.append("clone")
        return executados


def executar(
    caminho_imagem: str | Path,
    config: Optional[ConfiguracaoPipeline] = None,
    diretorio_resultados: Path = result_writer.RESULTS_DIR,
) -> ResultadoAnalise:
    if config is None:
        config = ConfiguracaoPipeline()  # evita objeto mutável como default de função

    if not (config.executar_ela or config.executar_noise or config.executar_clone):
        raise ValueError("Pelo menos um método de análise deve estar habilitado")

    caminho_imagem = Path(caminho_imagem)
    imagem = image_loader.carregar(caminho_imagem)

    ela_mapa = (
        ela.analisar(imagem, qualidade=config.ela_qualidade, amplificacao=config.ela_amplificacao)
        if config.executar_ela
        else None
    )

    noise_mapa = (
        noise.analisar(imagem, sigma=config.noise_sigma, tamanho_bloco=config.noise_tamanho_bloco)
        if config.executar_noise
        else None
    )

    clone_tamanho_bloco_efetivo = (
        clone.tamanho_bloco_efetivo(
            largura=imagem.width,
            altura=imagem.height,
            tamanho_bloco=config.clone_tamanho_bloco,
        )
        if config.executar_clone
        else None
    )

    clone_pares = (
        clone.analisar(imagem, tamanho_bloco=clone_tamanho_bloco_efetivo, limiar=config.clone_limiar)
        if clone_tamanho_bloco_efetivo is not None
        else None
    )

    salvo = result_writer.salvar(
        nome_arquivo_original=caminho_imagem.name,
        ela_mapa=ela_mapa,
        noise_mapa=noise_mapa,
        clone_pares=clone_pares,
        diretorio_base=diretorio_resultados,
    )

    return ResultadoAnalise(
        id=salvo.id,
        arquivo_original=caminho_imagem.name,
        ela_mapa=ela_mapa,
        noise_mapa=noise_mapa,
        clone_pares=clone_pares,
        clone_tamanho_bloco_efetivo=clone_tamanho_bloco_efetivo,
        salvo=salvo,
        config=config,
    )


def _mapa_ela_tem_anomalia(mapa: Image.Image, limiar_brilho_medio: float) -> bool:
    arr = np.array(mapa, dtype=float)
    return float(arr.mean()) > limiar_brilho_medio  # brilho médio alto indica regiões com compressão diferente


def _mapa_noise_tem_anomalia(mapa: np.ndarray, fator_desvio: float) -> bool:
    media = mapa.mean()
    desvio = mapa.std()
    return bool((mapa > media + fator_desvio * desvio).any())  # algum bloco acima de Nσ da média global
