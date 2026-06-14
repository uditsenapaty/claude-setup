#!/usr/bin/env python3
"""
claude-setup.py — one-shot local setup for a Claude Code research project.

What it does:
  1. Creates .claude/skills/ in the current project.
  2. Clones the 5 skill repos (gstack, gsd, superpowers, anthropic, custom-skills),
     hoisting the ones that ship their skills inside a subfolder.
  3. Runs gstack's ./setup (POSIX only).
  4. Installs the global codebase tools:
       - graphify            -> a uv/pip CLI tool (package: graphifyy, command: graphify)
       - understand-anything -> a Claude Code PLUGIN (added via a marketplace, not a PATH binary)

Safe to re-run. By default it skips a repo whose folder already exists; pass --force to re-clone.
Cross-platform (Linux / macOS / Windows). Tool install is non-fatal: if it can't finish a step it
prints the exact manual commands and keeps going.

Usage:
    python claude-setup.py                 # full setup
    python claude-setup.py --force         # re-clone all repos
    python claude-setup.py --skip-global   # repos only, no global tools
    python claude-setup.py --skip-clone    # global tools only
    python claude-setup.py --root /path    # target a different project root
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path

IS_WIN = platform.system() == "Windows"

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────────────────────

GIT_FLAGS = ["--single-branch", "--depth", "1"]

# Each repo: (folder_name, git_url, hoist_subdir_or_None, run_setup_bool)
REPOS = [
    ("gstack",       "https://github.com/garrytan/gstack.git",            None,     True),
    ("gsd",          "https://github.com/open-gsd/gsd-core.git",          None,     False),
    ("superpowers",  "https://github.com/obra/superpowers.git",           None,     False),
    ("anthropic",    "https://github.com/anthropics/skills.git",          "skills", False),
    # Your own repo. Your original command pointed at ".../claude-setup/custom-skills.git",
    # which isn't a valid clone URL — clone the repo and hoist its top-level `skills/` folder:
    ("custom-skills","https://github.com/UzzyDizzy/claude-setup.git",     "skills", False),
]

# Global tools have two different shapes now:
#   kind="uv_tool"       -> installed via uv (preferred) or pip; detected on PATH by `check`.
#   kind="claude_plugin" -> a Claude Code plugin added from a marketplace URL; NOT a PATH binary.
GLOBAL_TOOLS = {
    "graphify": {
        "kind": "uv_tool",
        "package": "graphifyy",           # PyPI/uv package name (note the double y)
        "check": "graphify",              # executable name after install
        "post_install": ["graphify", "install"],   # run once after a fresh install; or None
        "manual": [
            "uv tool install graphifyy        (or: pip install graphifyy)",
            "graphify install",
        ],
    },
    "understand-anything": {
        "kind": "claude_plugin",
        "plugin": "understand-anything",
        "marketplace_url": "https://github.com/Egonex-AI/Understand-Anything.git",
        "manual": [
            "Open Claude Code in a terminal (run: claude), then:",
            "  /plugin marketplace add https://github.com/Egonex-AI/Understand-Anything.git",
            "  /plugin install understand-anything",
        ],
    },
}

# ──────────────────────────────────────────────────────────────────────────────
# Logging helpers (plain tags — no color deps, works in every terminal)
# ──────────────────────────────────────────────────────────────────────────────

def log(tag: str, msg: str) -> None:
    print(f"[{tag:^4}] {msg}", flush=True)

def ok(m):   log("OK", m)
def skip(m): log("SKIP", m)
def warn(m): log("WARN", m)
def fail(m): log("FAIL", m)
def step(m): print(f"\n=== {m} ===", flush=True)

def print_manual(name: str, lines: list[str]) -> None:
    warn(f"{name}: finish manually —")
    for ln in lines:
        print("        " + ln, flush=True)


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> int:
    """Run a command, streaming output. Returns the exit code."""
    printable = " ".join(cmd)
    log("RUN", printable + (f"   (cwd={cwd})" if cwd else ""))
    try:
        proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None)
    except FileNotFoundError:
        fail(f"command not found: {cmd[0]}")
        if check:
            raise
        return 127
    if check and proc.returncode != 0:
        fail(f"exited {proc.returncode}: {printable}")
        raise subprocess.CalledProcessError(proc.returncode, cmd)
    return proc.returncode


def require_git() -> None:
    if shutil.which("git") is None:
        fail("git is not installed or not on PATH. Install git and re-run.")
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# Executable resolution (handles tools installed off the current PATH)
# ──────────────────────────────────────────────────────────────────────────────

def script_dirs() -> list[Path]:
    """Dirs where pip / uv console scripts commonly land for this interpreter + user."""
    cands: list[str] = []
    try:
        cands.append(sysconfig.get_path("scripts"))
    except Exception:
        pass
    try:
        cands.append(sysconfig.get_path("scripts", f"{os.name}_user"))
    except Exception:
        pass
    home = Path.home()
    cands.append(str(home / ".local" / "bin"))          # uv tool bin (Unix) + pip --user (Unix)
    if IS_WIN:
        cands.append(str(home / ".local" / "bin"))      # uv tool bin (Windows)
        appdata = os.environ.get("APPDATA")
        if appdata:
            cands.append(str(Path(appdata) / "Python" / "Scripts"))
    # de-dup, drop blanks
    seen, out = set(), []
    for c in cands:
        if c and c not in seen:
            seen.add(c); out.append(Path(c))
    return out


def find_executable(name: str) -> str | None:
    """which(), then scan known script dirs (adding .exe on Windows)."""
    p = shutil.which(name)
    if p:
        return p
    exe = name + (".exe" if IS_WIN else "")
    for d in script_dirs():
        cand = d / exe
        if cand.exists():
            return str(cand)
    return None


def pip(*args: str, check: bool = False) -> int:
    """Always use the pip tied to THIS interpreter (avoids the wrong pip)."""
    return run([sys.executable, "-m", "pip", *args], check=check)


def ensure_uv() -> str | None:
    """Return a usable uv path, bootstrapping it if needed (pip, then official installer)."""
    uv = find_executable("uv")
    if uv:
        return uv
    log("INFO", "uv not found — bootstrapping (pip)")
    pip("install", "--upgrade", "uv")
    uv = find_executable("uv")
    if uv:
        return uv
    # PEP 668 / externally-managed envs can block pip — fall back to the standalone installer.
    log("INFO", "uv still missing — trying the official standalone installer")
    if IS_WIN:
        run(["powershell", "-NoProfile", "-ExecutionPolicy", "ByPass", "-Command",
             "irm https://astral.sh/uv/install.ps1 | iex"], check=False)
    else:
        run(["sh", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"], check=False)
    return find_executable("uv")


# ──────────────────────────────────────────────────────────────────────────────
# Global tool installers
# ──────────────────────────────────────────────────────────────────────────────

def install_uv_tool(name: str, spec: dict) -> None:
    check = spec["check"]
    if find_executable(check):
        skip(f"{name}: already installed ({check} found)")
        return

    pkg = spec["package"]
    installed = False

    uv = ensure_uv()
    if uv:
        if run([uv, "tool", "install", pkg], check=False) == 0:
            run([uv, "tool", "update-shell"], check=False)   # put uv's tool bin on PATH (future shells)
            installed = find_executable(check) is not None
    else:
        warn(f"{name}: uv unavailable, will try pip")

    if not installed:
        warn(f"{name}: trying 'pip install {pkg}'")
        pip("install", "--upgrade", pkg)
        installed = find_executable(check) is not None

    if not installed:
        fail(f"{name}: could not install '{pkg}'.")
        print_manual(name, spec["manual"])
        return

    exe = find_executable(check)
    ok(f"{name}: installed ({exe})")

    if spec.get("post_install"):
        cmd = list(spec["post_install"])
        cmd[0] = exe  # call by resolved absolute path so PATH gaps don't matter
        code = run(cmd, check=False)
        (ok if code == 0 else warn)(f"{name}: post-install '{' '.join(spec['post_install'])}' exited {code}")

    if shutil.which(check) is None:
        warn(f"{name}: '{check}' installed but not on the CURRENT PATH ({exe}). "
             f"Open a new terminal (uv updated the shell profile) or add that dir to PATH.")


def claude_plugin_installed(plugin: str) -> bool:
    claude = shutil.which("claude")
    if claude:
        try:
            out = subprocess.run([claude, "plugin", "list"],
                                 capture_output=True, text=True, timeout=30)
            if out.returncode == 0 and plugin in (out.stdout or ""):
                return True
        except Exception:
            pass
    # shallow scan of the plugin cache as a fallback
    base = Path.home() / ".claude" / "plugins"
    if base.exists():
        try:
            for depth1 in base.iterdir():
                if plugin in depth1.name:
                    return True
                if depth1.is_dir():
                    for depth2 in depth1.iterdir():
                        if plugin in depth2.name:
                            return True
        except Exception:
            pass
    return False


def install_claude_plugin(name: str, spec: dict) -> None:
    plugin = spec["plugin"]
    if claude_plugin_installed(plugin):
        skip(f"{name}: plugin already installed")
        return

    claude = shutil.which("claude")
    if not claude:
        warn(f"{name}: this is a Claude Code plugin and the 'claude' CLI isn't on PATH "
             f"({'on Windows, Claude Code runs under WSL — run these inside WSL' if IS_WIN else 'install Claude Code first'}).")
        print_manual(name, spec["manual"])
        return

    # Non-interactive CLI subcommands exist in recent Claude Code; fall back to manual if not.
    c1 = run([claude, "plugin", "marketplace", "add", spec["marketplace_url"]], check=False)
    c2 = run([claude, "plugin", "install", plugin], check=False) if c1 == 0 else 1
    if c1 == 0 and c2 == 0:
        ok(f"{name}: plugin installed via claude CLI")
    else:
        warn(f"{name}: 'claude plugin' subcommands unavailable or failed on this version.")
        print_manual(name, spec["manual"])


def install_global_tool(name: str, spec: dict) -> None:
    kind = spec.get("kind")
    if kind == "uv_tool":
        install_uv_tool(name, spec)
    elif kind == "claude_plugin":
        install_claude_plugin(name, spec)
    else:
        fail(f"{name}: unknown tool kind '{kind}' — skipping")


# ──────────────────────────────────────────────────────────────────────────────
# Repo cloning
# ──────────────────────────────────────────────────────────────────────────────

def is_nonempty_dir(p: Path) -> bool:
    return p.is_dir() and any(p.iterdir())


def clone_repo(name: str, url: str, hoist: str | None, run_setup: bool,
               skills_dir: Path, force: bool) -> None:
    dest = skills_dir / name

    if is_nonempty_dir(dest):
        if not force:
            skip(f"{name} already present at {dest} (use --force to re-clone)")
            return
        warn(f"--force: removing existing {dest}")
        shutil.rmtree(dest, ignore_errors=True)

    if hoist:
        with tempfile.TemporaryDirectory(prefix=f"{name}-") as tmp:
            tmp_path = Path(tmp) / "repo"
            run(["git", "clone", *GIT_FLAGS, url, str(tmp_path)])
            src = tmp_path / hoist
            if not src.is_dir():
                fail(f"{name}: expected '{hoist}/' inside the repo but it's missing — "
                     f"check the repo layout / URL.")
                return
            shutil.copytree(src, dest)
        ok(f"{name}: hoisted '{hoist}/' -> {dest}")
    else:
        run(["git", "clone", *GIT_FLAGS, url, str(dest)])
        ok(f"{name}: cloned -> {dest}")

    if run_setup:
        run_gstack_setup(dest)


def run_gstack_setup(repo_dir: Path) -> None:
    """gstack ships a POSIX ./setup. Run it on Unix; warn on Windows."""
    setup = repo_dir / "setup"
    if not setup.exists():
        skip("gstack: no ./setup found, nothing to run")
        return
    if IS_WIN:
        warn("gstack: ./setup is a POSIX script — run it from Git Bash / WSL manually:")
        warn(f"      cd {repo_dir} && ./setup")
        return
    try:
        os.chmod(setup, 0o755)
    except OSError:
        pass
    sh = shutil.which("bash") or shutil.which("sh") or "sh"
    code = run([sh, "./setup"], cwd=repo_dir, check=False)
    (ok if code == 0 else warn)(f"gstack ./setup exited {code}")


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Set up Claude Code skills + global tools.")
    ap.add_argument("--root", default=".", help="project root (default: current dir)")
    ap.add_argument("--force", action="store_true", help="re-clone repos that already exist")
    ap.add_argument("--skip-clone", action="store_true", help="don't clone skill repos")
    ap.add_argument("--skip-global", action="store_true", help="don't install global tools")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    skills_dir = root / ".claude" / "skills"

    step(f"Project root: {root}")
    skills_dir.mkdir(parents=True, exist_ok=True)
    ok(f"ensured {skills_dir}")

    if not args.skip_clone:
        require_git()
        step("Cloning skill repos")
        for name, url, hoist, run_setup in REPOS:
            try:
                clone_repo(name, url, hoist, run_setup, skills_dir, args.force)
            except subprocess.CalledProcessError:
                fail(f"{name}: clone failed — continuing with the rest")
    else:
        skip("clone step skipped (--skip-clone)")

    if not args.skip_global:
        step("Global tools (graphify = uv tool · understand-anything = Claude Code plugin)")
        for name, spec in GLOBAL_TOOLS.items():
            install_global_tool(name, spec)
    else:
        skip("global-tool step skipped (--skip-global)")

    step("Done")
    ok("Skills are under .claude/skills/. Start research by invoking ml-research-queries.")
    print("    If a tool printed a 'finish manually' block, run those lines once in a new shell.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
