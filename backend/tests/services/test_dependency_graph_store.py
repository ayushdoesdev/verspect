"""Graph persistence must not PEP-503 non-Python package names."""

from app.scanners.normalize import normalize_package_name
from app.services.dependency_graph_store import resolve_graph_endpoint


class _Dep:
    def __init__(self, key: str) -> None:
        self.key = key


def test_resolve_keeps_go_module_paths() -> None:
    gin = _Dep("github.com/gin-gonic/gin")
    deps = {"github.com/gin-gonic/gin": gin}
    assert resolve_graph_endpoint(deps, "github.com/gin-gonic/gin") is gin
    assert normalize_package_name("github.com/gin-gonic/gin") == "github-com/gin-gonic/gin"
    assert resolve_graph_endpoint(deps, "github.com/gin-gonic/gin").key == "github.com/gin-gonic/gin"


def test_resolve_keeps_maven_coordinates() -> None:
    spring = _Dep("org.springframework:spring-core")
    deps = {"org.springframework:spring-core": spring}
    assert resolve_graph_endpoint(deps, "org.springframework:spring-core") is spring


def test_resolve_keeps_npm_scopes() -> None:
    scoped = _Dep("@babel/core")
    deps = {"@babel/core": scoped}
    assert resolve_graph_endpoint(deps, "@babel/core") is scoped
    assert resolve_graph_endpoint(deps, "@Babel/Core") is scoped


def test_resolve_pypi_pep503_fallback() -> None:
    django = _Dep("django")
    deps = {"django": django}
    assert resolve_graph_endpoint(deps, "Django") is django
    assert resolve_graph_endpoint(deps, "missing") is None
