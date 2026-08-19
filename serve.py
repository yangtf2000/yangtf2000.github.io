#!/usr/bin/env python3
# 本地预览服务器：解析 _posts front matter + 内置最小 Liquid 引擎渲染首页/分类/标签/文章
# 与 GitHub Pages 的 Jekyll 输出保持视觉一致（共用 main.css 与模板）。
import re, os, glob, datetime, http.server, socketserver

ROOT = os.path.dirname(os.path.abspath(__file__))

# ---------- front matter ----------
FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)

def parse_fm(text):
    m = FM_RE.match(text)
    if not m:
        return {}, text
    fm = {}
    body = text[m.end():]
    cur_key = None
    for line in m.group(1).split("\n"):
        if not line.strip():
            continue
        if re.match(r"^\s+", line) and cur_key:
            fm[cur_key] += " " + line.strip()
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip(); v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                inner = v[1:-1].strip()
                fm[k] = [x.strip() for x in inner.split(",") if x.strip()] if inner else []
            elif v == "":
                fm[k] = ""
            else:
                fm[k] = v.strip().strip('"').strip("'")
            cur_key = k
    return fm, body

def parse_date(s):
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.datetime.strptime(s, fmt)
        except Exception:
            pass
    return None

# ---------- 收集 site 数据 ----------
def collect():
    posts = []
    for path in glob.glob(os.path.join(ROOT, "_posts", "*.html")):
        text = open(path, encoding="utf-8").read()
        fm, body = parse_fm(text)
        fn = os.path.splitext(os.path.basename(path))[0]
        slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", fn)
        d = parse_date(fm.get("date", "")) or datetime.datetime(2000, 1, 1)
        post = {
            "title": fm.get("title", fn),
            "date": d,
            "category": fm.get("category", ""),
            "tags": fm.get("tags", []),
            "excerpt": fm.get("excerpt", ""),
            "icon": fm.get("icon", "news"),
            "image": fm.get("image", ""),
            "featured": fm.get("featured", ""),
            "updated": fm.get("updated", ""),
            "url": "/" + slug + "/",
            "content": body,
            "fm": fm,
            "_fn": fn,
        }
        posts.append(post)
    # 与线上 Jekyll 一致：日期倒序；同一天则按文件名倒序（避免本地与线上首篇不同）
    posts.sort(key=lambda p: (p["date"], p["_fn"]), reverse=True)
    # categories / tags
    cats = {}
    tags = {}
    for p in posts:
        cats.setdefault(p["category"], []).append(p)
        for t in p["tags"]:
            tags.setdefault(t, []).append(p)
    # categories 按固定展示顺序（按实际用途）
    CAT_ORDER = {"政策周报": 0, "教程指南": 1, "查询手册": 2, "工具盘点": 3, "研究成果": 4}
    site = {
        "posts": posts,
        "categories": [[k, v] for k, v in sorted(cats.items(), key=lambda kv: CAT_ORDER.get(kv[0], 99))],
        "tags": [[k, v] for k, v in sorted(tags.items())],
        "title": "茶叶末",
        "description": "都是些碎末，泡出来也有茶味。",
        "baseurl": "",
        "url": "https://yangtf2000.github.io",
    }
    return site, posts

SITE, POSTS = collect()

