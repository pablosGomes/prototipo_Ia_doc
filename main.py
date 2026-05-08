from dotenv import load_dotenv

load_dotenv()  # carrega .env antes de qualquer import que dependa de variáveis de ambiente

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run("src.presentation.api:app", host="0.0.0.0", port=8000, reload=True)
