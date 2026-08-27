"""inline helper; may decrease code run speed due to inline decorator overhead. basically turns any function into syntatic sugar.
or poor man's macro.
mark functions to be inlined with @inline.
automatically outputs to ./mod/<filename>_inlined.py. overwrites.

supports:
  - single-expression functions (body is just `return <expr>`)
    → call site replaced with the expression directly
  - multi-statement functions
    → statements hoisted above call site as _funcname_varname locals,
      return expression substituted in place of the call
"""

import ast
import atexit
import copy
import inspect
import os
import subprocess
import time

LOUD = False
BLACK_FORMAT = True


def loud():
    global LOUD
    LOUD = True


def no_black():
    global BLACK_FORMAT
    BLACK_FORMAT = False


def _log(msg: str):
    if LOUD:
        print(msg, flush=True)


def _black_format(filename):
    try:
        subprocess.run(
            ["black", filename],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except FileNotFoundError:
        _log("[inliner] black not found, skipping formatting")
    except subprocess.CalledProcessError as e:
        _log(f"[inliner] black failed: {e}")


def _capture_caller():
    stack = inspect.stack()
    return stack[-1].filename


def inline(func):
    """mark function for inlining."""
    return func


def _is_single_expr_func(funcdef: ast.FunctionDef) -> bool:
    """true if body is exactly `return <expr>` (ignoring docstring)"""
    body = funcdef.body
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
    ):
        body = body[1:]
    return (
        len(body) == 1 and isinstance(body[0], ast.Return) and body[0].value is not None
    )


def _make_arg_map(funcdef: ast.FunctionDef, call: ast.Call) -> dict:
    """map param names → call argument nodes (positional only for now)"""
    params = [arg.arg for arg in funcdef.args.args]
    return dict(zip(params, call.args))


class _SubstituteNames(ast.NodeTransformer):
    """replace Name nodes according to a substitution map"""

    def __init__(self, subst: dict):
        self.subst = subst

    def visit_Name(self, node):
        if node.id in self.subst:
            return copy.deepcopy(self.subst[node.id])
        return node


def _substitute(tree, subst: dict):
    return _SubstituteNames(subst).visit(copy.deepcopy(tree))


def _mangle(func_name: str, var_name: str) -> str:
    return f"_{func_name}_{var_name}"


class _Inliner(ast.NodeTransformer):
    """
    two-pass inline transformer.
    pass 1 (statement level): for multi-stmt inlines, hoist assignments before
                              the containing statement.
    pass 2 (expression level): replace Call nodes with inlined expressions.
    """

    def __init__(self, inline_funcs: dict[str, ast.FunctionDef]):
        self.inline_funcs = inline_funcs
        self._pending_prepend: list[ast.stmt] = []

    def visit_Call(self, node: ast.Call):
        self.generic_visit(node)

        func_name = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if func_name not in self.inline_funcs:
            return node

        funcdef = self.inline_funcs[func_name]
        arg_map = _make_arg_map(funcdef, node)

        body = funcdef.body
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
        ):
            body = body[1:]

        if _is_single_expr_func(funcdef):
            ret_expr = body[0].value
            return _substitute(ret_expr, arg_map)

        local_names: set[str] = set()
        for stmt in body:
            for n in ast.walk(stmt):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                    local_names.add(n.id)

        mangle_map = {
            name: ast.Name(id=_mangle(func_name, name), ctx=ast.Load())
            for name in local_names
        }
        subst = {**arg_map, **mangle_map}

        return_expr = None
        for stmt in body:
            if isinstance(stmt, ast.Return):
                return_expr = _substitute(stmt.value, subst)
                break
            new_stmt = _substitute(stmt, subst)
            for n in ast.walk(new_stmt):
                if isinstance(n, ast.Name) and n.id.startswith(f"_{func_name}_"):
                    n.ctx = ast.Store() if isinstance(n.ctx, ast.Store) else n.ctx
            ast.fix_missing_locations(new_stmt)
            self._pending_prepend.append(new_stmt)

        if return_expr is None:
            return ast.Constant(value=None)

        ast.fix_missing_locations(return_expr)
        return return_expr

    def _process_stmt_list(self, stmts: list[ast.stmt]) -> list[ast.stmt]:
        result = []
        for stmt in stmts:
            self._pending_prepend = []
            new_stmt = self.visit(stmt)
            if self._pending_prepend:
                result.extend(self._pending_prepend)
            if new_stmt is None:
                pass
            elif isinstance(new_stmt, list):
                result.extend(new_stmt)
            else:
                result.append(new_stmt)
        return result

    def visit_Module(self, node: ast.Module):
        node.body = self._process_stmt_list(node.body)
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if node.name in self.inline_funcs:
            return None
        node.body = self._process_stmt_list(node.body)
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_If(self, node):
        node.body = self._process_stmt_list(node.body)
        node.orelse = self._process_stmt_list(node.orelse)
        return node

    def visit_While(self, node):
        node.body = self._process_stmt_list(node.body)
        node.orelse = self._process_stmt_list(node.orelse)
        return node

    def visit_For(self, node):
        self.generic_visit(node)
        node.body = self._process_stmt_list(node.body)
        node.orelse = self._process_stmt_list(node.orelse)
        return node

    def visit_With(self, node):
        node.body = self._process_stmt_list(node.body)
        return node

    def visit_Try(self, node):
        node.body = self._process_stmt_list(node.body)
        node.orelse = self._process_stmt_list(node.orelse)
        node.finalbody = self._process_stmt_list(node.finalbody)
        for handler in node.handlers:
            handler.body = self._process_stmt_list(handler.body)
        return node


def _collect_inline_funcs(source_ast: ast.Module) -> dict[str, ast.FunctionDef]:
    result = {}
    for node in ast.walk(source_ast):
        if isinstance(node, ast.FunctionDef):
            if any(
                (isinstance(d, ast.Name) and d.id == "inline")
                or (isinstance(d, ast.Attribute) and d.attr == "inline")
                for d in node.decorator_list
            ):
                result[node.name] = node
    return result


def _strip_inliner_import(source_ast: ast.Module) -> ast.Module:
    """remove `import inliner` / `from inliner import inline` lines"""
    new_body = []
    for node in source_ast.body:
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
            if any("inliner" in n for n in names):
                continue
        if isinstance(node, ast.ImportFrom):
            if node.module and "inliner" in node.module:
                continue
        new_body.append(node)
    source_ast.body = new_body
    return source_ast


def _inline_file(source_file: str):
    start_time = time.time()
    with open(source_file, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)
    inline_funcs = _collect_inline_funcs(tree)

    if not inline_funcs:
        _log(f"[inliner] no @inline functions found in {source_file}, nothing to do")
        return

    _log(f"[inliner] inlining: {list(inline_funcs.keys())}")

    tree = _strip_inliner_import(tree)
    tree = _Inliner(inline_funcs).visit(tree)
    ast.fix_missing_locations(tree)

    out_source = ast.unparse(tree)

    out_dir = os.path.join(os.path.dirname(source_file), "mod")
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(source_file))[0]
    out_path = os.path.join(out_dir, f"{base}_inlined.py")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out_source)

    if BLACK_FORMAT:
        _black_format(out_path)

    _log(f"[inliner] wrote → {out_path}")
    _log(f"[inliner] output:\n{out_source}")
    _log(f"[inliner] finished in {time.time() - start_time:.3f}s")


if __name__ != "__main__":
    _source_file = _capture_caller()
    atexit.register(_inline_file, _source_file)
