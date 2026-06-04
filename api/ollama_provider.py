import httpx
import json
from typing import AsyncGenerator, List, Dict

class OllamaProvider:
    def __init__(self, endpoint: str, model: str, temperature: float):
        self.endpoint = endpoint
        self.model = model
        self.temperature = temperature
        self.base_url = f"{self.endpoint.rstrip('/')}/api/chat"

    async def chat_stream(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": self.temperature
            }
        }
        
        # Timeout corto de conexión (5s), pero largo para lectura (60s)
        timeout = httpx.Timeout(60.0, connect=5.0)
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                async with client.stream("POST", self.base_url, json=payload) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_lines():
                        if chunk:
                            try:
                                data = json.loads(chunk)
                                if "message" in data and "content" in data["message"]:
                                    yield data["message"]["content"]
                            except json.JSONDecodeError:
                                pass
            except httpx.ConnectError:
                yield f"\n[Sistema: Error de conexión. No se pudo conectar a {self.base_url}. Verifica que el servicio local o Docker esté corriendo.]"
            except httpx.HTTPStatusError as e:
                yield f"\n[Sistema: Error HTTP {e.response.status_code} desde {self.base_url}]"
            except Exception as e:
                yield f"\n[Sistema: Error inesperado de conexión con Ollama: {str(e)}]"