# ---------- 最小 Liquid 引擎 ----------
class Liquid:
    def __init__(self, ctx):
        self.ctx = ctx

    def render(self, tmpl):
        tokens = self._tokenize(tmpl)
        return self._block(tokens, 0, self.ctx, [])[0]

    def _tokenize(self, tmpl):
        pat = re.compile(r"{%\s*(.*?)\s*%}|{{\s*(.*?)\s*}}", re.S)
        tokens, pos = [], 0
        for m in pat.finditer(tmpl):
            if m.start() > pos:
                tokens.append(("text", tmpl[pos:m.start()]))
            tokens.append(("tag", m.group(1)) if m.group(1) is not None else ("var", m.group(2)))
            pos = m.end()
        if pos < len(tmpl):
            tokens.append(("text", tmpl[pos:]))
        return tokens

    def _block(self, tokens, start, ctx, stop):
        out, i, n = [], start, len(tokens)
        while i < n:
            kind, val = tokens[i]
            if kind == "text":
                out.append(val); i += 1; continue
            if kind == "tag":
                cmd = val.strip()
                tagname = cmd.split()[0] if cmd else ""
                if tagname in stop:
                    return "".join(out), i
                if cmd.startswith("assign "):
                    mm = re.match(r"assign\s+(\w+)\s*=\s*(.*)", cmd)
                    ctx[mm.group(1)] = self._expr(mm.group(2), ctx); i += 1
                elif cmd.startswith("for "):
                    mm = re.match(r"for\s+(\w+)\s+in\s+(.*)", cmd)
                    var, seq = mm.group(1), self._expr(mm.group(2), ctx) or []
                    inner, end = self._block(tokens, i + 1, ctx, ["endfor"])
                    buf = []
                    for item in seq:
                        c2 = dict(ctx); c2[var] = item
                        buf.append(self._block(tokens, i + 1, c2, ["endfor"])[0])
                    out.append("".join(buf)); i = end + 1
                elif cmd.startswith("if "):
                    rendered, end = self._if(tokens, i, ctx)
                    out.append(rendered); i = end + 1
                elif cmd.startswith("include "):
                    out.append(self._include(cmd[8:].strip(), ctx)); i += 1
                else:
                    i += 1
            else:
                out.append(self._var(val, ctx)); i += 1
        return "".join(out), i

    def _include(self, rest, ctx):
        """支持 {% include file.html key=value %}，片段内用 {{ include.key }} 取值（与 Jekyll 一致）"""
        parts = rest.split()
        if not parts:
            return ""
        fname = parts[0].strip('"').strip("'")
        params = {}
        for kv in parts[1:]:
            if "=" in kv:
                k, v = kv.split("=", 1)
                params[k.strip()] = self._expr(v.strip(), ctx)
        fpath = os.path.join(ROOT, "_includes", fname)
        if not os.path.isfile(fpath):
            return ""
        inc_ctx = dict(ctx); inc_ctx["include"] = params
        return Liquid(inc_ctx).render(open(fpath, encoding="utf-8").read())

    def _if(self, tokens, start, ctx):
        branches = []  # (cond_str, body_start)
        i, n = start, len(tokens)
        cur = ("", i + 1)
        depth = 0
        while i < n:
            kind, val = tokens[i]
            if kind == "tag":
                c = val.strip()
                tag = c.split()[0] if c else ""
                if tag == "if":
                    if depth == 0:
                        cur = (c[2:].strip() if len(c) > 2 else "", i + 1)
                    depth += 1; i += 1; continue
                if tag == "elsif":
                    if depth == 1:
                        branches.append(cur); cur = (c[5:].strip(), i + 1)
                    i += 1; continue
                if tag == "else":
                    if depth == 1:
                        branches.append(cur); cur = ("true", i + 1)
                    i += 1; continue
                if tag == "endif":
                    depth = depth - 1 if depth > 0 else 0
                    if depth == 0:
                        branches.append(cur)
                        for cond, bstart in branches:
                            if self._cond(cond, ctx):
                                return self._block(tokens, bstart, ctx, ["endif", "else", "elsif"])[0], i
                        return "", i
                    i += 1; continue
                i += 1
            else:
                i += 1
        return "", n

    def _cond(self, cond, ctx):
        if not cond or cond == "true":
            return True
        cond = cond.strip()
        if cond.startswith("not "):
            return not self._cond(cond[4:].strip(), ctx)
        for op, fn in ((">=", lambda a,b:a>=b), ("<=", lambda a,b:a<=b),
                       ("==", lambda a,b:a==b), ("!=", lambda a,b:a!=b),
                       (">", lambda a,b:a>b), ("<", lambda a,b:a<b)):
            if op in cond:
                a, b = [x.strip() for x in cond.split(op, 1)]
                return fn(self._lit(a, ctx), self._lit(b, ctx))
        v = self._expr(cond, ctx)
        return bool(v)

    def _lit(self, s, ctx):
        s = s.strip()
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            return s[1:-1]
        if s == "true":
            return True
        if s == "false":
            return False
        return self._expr(s, ctx)

    def _expr(self, expr, ctx):
        expr = expr.strip()
        if "|" in expr:
            base, *filt = [x.strip() for x in expr.split("|")]
            val = self._base(base, ctx)
            for f in filt:
                name, _, arg = f.partition(":")
                val = self._filter(name.strip(), val, arg.strip(), ctx)
            return val
        return self._base(expr, ctx)

    def _base(self, base, ctx):
        """按 . 逐级取值，支持任意层级与 name[idx] 下标（如 page.previous.title / cat[1].size）"""
        base = base.strip()
        if (base.startswith('"') and base.endswith('"')) or (base.startswith("'") and base.endswith("'")):
            return base[1:-1]
        if re.match(r"^-?\d+$", base):
            return int(base)
        cur, first = "", True
        for seg in base.split("."):
            seg = seg.strip()
            if not seg:
                return ""
            m = re.match(r"^([A-Za-z_]\w*)\[(.+)\]$", seg)
            idx = None
            if m:
                seg, idx = m.group(1), m.group(2).strip()
            cur = ctx.get(seg, "") if first else self._attr(cur, seg)
            first = False
            if idx is not None:
                cur = self._index(cur, idx)
        return cur

    @staticmethod
    def _attr(obj, key):
        if isinstance(obj, dict):
            return obj.get(key, "")
        if isinstance(obj, (list, tuple)):
            if key in ("size", "length"):
                return len(obj)
            if key == "first":
                return obj[0] if obj else ""
            if key == "last":
                return obj[-1] if obj else ""
        if isinstance(obj, str) and key in ("size", "length"):
            return len(obj)
        return ""

    @staticmethod
    def _index(obj, idx):
        if (idx.startswith('"') and idx.endswith('"')) or (idx.startswith("'") and idx.endswith("'")):
            idx = idx[1:-1]
        else:
            try:
                idx = int(idx)
            except Exception:
                pass
        if isinstance(obj, (list, tuple)):
            try:
                return obj[idx]
            except Exception:
                return ""
        if isinstance(obj, dict):
            return obj.get(idx, "")
        return ""

    def _filter(self, name, val, arg, ctx):
        if name == "split":
            return [x.strip() for x in str(val).split(arg.strip('"') if arg else ",")]
        if name == "default":
            return val if str(val).strip() else self._lit(arg, ctx)
        if name == "where":
            field, _, value = arg.partition(",")
            field = field.strip().strip('"').strip("'")
            value = self._lit(value.strip(), ctx)
            return [x for x in (val or [])
                    if str(x.get(field, "")).strip().lower() == str(value).strip().lower()]
        if name == "date":
            fmt = arg.strip().strip('"').strip("'")
            try:
                return val.strftime(fmt) if isinstance(val, datetime.datetime) else str(val)
            except Exception:
                return str(val)
        if name == "date_to_xmlschema":
            return val.isoformat() + "Z" if isinstance(val, datetime.datetime) else str(val)
        if name == "relative_url":
            return (ctx.get("site", {}).get("baseurl", "") or "") + str(val)
        if name == "strip_html":
            return re.sub(r"<[^>]+>", "", str(val))
        if name == "truncate":
            n = int(arg.strip()); s = str(val)
            return s[:n] + "…" if len(s) > n else s
        if name == "size":
            return len(val)
        return val

    def _var(self, expr, ctx):
        if expr.strip() == "content":
            return ctx.get("content", "")
        return str(self._expr(expr, ctx))

