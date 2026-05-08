# Documentação Técnica — Detecção de Documentos Falsificados

**Projeto:** Pré-Iniciação Científica 2026  
**Área:** Forense digital de imagens  
**Objetivo:** Detectar falsificações em documentos (RG, CPF) por análise pixel a pixel

---

## O que o projeto faz

O sistema recebe a foto de um documento e passa por um pipeline de três métodos de análise forense independentes. Cada método detecta um tipo diferente de falsificação. Juntos, eles cobrem os principais vetores de ataque:

| Tipo de falsificação | ELA | Noise | Clone |
|---|---|---|---|
| Colagem externa — Photoshop, GIMP | Detecta | Detecta | — |
| Edição limpa exportada pelo Canva ou IA | Pode falhar | Detecta | — |
| Dígito ou região copiada do próprio documento | Pode falhar | Pode falhar | Detecta |

O resultado de cada análise é salvo em disco (mapas PNG + JSON) e retornado para a API, que serve o frontend React para visualização.

---

## Arquitetura — Layered Architecture

O projeto segue arquitetura em camadas, onde cada camada só conhece a camada imediatamente abaixo dela. Isso garante que a lógica forense não dependa de detalhes de I/O, e que a API não dependa de como os algoritmos funcionam internamente.

```
┌─────────────────────────────────────┐
│         presentation/               │  API FastAPI — recebe requisições HTTP
├─────────────────────────────────────┤
│         application/                │  Pipeline — orquestra os 3 métodos
├─────────────────────────────────────┤
│           domain/                   │  ELA, Noise, Clone — lógica pura
├─────────────────────────────────────┤
│        infrastructure/              │  Carregamento e escrita em disco
└─────────────────────────────────────┘
```

### Por que essa separação importa

- **domain** não sabe que existe disco, API ou React. Recebe `PIL.Image`, devolve resultado.
- **infrastructure** não sabe que existe pipeline ou API. Só carrega e salva arquivos.
- **application** não sabe que existe HTTP. Só coordena domain e infrastructure.
- **presentation** não sabe como os algoritmos funcionam. Só traduz HTTP ↔ pipeline.

