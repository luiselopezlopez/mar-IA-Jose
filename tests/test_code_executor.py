"""Tests para el módulo de ejecución de código Python."""

from __future__ import annotations

import pytest

from code_executor import MAX_CODE_LENGTH, execute_python_code


def test_execute_simple_print() -> None:
    result = execute_python_code("print('hola')")
    assert result["exit_code"] == 0
    assert result["output"].strip() == "hola"
    assert result["error"] == ""


def test_execute_arithmetic() -> None:
    result = execute_python_code("print(2 + 2)")
    assert result["exit_code"] == 0
    assert result["output"].strip() == "4"


def test_execute_multiline_code() -> None:
    code = "x = 10\ny = 20\nprint(x + y)"
    result = execute_python_code(code)
    assert result["exit_code"] == 0
    assert result["output"].strip() == "30"


def test_execute_syntax_error() -> None:
    result = execute_python_code("def bad syntax:")
    assert result["exit_code"] != 0
    assert result["error"]


def test_execute_runtime_error() -> None:
    result = execute_python_code("1 / 0")
    assert result["exit_code"] != 0
    assert "ZeroDivisionError" in result["error"]


def test_execute_timeout() -> None:
    result = execute_python_code("while True: pass", timeout=2)
    assert result["exit_code"] != 0
    assert "tiempo límite" in result["error"]


def test_code_too_long() -> None:
    long_code = "x = 1\n" * (MAX_CODE_LENGTH // 6 + 1)
    result = execute_python_code(long_code)
    assert result["exit_code"] == 1
    assert "tamaño máximo" in result["error"]


def test_invalid_code_type() -> None:
    result = execute_python_code(12345)  # type: ignore[arg-type]
    assert result["exit_code"] == 1
    assert result["error"]


def test_execute_imports() -> None:
    result = execute_python_code("import math\nprint(math.pi)")
    assert result["exit_code"] == 0
    assert "3.14" in result["output"]


def test_execute_empty_output() -> None:
    result = execute_python_code("x = 42")
    assert result["exit_code"] == 0
    assert result["output"] == ""
    assert result["error"] == ""
