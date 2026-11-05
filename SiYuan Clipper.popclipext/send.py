#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""PopClip -> SiYuan Note.

Writes the selected text to a SiYuan document through the built-in
SiYuan-Kernel CLI. No HTTP API, no API token, no network access.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

LOG_PATH = os.path.expanduser("~/Library/Logs/PopClip-Siyuan.log")
DEFAULT_CLI = "/Applications/SiYuan.app/Contents/Resources/kernel/SiYuan-Kernel"
ID_RE = re.compile(r"\d{14}-[a-z0-9]{7}")

# PopClip modifier flag values (see dev docs "Script variables / Modifier values").
MODIFIER_MASKS = (
    (("option", "opt", "alt", "⌥"), 524288),
    (("command", "cmd", "⌘"), 1048576),
    (("control", "ctrl", "⌃"), 262144),
    (("shift", "⇧"), 131072),
)

# Apps that typically produce hard line breaks when text is copied.
BUILTIN_PDF_KEYWORDS = (
    "preview", "预览", "skim", "pdf expert", "pdfexpert", "acrobat",
    "adobe reader", "foxit", "福昕", "zotero", "pdf", "okular", "mupdf",
)
INLINE_SPECIAL = set(r"\`*_{}[]()<>|~$")


def env(name, default=""):
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def opt(name, default=""):
    return env("POPCLIP_OPTION_" + name.upper(), default)


def flag(name, default="0"):
    return str(opt(name, default)).strip().lower() in ("1", "true", "yes", "on")


def log(message):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S ") + message + "\n")
    except Exception:
        pass
    print(message, file=sys.stderr)


