#!/usr/bin/env python3
"""
文档一致性验证脚本

检查代码与文档是否同步。退出码：
  0 = 全部通过
  1 = 存在不一致
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ERRORS = []


def err(category: str, msg: str):
    ERRORS.append(f"[{category}] {msg}")


def warn(category: str, msg: str):
    print(f"  WARN [{category}] {msg}")


# ── 1. 检查 AGENTS.md 中的链接是否指向存在的文件 ──────────────────────

def check_agents_links():
    agents = ROOT / "AGENTS.md"
    if not agents.exists():
        err("LINK", "AGENTS.md 不存在")
        return

    for match in re.finditer(r'\]\(([^)]+)\)', agents.read_text()):
        link = match.group(1)
        if link.startswith("http"):
            continue
        target = ROOT / link
        if not target.exists():
            err("LINK", f"AGENTS.md 中的链接指向不存在的文件: {link}")


# ── 2. 检查 app/routes/ 中的路由是否在 docs/references/api.md 中有记录 ──

def check_api_docs():
    api_doc = ROOT / "docs" / "references" / "api.md"
    if not api_doc.exists():
        err("API", "docs/references/api.md 不存在")
        return

    api_content = api_doc.read_text()

    routes_dir = ROOT / "app" / "routes"
    if not routes_dir.exists():
        return

    for route_file in sorted(routes_dir.glob("*.py")):
        if route_file.name == "__init__.py":
            continue
        content = route_file.read_text()
        # 提取 @router.get/post/put/delete 装饰器中的路径
        for match in re.finditer(
            r'@router\.(get|post|put|delete|websocket)\(\s*["\']([^"\']+)', content
        ):
            method = match.group(1).upper()
            path = match.group(2)
            # 检查文档中是否提到这个端点
            # 允许路径参数差异（{id} vs {request_id}）
            path_pattern = re.sub(r'\{[^}]+\}', r'{[^}]+}', path)
            if not re.search(rf'{method}\s+`?/?{path_pattern}`?', api_content, re.IGNORECASE):
                warn("API", f"{route_file.name}: {method} {path} 未在 api.md 中记录")


# ── 3. 检查模块结构是否与 ARCHITECTURE.md 描述一致 ────────────────────

def check_architecture():
    arch = ROOT / "ARCHITECTURE.md"
    if not arch.exists():
        err("ARCH", "ARCHITECTURE.md 不存在")
        return

    # 检查 modules/ 下的子包是否都在 ARCHITECTURE.md 中被提及
    modules_dir = ROOT / "modules"
    if not modules_dir.exists():
        return

    arch_content = arch.read_text()
    for subdir in sorted(modules_dir.iterdir()):
        if subdir.is_dir() and not subdir.name.startswith("_"):
            if subdir.name not in arch_content:
                err("ARCH", f"模块 modules/{subdir.name}/ 未在 ARCHITECTURE.md 中描述")


# ── 4. 检查 docs/ 下的文件是否都在索引中注册 ──────────────────────────

def check_doc_index():
    docs_dir = ROOT / "docs"
    if not docs_dir.exists():
        return

    # 收集所有 .md 和 .txt 文件
    doc_files = set()
    for f in docs_dir.rglob("*"):
        if f.is_file() and f.suffix in (".md", ".txt"):
            rel = f.relative_to(docs_dir)
            doc_files.add(str(rel))

    # 检查每个目录的 index.md
    for subdir in sorted(docs_dir.iterdir()):
        if not subdir.is_dir():
            continue
        index = subdir / "index.md"
        if not index.exists():
            warn("INDEX", f"docs/{subdir.name}/ 没有 index.md")
            continue

        index_content = index.read_text()
        for f in sorted(subdir.iterdir()):
            if f.is_file() and f.name != "index.md":
                if f.name not in index_content:
                    warn("INDEX", f"docs/{subdir.name}/{f.name} 未在 index.md 中注册")


# ── 5. 检查 AGENTS.md 中描述的领域模块是否在 modules/ 中存在 ────────────

def check_agents_modules():
    agents = ROOT / "AGENTS.md"
    if not agents.exists():
        return

    modules_dir = ROOT / "modules"
    if not modules_dir.exists():
        return

    # 检查 AGENTS.md 中提到的模块路径
    for match in re.finditer(r'modules/(\w+)/', agents.read_text()):
        module_name = match.group(1)
        if not (modules_dir / module_name).is_dir():
            err("MODULE", f"AGENTS.md 引用的模块 modules/{module_name}/ 不存在")


# ── 6. 检查 CLAUDE.md 中引用的脚本是否存在 ─────────────────────────────

def check_claude_md():
    claude = ROOT / "CLAUDE.md"
    if not claude.exists():
        return

    for match in re.finditer(r'`([^`]+\.py)`', claude.read_text()):
        script = match.group(1)
        # 跳过含空格的命令行示例（如 `python scripts/verify_docs.py`）
        if " " in script:
            continue
        if not (ROOT / script).exists():
            err("CLAUDE", f"CLAUDE.md 引用的脚本 {script} 不存在")


# ── 7. 检查文档中的已废弃路径和引用 ───────────────────────────────────

DEPRECATED_PATHS = {
    "data/events.jsonl": "data/logs/demo_events.jsonl",
    "docs/design/": "docs/design-docs/",
    "docs/plans/": "docs/exec-plans/",
    "docs/reference/": "docs/references/",
    "docs/operations/": "已删除",
    "docs/WORKLOG.md": "已删除",
    "PROJECT_MEMORY.md": "已删除",
}

DEPRECATED_PORTS = {
    "8002": "8010（YOLO API 默认端口）",
    "8501": "5173（Vite 默认端口）",
}

DOC_FILES_TO_CHECK = [
    "README.md", "AGENTS.md", "ARCHITECTURE.md", "DESIGN.md",
    "FRONTEND.md", "PLANS.md", "PRODUCT_SENSE.md", "QUALITY_SCORE.md",
    "RELIABILITY.md", "SECURITY.md",
]


def check_deprecated_refs():
    for doc_name in DOC_FILES_TO_CHECK:
        doc_path = ROOT / doc_name
        if not doc_path.exists():
            continue
        content = doc_path.read_text()

        # 检查废弃路径
        for old, new in DEPRECATED_PATHS.items():
            if old in content:
                err("DEPRECATED", f"{doc_name} 引用了已废弃的路径 '{old}'，应为 '{new}'")

        # 检查废弃端口（仅在非历史记录上下文中）
        for old_port, new_port in DEPRECATED_PORTS.items():
            # 匹配 "端口 8002" 或 ":8002" 格式
            if re.search(rf'(?:端口|port|:)\s*{old_port}\b', content, re.IGNORECASE):
                err("DEPRECATED", f"{doc_name} 引用了已废弃的端口 {old_port}，应为 {new_port}")


# ── 8. 检查 docs/ 子目录文档中的废弃引用 ─────────────────────────────

def check_deprecated_in_docs():
    docs_dir = ROOT / "docs"
    if not docs_dir.exists():
        return

    for f in docs_dir.rglob("*.md"):
        content = f.read_text()
        rel = f.relative_to(ROOT)
        for old, new in DEPRECATED_PATHS.items():
            if old in content:
                err("DEPRECATED", f"{rel} 引用了已废弃的路径 '{old}'，应为 '{new}'")


# ── 9. 检查 API 文档中是否包含代码中的实际路由（含 app.get/app.websocket） ──

def check_api_routes_full():
    """检查 app/routes/ 中通过 app.get/post/websocket 注册的路由"""
    api_doc = ROOT / "docs" / "references" / "api.md"
    if not api_doc.exists():
        return

    api_content = api_doc.read_text()
    routes_dir = ROOT / "app" / "routes"
    if not routes_dir.exists():
        return

    for route_file in sorted(routes_dir.glob("*.py")):
        if route_file.name == "__init__.py":
            continue
        content = route_file.read_text()
        # 匹配 app.get/post/websocket 注册
        for match in re.finditer(
            r'app\.(get|post|put|delete|websocket)\(\s*["\']([^"\']+)', content
        ):
            method = match.group(1).upper()
            path = match.group(2)
            # 跳过 /api/ 前缀的重复路由
            if path.startswith("/api/"):
                continue
            path_pattern = re.sub(r'\{[^}]+\}', r'\\{[^}]+\\}', path)
            if not re.search(rf'{method}\s+`?/?{path_pattern}`?', api_content, re.IGNORECASE):
                warn("API", f"{route_file.name}: {method} {path} 未在 api.md 中记录")


# ── 主函数 ─────────────────────────────────────────────────────────────

def main():
    print("牧野文档一致性验证\n")

    checks = [
        ("AGENTS.md 链接", check_agents_links),
        ("API 文档覆盖", check_api_docs),
        ("API 路由完整", check_api_routes_full),
        ("架构描述一致", check_architecture),
        ("文档索引完整", check_doc_index),
        ("模块引用有效", check_agents_modules),
        ("CLAUDE.md 引用", check_claude_md),
        ("废弃路径/端口", check_deprecated_refs),
        ("子文档废弃引用", check_deprecated_in_docs),
    ]

    for name, fn in checks:
        print(f"检查: {name}")
        fn()

    print()
    if ERRORS:
        print(f"发现 {len(ERRORS)} 个问题:\n")
        for e in ERRORS:
            print(f"  ERROR {e}")
        sys.exit(1)
    else:
        print("全部通过。")
        sys.exit(0)


if __name__ == "__main__":
    main()
