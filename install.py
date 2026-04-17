#!/usr/bin/env python3
import os, sys, shutil, subprocess
from pathlib import Path

R     = "\033[0m"
BOLD  = "\033[1m"
GREEN = "\033[38;5;121m"
CYAN  = "\033[38;5;116m"
LILA  = "\033[38;5;183m"
GRAY  = "\033[38;5;246m"
RED   = "\033[38;5;203m"
YEL   = "\033[38;5;228m"

def p(color, msg): print(f"  {color}{msg}{R}")
def ok(msg):  p(GREEN, f"✓  {msg}")
def err(msg): p(RED,   f"✗  {msg}"); sys.exit(1)
def info(msg):p(LILA,  f"·  {msg}")
def hdr(msg): print(f"\n{CYAN}{BOLD}{msg}{R}\n")

SCRIPT_DIR = Path(__file__).parent.resolve()
RTCAI_DIR  = Path.home() / ".rtcai"

def install_deps():
    hdr("Installing dependencies")
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        p(YEL, f"pip warning: {r.stderr[:100]}")
    else:
        ok("python-dotenv installed")

def setup_dir():
    hdr("Setting up ~/.rtcai")
    RTCAI_DIR.mkdir(parents=True, exist_ok=True)
    ok(f"Directory: {RTCAI_DIR}")

    env_target = RTCAI_DIR / ".env"
    if not env_target.exists():
        shutil.copy(SCRIPT_DIR / ".env.example", env_target)
        ok(f"Config created: {env_target}")
        p(YEL, f"Edit {env_target} and add your GROQ_API_KEY")
    else:
        info(f"Config exists: {env_target}")

    sys_target = RTCAI_DIR / "system.txt"
    src_sys    = SCRIPT_DIR / "system.txt"
    if not sys_target.exists() and src_sys.exists():
        shutil.copy(src_sys, sys_target)
        ok(f"System prompt: {sys_target}")

    ctx = RTCAI_DIR / "ctx.json"
    if not ctx.exists():
        ctx.write_text("[]")
        ok(f"Context file:  {ctx}")

def install_script():
    hdr("Installing ai command")
    target = Path.home() / ".local" / "bin" / "ai"
    target.parent.mkdir(parents=True, exist_ok=True)

    ai_py = SCRIPT_DIR / "ai.py"
    shutil.copy(ai_py, target)
    target.chmod(0o755)
    ok(f"Installed: {target}")

    lines = target.read_text().splitlines()
    lines[0] = f"#!{sys.executable}"
    target.write_text("\n".join(lines))

def detect_shell():
    shell = os.environ.get("SHELL", "")
    if "zsh"  in shell: return "zsh",  Path.home() / ".zshrc"
    if "bash" in shell: return "bash", Path.home() / ".bashrc"
    
    if (Path.home() / ".zshrc").exists():  return "zsh",  Path.home() / ".zshrc"
    return "bash", Path.home() / ".bashrc"

ALIAS_MARKER = "# rtcai-alias"
ALIAS_BLOCK  = (
    "\n# rtcai-alias — added by rtcai installer\n"
    'export PATH="$HOME/.local/bin:$PATH"\n'
    "alias ai='ai'\n"
)

def inject_alias():
    hdr("Shell integration")
    shell_name, rc = detect_shell()
    info(f"Detected shell: {shell_name}  ({rc})")

    if rc.exists():
        content = rc.read_text()
        if ALIAS_MARKER in content:
            ok("Alias already present")
            return
    print(f"\n  {YEL}Add the following to {rc}?{R}")
    print(f"{GRAY}{ALIAS_BLOCK}{R}")
    ans = input(f"  {LILA}Inject? [y/N]{R} ").strip().lower()
    if ans in ("y", "yes"):
        with open(rc, "a") as f: f.write(ALIAS_BLOCK)
        ok(f"Injected into {rc}")
        p(YEL, f"Run:  source {rc}")
    else:
        info("Skipped. Add manually:")
        print(f"{GRAY}{ALIAS_BLOCK}{R}")

def check_api_key():
    hdr("API Key check")
    env = RTCAI_DIR / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("GROQ_API_KEY=") and len(line) > 20 and "your_groq" not in line:
                ok("GROQ_API_KEY found in .env")
                return
    p(YEL, f"Set GROQ_API_KEY in {RTCAI_DIR}/.env")

def main():
    print(f"\n{CYAN}{BOLD}  ┌─────────────────────────────┐{R}")
    print(f"{CYAN}{BOLD}  │  rtcai  installer           │{R}")
    print(f"{CYAN}{BOLD}  │  llama · groq · terminal    │{R}")
    print(f"{CYAN}{BOLD}  └─────────────────────────────┘{R}")

    install_deps()
    setup_dir()
    install_script()
    inject_alias()
    check_api_key()

    print(f"\n{GREEN}{BOLD}  All done.{R}")
    print(f"  {GRAY}Try:{R}  {CYAN}ai Hello!{R}")
    print(f"  {GRAY}Or:{R}   {CYAN}ai long{R}\n")

if __name__ == "__main__":
    main()
