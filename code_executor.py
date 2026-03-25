"""Ejecución segura de fragmentos de código Python en un subproceso aislado."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap

# Límites de tamaño para prevenir abusos
MAX_CODE_LENGTH = 10_000   # 10 KB
MAX_OUTPUT_LENGTH = 50_000  # 50 KB
DEFAULT_TIMEOUT = 30        # segundos


def execute_python_code(code: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Ejecuta código Python en un subproceso y devuelve el resultado.

    Args:
        code: Código Python a ejecutar.
        timeout: Tiempo máximo de ejecución en segundos.

    Returns:
        Diccionario con las claves ``output``, ``error`` y ``exit_code``.
    """
    if not isinstance(code, str):
        return {"output": "", "error": "El código debe ser una cadena de texto.", "exit_code": 1}

    if len(code) > MAX_CODE_LENGTH:
        return {
            "output": "",
            "error": (
                f"El código excede el tamaño máximo permitido "
                f"({MAX_CODE_LENGTH} caracteres)."
            ),
            "exit_code": 1,
        }

    # Normalizar la indentación para evitar errores de sangría
    code = textwrap.dedent(code)

    # Configurar límites de recursos en plataformas Unix.
    # En Windows no hay módulo ``resource``; el timeout sigue siendo el principal
    # mecanismo de protección contra ejecuciones que no terminan.
    preexec_fn = None
    if sys.platform != "win32":
        try:
            import resource  # noqa: PLC0415

            def _set_limits() -> None:
                memory_limit = 256 * 1024 * 1024  # 256 MB
                resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
                resource.setrlimit(resource.RLIMIT_NPROC, (50, 50))

            preexec_fn = _set_limits
        except ImportError:
            pass

    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
            preexec_fn=preexec_fn,
            env={
                "PATH": os.environ.get("PATH", ""),
            },
        )

        output = result.stdout[:MAX_OUTPUT_LENGTH]
        error = result.stderr[:MAX_OUTPUT_LENGTH]

        return {
            "output": output,
            "error": error,
            "exit_code": result.returncode,
        }

    except subprocess.TimeoutExpired:
        return {
            "output": "",
            "error": f"La ejecución excedió el tiempo límite de {timeout} segundos.",
            "exit_code": 1,
        }
    except Exception as exc:
        return {
            "output": "",
            "error": f"Error al ejecutar el código: {exc}",
            "exit_code": 1,
        }
