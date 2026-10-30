"""AST parser tests."""

from pathlib import Path

from app.scanners.ast_parser import ASTParser
from app.core.enums import UsageKind


def test_ast_extracts_imports_and_calls(tmp_path: Path):
    pkg = tmp_path / "app"
    pkg.mkdir()
    (pkg / "users.py").write_text(
        """
import requests
from fastapi import FastAPI

app = FastAPI()

def fetch():
    return requests.get("https://example.com")
""",
        encoding="utf-8",
    )
    result = ASTParser(
        tmp_path,
        known_packages={"requests", "fastapi"},
    ).scan()
    fqns = {u.fully_qualified_name for u in result.usages}
    kinds = {u.usage_kind for u in result.usages}
    assert "requests" in fqns or any(u.startswith("requests") for u in fqns)
    assert "requests.get" in fqns
    assert UsageKind.METHOD_CALL.value in kinds or UsageKind.FUNCTION_CALL.value in kinds
    assert result.files_parsed == 1


def test_ast_captures_decorator_and_inheritance(tmp_path: Path):
    (tmp_path / "models.py").write_text(
        """
from pydantic import BaseModel, field_validator

class User(BaseModel):
    name: str

    @field_validator("name")
    def check(cls, v):
        return v
""",
        encoding="utf-8",
    )
    result = ASTParser(tmp_path, known_packages={"pydantic"}).scan()
    kinds = {u.usage_kind for u in result.usages}
    assert UsageKind.INHERITANCE.value in kinds
    assert UsageKind.DECORATOR.value in kinds or UsageKind.FROM_IMPORT.value in kinds
