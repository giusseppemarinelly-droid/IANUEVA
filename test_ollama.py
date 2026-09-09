import requests

respuesta = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "qwen2.5:3b",
        "prompt": "Decime 'hola' y nada más.",
        "stream": False,
    },
)

respuesta.raise_for_status()
print(respuesta.json()["response"])
