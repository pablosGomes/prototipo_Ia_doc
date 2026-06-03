import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image
import numpy as np

# Diretório base para resultados (usa a pasta data/results no cwd)
RESULTS_DIR: Path = Path.cwd() / "data" / "results"


@dataclass
class ResultadoSalvo:
    id: str
    path: Path


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def salvar(
    nome_arquivo_original: str,
    ela_mapa: Optional[Image.Image],
    noise_mapa: Optional[np.ndarray],
    clone_pares: Optional[list],
    diretorio_base: Path = RESULTS_DIR,
) -> ResultadoSalvo:
    """Salva os artefatos de análise em um diretório identificado por UUID e retorna metadados."""
    id_str = str(uuid.uuid4())
    dir_path = Path(diretorio_base) / id_str
    _ensure_dir(dir_path)

    arquivos = {}
    # Salva mapa ELA
    if ela_mapa is not None:
        ela_path = dir_path / "ela_mapa.png"
        ela_mapa.save(ela_path, format="PNG")
        arquivos["ela_mapa"] = ela_path.name

    # Salva mapa de noise (numpy array -> imagem)
    if noise_mapa is not None:
        arr = noise_mapa
        # Normaliza para 0-255
        try:
            if arr.dtype != np.uint8:
                vmin = float(arr.min())
                vmax = float(arr.max())
                if vmax == vmin:
                    scaled = np.zeros_like(arr, dtype=np.uint8)
                else:
                    scaled = ((arr - vmin) / (vmax - vmin) * 255).astype(np.uint8)
            else:
                scaled = arr
        except Exception:
            # Em caso de formato inesperado, tenta converter diretamente
            scaled = (arr * 255).astype(np.uint8)

        # Se o array for 2D, cria imagem em escala de cinza; se 3D, assume RGB
        if scaled.ndim == 2:
            im = Image.fromarray(scaled)
        else:
            im = Image.fromarray(scaled)

        noise_path = dir_path / "noise_mapa.png"
        im.save(noise_path, format="PNG")
        arquivos["noise_mapa"] = noise_path.name

    # Salva pares de clone como JSON
    if clone_pares is not None:
        clone_path = dir_path / "clone_pares.json"
        clone_path.write_text(json.dumps(clone_pares, default=str, ensure_ascii=False), encoding="utf-8")
        arquivos["clone_pares"] = clone_path.name

    resultado = {
        "id": id_str,
        "arquivo_original": nome_arquivo_original,
        "arquivos": arquivos,
    }

    resultado_path = dir_path / "resultado.json"
    resultado_path.write_text(json.dumps(resultado, ensure_ascii=False), encoding="utf-8")

    return ResultadoSalvo(id=id_str, path=dir_path)
