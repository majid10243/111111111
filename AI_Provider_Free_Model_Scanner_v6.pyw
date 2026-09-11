import csv
import json
import threading
import urllib.request
import urllib.error
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

DATA = []
LAST_BASE = ""
ROUTER_COOKIE = ""


def clean(s):
    if s is None:
        return ""
    return str(s).replace("\ufeff", "").replace("\u200b", "").replace("\u200c", "").replace("\u200d", "").strip()


def validate_key(key):
    key = clean(key)
    if not key:
        return ""
    bad = [(c, f"U+{ord(c):04X}") for c in key if ord(c) > 255 or ord(c) in (10, 13)]
    if bad:
        raise ValueError("API Key شامل کاراکتر نامعتبر است: " + ", ".join(f"{c} ({u})" for c, u in bad[:8]))
    return key


def normalize_models_url(base):
    base = clean(base).rstrip("/")
    if not base:
        raise ValueError("Base URL را وارد کنید.")
    return base if base.endswith("/models") else base + "/models"


def fmt_int(v):
    try:
        return f"{int(v):,}"
    except Exception:
        return "-"


def get_provider(mid):
    return mid.split("/", 1)[0] if "/" in mid else ""


def http_json(url, method="GET", headers=None, payload=None, timeout=30):
    headers = dict(headers or {})
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        text = raw.decode("utf-8", errors="replace")
        try:
            obj = json.loads(text) if text else {}
        except json.JSONDecodeError:
            obj = {"_raw": text}
        return r.status, obj


def api_headers(key=""):
    h = {"User-Agent": "AI-Provider-Free-Model-Scanner/5.0", "Accept": "application/json"}
    if clean(key):
        h["Authorization"] = "Bearer " + validate_key(key)
    return h


def scan():
    base = clean(url_var.get())
    try:
        key = validate_key(key_var.get())
    except ValueError as e:
        messagebox.showerror("API Key نامعتبر", str(e)); return
    if not base:
        messagebox.showwarning("ورودی لازم است", "Base URL را وارد کنید."); return
    btn.config(state="disabled")
    status.set("در حال دریافت فهرست مدل‌ها...")
    for item in tree.get_children(): tree.delete(item)
    threading.Thread(target=scan_worker, args=(base, key), daemon=True).start()


def scan_worker(base, key):
    global LAST_BASE
    try:
        url = normalize_models_url(base)
        LAST_BASE = base.rstrip("/")
        _, obj = http_json(url, headers=api_headers(key), timeout=45)
        models = obj.get("data", []) if isinstance(obj, dict) else []
        free = []
        for m in models:
            mid = str(m.get("id", ""))
            p = m.get("pricing") or {}
            explicit_free = mid.endswith(":free")
            zero_price = str(p.get("prompt", "")) in ("0", "0.0", "0.00") and str(p.get("completion", "")) in ("0", "0.0", "0.00")
            if not (explicit_free or zero_price): continue
            arch = m.get("architecture") or {}
            modalities = arch.get("input_modalities") or []
            if modalities and "text" not in modalities: continue
            free.append(m)
        free.sort(key=lambda m: (m.get("context_length") or 0), reverse=True)
        root.after(0, lambda: show_results(free))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:1800]
        root.after(0, lambda: scan_error(f"HTTP {e.code}\n{body}"))
    except Exception as e:
        root.after(0, lambda: scan_error(str(e)))


def show_results(models):
    global DATA
    DATA = models
    for i, m in enumerate(models):
        mid = str(m.get("id", "")); arch = m.get("architecture") or {}; params = set(m.get("supported_parameters") or []); p = m.get("pricing") or {}
        tree.insert("", "end", iid=str(i), values=(i+1, m.get("name") or mid, mid, fmt_int(m.get("context_length")), get_provider(mid), ", ".join(arch.get("input_modalities") or []) or "-", "بله" if ("tools" in params or "tool_choice" in params) else "خیر", "بله" if "reasoning" in params else "خیر", "بله" if ("structured_outputs" in params or "response_format" in params) else "خیر", p.get("prompt", "0"), p.get("completion", "0")))
    status.set(f"{len(models)} مدل رایگان پیدا شد.")
    btn.config(state="normal")
    select_all()