Isso permite testar cada camada isoladamente e trocar qualquer uma sem afetar as outras (ex: substituir FastAPI por CLI sem tocar nos algoritmos).

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
│   ├── infrastructure/          # I/O — disco, imagens, arquivos
│   │   ├── image_loader.py      # Carrega imagem do disco → PIL.Image
│   │   └── result_writer.py     # Salva mapas e JSON em data/results/
│   │
│   ├── application/             # Orquestração
│   │   └── pipeline.py          # Coordena domain + infrastructure
│   │
│   └── presentation/            # Interface HTTP
│       └── api.py               # FastAPI — endpoints REST
│
├── tests/
│   ├── unit/domain/             # Testes isolados por método forense
│   └── integration/             # Testes do pipeline completo
│
├── data/
│   ├── samples/                 # Imagens de documento para teste
│   └── results/                 # Saída das análises (gerado automaticamente)
│       └── {uuid}/
│           ├── ela_mapa.png
│           ├── noise_mapa.png
│           ├── clone_pares.json
│           └── resultado.json
│
├── frontend/                    # Interface React (Vite)
├── docs/                        # Esta documentação
└── requirements.txt
```

---

## Camada Domain — `src/domain/`

Contém os três algoritmos forenses. Cada arquivo expõe uma função pública `analisar()` que recebe uma `PIL.Image` e retorna o resultado do método. Nenhum arquivo desta camada faz I/O de disco ou rede.

---

### `ela.py` — Error Level Analysis

**O que faz:** Detecta regiões da imagem que foram editadas em software externo (Photoshop, GIMP) e salvas com nível de compressão JPEG diferente do restante.

**Como funciona:**

Imagens JPEG são comprimidas em blocos de 8×8 pixels. Quando a imagem é salva pela primeira vez, todos os blocos ficam com o mesmo nível de erro de compressão. Quando alguém edita uma região — cola uma foto de rosto, altera um número — e salva novamente, aquela região passa por uma compressão adicional e fica com nível de erro diferente.

O ELA recomprime a imagem com qualidade conhecida (padrão: 90%) e subtrai pixel a pixel do original. Regiões íntegras têm diferença pequena e uniforme (escura no mapa). Regiões editadas têm diferença alta (clara no mapa).

**Função: `analisar(imagem, qualidade=90, amplificacao=15)`**

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `imagem` | `PIL.Image` | Imagem já carregada pela infrastructure |
| `qualidade` | `int` | Nível de recompressão JPEG (0–100). Padrão 90 é sensível sem gerar ruído excessivo |
| `amplificacao` | `int` | Fator multiplicador da diferença. Necessário pois as diferenças são imperceptíveis sem amplificação |

**Retorno:** `PIL.Image` RGB — pixels mais claros = maior suspeita de edição.

**Detalhe técnico:** A subtração usa `np.int16` em vez de `uint8` para evitar underflow silencioso: `10 - 20` em `uint8` retorna `246` em vez de `-10`.

**Limitações:**
- Perde eficácia em imagens PNG (sem compressão lossy, não há diferença de compressão para medir)
- Pode ser enganado se o falsificador recomprimir a imagem várias vezes após a edição, homogeneizando os níveis de erro

---

### `noise.py` — Análise de Inconsistência de Ruído

**O que faz:** Detecta regiões que vieram de uma fonte diferente — outra câmera, exportação digital do Canva, ou geração por IA.

**Como funciona:**

Toda câmera introduz um padrão de ruído microscópico nos pixels, causado pelas imperfeições do sensor. Esse ruído é consistente em toda a foto tirada pela mesma câmera. Quando alguém insere uma região de outra fonte, o padrão de ruído daquela região é diferente — ou ausente, no caso de imagens geradas digitalmente.

O método separa o ruído do conteúdo visual aplicando um filtro gaussiano (que suaviza bordas e texturas mas preserva o ruído de sensor), depois subtrai a versão suavizada da original. O que sobra é o ruído. A imagem é dividida em blocos e o desvio padrão do ruído é medido em cada um. Blocos com desvio muito diferente dos vizinhos indicam origem distinta.

**Funções:**

`_extrair_ruido(img_cinza, sigma)` *(privada)*

Separa o ruído do sensor do conteúdo visual via filtro gaussiano. O `sigma` controla o raio de suavização — muito baixo deixa resíduos de textura; muito alto apaga o próprio ruído. Valor padrão `2.0` é o equilíbrio empírico para documentos digitalizados.

`analisar(imagem, sigma=2.0, tamanho_bloco=64)`

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `imagem` | `PIL.Image` | Imagem já carregada |
| `sigma` | `float` | Raio do filtro gaussiano para separar ruído do conteúdo visual |
| `tamanho_bloco` | `int` | Tamanho em pixels de cada região analisada. Menor = mais localizado; maior = mais robusto |

**Retorno:** `np.ndarray` 2D float — cada pixel contém o desvio padrão do bloco ao qual pertence. Regiões com valor muito acima da média global são suspeitas.

**Limitações:**
- Fotos em modo noturno, HDR ou com redução de ruído automática do celular já têm o ruído suprimido pelo dispositivo, gerando falsos positivos
- Menos eficaz em imagens de baixa resolução

---

### `clone.py` — Clone Detection (Copy-move)

**O que faz:** Detecta regiões copiadas e coladas de dentro da própria imagem — o ponto cego dos outros dois métodos.

**Como funciona:**

Quando alguém copia um dígito do próprio documento e cola em outro lugar, ELA e Noise não detectam: o material veio da mesma imagem, então compressão e ruído são idênticos. O método divide a imagem em blocos sobrepostos (passo de 50% do tamanho do bloco) e calcula o coeficiente de correlação de Pearson entre todos os pares de blocos. Alta correlação entre blocos distantes indica cópia.

**Classe: `ParClonado`**

```python
@dataclass
class ParClonado:
    posicao_a: tuple   # (y, x) do bloco A
    posicao_b: tuple   # (y, x) do bloco B
    correlacao: float  # coeficiente de Pearson entre os dois blocos