def notify(title, message):
    def escape(value):
        return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")

    try:
        subprocess.run(
            ["/usr/bin/osascript", "-e",
             'display notification "%s" with title "%s"' % (escape(message), escape(title))],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
    except Exception:
        pass


def brief(text, limit=220):
    collapsed = " ".join(str(text).split())
    return collapsed[:limit] + ("…" if len(collapsed) > limit else "")


def parse_json(text):
    """Tolerate log lines printed before the JSON payload."""
    value = (text or "").strip()
    positions = [p for p in (value.find("["), value.find("{")) if p >= 0]
    if not positions:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(value[min(positions):])
        return obj
    except Exception:
        return None


def md_escape(value):
    return re.sub(r"([\\\[\]()])", r"\\\1", value)


def sql_escape(value):
    return value.replace("'", "''")


def is_cjk(char):
    code = ord(char)
    return (0x4E00 <= code <= 0x9FFF or 0x3400 <= code <= 0x4DBF
            or 0x3000 <= code <= 0x303F or 0xFF00 <= code <= 0xFFEF)


def needs_space(before, after):
    if after in ".,;:!?，。；：！？、）】》」』%)]}":
        return False
    if before in "（【《「『([{":
        return False
    if is_cjk(before) or is_cjk(after):
        return False
    return True


def smart_join(text):
    """Collapse PDF-style hard line breaks into one continuous sentence."""
    result = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            if result and not result.endswith(" "):
                result += " "
            continue
        if not result:
            result = line
            continue
        if result.endswith("-") and re.match(r"[A-Za-z]", line[0]):
            result = result[:-1] + line  # de-hyphenate "inter-" + "national"
        elif needs_space(result[-1], line[0]):
            result += " " + line
        else:
            result += line
    return re.sub(r"\s+", " ", result).strip()


def escape_plain(line):
    """Keep the selection as literal text instead of Markdown formatting."""
    line = line.strip()
    escaped = "".join("\\" + char if char in INLINE_SPECIAL else char
                      for char in line)
    if escaped and escaped[0] in "-+>#":
        escaped = "\\" + escaped
    match = re.match(r"^(\d+)([.)])(\s|$)", escaped)
    if match:
        escaped = escaped[:match.end(1)] + "\\" + escaped[match.end(1):]
    return escaped


def looks_like_pdf_breaks(text):
    """Detect PDF-style hard wrapping without relying on app name or URL.

    Copied PDF text is wrapped mid-sentence into short lines. Structured
    content (lists, blank-line paragraphs, code, links) is left alone so that
    ordinary web selections keep their line breaks.
    """
    raw = text.splitlines()
    lines = [line.strip() for line in raw if line.strip()]
    if len(lines) < 2 or any(not line.strip() for line in raw):
        return False
    for line in lines:
        if re.match(r"^([-*+>]|\d+[.)]|#{1,6}\s|```|\|)", line):
            return False
        if "\t" in line or "http://" in line or "https://" in line:
            return False
    lengths = [len(line) for line in lines]
    if max(lengths) > 120 or sum(lengths) / len(lengths) > 80:
        return False
    sentence_end = tuple("。！？；：.!?;:」』》】）)\"'")
    broken = sum(1 for line in lines[:-1]
                 if not line.endswith(sentence_end))
    needed = 1 if len(lines) == 2 else max(2, (len(lines) - 1) * 3 // 4)
    return broken >= needed


def is_pdf_source(text=""):
    # Text shape first: this also covers browser built-in PDF viewers where
    # PopClip cannot supply a page URL (e.g. Microsoft Edge).
    if flag("detectpdfbreaks", "1") and looks_like_pdf_breaks(text):
        return True
    if ".pdf" in env("POPCLIP_BROWSER_URL").lower():
        return True
    haystack = (env("POPCLIP_APP_NAME") + " " +
                env("POPCLIP_BUNDLE_IDENTIFIER")).lower()
    custom = [k.strip().lower() for k in opt("pdfapps").splitlines()
              if k.strip() and not k.strip().startswith("#")]
    return any(keyword in haystack
               for keyword in list(BUILTIN_PDF_KEYWORDS) + custom)


class Fail(Exception):
    def __init__(self, message, config=False):
        super().__init__(message)
        self.config = config


def fail(message, config=False):
    raise Fail(message, config)


class SiYuan:
    def __init__(self):
        self.workspace = None
        self.home = None
        try:
            self.timeout = float(opt("timeout", "10"))
        except (TypeError, ValueError):
            self.timeout = 10.0
        if self.timeout <= 0:
            self.timeout = 10.0
        self.cli = self.resolve_cli()
        self.workspace = self.resolve_workspace()

    def resolve_cli(self):
        candidates = [opt("clipath").strip(), DEFAULT_CLI,
                      shutil.which("siyuan"), shutil.which("SiYuan-Kernel")]
        for candidate in candidates:
            if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
        fail("找不到思源 CLI（SiYuan-Kernel），请在设置里填写 CLI 路径", True)

    def run(self, args, stdin=None, with_workspace=True, allow_home_retry=True):
        cmd = [self.cli] + list(args)
        if with_workspace:
            cmd += ["-w", self.workspace]
        if self.home:
            cmd += ["--home-dir", self.home]
        cmd += ["-f", "json"]
        payload = stdin.encode("utf-8") if stdin is not None else None
        try:
            result = subprocess.run(
                cmd, input=payload, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            fail("思源命令超时（%g 秒）：%s" % (self.timeout, " ".join(args[:2])))
        except OSError as exc:
            fail("无法启动思源 CLI：%s" % exc)

        output = (result.stdout + b"\n" + result.stderr).decode("utf-8", "replace")
        if result.returncode != 0:
            # The kernel writes ~/.config/siyuan/workspace.json on startup.
            # In restricted environments that fails; retry with a private home.
            locked = ("workspace.json" in output and
                      ("operation not permitted" in output or "permission denied" in output.lower()))
            if locked and allow_home_retry and self.home is None:
                self.home = tempfile.mkdtemp(prefix="popclip-siyuan-")
                return self.run(args, stdin, with_workspace, allow_home_retry=False)
            fail("思源命令失败（%s）：%s" % (" ".join(args[:2]), brief(output)))
        return output

    def resolve_workspace(self):
        configured = opt("workspace").strip()
        if configured:
            if not os.path.isdir(configured):
                fail("Workspace 路径不存在：%s" % configured, True)
            return configured
        output = self.run(["workspace", "info"], with_workspace=False)
        data = parse_json(output)
        path = data.get("path") if isinstance(data, dict) else None
        if not path:
            match = re.search(r'"path"\s*:\s*"([^"]+)"', output)
            path = match.group(1) if match else None
        if not path or not os.path.isdir(path):
            fail("无法自动探测 Workspace，请在设置里手动填写", True)
        return path

    def notebook_id(self, wanted=""):
        output = self.run(["notebook", "list"])
        rows = parse_json(output) or []
        if not isinstance(rows, list) or not rows:
            fail("读取笔记本列表失败：%s" % brief(output), True)
        if wanted:
            for row in rows:
                if wanted in (row.get("id"), row.get("name")):
                    return row["id"], row.get("name", "")
            for row in rows:
                if wanted in (row.get("name") or ""):
                    return row["id"], row.get("name", "")
            fail("找不到笔记本：%s" % wanted, True)
        for row in rows:
            if not row.get("closed") and not row.get("encrypted"):
                return row["id"], row.get("name", "")
        fail("没有可用的笔记本（都已关闭或已加密）", True)

    def doc_id_by_path(self, spec):
        spec = spec.strip().strip("/")
        if not spec:
            fail("按标题定位需要在设置里填写「文档标题或路径」", True)
        parts = [part for part in spec.split("/") if part]
        title = parts[-1]
        wanted_box = parts[0] if len(parts) > 1 else opt("notebook").strip()
        box = None
        if wanted_box:
            box, _ = self.notebook_id(wanted_box)
        stmt = ("SELECT id, hpath, box FROM blocks WHERE type = 'd' AND "
                "(hpath = '/%s' OR hpath LIKE '%%/%s' OR content = '%s')"
                % (sql_escape(spec), sql_escape(title), sql_escape(title)))
        if box:
            stmt += " AND box = '%s'" % sql_escape(box)
        stmt += " LIMIT 20"
        rows = parse_json(self.run(["sql", stmt])) or []
        if not rows:
            fail("找不到文档：%s（请检查标题或写全「笔记本/文档标题」）" % spec, True)
        exact = [r for r in rows if (r.get("hpath") or "").rstrip("/").endswith("/" + title)]
        candidates = exact or rows
        if len(candidates) > 1:
            fail("匹配到 %d 个同名文档，请在设置里写完整的「笔记本/文档路径」" % len(candidates), True)
        return candidates[0]["id"]

    def daily_doc_id(self, notebook):
        notebook_id, notebook_name = self.notebook_id(notebook)
        output = self.run(["dailynote", "create", "--notebook", notebook_id])
        match = ID_RE.search(output)
        if not match:
            fail("创建今日日记失败：%s" % brief(output))
        return match.group(0), "今日日记 · " + (notebook_name or notebook_id)


def parse_spec(spec):
    value = spec.strip()
    lower = value.lower()
    if lower.startswith("id:"):
        return "id", value[3:].strip()
    if lower.startswith("path:"):
        return "path", value[5:].strip()
    if lower == "daily":
        return "daily", ""
    if lower.startswith("daily:"):
        return "daily", value[6:].strip()
    if ID_RE.fullmatch(value):
        return "id", value
    fail("场景目标格式无法识别：%s" % value, True)


def default_target():
    mode = opt("targetmode", "id").strip().lower()
    if mode == "path":
        spec = opt("docpath").strip()
        return "path", spec, spec or "文档路径"
    if mode == "daily":
        return "daily", opt("notebook").strip(), "今日日记"
    return "id", opt("docid").strip(), "默认文档"


def resolve_target():
    try:
        flags = int(env("POPCLIP_MODIFIER_FLAGS", "0") or 0)
    except ValueError:
        flags = 0
    scenes = opt("scenes")
    if scenes and flags:
        for line in scenes.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [part.strip() for part in line.split("|")]
            if len(parts) < 3:
                continue
            key, name, spec = parts[0], parts[1], "|".join(parts[2:]).strip()
            mask = None
            for aliases, value in MODIFIER_MASKS:
                if key.lower() in aliases:
                    mask = value
                    break
            if mask and (flags & mask):
                mode, value = parse_spec(spec)
                return mode, value, name or "场景"
    return default_target()


def target_to_parent(siyuan, mode, value, label):
    if mode == "id":
        if not ID_RE.fullmatch(value or ""):
            fail("文档 ID 无效或为空：%s（应形如 20210808180117-abc1234）" % (value or "空"), True)
        return value, label
    if mode == "path":
        return siyuan.doc_id_by_path(value), label
    if mode == "daily":
        return siyuan.daily_doc_id(value)
    fail("未知的定位方式：%s" % mode, True)


def build_markdown():
    text = (env("POPCLIP_TEXT") or env("POPCLIP_FULL_TEXT") or "").strip()
    if not text:
        fail("选中的文本为空", True)

    if flag("alwaysjoin") or is_pdf_source(text):
        # PDF (or the explicit override): one continuous line, no breaks.
        body = escape_plain(smart_join(text))
    else:
        # Web pages: keep the line breaks, but <br> keeps every line inside
        # the very same list item block instead of creating new blocks.
        parts = [escape_plain(line) if line.strip() else ""
                 for line in text.splitlines()]
        while parts and not parts[0]:
            parts.pop(0)
        while parts and not parts[-1]:
            parts.pop()
        body = "<br>".join(parts)

    if not flag("includesource"):
        return body, ""

    fmt = opt("timeformat", "hm").strip().lower()
    now = datetime.now()
    stamp = {"hm": now.strftime("%H:%M"),
             "full": now.strftime("%Y-%m-%d %H:%M"),
             "none": ""}.get(fmt, now.strftime("%H:%M"))
    title = env("POPCLIP_BROWSER_TITLE").strip()
    url = env("POPCLIP_BROWSER_URL").strip()
    app = env("POPCLIP_APP_NAME").strip()

    bits = [bit for bit in (stamp,) if bit]
    if url:
        safe_url = url.replace(" ", "%20").replace(")", "%29").replace("(", "%28")
        bits.append("[%s](%s)" % (md_escape(title or url), safe_url))
    elif title:
        bits.append(md_escape(title))
    if app:
        bits.append(md_escape(app))
    return body, (" · ".join(bits) if bits else "")


def main():
    siyuan = None
    try:
        siyuan = SiYuan()
        mode, value, label = resolve_target()
        parent_id, label = target_to_parent(siyuan, mode, value, label)
        body, source = build_markdown()
        # One list item for the excerpt, with the source as its nested child.
        # A blank line between them would create an extra empty block.
        markdown = "- " + body + ("\n  - " + source if source else "")
        output = siyuan.run(
            ["block", "append", "--parent", parent_id, "--file", "-"],
            stdin=markdown,
        )
        block = ID_RE.search(output)
        log("OK target=%s parent=%s block=%s" %
            (label, parent_id, block.group(0) if block else "unknown"))
        if flag("successhint"):
            notify("存入思源", "已存入：%s" % label)
        print("已存入：%s" % label)
        return 0
    except Fail as exc:
        log("FAIL config=%s: %s" % (exc.config, exc))
        notify("存入思源失败", str(exc))
        print(str(exc), file=sys.stderr)
        return 2 if (exc.config and flag("settingsonerror", "1")) else 1
    except Exception as exc:  # noqa: BLE001 - report every unexpected failure
        log("ERROR: %r" % (exc,))
        notify("存入思源失败", "未知错误：%s" % brief(str(exc), 120))
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        if siyuan is not None and siyuan.home:
            shutil.rmtree(siyuan.home, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
