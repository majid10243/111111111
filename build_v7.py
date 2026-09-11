from pathlib import Path
import urllib.request, re

URL='https://raw.githubusercontent.com/majid10243/111111111/main/AI_Provider_Free_Model_Scanner_v6.pyw'
out=Path(__file__).with_name('AI_Provider_Free_Model_Scanner_v7.pyw')
src=Path(__file__).with_name('AI_Provider_Free_Model_Scanner_v6.pyw')
if not src.exists():
    print('Downloading v6 from GitHub...')
    urllib.request.urlretrieve(URL, src)
s=src.read_text(encoding='utf-8')
# Make password optional.
s=s.replace('''    if not password:\n        messagebox.showwarning("9Router Login", "رمز ورود Dashboard 9Router را وارد کنید.")\n        return\n''','''    if not password:\n        ROUTER_COOKIE = ""\n        def probe_no_password():\n            try:\n                code, obj = management_request("/api/providers")\n                root.after(0, lambda: messagebox.showinfo("9Router Login", f"Dashboard بدون Password فعال است.\\n/api/providers -> HTTP {code}"))\n            except urllib.error.HTTPError as e:\n                body = e.read().decode("utf-8", errors="replace")[:1500]\n                root.after(0, lambda: messagebox.showerror("9Router", f"HTTP {e.code}\\n{body}"))\n            except Exception as e:\n                root.after(0, lambda: messagebox.showerror("9Router", str(e)))\n        threading.Thread(target=probe_no_password, daemon=True).start()\n        return\n''',1)
start=s.index('def register_9router_provider():')
end=s.index('\ndef export_csv():',start)
fn=r'''def register_9router_provider():
    models = selected_models()
    if not models: return
    if not clean(router_url_var.get()):
        messagebox.showwarning("9Router", "Base URL را وارد کنید."); return
    name = clean(provider_var.get()) or "Imported Provider"
    upstream = clean(url_var.get()).rstrip("/")
    upstream_key = clean(key_var.get())
    prefix = clean(prefix_var.get()) or "up"
    if not upstream_key:
        messagebox.showwarning("Provider", "API Key سرویس Provider را وارد کنید."); return

    def worker():
        try:
            node_id=None
            # Find existing OpenAI-compatible node.
            try:
                ncode,nres=management_request("/api/provider-nodes","GET")
                nodes=(nres if isinstance(nres,list) else (nres.get("nodes") or nres.get("providerNodes") or nres.get("data") or []) if isinstance(nres,dict) else [])
                for n in nodes:
                    if isinstance(n,dict) and (clean(n.get("prefix"))==prefix or clean(n.get("baseUrl")).rstrip("/")==upstream):
                        node_id=n.get("id") or n.get("_id"); break
            except Exception:
                pass
            # Create node first. This fixes: OpenAI Compatible node not found.
            if not node_id:
                payload={"name":name,"type":"openai-compatible","prefix":prefix,"apiType":"chat","baseUrl":upstream,"chatPath":"/chat/completions","modelsPath":"/models"}
                code,res=management_request("/api/provider-nodes","POST",payload)
                if code not in (200,201):
                    raise RuntimeError(f"ساخت OpenAI Compatible Node ناموفق بود.\\nHTTP {code}\\n{json.dumps(res,ensure_ascii=False)[:2500]}")
                if isinstance(res,dict):
                    n=res.get("node") or res
                    node_id=n.get("id") or n.get("_id") if isinstance(n,dict) else None
            if not node_id:
                raise RuntimeError("OpenAI Compatible Node ساخته/پیدا نشد و ID آن دریافت نشد.")
            payload={"name":name,"provider":node_id,"authType":"apikey","apiKey":upstream_key,"baseUrl":upstream,"priority":10,"isActive":True,"providerSpecificData":{"prefix":prefix,"baseUrl":upstream,"apiType":"chat","enabledModels":[str(m.get("id","")) for m in models]}}
            code,res=management_request("/api/providers","POST",payload)
            if code not in (200,201):
                raise RuntimeError(f"ثبت Provider ناموفق بود.\\nHTTP {code}\\n{json.dumps(res,ensure_ascii=False)[:3000]}")
            pid=res.get("id") or res.get("connectionId") or res.get("providerId") if isinstance(res,dict) else None
            update_note=""
            if pid:
                try:
                    uc,_=management_request(f"/api/providers/{pid}","PUT",{"name":name,"priority":10,"isActive":True,"providerSpecificData":{"prefix":prefix,"baseUrl":upstream,"apiType":"chat","enabledModels":[str(m.get("id","")) for m in models]}})
                    update_note=f"\\nUpdate Provider: HTTP {uc}"
                except Exception as e: update_note=f"\\nUpdate Provider: {e}"
            root.after(0,lambda:messagebox.showinfo("9Router",f"Provider با موفقیت ثبت شد.\\nNode ID: {node_id}\\nConnection HTTP: {code}{update_note}\\n\\nمدل‌ها:\\n"+"\\n".join("• "+router_model_id(m) for m in models)))
        except urllib.error.HTTPError as e:
            body=e.read().decode("utf-8",errors="replace")[:3000]
            root.after(0,lambda:messagebox.showerror("خطای 9Router",f"HTTP {e.code}\\n{body}"))
        except Exception as e:
            root.after(0,lambda:messagebox.showerror("خطای 9Router",str(e)))
    threading.Thread(target=worker,daemon=True).start()
'''
s=s[:start]+fn+s[end:]
s=s.replace('AI Provider Free Model Scanner v6','AI Provider Free Model Scanner v7')
out.write_text(s,encoding='utf-8')
print(out)
