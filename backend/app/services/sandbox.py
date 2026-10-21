"""AI Referee, part 1: deterministic grading of Python submissions.

Submitted code is statically screened (AST allow-list) and then executed in a separate,
isolated interpreter process with a timeout, against the challenge's visible and hidden
test cases.

This is prototype-grade isolation. In production the harness runs inside a throwaway
container (gVisor / Firecracker) with no network and CPU/memory cgroup limits; the
interface below stays the same.
"""
import ast
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from .. import config

MAX_CODE_BYTES = 20_000

ALLOWED_IMPORTS = {
    "math", "itertools", "collections", "functools", "re", "string", "heapq", "bisect",
    "statistics", "typing", "dataclasses", "operator", "fractions", "decimal",
}
BLOCKED_CALLS = {
    "open", "exec", "eval", "compile", "__import__", "globals", "locals", "vars",
    "getattr", "setattr", "delattr", "input", "breakpoint", "help", "memoryview",
}

HARNESS = r'''
import contextlib, importlib.util, io, json, sys

def _norm(v):
    return json.loads(json.dumps(v, default=str))

payload = json.loads(sys.stdin.read())
spec = importlib.util.spec_from_file_location("solution", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
out = {"results": []}
try:
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(mod)
    fn = getattr(mod, payload["function"])
except Exception as e:
    out = {"error": f"{type(e).__name__}: {e}"}
else:
    for t in payload["tests"]:
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                got = fn(*t["args"])
            got = _norm(got)
            out["results"].append({"ok": got == t["expected"], "got": got})
        except Exception as e:
            out["results"].append({"ok": False, "error": f"{type(e).__name__}: {e}"[:300]})
sys.stdout.write("\n@@RESULT@@" + json.dumps(out))
'''


class ScreeningError(ValueError):
    pass


def screen(code: str) -> None:
    """Reject code that reaches outside the pure-computation subset we allow."""
    if len(code.encode()) > MAX_CODE_BYTES:
        raise ScreeningError("code_too_large")
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise ScreeningError(f"SyntaxError: {e.msg} (line {e.lineno})")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in ALLOWED_IMPORTS:
                    raise ScreeningError(f"import_not_allowed: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                raise ScreeningError(f"import_not_allowed: {node.module}")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ScreeningError(f"dunder_access_not_allowed: {node.attr}")
        elif isinstance(node, ast.Name) and (
            node.id in BLOCKED_CALLS or (node.id.startswith("__") and node.id != "__name__")
        ):
            raise ScreeningError(f"name_not_allowed: {node.id}")


def _limit_resources():  # POSIX only
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (int(config.SANDBOX_TIMEOUT_SECONDS) + 1,) * 2)


def run_tests(code: str, function_name: str, tests: list[dict], include_hidden: bool = True) -> dict:
    """Grade `code`. Returns {passed, total, cases, error}. Hidden cases never leak inputs."""
    selected = [t for t in tests if include_hidden or not t.get("hidden")]
    result = {"passed": 0, "total": len(selected), "cases": [], "error": None}
    try:
        screen(code)
    except ScreeningError as e:
        result["error"] = str(e)
        return result

    with tempfile.TemporaryDirectory(prefix="tempa_") as tmp:
        sol = Path(tmp, "solution.py")
        sol.write_text(code, encoding="utf-8")
        harness = Path(tmp, "harness.py")
        harness.write_text(HARNESS, encoding="utf-8")
        env = {"PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
        if os.name == "nt":
            env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", r"C:\Windows")
        try:
            proc = subprocess.run(
                [sys.executable, "-I", str(harness), str(sol)],
                input=json.dumps({"function": function_name, "tests": selected}),
                capture_output=True, text=True, cwd=tmp, env=env,
                timeout=config.SANDBOX_TIMEOUT_SECONDS,
                preexec_fn=_limit_resources if os.name == "posix" else None,
            )
        except subprocess.TimeoutExpired:
            result["error"] = "timeout"
            return result

    marker = proc.stdout.rfind("@@RESULT@@")
    if marker == -1:
        result["error"] = (proc.stderr.strip().splitlines() or ["crashed"])[-1][:300]
        return result
    out = json.loads(proc.stdout[marker + len("@@RESULT@@"):])
    if out.get("error"):
        result["error"] = out["error"]
        return result

    for i, (t, r) in enumerate(zip(selected, out["results"]), start=1):
        case = {"n": i, "ok": r["ok"], "hidden": bool(t.get("hidden"))}
        if not t.get("hidden"):
            case.update(args=t["args"], expected=t["expected"], got=r.get("got"), error=r.get("error"))
        elif r.get("error"):
            case["error"] = r["error"].split(":")[0]  # exception type only
        result["cases"].append(case)
        result["passed"] += int(r["ok"])
    return result
