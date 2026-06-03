import json
import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from src.application.pipeline import ConfiguracaoPipeline, executar
from src.infrastructure import result_writer

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB

app = FastAPI(title="Detector de Documentos Falsificados")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analisar")
async def analisar(
    arquivo: UploadFile = File(...),
    executar_ela: bool = Form(True),
    executar_noise: bool = Form(True),
    executar_clone: bool = Form(True),
    ela_qualidade: int = Form(90),
    ela_amplificacao: float = Form(15.0),
    noise_sigma: float = Form(2.0),
    noise_tamanho_bloco: int = Form(64),
    clone_tamanho_bloco: int = Form(16),
    clone_limiar: float = Form(0.995),
):
    if not arquivo.filename:
        raise HTTPException(status_code=400, detail="Nome de arquivo ausente no upload")

    sufixo = Path(arquivo.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=sufixo) as tmp:
        bytes_lidos = 0
        while chunk := await arquivo.read(1024 * 1024):  # streaming em chunks de 1 MB
            bytes_lidos += len(chunk)
            if bytes_lidos > MAX_UPLOAD_BYTES:
                tmp.close()
                Path(tmp.name).unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f"Arquivo excede {MAX_UPLOAD_BYTES} bytes")
            tmp.write(chunk)
        tmp_path = Path(tmp.name)

    try:
        config = ConfiguracaoPipeline(
            executar_ela=executar_ela,
            executar_noise=executar_noise,
            executar_clone=executar_clone,
            ela_qualidade=ela_qualidade,
            ela_amplificacao=ela_amplificacao,
            noise_sigma=noise_sigma,
            noise_tamanho_bloco=noise_tamanho_bloco,
            clone_tamanho_bloco=clone_tamanho_bloco,
            clone_limiar=clone_limiar,
        )
        resultado = executar(tmp_path, config=config)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))  # erros de validação/entrada → 400
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {e}")
    finally:
        tmp_path.unlink(missing_ok=True)  # remove arquivo temporário independente de erro

    return {
        "id": resultado.id,
        "arquivo_original": resultado.arquivo_original,
        "tem_suspeitas": resultado.tem_suspeitas,
        "metodos_executados": resultado.metodos_executados,
        "clone_total_pares": len(resultado.clone_pares) if resultado.clone_pares is not None else None,
        "clone_tamanho_bloco_solicitado": clone_tamanho_bloco if resultado.clone_pares is not None else None,
        "clone_tamanho_bloco_efetivo": resultado.clone_tamanho_bloco_efetivo,
        "mapas": {
            "ela":   f"/resultado/{resultado.id}/mapa/ela"   if resultado.ela_mapa   is not None else None,
            "noise": f"/resultado/{resultado.id}/mapa/noise" if resultado.noise_mapa is not None else None,
        },
    }


@app.get("/resultado/{analise_id}")
def obter_resultado(analise_id: str):
    _validar_id(analise_id)
    caminho = result_writer.RESULTS_DIR / analise_id / "resultado.json"
    if not caminho.exists():
        raise HTTPException(status_code=404, detail="Análise não encontrada")
    return JSONResponse(content=json.loads(caminho.read_text(encoding="utf-8")))


@app.get("/resultado/{analise_id}/mapa/{tipo}")
def obter_mapa(analise_id: str, tipo: str):
    _validar_id(analise_id)
    arquivos = {
        "ela":   "ela_mapa.png",
        "noise": "noise_mapa.png",
    }
    if tipo not in arquivos:
        raise HTTPException(status_code=400, detail=f"Tipo inválido. Use: {list(arquivos)}")

    caminho = result_writer.RESULTS_DIR / analise_id / arquivos[tipo]
    if not caminho.exists():
        raise HTTPException(status_code=404, detail="Mapa não encontrado para esta análise")

    return FileResponse(caminho, media_type="image/png")


def _validar_id(analise_id: str) -> None:
    try:
        uuid.UUID(analise_id)  # bloqueia path traversal e qualquer string que não seja UUID válido
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de análise inválido")
