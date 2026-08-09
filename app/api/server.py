"""Servidor local (FastAPI + Uvicorn) para acesso pelo celular na rede."""

from __future__ import annotations

import socket
import threading
from dataclasses import dataclass

from app.config import APP_NAME, APP_VERSION, settings
from app.security.authentication import token_store


def create_app():  # noqa: ANN201 - tipo depende do FastAPI instalado
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    from app.api.routes import auth, clients, credits, payments

    application = FastAPI(
        title=f"{APP_NAME} — API local",
        version=APP_VERSION,
        description="Acesso somente pela rede local da empresa.",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/saude", tags=["Status"])
    def health() -> dict[str, str]:
        return {"status": "ok", "sistema": APP_NAME, "versao": APP_VERSION}

    application.include_router(auth.router)
    application.include_router(clients.router)
    application.include_router(credits.router)
    application.include_router(payments.router)
    return application


def local_ip() -> str:
    """IP da máquina na rede local (sem depender de internet)."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("10.255.255.255", 1))
        return str(probe.getsockname()[0])
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        probe.close()


@dataclass
class ServerStatus:
    running: bool
    host: str
    port: int
    url: str
    detail: str


class ApiServer:
    """Liga e desliga o Uvicorn em uma thread, sem travar a interface."""

    def __init__(self, host: str | None = None, port: int | None = None) -> None:
        self.host = host or settings.api_host
        self.port = port or settings.api_port
        self._server = None
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> ServerStatus:
        if self.is_running:
            return self.status("Servidor já estava ligado.")
        try:
            import uvicorn
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Instale as dependências da API: pip install fastapi uvicorn"
            ) from exc

        config = uvicorn.Config(
            create_app(), host=self.host, port=self.port, log_level="warning"
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(
            target=self._server.run, name="sys-api", daemon=True
        )
        self._thread.start()
        return self.status("SYS Mobile disponível na rede local.")

    def stop(self) -> ServerStatus:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._server = None
        self._thread = None
        # Desligar o acesso encerra a sessão de todos os aparelhos: os tokens
        # emitidos não voltam a valer quando o acesso for religado.
        token_store.clear()
        return self.status("Acesso pelo celular desligado.")

    def status(self, detail: str = "") -> ServerStatus:
        ip = local_ip() if self.host in {"0.0.0.0", ""} else self.host
        return ServerStatus(
            running=self.is_running,
            host=ip,
            port=self.port,
            url=f"http://{ip}:{self.port}",
            detail=detail,
        )


api_server = ApiServer()
