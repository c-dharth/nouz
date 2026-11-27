"""Phone-shell checks: the app as the Capacitor build runs it.

No claude.ai (no window.claude), a phone-sized screen, and a stand-in for Capacitor's App plugin
so the Android back button and platform detection can be driven. This is Chromium, not the iOS
WKWebView or the Android System WebView: it checks the app's logic, not a real device.
"""
import os, sys, subprocess, time
from playwright.sync_api import sync_playwright
HERE=os.path.dirname(os.path.abspath(__file__)); WEB=os.path.join(HERE,"..","web")
srv=subprocess.Popen(["python3","-m","http.server","8766","--bind","127.0.0.1"],cwd=WEB,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
URL="http://127.0.0.1:8766/index.html"
CAP=r"""
window.__min=0;window.__ls={};
window.Capacitor={isNativePlatform:()=>true,getPlatform:()=>"__PLAT__",Plugins:{App:{
  addListener:(n,f)=>{window.__ls[n]=f;return Promise.resolve({remove(){}})},
  minimizeApp:()=>{window.__min++;return Promise.resolve()}}}};
"""
passed=failed=0; errs=[]
def ok(name,cond,extra=""):
    global passed,failed
    if cond: passed+=1; print("PASS",name)
    else: failed+=1; print("FAIL",name,extra)
def act(p,a,**kw):
    p.locator(f'[data-act="{a}"]'+''.join(f'[data-{k}="{v}"]' for k,v in kw.items())).first.click()
def back(p): p.evaluate("window.__ls.backButton&&window.__ls.backButton({canGoBack:false})"); p.wait_for_timeout(80)
def S(p): return p.evaluate("JSON.parse(JSON.stringify(window.__vouz.S))")
def ui(p): return p.evaluate("location.hash")
def overflow(p): return p.evaluate("document.documentElement.scrollWidth>window.innerWidth+1")
def ctx_for(b,plat,w=390,h=844):
    c=b.new_context(viewport={"width":w,"height":h},reduced_motion="reduce",is_mobile=True,has_touch=True)
    c.add_init_script(CAP.replace("__PLAT__",plat))
    p=c.new_page(); p.on("pageerror",lambda e:errs.append(str(e)))
    p.on("console",lambda m: errs.append(m.text) if m.type=="error" and "ERR_" not in m.text and "Failed to load" not in m.text else None)
    return c,p
def onboard_to_pass(p):
    p.goto(URL); p.wait_for_selector(".ob"); act(p,"obNext")
    for pre,v in (("m","4"),("d","9"),("y","1993")): p.select_option(f"#ob-{pre}",v)
    act(p,"obNext"); p.wait_for_selector('[data-act="obMode"]')

with sync_playwright() as pw:
    b=pw.chromium.launch()
    # ---------- Android shell ----------
    c,p=ctx_for(b,"android")
    onboard_to_pass(p)
    ok("native: detected as the phone app, platform class set",p.evaluate("window.__vouz.Native.on") and p.evaluate("document.documentElement.classList.contains('native-android')"))
    ok("native: no claude.ai, so sync is off and the reason fits the phone app",
       p.locator('[data-act="obMode"][data-mode="account"]').is_disabled() and "Not in the phone app yet" in p.inner_text(".ob"))
    back(p); ok("native: back during setup goes to the previous step, not out of the app",p.locator("#ob-y").count()==1 and p.evaluate("window.__min")==0)
    act(p,"obNext"); p.wait_for_selector('[data-act="obMode"]')
    act(p,"obNext"); p.wait_for_selector('[data-act="obPass"]')
    ok("native: setup leads with encryption",p.locator('[data-act="obNext"]').count()==0 and "on by default" in p.inner_text(".ob").lower())
    p.fill("#ob-pp1","quiet harbor lamp"); p.fill("#ob-pp2","quiet harbor lamp"); act(p,"obPass"); p.wait_for_selector(".tabs",timeout=8000)
    raw=p.evaluate("localStorage.getItem('vouz.v1')")
    ok("native: data is encrypted on the device from the first save",'"enc"' in raw and "1993-04-09" not in raw)
    ok("native: Home fits a 390px phone with no sideways scroll",not overflow(p))
    # back button: tab -> Home, page -> previous, sheet -> closed, Home -> leave
    act(p,"tab",tab="profile") if p.locator('[data-act="tab"][data-tab="profile"]').count() else p.locator(".tab",has_text="Profile").click()
    p.wait_for_timeout(80); act(p,"page",page="privacy"); p.wait_for_timeout(80)
    ok("native: Privacy page open",p.locator(".top [data-act='back']").count()==1)
    back(p); ok("native: back closes a page first",p.locator(".top [data-act='back']").count()==0 and p.evaluate("window.__min")==0)
    act(p,"sheet",s="deleteAccount"); p.wait_for_timeout(80); ok("native: a sheet is open",p.locator(".sheet").count()==1)
    back(p); ok("native: back closes a sheet",p.locator(".sheet").count()==0 and p.evaluate("window.__min")==0)
    back(p); ok("native: back from another tab goes Home",p.locator(".today").count()==1 and p.evaluate("window.__min")==0)
    back(p); ok("native: back on Home leaves the app (minimizes)",p.evaluate("window.__min")==1)
    # Discover without connectors
    p.locator(".tab",has_text="Discover").click(); p.wait_for_timeout(300); t=p.inner_text("#app").lower()
    ok("native: Discover without connectors says its places are demo, not real","demo" in t or "sample" in t)
    ok("native: Discover fits the screen",not overflow(p))
    # Quick hide: back must not reveal
    p.locator(".tab",has_text="Home").click(); p.evaluate("window.__vouz.panic()"); p.wait_for_timeout(150)
    p.wait_for_timeout(400); covered=p.locator(".today").count()==0; m0=p.evaluate("window.__min")
    back(p); ok("native: back does nothing while Quick hide is up",covered and p.locator(".today").count()==0 and p.evaluate("window.__min")==m0)
    # reopen: locked; back can't get past the lock
    p.evaluate("sessionStorage.clear()"); p.reload(); p.wait_for_timeout(500)
    ok("native: reopening asks for the passphrase",p.locator("#vault-in").count()==1)
    back(p); ok("native: back can't get past the passphrase",p.locator("#vault-in").count()==1 and p.locator(".tabs").count()==0)
    p.fill("#vault-in","quiet harbor lamp"); act(p,"vaultUnlock"); p.wait_for_selector(".tabs",timeout=8000)
    ok("native: unlocks with the passphrase",p.locator(".tabs").count()==1)
    c.close()
    # ---------- iOS shell, small phone ----------
    c,p=ctx_for(b,"ios",360,740)
    onboard_to_pass(p); act(p,"obNext"); p.wait_for_selector('[data-act="obPass"]')
    act(p,"obSkip"); act(p,"obSkipYes"); p.wait_for_selector(".tabs")
    ok("native iOS: platform class set",p.evaluate("document.documentElement.classList.contains('native-ios')"))
    bad=[]
    for tab in ("Home","Sessions","Discover","Forecast","Profile"):
        p.locator(".tab",has_text=tab).click(); p.wait_for_timeout(200)
        if overflow(p): bad.append(tab)
    ok("native iOS: every tab fits a 360px phone",not bad,str(bad))
    ok("native iOS: notch-safe viewport",p.evaluate("document.querySelector('meta[name=viewport]').content.includes('viewport-fit=cover')"))
    c.close()
    # ---------- the artifact is unchanged ----------
    c=b.new_context(viewport={"width":390,"height":844}); p=c.new_page(); p.goto(URL); p.wait_for_selector(".ob")
    ok("web: without Capacitor the native layer stays off",p.evaluate("window.__vouz.Native.on")==False and not p.evaluate("document.documentElement.classList.contains('native')"))
    c.close(); b.close()
srv.terminate()
ok("no uncaught page errors",not errs,"\n".join(errs[:5]))
print(f"\n{passed}/{passed+failed} passed"); sys.exit(1 if failed else 0)
