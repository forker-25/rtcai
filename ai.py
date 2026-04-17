#!/usr/bin/env python3
import os, sys, json, time, re, subprocess, uuid, asyncio, readline
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path.home() / ".rtcai" / ".env")

GROQ_KEY   = os.getenv("GROQ_API_KEY", "")
MODEL      = os.getenv("MODEL", "llama-3.3-70b-versatile")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1024"))
CTX_FILE   = os.getenv("CTX_FILE", str(Path.home() / ".rtcai" / "ctx.json"))
SYS_FILE   = os.getenv("SYS_PROMPT_FILE", str(Path(__file__).parent / "system.txt"))

R    = "\033[0m"
BOLD = "\033[1m"

C = {
    "cyan":     "\033[38;5;116m",
    "mint":     "\033[38;5;121m",
    "rose":     "\033[38;5;217m",
    "peach":    "\033[38;5;223m",
    "lavender": "\033[38;5;183m",
    "sky":      "\033[38;5;153m",
    "sand":     "\033[38;5;222m",
    "sage":     "\033[38;5;150m",
    "lilac":    "\033[38;5;189m",
    "gray":     "\033[38;5;246m",
    "white":    "\033[38;5;255m",
    "yellow":   "\033[38;5;228m",
    "red":      "\033[38;5;203m",
    "green":    "\033[38;5;156m",
}

AI_COLORS = ["cyan", "mint", "sky", "lavender", "peach", "sage", "lilac", "rose"]

def nc(name):          return C.get(name, "")
def colored(t, name):  return f"{nc(name)}{t}{R}"

def spinner(label="Thinking", color="lavender"):
    frames = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    sys.stdout.write("\n")
    for i in range(14):
        sys.stdout.write(f"\r  {nc(color)}{frames[i%len(frames)]}{R}  {nc('gray')}{label}...{R}   ")
        sys.stdout.flush()
        time.sleep(0.08)
    sys.stdout.write("\r" + " "*42 + "\r")
    sys.stdout.flush()

def load_ctx():
    try:
        with open(CTX_FILE) as f: return json.load(f)
    except: return []

def save_ctx(ctx):
    Path(CTX_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(CTX_FILE, "w") as f: json.dump(ctx, f, ensure_ascii=False, indent=2)

def clear_ctx(): save_ctx([])

DEFAULT_SYS = """You are a concise, friendly, formal terminal AI assistant named rtcai.

Rules:
- Be brief. 1-3 sentences max unless asked for detail.
- No LaTeX. No markdown symbols (* # ` _ ~ etc).
- No emojis or emoticons.
- Use only \\n for line breaks, never markdown.
- Formal but warm tone.
- In code: short names, no comments unless critical, minimal lines.

You can perform actions using tags (only when user explicitly asks):

Run a shell command:
  rtcai25:"<command>"

Create a file:
  ctfai25:"<content>","<extension>"

Use tags only for real actions. After a tag, confirm briefly in plain text.
You will see outputs of last 5 commands for context.
Answer in user language."""

def load_sys():
    try:
        with open(SYS_FILE) as f: return f.read().strip()
    except: return DEFAULT_SYS

CMD_HIST: list[dict] = []

def add_cmd(cmd, out, ok):
    CMD_HIST.append({"cmd": cmd, "out": out[:500], "ok": ok})
    if len(CMD_HIST) > 5: CMD_HIST.pop(0)

def cmd_hist_str():
    if not CMD_HIST: return ""
    lines = ["Last commands:"]
    for h in CMD_HIST:
        s = "ok" if h["ok"] else "err"
        lines.append(f"  [{s}] $ {h['cmd']}\n       {h['out'][:120]}")
    return "\n".join(lines)

async def ask_groq_async(messages):
    if not GROQ_KEY:
        return None, "GROQ_API_KEY not set. Check ~/.rtcai/.env", 0, 0

    try:
        import aiohttp
    except ImportError:
        return None, "aiohttp not installed. Run: pip install aiohttp", 0, 0

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type":  "application/json",
        "User-Agent":    "rtcai/1.0",
    }
    payload = {
        "model":      MODEL,
        "max_tokens": MAX_TOKENS,
        "messages":   messages,
    }

    t0 = time.time()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                elapsed = time.time() - t0
                data = await resp.json()
                if resp.status != 200:
                    err = data.get("error", {})
                    msg = err.get("message", str(data)) if isinstance(err, dict) else str(err)
                    return None, f"HTTP {resp.status}: {msg}", 0, 0
                text   = data["choices"][0]["message"]["content"]
                tokens = data.get("usage", {}).get("completion_tokens", 0)
                return text, None, elapsed, tokens
    except asyncio.TimeoutError:
        return None, "Request timed out", 0, 0
    except Exception as e:
        return None, str(e), 0, 0

