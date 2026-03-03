import ast
import re
from pathlib import Path


HTTP_METHODS = {"get", "post", "put", "delete", "patch"}
UUID_SAMPLE = "00000000-0000-0000-0000-000000000000"

# 用于将测试里的变量占位符替换成可匹配路由的稳定值。
VARIABLE_SAMPLES = {
    "provider_name": "provider",
    "tool_name": "tool",
    "token": "token",
    "model_name": "model",
    "batch": "batch-1",
}


def _repo_root() -> Path:
    # test/internal/handler/test_route_coverage_contract.py -> api/
    return Path(__file__).resolve().parents[3]


def _evaluate_expr(expr, constants: dict[str, object]):
    """在不执行代码的前提下，尽量还原字面量/F-string 结果。"""
    if isinstance(expr, ast.Constant):
        return expr.value
    if isinstance(expr, ast.Name):
        # 常量（例如 APP_ID）会在 module constants 中还原。
        if expr.id in constants:
            return constants[expr.id]
        # 其余变量（例如 provider_name）保留成占位符，后续再做物化。
        return f"<<{expr.id}>>"
    if isinstance(expr, ast.JoinedStr):
        pieces = []
        for value in expr.values:
            if isinstance(value, ast.Constant):
                pieces.append(str(value.value))
            elif isinstance(value, ast.FormattedValue):
                pieces.append(str(_evaluate_expr(value.value, constants)))
        return "".join(pieces)
    return None


def _extract_module_constants(tree: ast.AST) -> dict[str, object]:
    constants: dict[str, object] = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            value = _evaluate_expr(node.value, constants)
            if isinstance(value, (str, int, float, bool)):
                constants[node.targets[0].id] = value
    return constants


def _materialize_test_path(path: str) -> str:
    """将测试里的变量占位符转换为稳定可匹配的路径。"""
    segments = path.split("/")
    normalized_segments = []
    for segment in segments:
        if segment.startswith("<<") and segment.endswith(">>"):
            variable_name = segment[2:-2]
            if (
                variable_name.endswith("_id")
                or variable_name.endswith("ID")
                or variable_name.lower().endswith("id")
            ):
                normalized_segments.append(UUID_SAMPLE)
            else:
                normalized_segments.append(VARIABLE_SAMPLES.get(variable_name, "value"))
            continue
        normalized_segments.append(segment)
    return "/".join(normalized_segments)


def _route_path_to_regex(route_path: str) -> re.Pattern[str]:
    """将 Flask 路由模板（含 <uuid:...>/<string:...>）转成可匹配正则。"""
    parts = re.split(r"(<[^>]+>)", route_path)
    pattern = "^"
    for part in parts:
        if part.startswith("<uuid:") and part.endswith(">"):
            pattern += r"[0-9a-fA-F-]{36}"
        elif part.startswith("<string:") and part.endswith(">"):
            pattern += r"[^/]+"
        else:
            pattern += re.escape(part)
    pattern += "$"
    return re.compile(pattern)


def _extract_router_routes() -> set[tuple[str, str]]:
    router_file = _repo_root() / "internal" / "router" / "router.py"
    tree = ast.parse(router_file.read_text(encoding="utf-8"))
    routes: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_url_rule"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            continue

        path = node.args[0].value
        methods = ["GET"]
        for keyword in node.keywords:
            if keyword.arg == "methods" and isinstance(keyword.value, (ast.List, ast.Tuple)):
                methods = [
                    element.value
                    for element in keyword.value.elts
                    if isinstance(element, ast.Constant) and isinstance(element.value, str)
                ] or ["GET"]
        for method in methods:
            routes.add((method.upper(), path))
    return routes


def _extract_test_routes() -> list[tuple[str, str]]:
    handler_test_dir = _repo_root() / "test" / "internal" / "handler"
    test_routes: list[tuple[str, str]] = []

    for test_file in sorted(handler_test_dir.glob("test_*.py")):
        tree = ast.parse(test_file.read_text(encoding="utf-8"))
        constants = _extract_module_constants(tree)

        for node in ast.walk(tree):
            # 1) 矩阵用例（dict）里的 method/url 对。
            if isinstance(node, ast.Dict):
                entries = {}
                for key, value in zip(node.keys, node.values):
                    if isinstance(key, ast.Constant):
                        entries[key.value] = value

                if "method" in entries and "url" in entries:
                    method = _evaluate_expr(entries["method"], constants)
                    url = _evaluate_expr(entries["url"], constants)
                    if isinstance(method, str) and isinstance(url, str) and url.startswith("/"):
                        test_routes.append((method.upper(), _materialize_test_path(url)))

            # 2) 直接调用 client/http_client.get(...) / post(...) 等。
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in HTTP_METHODS
                and node.args
            ):
                url = _evaluate_expr(node.args[0], constants)
                if isinstance(url, str) and url.startswith("/"):
                    test_routes.append((node.func.attr.upper(), _materialize_test_path(url)))

    return test_routes


class TestRouteCoverageContract:
    """路由覆盖契约：每个已注册路由都必须至少被一个 handler 测试请求触发。"""

    def test_all_registered_routes_should_be_triggered_in_handler_tests(self):
        router_routes = _extract_router_routes()
        tested_routes = _extract_test_routes()

        missing_routes = []
        for method, route_path in sorted(router_routes):
            matcher = _route_path_to_regex(route_path)
            is_covered = any(
                tested_method == method and matcher.match(tested_path)
                for tested_method, tested_path in tested_routes
            )
            if not is_covered:
                missing_routes.append((method, route_path))

        assert not missing_routes, (
            "以下路由尚未在 handler 测试中触发，请补齐：\n"
            + "\n".join(f"- {method} {path}" for method, path in missing_routes)
        )