def scan_error(err):
    btn.config(state="normal"); status.set("اسکن ناموفق بود."); messagebox.showerror("خطا در اتصال", "اسکن مدل‌ها ناموفق بود.\n\n" + err)


def select_all(): tree.selection_set(tree.get_children())
def select_none(): tree.selection_remove(tree.selection())


def selected_models():
    ids = tree.selection()
    if not ids:
        messagebox.showwarning("انتخاب مدل", "حداقل یک مدل را انتخاب کنید."); return []
    return [DATA[int(i)] for i in ids]


def router_model_id(m):
    mid = str(m.get("id", ""))
    prefix = clean(prefix_var.get()) or "up"
    if mid.startswith(prefix + "/"):
        return mid
    return prefix + "/" + mid


def safe_name(m):
    return str(m.get("name") or m.get("id") or "model").replace("/", "_").replace(":", "_")


def router_base():
    b = clean(router_url_var.get()).rstrip("/")
    if b.endswith("/v1"): return b[:-3]
    return b


def router_login():
    """Login to the 9Router dashboard and keep only the in-memory auth cookie."""
    global ROUTER_COOKIE
    base = router_base()
    password = clean(router_password_var.get())
    if not password:
        messagebox.showwarning("9Router Login", "رمز ورود Dashboard 9Router را وارد کنید.")
        return
    def worker():
        global ROUTER_COOKIE
        try:
            data = json.dumps({"password": password}).encode("utf-8")
            req = urllib.request.Request(
                base + "/api/auth/login", data=data, method="POST",
                headers={"Content-Type":"application/json", "Accept":"application/json",
                         "User-Agent":"AI-Provider-Free-Model-Scanner/6.0"}
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read().decode("utf-8", errors="replace")
                cookie = r.headers.get("Set-Cookie", "")
                if cookie:
                    ROUTER_COOKIE = cookie.split(";", 1)[0]
                else:
                    ROUTER_COOKIE = ""
                if r.status < 200 or r.status >= 300:
                    raise RuntimeError(f"HTTP {r.status}: {raw[:1000]}")
            if not ROUTER_COOKIE:
                raise RuntimeError("Login پاسخ داد ولی auth_token cookie دریافت نشد.")
            root.after(0, lambda: messagebox.showinfo("9Router Login", "ورود به Dashboard 9Router موفق بود.\nSession فقط در حافظه برنامه نگه داشته می‌شود."))
        except urllib.error.HTTPError as e:
            body=e.read().decode("utf-8", errors="replace")[:1500]
            root.after(0, lambda: messagebox.showerror("9Router Login", f"HTTP {e.code}\n{body}"))
        except Exception as e:
            root.after(0, lambda: messagebox.showerror("9Router Login", str(e)))
    threading.Thread(target=worker, daemon=True).start()


def router_headers():
    h = {"User-Agent":"AI-Provider-Free-Model-Scanner/6.0", "Accept":"application/json"}
    if ROUTER_COOKIE:
        h["Cookie"] = ROUTER_COOKIE
    # Keep API key fallback for older/unprotected local builds.
    key = clean(router_key_var.get())
    if key:
        h["Authorization"] = "Bearer " + validate_key(key)
    return h


def management_request(path, method="GET", payload=None):
    base = router_base()
    key = clean(router_key_var.get())
    headers = router_headers()
    return http_json(base + path, method=method, headers=headers, payload=payload, timeout=45)


def router_probe():
    """Probe current 9Router instance without modifying anything."""
    def worker():
        base = router_base()
        paths = ["/api/version", "/api/providers", "/api/models", "/v1/models"]
        lines = [f"9Router: {base}", ""]
        for p in paths:
            try:
                code, obj = management_request(p)
                if isinstance(obj, dict) and "_raw" in obj:
                    val = obj["_raw"][:300].replace("\n", " ")
                else:
                    val = json.dumps(obj, ensure_ascii=False)[:500]
                lines.append(f"{p} -> HTTP {code}: {val}")
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")[:300].replace("\n", " ")
                lines.append(f"{p} -> HTTP {e.code}: {body}")
            except Exception as e:
                lines.append(f"{p} -> ERROR: {e}")
        root.after(0, lambda: messagebox.showinfo("9Router Diagnostics", "\n".join(lines)))
    threading.Thread(target=worker, daemon=True).start()


def register_9router_provider():
    if not ROUTER_COOKIE:
        messagebox.showwarning("9Router", "ابتدا روی Login بزنید و وارد Dashboard 9Router شوید.")
        return
    models = selected_models()
    if not models: return
    if not clean(router_url_var.get()):
        messagebox.showwarning("9Router", "Base URL را وارد کنید."); return
    name = clean(provider_var.get()) or "Imported Provider"
    provider_type = clean(router_provider_var.get()) or "openai-compatible-chat"
    upstream = clean(url_var.get()).rstrip("/")
    upstream_key = clean(key_var.get())
    prefix = clean(prefix_var.get()) or "up"

    payload = {
        "name": name,
        "provider": provider_type,
        "authType": "apikey",
        "apiKey": upstream_key,
        "baseUrl": upstream,
        "priority": 10,
        "isActive": True,
        "providerSpecificData": {
            "prefix": prefix,
            "baseUrl": upstream,
            "apiType": "chat",
        },
    }

    def worker():
        try:
            code, result = management_request("/api/providers", "POST", payload)
            pid = result.get("id") or result.get("connectionId") or result.get("providerId") if isinstance(result, dict) else None
            # Some 9Router builds return the connection but ignore enabledModels. Try the update endpoint if an id exists.
            update_note = ""
            if pid:
                update_payload = {
                    "name": name,
                    "priority": 10,
                    "isActive": True,
                    "providerSpecificData": {
                        "prefix": prefix,
                        "baseUrl": upstream,
                        "apiType": "chat",
                        "enabledModels": [str(m.get("id", "")) for m in models],
                    },
                }
                try:
                    ucode, ures = management_request(f"/api/providers/{pid}", "PUT", update_payload)
                    update_note = f"\nUpdate Provider: HTTP {ucode}"
                except urllib.error.HTTPError as ue:
                    update_note = f"\nUpdate Provider: HTTP {ue.code} (این نسخه ممکن است enabledModels را نپذیرد.)"
                except Exception as ue:
                    update_note = f"\nUpdate Provider: {ue}"
                # Verify the provider is actually present in the dashboard API.
                try:
                    vcode, vres = management_request("/api/providers", "GET")
                    found = False
                    if isinstance(vres, list):
                        found = any(str(x.get("id")) == str(pid) for x in vres if isinstance(x, dict))
                    elif isinstance(vres, dict):
                        arr = vres.get("providers") or vres.get("connections") or vres.get("data") or []
                        if isinstance(arr, list):
                            found = any(str(x.get("id")) == str(pid) for x in arr if isinstance(x, dict))
                    update_note += f"\nDashboard Verify: HTTP {vcode} — " + ("FOUND" if found else "NOT FOUND")
                except Exception as ve:
                    update_note += f"\nDashboard Verify: {ve}"
            msg = f"Provider با HTTP {code} ثبت شد."
            if pid: msg += f"\nID: {pid}"
            msg += update_note
            msg += "\n\nمدل‌ها:\n" + "\n".join("• " + router_model_id(m) for m in models)
            root.after(0, lambda: messagebox.showinfo("9Router", msg))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:2500]
            root.after(0, lambda: messagebox.showerror("خطای 9Router", f"HTTP {e.code}\n{body}\n\nاگر /api/providers در نسخه شما 404 است، از 9Router Diagnostics استفاده کنید."))
        except Exception as e:
            root.after(0, lambda: messagebox.showerror("خطای 9Router", str(e)))
    threading.Thread(target=worker, daemon=True).start()


