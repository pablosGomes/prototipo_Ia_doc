import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from src.domain.clone import ParClonado

RESULTS_DIR = Path("data/results")


@dataclass
class ResultadoSalvo:
    id: str
    diretorio: Path
    ela: Optional[Path]
    noise: Optional[Path]
    clone: Optional[Path]
    metadata: Path


def salvar(
    nome_arquivo_original: str,
    ela_mapa: Optional[Image.Image] = None,
    noise_mapa: Optional[np.ndarray] = None,
    clone_pares: Optional[list[ParClonado]] = None,
    diretorio_base: Path = RESULTS_DIR,
) -> ResultadoSalvo:
    analise_id = str(uuid.uuid4())  # ID único para esta análise
    diretorio = diretorio_base / analise_id
    diretorio.mkdir(parents=True, exist_ok=False)  # falha em colisão de UUID em vez de sobrescrever

    caminho_ela = _salvar_ela(ela_mapa, diretorio)
    caminho_noise = _salvar_noise(noise_mapa, diretorio)
    caminho_clone = _salvar_clone(clone_pares, diretorio)
    caminho_metadata = _salvar_metadata(
        analise_id=analise_id,
        nome_arquivo_original=nome_arquivo_original,
        caminho_ela=caminho_ela,
        caminho_noise=caminho_noise,
        caminho_clone=caminho_clone,
        clone_pares=clone_pares,
        diretorio=diretorio,
    )

    return ResultadoSalvo(
        id=analise_id,
        diretorio=diretorio,
        ela=caminho_ela,
        noise=caminho_noise,
        clone=caminho_clone,
        metadata=caminho_metadata,
    )


def _salvar_ela(mapa: Optional[Image.Image], diretorio: Path) -> Optional[Path]:
    if mapa is None:
        return None
    caminho = diretorio / "ela_mapa.png"
    mapa.save(caminho)
    return caminho


def _salvar_noise(mapa: Optional[np.ndarray], diretorio: Path) -> Optional[Path]:
    if mapa is None:
        return None

    minv, maxv = mapa.min(), mapa.max()
    if maxv > minv:
        normalizado = ((mapa - minv) / (maxv - minv) * 255).astype(np.uint8)  # normaliza float → uint8 para salvar como PNG
    else:
        normalizado = np.zeros_like(mapa, dtype=np.uint8)  # imagem uniforme: evita divisão por zero na normalização

    caminho = diretorio / "noise_mapa.png"
    Image.fromarray(normalizado).save(caminho)
    return caminho


def _salvar_clone(
    pares: Optional[list[ParClonado]], diretorio: Path
) -> Optional[Path]:
    if pares is None:
        return None

    payload = [
        {
            "posicao_a": list(p.posicao_a),        # tuple → list: JSON não serializa tuple
            "posicao_b": list(p.posicao_b),
            "correlacao": round(p.correlacao, 6),   # limita precisão desnecessária do float64
        }
        for p in pares
    ]

    caminho = diretorio / "clone_pares.json"
    caminho.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return caminho


def _salvar_metadata(
    analise_id: str,
    nome_arquivo_original: str,
    caminho_ela: Optional[Path],
    caminho_noise: Optional[Path],
    caminho_clone: Optional[Path],
    clone_pares: Optional[list[ParClonado]],
    diretorio: Path,
) -> Path:
    metodos_executados = []
    if caminho_ela is not None:
        metodos_executados.append("ela")
    if caminho_noise is not None:
        metodos_executados.append("noise")
    if caminho_clone is not None:
        metodos_executados.append("clone")

    metadata = {
        "id": analise_id,
        "arquivo_original": nome_arquivo_original,
        "timestamp": datetime.now(timezone.utc).isoformat(),  # UTC em formato ISO 8601
        "metodos_executados": metodos_executados,
        "resumo": {
            "ela_executado": caminho_ela is not None,
            "noise_executado": caminho_noise is not None,
            "clone_executado": caminho_clone is not None,
            "clone_total_pares": len(clone_pares) if clone_pares is not None else None,
        },
        "arquivos": {
            "ela_mapa": caminho_ela.name if caminho_ela else None,         # apenas o basename: paths absolutos vazariam o filesystem do servidor
            "noise_mapa": caminho_noise.name if caminho_noise else None,
            "clone_pares": caminho_clone.name if caminho_clone else None,
        },
    }

    caminho = diretorio / "resultado.json"
    caminho.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return caminho