def ask_groq(messages):
    return asyncio.run(ask_groq_async(messages))

RUN_RE  = re.compile(r'rtcai25:"([^"]*)"')
FILE_RE = re.compile(r'ctfai25:"((?:[^"\\]|\\.)*)","([^"]*)"')

def handle_run(cmd):
    print(f"\n{nc('yellow')}  ┌ Command from AI{R}")
    print(f"{nc('yellow')}  │{R} {nc('white')}{cmd}{R}")
    ans = input(f"{nc('yellow')}  └ Execute? [y/N]{R} ").strip().lower()
    if ans in ("y", "yes"):
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            out = (r.stdout + r.stderr).strip()
            ok  = r.returncode == 0
            print(f"  {colored('✓ done', 'green') if ok else colored('✗ error', 'red')}")
            if out: print(f"{nc('gray')}{out[:600]}{R}\n")
            add_cmd(cmd, out, ok)
            return out, ok
        except subprocess.TimeoutExpired:
            print(colored("  Timeout.", "red"))
            add_cmd(cmd, "timeout", False)
            return "timeout", False
    print(colored("  Skipped.", "gray"))
    return "", False

def handle_file(content, ext):
    fname = f"file_{int(time.time())}.{ext}"
    print(f"\n{nc('lavender')}  ┌ Create file from AI: {nc('white')}{fname}{R}")
    ans = input(f"{nc('lavender')}  └ Write? [y/N]{R} ").strip().lower()
    if ans in ("y", "yes"):
        clean = content.replace("\\n", "\n").replace('\\"', '"')
        with open(fname, "w") as f: f.write(clean)
        print(colored(f"  Written: {fname}", "green"))
        return fname
    print(colored("  Skipped.", "gray"))
    return None

def process_tags(text):
    results = []
    for m in RUN_RE.finditer(text):
        out, _ = handle_run(m.group(1))
        if out: results.append(f"Command output: {out}")
    for m in FILE_RE.finditer(text):
        handle_file(m.group(1), m.group(2))
    clean = FILE_RE.sub("", RUN_RE.sub("", text)).strip()
    return clean, "\n".join(results)

EDIT_RE = re.compile(r'^edit:"([^"]+)"\s*,\s*"((?:[^"\\]|\\.)*)"', re.I)

def try_edit(inp, ctx):
    m = EDIT_RE.match(inp.strip())
    if not m: return False
    mid, val = m.group(1), m.group(2).replace("\\n", "\n")
    for msg in ctx:
        if msg.get("id") == mid:
            msg["content"] = val
            save_ctx(ctx)
            print(colored(f"  Message {mid} updated.", "mint"))
            return True
    print(colored(f"  ID {mid} not found.", "red"))
    return True

def stream_words(text, prefix="  → "):
    sys.stdout.write(f"{nc('cyan')}{prefix}{R}")
    for i, w in enumerate(text.split(" ")):
        col = AI_COLORS[i % len(AI_COLORS)]
        sys.stdout.write(f"{nc(col)}{w}{R} ")
        sys.stdout.flush()
        time.sleep(0.017)
    print()