```

**Função: `analisar(imagem, tamanho_bloco=16, limiar=0.995)`**

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `imagem` | `PIL.Image` | Imagem já carregada |
| `tamanho_bloco` | `int` | Tamanho dos blocos. 16px captura dígitos; 32–64px captura regiões maiores |
| `limiar` | `float` | Correlação mínima para considerar dois blocos como cópias (0.995 = conservador) |

**Retorno:** `List[ParClonado]` — lista de pares suspeitos com coordenadas e correlação.

**Otimizações implementadas:**
- Blocos com `std < 1e-6` (fundo branco, linhas uniformes) são descartados antes da comparação — reduz falsos positivos e custo computacional
- Blocos vizinhos (dentro de `2 × tamanho_bloco`) são ignorados — sua similaridade é geométrica (overlap natural), não indica cópia

**Limitações:**
- Complexidade O(n²) no número de blocos — imagens grandes são lentas
- Documentos com muito fundo uniforme ainda podem gerar alguns falsos positivos mesmo com o filtro

---

## Camada Infrastructure — `src/infrastructure/`

Responsável por toda interação com o disco. As camadas superiores (domain, application) nunca tocam em caminhos de arquivo diretamente.

---

### `image_loader.py`

**O que faz:** Carrega uma imagem do disco com validação completa antes de retornar.

**Função: `carregar(caminho)`**

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `caminho` | `str` ou `Path` | Caminho para o arquivo de imagem |

**Retorno:** `PIL.Image` com dados completamente carregados em memória.

**Erros levantados:**

| Erro | Quando ocorre |
|---|---|
| `FileNotFoundError` | Arquivo não existe no caminho informado |
| `FormatoNaoSuportadoError` | Extensão não está em `FORMATOS_SUPORTADOS` |
| `ImagemInvalidaError` | Arquivo existe mas não é uma imagem válida (corrompido, renomeado) |

**Formatos aceitos:** `.jpg`, `.jpeg`, `.png`, `.bmp`, `.tiff`, `.webp`

**Detalhe técnico:** `imagem.load()` é chamado explicitamente para forçar a leitura completa ainda dentro do bloco `try`. O PIL usa leitura lazy por padrão — sem isso, erros de arquivo corrompido só apareceriam depois, fora da infrastructure, em lugares difíceis de rastrear.

---

### `result_writer.py`

**O que faz:** Persiste todos os artefatos de uma análise em um diretório identificado por UUID.

**Estrutura gerada em disco:**
```
data/results/{uuid}/
├── ela_mapa.png       # Mapa ELA como imagem RGB
├── noise_mapa.png     # Mapa de ruído normalizado para visualização
├── clone_pares.json   # Lista de pares clonados com coordenadas e correlação
└── resultado.json     # Metadata da análise: timestamp, métodos, resumo
```

**Classe: `ResultadoSalvo`**

```python
@dataclass
class ResultadoSalvo:
    id: str             # UUID gerado para esta análise
    diretorio: Path     # Caminho do diretório criado
    ela: Path | None    # Caminho do ela_mapa.png, ou None se ELA não foi executado
    noise: Path | None  # Caminho do noise_mapa.png, ou None se Noise não foi executado
    clone: Path | None  # Caminho do clone_pares.json, ou None se Clone não foi executado
    metadata: Path      # Caminho do resultado.json (sempre presente)
```

**Função principal: `salvar(...)`**

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `nome_arquivo_original` | `str` | Nome do arquivo enviado (para metadata) |
| `ela_mapa` | `PIL.Image` ou `None` | Mapa ELA gerado pelo domain |
| `noise_mapa` | `np.ndarray` ou `None` | Mapa de ruído gerado pelo domain |
| `clone_pares` | `list[ParClonado]` ou `None` | Pares clonados gerados pelo domain |
| `diretorio_base` | `Path` | Base para criação do diretório (configurável para testes) |

**Funções privadas:**

- `_salvar_ela()` — salva PIL.Image diretamente como PNG
- `_salvar_noise()` — normaliza o array float para [0, 255] antes de salvar (necessário pois o mapa contém desvios padrão, não valores de pixel). Trata o caso degenerado onde toda a imagem é uniforme (divisão por zero)
- `_salvar_clone()` — converte tuples para lists (JSON não suporta tuple nativamente) e arredonda correlação em 6 casas decimais
- `_salvar_metadata()` — gera `resultado.json` com timestamp UTC ISO 8601, lista de métodos executados e resumo legível

---

## Camada Application — `src/application/`

Coordena as camadas domain e infrastructure. Não contém lógica forense e não faz I/O diretamente.

---

### `pipeline.py`

**O que faz:** Recebe o caminho de uma imagem e uma configuração, executa os métodos selecionados e retorna o resultado consolidado com referência ao que foi salvo em disco.

**Classe: `ConfiguracaoPipeline`**

Agrupa todos os parâmetros ajustáveis do pipeline em um único objeto. A API e o frontend enviam esses valores com base nas escolhas do usuário.

```python
@dataclass
class ConfiguracaoPipeline:
    executar_ela: bool = True        # Habilita/desabilita ELA
    executar_noise: bool = True      # Habilita/desabilita Noise
    executar_clone: bool = True      # Habilita/desabilita Clone

    ela_qualidade: int = 90          # Qualidade de recompressão JPEG (0–100)
    ela_amplificacao: int = 15       # Fator de amplificação visual do mapa ELA

    noise_sigma: float = 2.0         # Raio do filtro gaussiano
    noise_tamanho_bloco: int = 64    # Tamanho dos blocos de análise de ruído

    clone_tamanho_bloco: int = 16    # Tamanho dos blocos para comparação
    clone_limiar: float = 0.995      # Correlação mínima para considerar clone
