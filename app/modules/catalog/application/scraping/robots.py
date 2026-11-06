"""Respeta robots.txt antes de descargar una página."""

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

USER_AGENT = "GuitarCoachBot/1.0"


def is_allowed(robots_txt: str, url: str, user_agent: str = USER_AGENT) -> bool:
    parser = RobotFileParser()
    parser.parse(robots_txt.splitlines())
    return parser.can_fetch(user_agent, url)


def domain_of(url: str) -> str:
    host = urlparse(url).hostname
    if not host:
        raise ValueError("La URL no tiene dominio.")
    return host
