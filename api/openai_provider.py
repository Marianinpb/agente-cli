import httpx
import json
from typing import AsyncGenerator, List, Dict

class OpenAIProvider:
    def __init__(self, endpoint: str, model: str, temperature: float):
        self.endpoint = endpoint
        self.model = model
        self.temperature = temperature
        # Aseguramos que la URL termine en /v1/chat/completions
        base = self.endpoint.rstrip('/')
        if not base.endswith('/v1'):
            base += '/v1'
        self.base_url = f"{base}/chat/completions"

    @staticmethod
    async def fetch_models(endpoint: str):
        try:
            base = endpoint.rstrip('/')
            if not base.endswith('/v1'):
                base += '/v1'
            url = f"{base}/models"
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(url)
                if r.status_code == 200:
                    data = r.json()
                    return [m.get("id") for m in data.get("data", [])]
        except Exception:
            pass
        return []

    async def chat_stream(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": self.temperature
        }
        
        # Timeout corto de conexión (5s), pero largo para lectura (60s)
        timeout = httpx.Timeout(60.0, connect=5.0)
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                async with client.stream("POST", self.base_url, json=payload) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_lines():
                        if chunk.startswith("data: "):
                            data_str = chunk[6:]
                            if data_str.strip() == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                choices = data.get("choices", [])
                                if choices and "delta" in choices[0]:
                                    content = choices[0]["delta"].get("content")
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                pass
            except httpx.ConnectError:
                yield f"\n[Sistema: Error de conexión. No se pudo conectar a {self.base_url}. Verifica que el servicio esté corriendo.]"
            except httpx.HTTPStatusError as e:
                yield f"\n[Sistema: Error HTTP {e.response.status_code} desde {self.base_url}]"
            except Exception as e:
                yield f"\n[Sistema: Error inesperado: {str(e)}]"