# ---------- 渲染页面 ----------
def render_template(rel_path, page_fm, page_body):
    tpath = os.path.join(ROOT, rel_path)
    tmpl = open(tpath, encoding="utf-8").read()
    fm, body = parse_fm(tmpl)
    layout = fm.get("layout", "")
    ctx = {"site": SITE, "page": {**page_fm, "content": page_body}, "content": page_body}
    inner = Liquid(ctx).render(body)
    if layout == "default":
        dft = open(os.path.join(ROOT, "_layouts", "default.html"), encoding="utf-8").read()
        ctx2 = {"site": SITE, "page": {**page_fm, "content": inner}, "content": inner}
        return Liquid(ctx2).render(dft)
    return inner

# ---------- HTTP ----------
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        url = self.path.split("?")[0]
        if url == "/favicon.ico":
            self.send_response(204); self.end_headers(); return
        if url == "/":
            html = render_template("index.html", {"layout": "default"}, "")
            return self._send(html, "text/html")
        if url.endswith("/") and url != "/":
            slug = url.rstrip("/").lstrip("/")
            idx = next((i for i, p in enumerate(POSTS) if p["url"].strip("/") == slug), None)
            if idx is not None:
                post = POSTS[idx]
                # POSTS 为新→旧排序；与 Jekyll 一致：previous = 更早一篇，next = 更新一篇
                older = POSTS[idx + 1] if idx + 1 < len(POSTS) else None
                newer = POSTS[idx - 1] if idx - 1 >= 0 else None
                fm = dict(post["fm"])
                fm["date"] = post["date"]
                fm["previous"] = {"title": older["title"], "url": older["url"]} if older else ""
                fm["next"] = {"title": newer["title"], "url": newer["url"]} if newer else ""
                html = render_template("_layouts/post.html", fm, post["content"])
                return self._send(html, "text/html")
        # 静态资源
        fpath = os.path.join(ROOT, url.lstrip("/"))
        if os.path.isfile(fpath):
            ct = {"css": "text/css", "svg": "image/svg+xml", "js": "application/javascript",
                  "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif",
                  "ico": "image/x-icon", "json": "application/json"}.get(fpath.rsplit(".", 1)[-1].lower(), "application/octet-stream")
            return self._send(open(fpath, "rb").read(), ct)
        self.send_error(404, "Not found: " + url)

    def _send(self, data, ct):
        if isinstance(data, str):
            data = data.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", ct + "; charset=utf-8" if ct.startswith("text") else ct)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    PORT = 8123
    with socketserver.TCPServer(("127.0.0.1", PORT), H) as httpd:
        print(f"本地预览: http://127.0.0.1:{PORT}/  (Ctrl+C 停止)")
        httpd.serve_forever()
