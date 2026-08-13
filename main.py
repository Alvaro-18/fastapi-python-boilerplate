from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware # 1. Importe o middleware
from fastapi.responses import JSONResponse
import urllib.request
import urllib.error
import json

app = FastAPI()

# 2. Defina as origens (frontends) que podem acessar sua API
origens_permitidas = [
    "*" # Exemplo para React/Vue local
    # Adicione aqui o domínio do seu site em produção, ex: "https://meusite.com.br"
    # Você pode usar ["*"] para liberar tudo, mas não é recomendado em produção.
]

# 3. Adicione o middleware ao app
app.add_middleware(
    CORSMiddleware,
    allow_origins=origens_permitidas,
    allow_credentials=True,
    allow_methods=["*"], # Libera todos os métodos (POST, GET, OPTIONS, etc)
    allow_headers=["*"], # Libera todos os cabeçalhos
)


# Atenção: Usamos "def" em vez de "async def" porque o urllib é síncrono
@app.post("/route-proxy")
def route_proxy(payload: dict):
    url_destino = "https://melhora.madesa.com:8090/api/avalsite/insert"
    
    # Prepara os dados convertendo o dicionário para string JSON e depois para bytes
    corpo_requisicao = json.dumps(payload).encode('utf-8')
    
    # Monta a requisição
    req = urllib.request.Request(url_destino, data=corpo_requisicao, method="POST")
    req.add_header("Content-Type", "application/json")
    
    status_code = 500
    response_text = ""
    
    try:
        # Envia a requisição
        with urllib.request.urlopen(req) as response:
            status_code = response.getcode()
            response_text = response.read().decode('utf-8')
            
    except urllib.error.HTTPError as e:
        # O urllib levanta uma exceção se a resposta for 4xx ou 5xx
        # Nós capturamos para pegar o status e o corpo do erro da mesma forma
        status_code = e.code
        response_text = e.read().decode('utf-8')
        
    except Exception as error:
        print(f"Erro ao contatar o servidor: {error}")
        return JSONResponse(
            status_code=500, 
            content={"message": "Erro interno ao tentar contatar o servidor de destino."}
        )

    # Tenta fazer o parse do JSON de resposta (exatamente como no seu código JS)
    try:
        data = json.loads(response_text) if response_text else {}
    except json.JSONDecodeError:
        data = {
            "message": "Resposta do servidor não é um JSON válido", 
            "raw": response_text
        }

    return JSONResponse(status_code=status_code, content=data)
