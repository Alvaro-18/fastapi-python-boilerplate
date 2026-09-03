
import json
import urllib.error
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI()

origens_permitidas = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origens_permitidas,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MELHORA_URL = "https://melhora.madesa.com:8090/api/avalsite/insert"
MAX_FIELD_LENGTH = 2000
POS_COMPRA_REQUIRED = (
    "numero_pedido",
    "nota",
    "primeira_compra",
    "como_conheceu",
    "whatsapp",
    "dispositivo",
)


def sanitize(value) -> str:
    if value is None:
        return ""
    clean_value = str(value).strip()[:MAX_FIELD_LENGTH]
    if clean_value and clean_value[0] in "=+-@":
        return f"'{clean_value}"
    return clean_value


def format_registro_sao_paulo() -> str:
    now = datetime.now(ZoneInfo("America/Sao_Paulo"))
    return now.strftime("%d/%m/%Y - %H:%M")


def build_melhora_payload(fields: dict) -> dict:
    nota_raw = sanitize(fields.get("nota"))
    try:
        nota_numero = int(nota_raw) if nota_raw else None
    except ValueError:
        nota_numero = None

    nota_motivo = sanitize(fields.get("nota_motivo")) or None

    payload = {
        "numero_pedido": sanitize(fields.get("numero_pedido")) or None,
        "nota": nota_numero,
        "nota_motivo": nota_motivo,
        "comentario": nota_motivo,
        "origem": sanitize(fields.get("como_conheceu")) or None,
        "input_origem": sanitize(fields.get("input_origem")) or None,
        "registro": format_registro_sao_paulo(),
        "dispositivo": sanitize(fields.get("dispositivo")) or None,
        "primeira_compra": sanitize(fields.get("primeira_compra")) or None,
        "wpp_contact": sanitize(fields.get("whatsapp")) or None,
    }

    return {key: value for key, value in payload.items() if value is not None and value != ""}



@app.post("/debug-raw")
async def log_raw_no_console(request: Request):
    """
    Captura e imprime exatamente o que foi enviado no corpo da requisição,
    independentemente do formato (JSON, texto puro, form-data, etc.).
    """
    body_bytes = await request.body()
    body_text = body_bytes.decode("utf-8", errors="replace")

    print("\n" + "=" * 50)
    print("📥 [DEBUG RAW] REQUISIÇÃO RECEBIDA EM /debug-raw")
    print("-" * 50)
    print("CORPO DA REQUISIÇÃO:")
    print(body_text if body_text else "(Corpo vazio)")
    print("=" * 50 + "\n")

    return JSONResponse(
        status_code=200,
        content={
            "status": "sucesso",
            "mensagem": "Corpo da requisição recebido e registrado no console.",
            "tamanho_bytes": len(body_bytes),
        },
    )



@app.post("/route-proxy-v2")
def route_proxy(payload: dict):
    origem = sanitize(payload.get("origem"))
    if origem and origem != "pos-compra":
        return JSONResponse(
            status_code=400,
            content={"error": "Este proxy só encaminha avaliações pós-compra."},
        )

    missing = []
    for field in POS_COMPRA_REQUIRED:
        if not sanitize(payload.get(field)):
            missing.append(field)
    if sanitize(payload.get("como_conheceu")) == "outro" and not sanitize(payload.get("input_origem")):
        missing.append("input_origem")

    if missing:
        return JSONResponse(
            status_code=400,
            content={"error": f"Campos obrigatórios para pós-compra ausentes: {', '.join(missing)}"},
        )

    melhora_payload = build_melhora_payload(payload)
    corpo_requisicao = json.dumps(melhora_payload).encode("utf-8")

    req = urllib.request.Request(MELHORA_URL, data=corpo_requisicao, method="POST")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            status_code = response.getcode()
            response_text = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        status_code = error.code
        response_text = error.read().decode("utf-8")
        print(f"Falha no endpoint melhora: {status_code} {response_text}")
        return JSONResponse(
            status_code=502,
            content={"error": "Erro ao salvar dados. Tente novamente."},
        )
    except Exception as error:
        print(f"Falha ao enviar para endpoint melhora: {error}")
        return JSONResponse(
            status_code=500,
            content={"error": "Erro interno ao tentar contatar o servidor de destino."},
        )

    try:
        data = json.loads(response_text) if response_text else {}
    except json.JSONDecodeError:
        data = {}

    if status_code >= 400 or data.get("success") is False or data.get("error"):
        print(f"Falha no endpoint melhora: {status_code} {response_text}")
        return JSONResponse(
            status_code=502,
            content={"error": "Erro ao salvar dados. Tente novamente."},
        )

    return JSONResponse(
        status_code=200,
        content={"success": True, "message": "Formulário enviado com sucesso!"},
    )