def export_csv():
    models = selected_models()
    if not models: return
    path = filedialog.asksaveasfilename(title="ذخیره CSV", defaultextension=".csv", filetypes=[("CSV", "*.csv")])
    if not path: return
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(["Rank","Name","Model ID","Context Tokens","Provider","Input Modalities","Tools","Reasoning","Structured Outputs","Input Price","Output Price"])
        for i,m in enumerate(models,1):
            mid=str(m.get("id","")); arch=m.get("architecture") or {}; params=set(m.get("supported_parameters") or []); p=m.get("pricing") or {}
            w.writerow([i,m.get("name") or mid,mid,m.get("context_length") or "",get_provider(mid),", ".join(arch.get("input_modalities") or []),"Yes" if ("tools" in params or "tool_choice" in params) else "No","Yes" if "reasoning" in params else "No","Yes" if ("structured_outputs" in params or "response_format" in params) else "No",p.get("prompt","0"),p.get("completion","0")])
    messagebox.showinfo("ذخیره شد", f"CSV ذخیره شد:\n{path}")



def export_continue():
    """Export the selected models in the original Continue YAML format."""
    models = selected_models()
    if not models:
        return

    base = clean(router_url_var.get()).rstrip("/")
    # Continue connects to 9Router. Prefer the 9Router key, then fall back
    # to the scanned provider key for compatibility with the original version.
    continue_key = clean(router_key_var.get()) or clean(key_var.get())
    if continue_key:
        try:
            validate_key(continue_key)
        except ValueError as e:
            messagebox.showerror("API Key نامعتبر", str(e))
            return
    else:
        messagebox.showwarning(
            "Continue Export",
            "API Key مربوط به 9Router را وارد کنید تا فایل Continue شامل API Key واقعی باشد."
        )
        return

    path = filedialog.asksaveasfilename(
        title="Export Continue YAML",
        defaultextension=".yml",
        filetypes=[("Continue YAML", "*.yml"), ("YAML", "*.yaml")]
    )
    if not path:
        return

    yaml_lines = [
        "name: 9Router Free Models",
        "version: 0.0.1",
        "schema: v1",
        "models:"
    ]
    for m in models:
        mid = router_model_id(m)
        name = str(m.get("name") or mid).replace('"', '\\"')
        yaml_lines += [
            f'  - name: "{name}"',
            "    provider: openai",
            f'    model: "{mid}"',
            f'    apiBase: "{base}"',
            f"    apiKey: {json.dumps(continue_key, ensure_ascii=False)}",
            f"    contextLength: {int(m.get('context_length') or 0)}",
            "    roles:",
            "      - chat",
            "      - edit",
            "      - apply"
        ]
        params = set(m.get("supported_parameters") or [])
        if "tools" in params or "tool_choice" in params:
            yaml_lines += ["    capabilities:", "      - tool_use"]

    Path(path).write_text("\n".join(yaml_lines) + "\n", encoding="utf-8")
    messagebox.showinfo("Continue Export", f"فایل YAML با موفقیت ساخته شد:\n{path}")

