# 🛠️ Auto Service

Ecossistema local que reúne **quatro ferramentas** sob um único **Hub web**, orquestrado por um único `docker-compose.yml`.

| # | Serviço | Ferramenta | Como foi conteinerizado | URL local |
|---|---------|-----------|--------------------------|-----------|
| — | **Hub** (portal central) | Nginx + HTML estático | Imagem oficial `nginx` | http://localhost:8080 |
| 1 | **Gerenciador de Arquivos** | ownCloud / oCIS | Imagem oficial `owncloud/ocis` | https://localhost:9200 |
| 2 | **Ferramentas de PDF** | Stirling-PDF | Imagem oficial `stirlingtools/stirling-pdf` | http://localhost:8081 |
| 3 | **Removedor de Fundo** | BackgroundRemover | 🔧 Wrapper **Flask** (build local) | http://localhost:8082 |
| 4 | **OCR** | PaddleOCR | 🔧 Wrapper **FastAPI** (build local) | http://localhost:8083 |

---

## 🧠 Decisão de arquitetura (Tree of Thoughts, resumo)

- **oCIS** e **Stirling-PDF** já publicam imagens Docker oficiais com GUI web → usadas diretamente.
- **BackgroundRemover** e **PaddleOCR** são CLI/biblioteca sem interface → foram encapsulados em **wrappers web leves** (upload → processa → resultado), construídos localmente.
- O **Hub** é apenas Nginx servindo um `index.html`; os botões apontam para `http://localhost:<porta>` do host — **sem proxy reverso**, o que evita quebrar as rotas internas dos apps oficiais.
- **Caminho escolhido:** imagens pré-construídas sempre que possível + wrappers mínimos. (Rejeitado: buildar tudo do zero — lento e de alta manutenção.)

---

## 🚀 Como executar

Pré-requisitos: **Docker Desktop** (ou Docker Engine + Compose v2).

```bash
# Na raiz do projeto (onde está o docker-compose.yml)
docker compose up -d --build
```

> ⚠️ O primeiro `up` **demora**: os wrappers baixam PyTorch/PaddlePaddle e, no primeiro uso de cada ferramenta, os modelos de IA (u2net / modelos PaddleOCR) são baixados e ficam em cache nos volumes.

Depois, abra o **Hub**: 👉 **http://localhost:8080**

### Parar / limpar

```bash
docker compose down            # para os containers
docker compose down -v         # para e apaga os volumes (dados/modelos)
docker compose logs -f ocis    # ver logs de um serviço
```

---

## 🔌 Portas

| Serviço | Host | Container |
|---|---|---|
| Hub | 8080 | 80 |
| Stirling-PDF | 8081 | 8080 |
| Background Remover | 8082 | 5000 |
| PaddleOCR | 8083 | 8000 |
| oCIS | 9200 | 9200 (HTTPS) |

As portas podem ser alteradas no arquivo **`.env`**.

---

## 🔑 Credenciais

- **oCIS** → usuário `admin` · senha `admin` (definida em `.env` → `OCIS_ADMIN_PASSWORD`).
  - Como usa certificado autoassinado, o navegador exibirá um aviso de segurança na primeira vez (aceite para prosseguir).
  - Usuários de demonstração habilitados (senha `demo`).

---

## 📁 Estrutura

```
.
├── docker-compose.yml          # Orquestra os 5 serviços
├── .env                        # Portas e configurações
├── hub/
│   ├── nginx.conf
│   └── html/
│       ├── index.html          # Portal central (cards/links)
│       └── styles.css
└── services/
    ├── background-remover/     # Wrapper Flask
    │   ├── Dockerfile
    │   ├── requirements.txt
    │   ├── app.py
    │   └── templates/index.html
    └── paddleocr/              # Wrapper FastAPI
        ├── Dockerfile
        ├── requirements.txt
        └── app.py
```

---

## 🧪 Endpoints úteis (API dos wrappers)

**Background Remover**
```bash
curl -X POST http://localhost:8082/remove \
     -F "image=@foto.jpg" --output resultado.png
```

**PaddleOCR**
```bash
curl -X POST http://localhost:8083/ocr \
     -F "file=@documento.png"
# -> JSON: { count, text, lines[] }
```

Healthchecks: `GET /healthz` em ambos os wrappers.

---

## 🛠️ Observações técnicas

- **PaddleOCR** carrega o modelo de forma *lazy* (no primeiro request), então o container sobe rápido; o primeiro OCR é mais lento.
- Idioma padrão do OCR é `pt` (mude em `.env` → `PADDLE_OCR_LANG`).
- Os wrappers rodam com **1 worker** (os modelos de IA são pesados em memória).
- Volumes persistem modelos e dados entre reinícios.
