# Documentação Técnica — Detecção de Documentos Falsificados

**Projeto:** Pré-Iniciação Científica 2026
**Área:** Forense digital de imagens
**Objetivo:** Detectar falsificações em documentos (RG, CPF) por análise pixel a pixel + explicação com LLM

---

## O que o projeto faz

O sistema recebe a foto de um documento e passa por um pipeline de três métodos de análise forense pixel a pixel. Cada método detecta um tipo diferente de falsificação. Os resultados numéricos são enviados para uma LLM (Google Gemini) que gera uma explicação técnica em português detalhando indícios, tipo provável de manipulação e nível de confiança.

| Tipo de falsificação | ELA | Noise | Clone |
|---|---|---|---|
| Colagem externa — Photoshop, GIMP | Detecta | Detecta | — |
| Edição limpa exportada pelo Canva ou IA | Pode falhar | Detecta | — |
| Dígito ou região copiada do próprio documento | Pode falhar | Pode falhar | Detecta |

---

## Arquitetura — Layered Architecture

Cada camada só conhece a camada abaixo. Lógica forense não depende de I/O; API não depende dos algoritmos.

```
┌─────────────────────────────────────┐
│         presentation/               │  API FastAPI
├─────────────────────────────────────┤
│         application/                │  Pipeline + Explicador
├─────────────────────────────────────┤
│           domain/                   │  ELA, Noise, Clone
├─────────────────────────────────────┤
│        infrastructure/              │  Imagem, disco, LLM
└─────────────────────────────────────┘
```

---

## Estrutura de pastas

```
prototipo_Ia_doc/
│
├── src/
│   ├── domain/                  # Lógica forense pura — sem I/O
│   │   ├── ela.py               # Error Level Analysis
│   │   ├── noise.py             # Análise de inconsistência de ruído
│   │   └── clone.py             # Detecção de copy-move
│   │
│   ├── infrastructure/          # I/O — disco, imagens, LLM
│   │   ├── image_loader.py      # Carrega imagem do disco
│   │   ├── result_writer.py     # Salva mapas e JSON em data/results/
│   │   └── llm_client.py        # Cliente do Gemini
│   │
│   ├── application/             # Orquestração
│   │   ├── pipeline.py          # Coordena domain + infrastructure
│   │   └── explicador.py        # Gera prompt e chama a LLM
│   │
│   └── presentation/            # Interface HTTP
│       └── api.py               # FastAPI — endpoints REST
│
├── data/
│   └── results/                 # Saída das análises (gerada em runtime)
│       └── {uuid}/
│           ├── ela_mapa.png
│           ├── noise_mapa.png
│           ├── clone_pares.json
│           └── resultado.json
│
├── docs/                        # Esta documentação
├── main.py                      # Entry point — sobe o servidor
├── requirements.txt
├── .env.example                 # Template (você copia para .env)
└── .gitignore
```

---

## Como rodar o projeto

### Pré-requisitos

- **Python 3.10+** (verifique com `python --version`)
- **Chave da API do Gemini** — gere gratuitamente em https://aistudio.google.com/apikey

### 1. Instalar dependências

```bash
pip install -r requirements.txt
```

### 2. Configurar a chave da API

Copie o template e edite com sua chave:

```bash
copy .env.example .env
```

Abra o arquivo `.env` e substitua pelo valor da chave gerada:

```
GEMINI_API_KEY=AIza...sua_chave_aqui
```

> O `.gitignore` já protege esse arquivo de ir para o git. Nunca commite `.env`.

### 3. Subir o servidor

```bash
python main.py
```

O servidor sobe em `http://localhost:8000` com auto-reload ativado para desenvolvimento.

### 4. Testar a API

| Endpoint | Como testar |
|---|---|
| **Documentação interativa** | Abra `http://localhost:8000/docs` no navegador |
| **Health check** | `curl http://localhost:8000/health` |
| **Análise** | Use o `/docs` (Swagger UI) — clique em `POST /analisar` → "Try it out" → faça upload de uma imagem |

### 5. Estrutura de uma resposta

Após executar `POST /analisar`, você recebe:

```json
{
  "id": "uuid-da-analise",
  "arquivo_original": "documento.jpg",
  "tem_suspeitas": true,
  "metodos_executados": ["ela", "noise", "clone"],
  "clone_total_pares": 3,
  "mapas": {
    "ela": "/resultado/{id}/mapa/ela",
    "noise": "/resultado/{id}/mapa/noise"
  }
}
```

Cada análise gera um diretório próprio em `data/results/{uuid}/` com os PNGs e o `resultado.json` completo.

---

## Camada Domain — `src/domain/`

Lógica forense pura. Cada arquivo expõe uma função `analisar()` que recebe uma `PIL.Image` e retorna o resultado.

### `ela.py` — Error Level Analysis
Recomprime a imagem em qualidade conhecida e mede a diferença pixel a pixel. Regiões editadas externamente aparecem mais claras no mapa.

`analisar(imagem, qualidade=90, amplificacao=15.0) → PIL.Image`

### `noise.py` — Análise de Inconsistência de Ruído
Separa o ruído do conteúdo via filtro gaussiano e mede o desvio padrão por bloco. Regiões de outra origem (Canva, IA, outra câmera) têm padrão de ruído diferente.

`analisar(imagem, sigma=2.0, tamanho_bloco=64) → np.ndarray`

### `clone.py` — Clone Detection
Compara blocos da imagem entre si pela correlação de Pearson. Blocos altamente correlacionados em posições distantes indicam cópia interna.

`analisar(imagem, tamanho_bloco=16, limiar=0.995) → list[ParClonado]`

---

## Camada Infrastructure — `src/infrastructure/`

### `image_loader.py`
Carrega imagem do disco com validação completa: existência, formato, tamanho, integridade. Aplica orientação EXIF para evitar análise em imagem girada.

### `result_writer.py`
Persiste cada análise em `data/results/{uuid}/` contendo os mapas (PNG), os pares clonados (JSON) e o `resultado.json` consolidado.

### `llm_client.py`
Cliente do Gemini via SDK `google-genai`. Função única `gerar_texto(prompt)`.

---

## Camada Application — `src/application/`

### `pipeline.py`
Recebe `caminho_imagem` + `ConfiguracaoPipeline`, executa os métodos habilitados, salva resultados, retorna `ResultadoAnalise`.

### `explicador.py`
Recebe os resultados forenses, monta um prompt estruturado com métricas concretas e chama a LLM. Retorna texto em português com:
1. Veredito
2. Evidências encontradas
3. Tipo provável de manipulação
4. Nível de confiança
5. Recomendações ao analista humano

---

## Camada Presentation — `src/presentation/`

### `api.py`
FastAPI com 4 endpoints:

| Método | Rota | Função |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/analisar` | Upload de imagem + análise + LLM |
| GET | `/resultado/{id}` | Recupera o `resultado.json` |
| GET | `/resultado/{id}/mapa/{tipo}` | Serve o PNG do mapa (`ela` ou `noise`) |

CORS liberado para `http://localhost:5173` (Vite). Limite de upload: 20 MB. Validação de UUID para evitar path traversal.

---

"esta documentação foi gerada por IA"