def export_package():
    models = selected_models()
    if not models: return
    folder = filedialog.askdirectory(title="پوشه خروجی")
    if not folder: return
    out = Path(folder) / "AI_Model_Exports"; out.mkdir(parents=True, exist_ok=True)
    base = clean(router_url_var.get()).rstrip("/")
    ids = [router_model_id(m) for m in models]
    (out/"9router_model_list.txt").write_text("\n".join(ids)+"\n", encoding="utf-8")
    (out/"9router_provider_payload.json").write_text(json.dumps({
        "name": clean(provider_var.get()) or "Imported Provider",
        "provider": clean(router_provider_var.get()) or "openai-compatible-chat",
        "authType":"apikey",
        "apiKey":"<UPSTREAM_API_KEY>",
        "baseUrl":clean(url_var.get()).rstrip("/"),
        "priority":10,
        "isActive":True,
        "providerSpecificData":{"prefix":clean(prefix_var.get()) or "up","apiType":"chat","baseUrl":clean(url_var.get()).rstrip("/"),"enabledModels":[str(m.get("id","")) for m in models]}
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    oc={"$schema":"https://opencode.ai/config.json","providers":{"9router":{"name":"9Router","package":"@opencode/ai/providers/openai-compatible","settings":{"baseURL":base,"apiKey":"{env:ROUTER_API_KEY}"},"models":{}}}}
    for m in models:
        mid=router_model_id(m); oc["providers"]["9router"]["models"][mid]={"name":m.get("name") or mid,"limit":{"context":int(m.get("context_length") or 0),"output":65536}}
    (out/"opencode_9router.json").write_text(json.dumps(oc,ensure_ascii=False,indent=2),encoding="utf-8")

    # Continue - restored from the original v4 workflow.
    continue_key = clean(router_key_var.get()) or clean(key_var.get())
    if continue_key:
        validate_key(continue_key)
        y = ["name: 9Router Free Models", "version: 0.0.1", "schema: v1", "models:"]
        for m in models:
            mid = router_model_id(m)
            name = str(m.get("name") or mid).replace('"', '\\"')
            y += [
                f'  - name: "{name}"',
                "    provider: openai",
                f'    model: "{mid}"',
                f'    apiBase: "{base}"',
                f"    apiKey: {json.dumps(continue_key, ensure_ascii=False)}",
                f"    contextLength: {int(m.get('context_length') or 0)}",
                "    roles:", "      - chat", "      - edit", "      - apply"
            ]
            params = set(m.get("supported_parameters") or [])
            if "tools" in params or "tool_choice" in params:
                y += ["    capabilities:", "      - tool_use"]
        (out/"continue_9router_config.yml").write_text("\n".join(y)+"\n",encoding="utf-8")
    else:
        (out/"continue_9router_config.yml").write_text(
            "# API Key was not entered. Re-export after entering the 9Router API Key.\n",
            encoding="utf-8"
        )

    (out/"README.txt").write_text("AI Provider Scanner v5.1\n\nDirect Register logs into 9Router Dashboard (/api/auth/login), then uses the authenticated /api/providers management API. The dashboard auth cookie is kept only in memory.\nIf your 9Router returns 404, click 9Router Diagnostics.\nContinue export has been restored from the original v4 workflow.\n",encoding="utf-8")
    messagebox.showinfo("Export", f"فایل‌ها ساخته شدند:\n{out}")


def clear_key(): key_var.set("")
def clear_router_key(): router_key_var.set("")


root=tk.Tk(); root.title("AI Provider Free Model Scanner v6"); root.geometry("1600x900"); root.minsize(1200,700)

top=ttk.Frame(root,padding=10); top.pack(fill="x")
ttk.Label(top,text="AI Provider Free Model Scanner v6",font=("Segoe UI",18,"bold")).pack(side="left")
ttk.Button(top,text="Export Package",command=export_package).pack(side="right",padx=5)
ttk.Button(top,text="Export CSV",command=export_csv).pack(side="right",padx=5)

provider_box=ttk.LabelFrame(root,text="Provider to Scan",padding=10); provider_box.pack(fill="x",padx=10,pady=(0,6))
provider_var=tk.StringVar(value="OpenRouter"); url_var=tk.StringVar(value="https://openrouter.ai/api/v1"); key_var=tk.StringVar()
router_provider_var=tk.StringVar(value="openai-compatible-chat"); prefix_var=tk.StringVar(value="up")
labels=[("Provider Name",0),("Base URL",2),("API Key",4),("9Router Provider Type",0),("Model Prefix",2)]
# first row
for text,col in [("Provider Name",0),("Base URL",2),("API Key",4)]: ttk.Label(provider_box,text=text).grid(row=0,column=col,padx=5,pady=5,sticky="w")
ttk.Entry(provider_box,textvariable=provider_var,width=24).grid(row=0,column=1,padx=5,pady=5,sticky="ew")
ttk.Entry(provider_box,textvariable=url_var,width=55).grid(row=0,column=3,padx=5,pady=5,sticky="ew")
ttk.Entry(provider_box,textvariable=key_var,width=38,show="•").grid(row=0,column=5,padx=5,pady=5,sticky="ew")
ttk.Button(provider_box,text="Clear",command=clear_key).grid(row=0,column=6,padx=5)
# second row
for text,col in [("9Router Provider Type",0),("Model Prefix",2)]: ttk.Label(provider_box,text=text).grid(row=1,column=col,padx=5,pady=5,sticky="w")
ttk.Entry(provider_box,textvariable=router_provider_var,width=30).grid(row=1,column=1,padx=5,pady=5,sticky="ew")
ttk.Entry(provider_box,textvariable=prefix_var,width=20).grid(row=1,column=3,padx=5,pady=5,sticky="w")
ttk.Label(provider_box,text="برای Provider عمومی: openai-compatible-chat   |   مثال Prefix: up").grid(row=1,column=4,columnspan=3,padx=5,sticky="w")
provider_box.columnconfigure(1,weight=1); provider_box.columnconfigure(3,weight=2); provider_box.columnconfigure(5,weight=1)

router_box=ttk.LabelFrame(root,text="9Router Target",padding=10); router_box.pack(fill="x",padx=10,pady=(0,6))
router_url_var=tk.StringVar(value="http://localhost:20128"); router_key_var=tk.StringVar(); router_password_var=tk.StringVar()
ttk.Label(router_box,text="9Router URL").grid(row=0,column=0,padx=5,pady=5,sticky="w")
ttk.Entry(router_box,textvariable=router_url_var,width=55).grid(row=0,column=1,padx=5,pady=5,sticky="ew")
ttk.Label(router_box,text="Dashboard Password").grid(row=0,column=2,padx=5,pady=5,sticky="w")
ttk.Entry(router_box,textvariable=router_password_var,width=28,show="•").grid(row=0,column=3,padx=5,pady=5,sticky="ew")
ttk.Button(router_box,text="Login",command=router_login).grid(row=0,column=4,padx=5)
ttk.Label(router_box,text="API Key (fallback)").grid(row=1,column=0,padx=5,pady=5,sticky="w")
ttk.Entry(router_box,textvariable=router_key_var,width=55,show="•").grid(row=1,column=1,padx=5,pady=5,sticky="ew")
ttk.Button(router_box,text="Clear",command=clear_router_key).grid(row=1,column=2,padx=5)
router_box.columnconfigure(1,weight=2); router_box.columnconfigure(3,weight=1)

actions=ttk.Frame(root,padding=(10,4)); actions.pack(fill="x")
btn=ttk.Button(actions,text="🔍 Scan Models",command=scan); btn.pack(side="left",padx=4)
ttk.Button(actions,text="Select All",command=select_all).pack(side="left",padx=4); ttk.Button(actions,text="Select None",command=select_none).pack(side="left",padx=4)
ttk.Button(actions,text="9Router Login",command=router_login).pack(side="right",padx=4)
ttk.Button(actions,text="9Router Diagnostics",command=router_probe).pack(side="right",padx=4)
ttk.Button(actions,text="9Router → Register Provider",command=register_9router_provider).pack(side="right",padx=4)
ttk.Button(actions,text="Continue Export",command=export_continue).pack(side="right",padx=4)

status=tk.StringVar(value="Provider را وارد کنید و Scan Models را بزنید."); ttk.Label(root,textvariable=status,padding=(10,2,10,6)).pack(fill="x")

frame=ttk.Frame(root); frame.pack(fill="both",expand=True,padx=10,pady=(0,10))
cols=("rank","name","id","context","provider","modalities","tools","reasoning","structured","in_price","out_price")
tree=ttk.Treeview(frame,columns=cols,show="headings",selectmode="extended")
headers={"rank":"رتبه","name":"نام","id":"Model ID","context":"Context Tokens","provider":"Provider","modalities":"Input","tools":"Tools","reasoning":"Reasoning","structured":"Structured","in_price":"Input $/token","out_price":"Output $/token"}
widths={"rank":60,"name":250,"id":390,"context":125,"provider":100,"modalities":130,"tools":75,"reasoning":90,"structured":105,"in_price":110,"out_price":110}
for c in cols: tree.heading(c,text=headers[c]); tree.column(c,width=widths[c],anchor="center")
ys=ttk.Scrollbar(frame,orient="vertical",command=tree.yview); xs=ttk.Scrollbar(frame,orient="horizontal",command=tree.xview); tree.configure(yscrollcommand=ys.set,xscrollcommand=xs.set)
tree.grid(row=0,column=0,sticky="nsew"); ys.grid(row=0,column=1,sticky="ns"); xs.grid(row=1,column=0,sticky="ew"); frame.rowconfigure(0,weight=1); frame.columnconfigure(0,weight=1)

ttk.Label(root,text="v6: ابتدا با رمز Dashboard وارد 9Router شوید، سپس Register Provider را بزنید. Session فقط در حافظه نگه داشته می‌شود.",padding=(10,0,10,8)).pack(fill="x")
root.mainloop()