def print_single(text, elapsed, tokens):
    clean, _ = process_tags(text)
    print(f"\n{nc('gray')}  Responded in {elapsed:.2f}s")
    print(f"  Tokens: {tokens}{R}")
    print(f"{nc('cyan')}  {'╌'*30}{R}")
    stream_words(clean, "  → ")
    print()
    return clean

def print_long(text, elapsed, tokens):
    clean, _ = process_tags(text)
    print(f"\n{nc('gray')}  R: {elapsed:.2f}s   T: {tokens}{R}")
    print(f"{nc('cyan')}  {'╌'*30}{R}")
    stream_words(clean, "  AI: ")
    return clean

def build_msgs(ctx, user_msg):
    sys_p = load_sys()
    hist  = cmd_hist_str()
    if hist: sys_p += "\n\n" + hist
    msgs = [{"role": "system", "content": sys_p}]
    for m in ctx[-20:]:
        msgs.append({"role": m["role"], "content": m["content"]})
    msgs.append({"role": "user", "content": user_msg})
    return msgs

def mode_single(query):
    print(f"\n  {nc('lavender')}◆{R} {nc('white')}{query}{R}")
    ctx  = load_ctx()
    msgs = build_msgs(ctx, query)
    spinner()
    text, err, elapsed, tokens = ask_groq(msgs)
    if err:
        print(f"\n  {nc('red')}Error:{R} {err}\n")
        return
    clean  = print_single(text, elapsed, tokens)
    print(f"  {R}\n")

HEADER = (
    f"\n{nc('cyan')}╭{'─'*52}╮{R}\n"
    f"{nc('cyan')}│{R}  {nc('lavender')}{BOLD}rtcai{R}  {nc('gray')}· long session{R}{' '*31}{nc('cyan')}│{R}\n"
    f"{nc('cyan')}│{R}  {nc('gray')}:!q  exit   clear  new context   edit:\"id\",\"txt\"{R}  {nc('cyan')}│{R}\n"
    f"{nc('cyan')}╰{'─'*52}╯{R}\n"
)

def mode_long(first=None):
    print(HEADER)
    ctx = load_ctx()
    while True:
        try:
            if first:
                user_in = first; first = None
                print(f"  {nc('peach')}You:{R} {user_in}")
            else:
                sys.stdout.write(f"  {nc('peach')}You:{R} ")
                sys.stdout.flush()
                user_in = input().strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{nc('gray')}  bye.{R}\n"); break

        if not user_in: continue
        if user_in.lower() in (":!q", "exit", "quit"):
            print(f"\n{nc('gray')}  bye.{R}\n"); break
        if user_in.lower() == "clear":
            clear_ctx(); ctx = []
            print(colored("  Context cleared.", "mint")); continue
        if try_edit(user_in, ctx): continue

        msgs = build_msgs(ctx, user_in)
        spinner()
        text, err, elapsed, tokens = ask_groq(msgs)
        if err:
            print(f"\n  {nc('red')}Error:{R} {err}\n"); continue

        clean  = print_long(text, elapsed, tokens)
        msg_id = str(uuid.uuid4())[:8]
        ctx.append({"role": "user",      "content": user_in, "id": msg_id})
        ctx.append({"role": "assistant", "content": clean,   "id": str(uuid.uuid4())[:8]})
        save_ctx(ctx)
        print(f"\n  {nc('gray')}ID: {msg_id}{R}\n")

def main():
    args = sys.argv[1:]
    if not args:
        print(f"\n  {nc('gray')}Usage:{R}  {nc('cyan')}ai{R} <message>")
        print(f"         {nc('cyan')}ai long{R} [message]\n")
        sys.exit(0)
    if args[0].lower() == "long":
        mode_long(" ".join(args[1:]) or None)
    else:
        mode_single(" ".join(args))

if __name__ == "__main__":
    main()

