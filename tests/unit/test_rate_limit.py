"""El límite de autenticación responde 429, se comparte por Redis y no se cae si Redis falla."""

from app.main import create_app
from app.shared.config import Settings
from app.shared.http.rate_limit import (
    AUTH_KEY_PREFIX,
    MemoryRateLimiter,
    RateLimiter,
    RedisRateLimiter,
    build_auth_rate_limiter,
    client_key,
    install_auth_rate_limit,
)
from fakeredis import FakeAsyncRedis, FakeServer
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request


class ManualClock:
    def __init__(self, now: float = 1_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class BrokenRedis:
    """Simula un Redis caído: cualquier transacción falla."""

    def pipeline(self, transaction: bool = True) -> object:
        raise ConnectionError("Redis no disponible")

    async def aclose(self) -> None:
        return None


def _request(headers: dict[str, str], host: str = "10.0.0.1") -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/auth/login",
            "headers": [(name.encode(), value.encode()) for name, value in headers.items()],
            "client": (host, 4321),
        }
    )


def _redis_limiter(server: FakeServer, limit: int, clock: ManualClock) -> RedisRateLimiter:
    client = FakeAsyncRedis(server=server, decode_responses=True)
    return RedisRateLimiter(client, limit, fallback=MemoryRateLimiter(limit), clock=clock)


def _limited_app(limiter: RateLimiter, trust_proxy_headers: bool) -> TestClient:
    app = FastAPI()
    install_auth_rate_limit(app, limiter, trust_proxy_headers=trust_proxy_headers)

    @app.post("/auth/login")
    def login() -> dict[str, str]:
        return {"status": "ok"}

    return TestClient(app)


def test_el_tercer_login_seguido_queda_bloqueado() -> None:
    settings = Settings(environment="local", auth_requests_per_minute=2, redis_url="")
    client = TestClient(create_app(settings))
    body = {"email": "nadie@example.com", "password": "secreto-largo"}
    assert client.post("/auth/login", json=body).status_code == 401
    assert client.post("/auth/login", json=body).status_code == 401
    blocked = client.post("/auth/login", json=body)
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "rate_limited"


async def test_sin_redis_url_el_limite_cuenta_en_memoria() -> None:
    assert isinstance(build_auth_rate_limiter("", 5), MemoryRateLimiter)
    assert isinstance(build_auth_rate_limiter("   ", 5), MemoryRateLimiter)


async def test_con_redis_url_el_limite_usa_redis() -> None:
    limiter = build_auth_rate_limiter("rediss://default:clave@ejemplo.upstash.io:6379", 5)
    assert isinstance(limiter, RedisRateLimiter)
    await limiter.aclose()


async def test_dos_instancias_comparten_el_conteo_por_redis() -> None:
    server = FakeServer()
    clock = ManualClock()
    first = _redis_limiter(server, limit=2, clock=clock)
    second = _redis_limiter(server, limit=2, clock=clock)
    assert await first.allow("203.0.113.7")
    assert await second.allow("203.0.113.7")
    assert not await first.allow("203.0.113.7")
    assert not await second.allow("203.0.113.7")


async def test_otro_cliente_no_hereda_el_bloqueo() -> None:
    limiter = _redis_limiter(FakeServer(), limit=1, clock=ManualClock())
    assert await limiter.allow("203.0.113.7")
    assert not await limiter.allow("203.0.113.7")
    assert await limiter.allow("198.51.100.9")


async def test_la_ventana_se_libera_al_pasar_el_minuto() -> None:
    clock = ManualClock()
    limiter = _redis_limiter(FakeServer(), limit=1, clock=clock)
    assert await limiter.allow("203.0.113.7")
    assert not await limiter.allow("203.0.113.7")
    clock.now += 61
    assert await limiter.allow("203.0.113.7")


async def test_la_clave_de_redis_caduca_sola() -> None:
    server = FakeServer()
    limiter = _redis_limiter(server, limit=3, clock=ManualClock())
    await limiter.allow("203.0.113.7")
    inspector = FakeAsyncRedis(server=server, decode_responses=True)
    ttl = await inspector.ttl(f"{AUTH_KEY_PREFIX}203.0.113.7")
    assert 0 < ttl <= 60


async def test_si_redis_falla_el_limite_sigue_en_memoria() -> None:
    limiter = RedisRateLimiter(
        BrokenRedis(),  # type: ignore[arg-type]
        limit=1,
        fallback=MemoryRateLimiter(1),
    )
    assert await limiter.allow("203.0.113.7")
    assert not await limiter.allow("203.0.113.7")


def test_detras_de_vercel_la_clave_es_la_ip_real() -> None:
    request = _request({"x-real-ip": "203.0.113.7", "x-forwarded-for": "198.51.100.9"})
    assert client_key(request, trust_proxy_headers=True) == "203.0.113.7"


def test_sin_x_real_ip_usa_el_primer_x_forwarded_for() -> None:
    request = _request({"x-forwarded-for": "198.51.100.9, 10.0.0.2"})
    assert client_key(request, trust_proxy_headers=True) == "198.51.100.9"


def test_fuera_de_un_proxy_de_confianza_se_ignoran_las_cabeceras() -> None:
    request = _request({"x-real-ip": "203.0.113.7"}, host="10.0.0.1")
    assert client_key(request, trust_proxy_headers=False) == "10.0.0.1"


def test_cambiar_x_real_ip_no_evita_el_bloqueo_fuera_del_proxy() -> None:
    client = _limited_app(MemoryRateLimiter(1), trust_proxy_headers=False)
    assert client.post("/auth/login", headers={"x-real-ip": "1.1.1.1"}).status_code == 200
    blocked = client.post("/auth/login", headers={"x-real-ip": "2.2.2.2"})
    assert blocked.status_code == 429


def test_detras_de_vercel_cada_usuario_tiene_su_propio_conteo() -> None:
    client = _limited_app(MemoryRateLimiter(1), trust_proxy_headers=True)
    assert client.post("/auth/login", headers={"x-real-ip": "203.0.113.7"}).status_code == 200
    assert client.post("/auth/login", headers={"x-real-ip": "198.51.100.9"}).status_code == 200
    assert client.post("/auth/login", headers={"x-real-ip": "203.0.113.7"}).status_code == 429


def test_las_rutas_fuera_de_auth_no_cuentan() -> None:
    app = FastAPI()
    install_auth_rate_limit(app, MemoryRateLimiter(1))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)
    assert all(client.get("/health").status_code == 200 for _ in range(3))
