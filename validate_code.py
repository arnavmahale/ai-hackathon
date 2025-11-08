#!/usr/bin/env python3
from __future__ import annotations
import argparse, ast, fnmatch, json, os, re, subprocess, sys, textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

# Optional YAML support (else use JSON for tasks file)
try:
    import yaml  # pip install pyyaml
except Exception:
    yaml = None

# ===================== Data types =====================

@dataclass
class Finding:
    task: str
    file: str
    line: int
    column: int
    message: str
    fix: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task, "file": self.file, "line": self.line,
            "column": self.column, "message": self.message, "fix": self.fix
        }

# ===================== Utilities ======================

TEXT_EXT_BLOCKLIST = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".gz", ".tar", ".rar", ".bmp", ".ico"}

def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""

def glob_many(patterns: List[str]) -> List[Path]:
    out: List[Path] = []
    for pat in patterns:
        # support simple globs relative to cwd
        out.extend(Path().glob(pat))
    # Deduplicate while preserving order
    seen = set()
    uniq = []
    for p in out:
        if p not in seen and p.is_file():
            seen.add(p)
            uniq.append(p)
    return uniq


def _rule_applies_to_file(rule: Dict[str, Any], rel_path: str) -> bool:
    globs = rule.get("file_globs")
    if not globs:
        return True
    return any(fnmatch.fnmatch(rel_path, pat) for pat in globs)


def list_changed_files_git(base: str, head: str) -> List[Path]:
    try:
        res = subprocess.run(
            ["git", "diff", "--name-only", f"{base}..{head}"],
            capture_output=True, text=True, check=True
        )
        files = [Path(line.strip()) for line in res.stdout.splitlines() if line.strip()]
        return [p for p in files if p.exists()]
    except Exception:
        return []

def line_col_from_offset(text: str, offset: int) -> Tuple[int, int]:
    line = text.count("\n", 0, offset) + 1
    col = offset - (text.rfind("\n", 0, offset) + 1)
    return line, col

def compile_flags(flag_names: List[str]) -> int:
    flag_map = {"IGNORECASE": re.IGNORECASE, "MULTILINE": re.MULTILINE, "DOTALL": re.DOTALL, "ASCII": re.ASCII}
    flags = 0
    for f in (flag_names or []):
        flags |= flag_map.get(f.upper(), 0)
    return flags


def build_parent_map(tree: ast.AST) -> Dict[ast.AST, Optional[ast.AST]]:
    parent_of: Dict[ast.AST, Optional[ast.AST]] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parent_of[child] = parent
    return parent_of


def _expr_to_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _expr_to_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return _expr_to_name(node.func)
    if isinstance(node, ast.Subscript):
        return _expr_to_name(node.value)
    return ""


def _node_end_lineno(node: ast.AST) -> int:
    end = getattr(node, "end_lineno", None)
    if end is not None:
        return end
    max_line = getattr(node, "lineno", 0)
    for child in ast.walk(node):
        if hasattr(child, "lineno"):
            max_line = max(max_line, child.lineno)  # type: ignore[arg-type]
    return max_line


def _iter_assigned_names(target: ast.AST):
    if isinstance(target, ast.Name):
        yield target.id
    elif isinstance(target, (ast.Tuple, ast.List)):
        for elt in target.elts:
            yield from _iter_assigned_names(elt)
    elif isinstance(target, ast.Starred):
        yield from _iter_assigned_names(target.value)

# ===================== Task loading ===================

def load_tasks(tasks_path: Path) -> Dict[str, Any]:
    text = read_text(tasks_path)
    if tasks_path.suffix.lower() in {".yml", ".yaml"}:
        if yaml is None:
            raise RuntimeError("Install 'pyyaml' or use a JSON tasks file.")
        return yaml.safe_load(text)
    return json.loads(text)