```

**Classe: `ResultadoAnalise`**

Retornado pelo pipeline, contém os resultados em memória e referência ao que foi salvo em disco.

```python
@dataclass
class ResultadoAnalise:
    id: str                          # UUID da análise (mesmo do ResultadoSalvo)
    arquivo_original: str            # Nome do arquivo analisado
    ela_mapa: PIL.Image | None       # Mapa ELA em memória
    noise_mapa: np.ndarray | None    # Mapa de ruído em memória
    clone_pares: list[ParClonado] | None  # Pares suspeitos em memória
    salvo: ResultadoSalvo            # Referência aos arquivos salvos em disco
```

**Propriedades calculadas:**

- `.tem_suspeitas` — `True` se qualquer método sinalizou anomalia. ELA usa brilho médio > 25; Noise usa desvio > 2σ acima da média; Clone usa lista não-vazia
- `.metodos_executados` — lista dos métodos que foram de fato executados (`["ela", "noise", "clone"]` ou subconjunto)

**Função principal: `executar(caminho_imagem, config=None, diretorio_resultados=...)`**

Fluxo interno:
1. Carrega imagem via `image_loader.carregar()`
2. Executa cada método habilitado em `config` passando a `PIL.Image`
3. Salva resultados via `result_writer.salvar()`
4. Retorna `ResultadoAnalise` com tudo consolidado

O parâmetro `config=None` com instanciação interna é o padrão pythônico para evitar objeto mutável como argumento default de função — objetos mutáveis como default são compartilhados entre todas as chamadas e causam bugs sutis.

---

## Como instalar e rodar

### Instalar dependências Python

```bash
pip install -r requirements.txt
```

### Dependências completas

```
Pillow        — manipulação de imagens (abrir, converter, salvar)
numpy         — operações matriciais pixel a pixel
scipy         — filtro gaussiano para análise de ruído
scikit-image  — análise de textura e métricas de similaridade
opencv-python — processamento de imagem e extração de blocos
matplotlib    — visualização de mapas (usada em scripts auxiliares)
imagehash     — hashing perceptual para comparação rápida de blocos
```

### Executar análise via Python (uso direto do pipeline)

```python
from src.application.pipeline import executar, ConfiguracaoPipeline

config = ConfiguracaoPipeline(
    executar_ela=True,
    executar_noise=True,
    executar_clone=False,  # desabilitado por ser mais lento
)

resultado = executar("data/samples/documento.jpg", config=config)

print(f"ID da análise: {resultado.id}")
print(f"Suspeitas detectadas: {resultado.tem_suspeitas}")
print(f"Métodos executados: {resultado.metodos_executados}")
print(f"Resultado salvo em: {resultado.salvo.diretorio}")
```

---

## Próximos passos

| Etapa | O que será feito |
|---|---|
| `presentation/api.py` | API FastAPI com `POST /analisar` e `GET /resultado/{id}` |
| `tests/unit/domain/` | Testes unitários isolados para ELA, Noise e Clone |
| `tests/integration/` | Teste do pipeline completo com imagens reais |
| `frontend/` | Interface React com Vite — upload, seleção de métodos, visualização dos mapas |