def normalize_tasks_config(tasks_cfg: Any) -> Dict[str, Any]:
    if isinstance(tasks_cfg, dict):
        cfg = dict(tasks_cfg)
        cfg.setdefault("rules", [])
        return cfg
    if isinstance(tasks_cfg, list):
        rules = []
        for task in tasks_cfg:
            rule = _convert_guardian_task(task)
            if rule:
                rules.append(rule)
        return {"rules": rules}
    raise RuntimeError("Unsupported tasks configuration format.")


def _convert_guardian_task(task: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    tid = task.get("id")
    base = {
        "name": task.get("title", tid or "task"),
        "message": task.get("description"),
        "file_globs": task.get("fileTypes") or ["*"],
        "severity": task.get("severity"),
        "fix": task.get("suggestedFix"),
        "doc": task.get("docReference"),
    }
    if tid == "task_001":
        base.update({
            "type": "require_jwt_auth",
            "auth_decorators": [
                "require_auth", "requireAuth", "jwt_required", "jwtRequired",
                "login_required", "requireJwtAuth"
            ],
            "route_suffixes": ["route", "get", "post", "put", "delete", "patch"],
            "text_route_patterns": [
                r"@app\\.route",
                r"\\bapp\\.(get|post|put|delete|patch)\\s*\\(",
                r"\\brouter\\.(get|post|put|delete|patch)\\s*\\(",
                r"\\bapi\\.(get|post|put|delete|patch)\\s*\\(",
            ],
            "text_auth_markers": [
                "require_auth", "requireAuth", "jwt_required", "jwtRequired",
                "requireJwt", "requireJWT", "authorize", "authorizeRequest"
            ],
        })
    elif tid == "task_002":
        base.update({
            "type": "require_exception_logging",
            "log_name_markers": ["log", "logger", "logging"],
        })
    elif tid == "task_003":
        base.update({
            "type": "min_coverage",
            "min_percent": 80,
            "pattern": r"Coverage:\\s*(\\d+)%",
        })
    elif tid == "task_004":
        base.update({
            "type": "max_function_length",
            "max_lines": 50,
        })
    elif tid == "task_005":
        base.update({
            "type": "function_name_style",
            "style": "camel",
            "allow_leading_underscore": False,
        })
    elif tid == "task_006":
        base.update({
            "type": "class_name_style",
            "style": "pascal",
            "pattern": r"[A-Z][A-Za-z0-9]+$",
        })
    elif tid == "task_007":
        base.update({
            "type": "constant_name_style",
            "pattern": r"[A-Z][A-Z0-9_]*$",
        })
    elif tid == "task_008":
        base.update({
            "type": "file_name_kebab",
            "pattern": r"[a-z0-9]+(?:-[a-z0-9]+)*\\.[A-Za-z0-9]+$",
        })
    elif tid == "task_009":
        base.update({
            "type": "function_docstring_required",
        })
    else:
        return None
    return base

# ===================== Built-in checkers ===============

def check_forbid_text(task: Dict[str, Any], fname: str, code: str) -> List[Finding]:
    rx = re.compile(task["pattern"], compile_flags(task.get("flags")))
    findings: List[Finding] = []
    for m in rx.finditer(code):
        ln, col = line_col_from_offset(code, m.start())
        findings.append(Finding(
            task=task.get("name", "forbid_text"), file=fname, line=ln, column=col,
            message=task.get("message", "Forbidden text match."), fix=task.get("fix")
        ))
    return findings

def check_require_text(task: Dict[str, Any], fname: str, code: str) -> List[Finding]:
    trigger = task.get("when_pattern_present")
    flags = compile_flags(task.get("flags"))
    if trigger and not re.search(trigger, code, flags):
        return []
    if re.search(task["pattern"], code, flags):
        return []
    return [Finding(
        task=task.get("name", "require_text"), file=fname, line=1, column=0,
        message=task.get("message", "Required text missing."), fix=task.get("fix")
    )]

def ast_parse_or_finding(task_name: str, fname: str, code: str) -> Tuple[Optional[ast.AST], Optional[Finding]]:
    try:
        return ast.parse(code), None
    except SyntaxError as e:
        return None, Finding(task=task_name, file=fname, line=e.lineno or 1, column=e.offset or 0,
                             message=f"Syntax error: {e.msg}", fix=None)

def _args_signature(args: ast.arguments):
    pos = [a.arg for a in (args.posonlyargs + args.args)]
    kwonly = [a.arg for a in args.kwonlyargs]
    has_var = args.vararg is not None
    has_kw = args.kwarg is not None
    return pos, kwonly, has_var, has_kw

def check_require_function(task: Dict[str, Any], fname: str, code: str) -> List[Finding]:
    tname = task.get("name", "require_function")
    tree, err = ast_parse_or_finding(tname, fname, code)
    if err: return [err]
    spec = task["function"]
    want_name = spec["name"]
    want_pos = spec.get("args", [])
    want_kwonly = spec.get("kwonly", [])
    want_var = bool(spec.get("vararg", False))
    want_kw = bool(spec.get("varkw", False))
    want_doc = bool(spec.get("docstring_required", False))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == want_name:
            pos, kwonly, has_var, has_kw = _args_signature(node.args)
            problems = []
            if pos != want_pos: problems.append(f"positional {pos} != {want_pos}")
            if kwonly != want_kwonly: problems.append(f"kwonly {kwonly} != {want_kwonly}")
            if has_var != want_var: problems.append(f"vararg {has_var} != {want_var}")
            if has_kw != want_kw: problems.append(f"varkw {has_kw} != {want_kw}")
            if want_doc and not ast.get_docstring(node): problems.append("missing docstring")
            if problems:
                return [Finding(tname, fname, node.lineno, node.col_offset,
                                task.get("message", "Function signature mismatch: ") + "; ".join(problems),
                                task.get("fix"))]
            return []
    return [Finding(tname, fname, 1, 0, task.get("message", f"Function `{want_name}` not found."), task.get("fix"))]

class _CxVisitor(ast.NodeVisitor):
    def __init__(self): self.score = 1
    def _bump(self, n=1): self.score += n
    def visit_If(self, n): self._bump(); self.generic_visit(n)
    def visit_For(self, n): self._bump(); self.generic_visit(n)
    def visit_While(self, n): self._bump(); self.generic_visit(n)
    def visit_With(self, n): self._bump(); self.generic_visit(n)
    def visit_AsyncWith(self, n): self._bump(); self.generic_visit(n)
    def visit_Try(self, n): self._bump(len(n.handlers) or 1); self.generic_visit(n)
    def visit_BoolOp(self, n): self._bump(len(n.values) - 1); self.generic_visit(n)
    def visit_IfExp(self, n): self._bump(); self.generic_visit(n)
    def visit_comprehension(self, n): self._bump(1 + len(n.ifs)); self.generic_visit(n)

def _fn_complexity(node: ast.AST) -> int:
    v = _CxVisitor(); v.visit(node); return v.score

def check_max_complexity(task: Dict[str, Any], fname: str, code: str) -> List[Finding]:
    tname = task.get("name", "max_complexity")
    tree, err = ast_parse_or_finding(tname, fname, code)
    if err: return [err]
    out: List[Finding] = []
    limit = int(task["max"])
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            cx = _fn_complexity(n)
            if cx > limit:
                out.append(Finding(
                    tname, fname, n.lineno, n.col_offset,
                    task.get("message", "Function too complex.") + f" (got {cx}, max {limit})",
                    task.get("fix")
                ))
    return out

# ---- camelCase function-name checker ----

def _is_magic(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")

def _to_camel(s: str) -> str:
    s = s.replace("-", "_")
    parts = re.split(r"_+", s.strip("_"))
    if not parts: return s
    first = parts[0].lower()
    rest = [p[:1].upper() + p[1:] for p in parts[1:]]
    return first + "".join(rest)

def _is_camel(name: str, allow_leading_underscore: bool) -> bool:
    if allow_leading_underscore and name.startswith("_"):
        name = name[1:]
    return bool(re.fullmatch(r"[a-z][A-Za-z0-9]*", name))

def check_function_name_style(task: Dict[str, Any], fname: str, code: str) -> List[Finding]:
    """
    Enforce function name style "camel" (camelCase).
    Task fields:
      - style: "camel" (supported)
      - scope: "all" | "top_level" | "methods"  (default "all")
      - allow_leading_underscore: bool (default True)
      - exclude_magic: bool (default True)
      - include_regex / exclude_regex: optional filters on names
    """
    tname = task.get("name", "function_name_style")
    style = task.get("style", "camel").lower()
    scope = task.get("scope", "all").lower()
    allow_leading = bool(task.get("allow_leading_underscore", True))
    exclude_magic = bool(task.get("exclude_magic", True))
    inc_rx = re.compile(task["include_regex"]) if "include_regex" in task else None
    exc_rx = re.compile(task["exclude_regex"]) if "exclude_regex" in task else None

    if style != "camel":
        return [Finding(tname, fname, 1, 0,
                        f"Unsupported style '{style}'. Only 'camel' implemented.",
                        "Extend checker if you need 'snake' or 'pascal'.")]

    tree, err = ast_parse_or_finding(tname, fname, code)
    if err: return [err]

    # parent map to know methods
    parent_of = build_parent_map(tree)

    def ok_scope(node: ast.AST) -> bool:
        if scope == "all": return True
        if scope == "top_level": return parent_of.get(node) is None
        if scope == "methods": return isinstance(parent_of.get(node), ast.ClassDef)
        return True

    findings: List[Finding] = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not ok_scope(n): continue
            name = n.name
            if exclude_magic and _is_magic(name): continue
            if inc_rx and not inc_rx.search(name): continue
            if exc_rx and exc_rx.search(name): continue

            if not _is_camel(name, allow_leading):
                suggested = _to_camel(name[1:] if (allow_leading and name.startswith("_")) else name)
                if allow_leading and name.startswith("_"):
                    suggested = "_" + suggested
                msg = task.get("message", "Function name must be camelCase.")
                fix = (task.get("fix_hint_prefix", "Rename to: ") + suggested)
                findings.append(Finding(tname, fname, n.lineno, n.col_offset,
                                        f"{msg} (found `{name}`)", fix))
    return findings


def check_require_jwt_auth(task: Dict[str, Any], fname: str, code: str) -> List[Finding]:
    tname = task.get("name", "require_jwt_auth")
    auth_names = {n.lower() for n in task.get("auth_decorators", [])}
    route_suffixes = {s.lower() for s in task.get("route_suffixes", [])}
    findings: List[Finding] = []
    message = task.get("message", "API endpoints must enforce JWT authentication.")
    ext = Path(fname).suffix.lower()
    if ext == ".py":
        tree, err = ast_parse_or_finding(tname, fname, code)
        if err:
            return [err]
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                deco_names = [_expr_to_name(d).lower() for d in node.decorator_list]
                if any((name.split(".")[-1] in route_suffixes) for name in deco_names):
                    if not any((name.split(".")[-1] in auth_names) for name in deco_names):
                        findings.append(Finding(
                            tname, fname, node.lineno, node.col_offset,
                            f"{message} (function `{node.name}` missing auth decorator)",
                            task.get("fix")
                        ))
        return findings

    route_patterns = [re.compile(p) for p in task.get("text_route_patterns", [])]
    auth_markers = [m.lower() for m in task.get("text_auth_markers", [])]
    lines = code.splitlines()
    for idx, line in enumerate(lines, 1):
        if not route_patterns:
            break
        if any(rx.search(line) for rx in route_patterns):
            low = line.lower()
            if not any(marker in low for marker in auth_markers):
                pos = 0
                for rx in route_patterns:
                    m = rx.search(line)
                    if m:
                        pos = m.start()
                        break
                findings.append(Finding(
                    tname, fname, idx, pos,
                    f"{message} (route/middleware defined without auth)",
                    task.get("fix")
                ))
    return findings


def _call_is_logger(call: ast.Call, markers: Set[str]) -> bool:
    name = _expr_to_name(call.func).lower()
    return any(marker in name for marker in markers)


def check_require_exception_logging(task: Dict[str, Any], fname: str, code: str) -> List[Finding]:
    tname = task.get("name", "require_exception_logging")
    markers = {m.lower() for m in task.get("log_name_markers", ["log", "logger"])}
    tree, err = ast_parse_or_finding(tname, fname, code)
    if err:
        return [err]
    findings: List[Finding] = []
    message = task.get("message", "Exceptions must be logged inside except blocks.")
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                if not handler.body:
                    findings.append(Finding(tname, fname, handler.lineno, handler.col_offset,
                                             f"{message} (empty handler)", task.get("fix")))
                    continue
                logged = False
                for child in handler.body:
                    for inner in ast.walk(child):
                        if isinstance(inner, ast.Call) and _call_is_logger(inner, markers):
                            logged = True
                            break
                    if logged:
                        break
                if not logged:
                    findings.append(Finding(
                        tname, fname, handler.lineno, handler.col_offset,
                        f"{message} (handler missing logger call)", task.get("fix")
                    ))
    return findings


def check_min_coverage(task: Dict[str, Any], fname: str, code: str) -> List[Finding]:
    pattern = re.compile(task.get("pattern", r"Coverage:\\s*(\\d+)%"))
    threshold = int(task.get("min_percent", 80))
    tname = task.get("name", "min_coverage")
    matches = [(int(m.group(1)), m.start()) for m in pattern.finditer(code)]
    if not matches:
        return [Finding(tname, fname, 1, 0,
                        task.get("message", "Coverage report missing."), task.get("fix"))]
    best = max(matches, key=lambda tup: tup[0])
    if best[0] < threshold:
        line, col = line_col_from_offset(code, best[1])
        return [Finding(
            tname, fname, line, col,
            f"{task.get('message', 'Coverage below threshold.')} (found {best[0]}%, need >= {threshold}%)",
            task.get("fix")
        )]
    return []


def check_max_function_length(task: Dict[str, Any], fname: str, code: str) -> List[Finding]:
    tname = task.get("name", "max_function_length")
    limit = int(task.get("max_lines", 50))
    tree, err = ast_parse_or_finding(tname, fname, code)
    if err:
        return [err]
    findings: List[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = _node_end_lineno(node)
            length = max(0, end - node.lineno + 1)
            if length > limit:
                msg = task.get("message", "Function exceeds maximum length.")
                findings.append(Finding(
                    tname, fname, node.lineno, node.col_offset,
                    f"{msg} (function `{node.name}` has {length} lines; limit {limit})",
                    task.get("fix")
                ))
    return findings


def check_class_name_style(task: Dict[str, Any], fname: str, code: str) -> List[Finding]:
    tname = task.get("name", "class_name_style")
    pattern = re.compile(task.get("pattern", r"[A-Z][A-Za-z0-9]+$"))
    tree, err = ast_parse_or_finding(tname, fname, code)
    if err:
        return [err]
    findings: List[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if not pattern.fullmatch(node.name):
                msg = task.get("message", "Class names must be PascalCase.")
                findings.append(Finding(
                    tname, fname, node.lineno, node.col_offset,
                    f"{msg} (found `{node.name}`)",
                    task.get("fix")
                ))
    return findings


def check_constant_name_style(task: Dict[str, Any], fname: str, code: str) -> List[Finding]:
    tname = task.get("name", "constant_name_style")
    pattern = re.compile(task.get("pattern", r"[A-Z][A-Z0-9_]*$"))
    tree, err = ast_parse_or_finding(tname, fname, code)
    if err:
        return [err]
    parent_map = build_parent_map(tree)
    findings: List[Finding] = []
    msg = task.get("message", "Constants must use UPPER_SNAKE_CASE.")
    def in_constant_scope(node: ast.AST) -> bool:
        parent = parent_map.get(node)
        return isinstance(parent, (ast.Module, ast.ClassDef))

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and in_constant_scope(node):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign) and in_constant_scope(node):
            targets = [node.target]
        else:
            continue
        for target in targets:
            for name in _iter_assigned_names(target):
                if name.startswith("__") and name.endswith("__"):
                    continue
                if not pattern.fullmatch(name):
                    findings.append(Finding(
                        tname, fname, getattr(target, "lineno", node.lineno), getattr(target, "col_offset", node.col_offset),
                        f"{msg} (found `{name}`)",
                        task.get("fix")
                    ))
    return findings


def check_file_name_kebab(task: Dict[str, Any], fname: str, code: str) -> List[Finding]:
    tname = task.get("name", "file_name_kebab")
    base = Path(fname).name
    pattern = re.compile(task.get("pattern", r"[a-z0-9]+(?:-[a-z0-9]+)*\\.[A-Za-z0-9]+$"))
    if pattern.fullmatch(base):
        return []
    msg = task.get("message", "File names must be kebab-case.")
    return [Finding(tname, fname, 1, 0, f"{msg} (found `{base}`)", task.get("fix"))]


def check_function_docstring_required(task: Dict[str, Any], fname: str, code: str) -> List[Finding]:
    tname = task.get("name", "function_docstring_required")
    tree, err = ast_parse_or_finding(tname, fname, code)
    if err:
        return [err]
    findings: List[Finding] = []
    msg = task.get("message", "Functions must include docstrings.")
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not ast.get_docstring(node):
                findings.append(Finding(
                    tname, fname, node.lineno, node.col_offset,
                    f"{msg} (function `{node.name}`)",
                    task.get("fix")
                ))
    return findings

# ===================== Runner =========================

CHECK_DISPATCH = {
    "forbid_text": check_forbid_text,
    "require_text": check_require_text,
    "require_function": check_require_function,
    "max_complexity": check_max_complexity,
    "function_name_style": check_function_name_style,
    "require_jwt_auth": check_require_jwt_auth,
    "require_exception_logging": check_require_exception_logging,
    "min_coverage": check_min_coverage,
    "max_function_length": check_max_function_length,
    "class_name_style": check_class_name_style,
    "constant_name_style": check_constant_name_style,
    "file_name_kebab": check_file_name_kebab,
    "function_docstring_required": check_function_docstring_required,
}

def run_checks(tasks_cfg: Dict[str, Any], files: List[Path], repo_root: Path) -> Tuple[List[Finding], Dict[str, Any]]:
    findings: List[Finding] = []
    rules = tasks_cfg.get("rules", [])
    total_rules = len(rules)
    failed_rule_indexes: Set[int] = set()
    passed_rule_names: List[str] = []
    # allow global include/exclude globs at top-level of tasks file
    global_includes = tasks_cfg.get("include", None)
    global_excludes = tasks_cfg.get("exclude", None)

    def included(p: Path) -> bool:
        rel = p.resolve().relative_to(repo_root.resolve()).as_posix()
        if global_includes and not any(fnmatch.fnmatch(rel, pat) for pat in global_includes):
            return False
        if global_excludes and any(fnmatch.fnmatch(rel, pat) for pat in global_excludes):
            return False
        return True

    for p in files:
        if not p.is_file(): continue
        if p.suffix.lower() in TEXT_EXT_BLOCKLIST: continue
        if not included(p): continue
        code = read_text(p)
        file_rel = p.resolve().relative_to(repo_root.resolve()).as_posix()
        for rule_idx, rule in enumerate(rules):
            if not _rule_applies_to_file(rule, file_rel):
                continue
            ctype = rule.get("type")
            fn = CHECK_DISPATCH.get(ctype)
            if not fn:
                findings.append(Finding(rule.get("name", ctype), file_rel, 1, 0, f"Unknown check type: {ctype}", None))
                failed_rule_indexes.add(rule_idx)
                continue
            rule_findings = fn(rule, file_rel, code)
            if rule_findings:
                failed_rule_indexes.add(rule_idx)
            findings.extend(rule_findings)
    for idx, rule in enumerate(rules):
        if idx not in failed_rule_indexes:
            passed_rule_names.append(rule.get("name", rule.get("type", f"rule_{idx}")))
    summary = {
        "total_rules": total_rules,
        "passed_rules": max(0, total_rules - len(failed_rule_indexes)),
        "passed_rule_names": passed_rule_names,
    }
    return findings, summary

def format_human(findings: List[Finding], summary: Dict[str, Any]) -> str:
    all_good = len(findings) == 0
    total_rules = summary.get("total_rules", 0)
    passed_rules = summary.get("passed_rules", 0)
    icon = "✅" if all_good else "❌"
    lines = [f"{icon} ALL_TASKS_MET: {all_good}"]
    lines.append(f"Tasks Passed: {passed_rules}/{total_rules}")
    passed_names = summary.get("passed_rule_names") or []
    if passed_names:
        lines.append("Passed Task Names: " + ", ".join(passed_names))
    lines.append("")
    if not findings:
        return "\n".join(lines)
    for f in findings:
        lines.append(f"- [{f.task}] {f.file}:{f.line}:{f.column} — {f.message}")
        if f.fix:
            lines.append(textwrap.indent("Fix:\n" + f.fix.strip(), "    "))
    return "\n".join(lines)

def main():
    ap = argparse.ArgumentParser(description="Code validator: checks updated/new files against hyper-specific tasks.")
    ap.add_argument("--tasks", required=True, help="Path to tasks file (.yml/.yaml or .json)")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--files", nargs="+", help="Explicit file globs/paths to validate")
    group.add_argument("--git-diff", nargs=2, metavar=("BASE", "HEAD"),
                       help="Validate files changed between two git refs (e.g., origin/main HEAD)")
    ap.add_argument("--json", action="store_true", help="Emit JSON findings instead of human text")
    ap.add_argument("--out-file", help="Write the report to this file instead of stdout")
    args = ap.parse_args()

    repo_root = Path.cwd()
    tasks_cfg = normalize_tasks_config(load_tasks(Path(args.tasks)))

    if args.files:
        # Expand globs
        files = []
        for token in args.files:
            files.extend(Path().glob(token))
        # Dedup
        files = [p for i, p in enumerate(files) if p.is_file() and files.index(p) == i]
    else:
        base, head = args.git_diff
        files = list_changed_files_git(base, head)

    findings, summary = run_checks(tasks_cfg, files, repo_root)
    all_good = len(findings) == 0

    out_file_path = Path(args.out_file) if args.out_file else None
    auto_json = bool(out_file_path and out_file_path.suffix.lower() == ".json" and not args.json)
    want_json = args.json or auto_json

    if want_json:
        out = {
            "ALL_TASKS_MET": all_good,
            "tasks": {
                "passed": summary.get("passed_rules", 0),
                "total": summary.get("total_rules", 0),
                "passed_names": summary.get("passed_rule_names", []),
            },
            "findings": [f.as_dict() for f in findings]
        }
        report = json.dumps(out, indent=2)
    else:
        report = format_human(findings, summary)

    if out_file_path:
        text = report if report.endswith("\n") else report + "\n"
        out_file_path.write_text(text, encoding="utf-8")
        label = "JSON" if want_json else "text"
        print(f"Report written to {out_file_path} ({label})")
    else:
        print(report)

    # process exit code is up to YOU; script returns 0 either way.
    # If you want non-zero on violations, uncomment next two lines:
    # if findings: sys.exit(1)

if __name__ == "__main__":
    main()
