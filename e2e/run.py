import os
import json, sys, subprocess, time, re
from playwright.sync_api import sync_playwright
HERE=os.path.dirname(os.path.abspath(__file__)); WEB=os.path.join(HERE,"..","web"); SH=os.path.join(HERE,"shots","")
os.makedirs(SH,exist_ok=True)
srv=subprocess.Popen(["python3","-m","http.server","8765","--bind","127.0.0.1"],cwd=WEB,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
URL="http://127.0.0.1:8765/index.html"
STORE={}; WRITES=[]
def can_read(u,p):
    s=p.split('/')
    if p.startswith('data/users/'): return s[2]==u
    if s[0]=='reports': return s[1]==u
    return True
def can_write(u,p):
    s=p.split('/')
    if p.startswith('data/users/'): return s[2]==u
    return s[0] in('profiles','posts','reactions','comments','links','invites','reports') and s[1]==u
def db_get(src,u,p): return STORE.get(p) if can_read(u,p) else None
def db_set(src,u,p,d):
    if not can_write(u,p): raise Exception('invalid_argument')
    STORE[p]=json.loads(d); WRITES.append(p)
def db_del(src,u,p):
    if not can_write(u,p): raise Exception('invalid_argument')
    STORE.pop(p,None)
def db_list(src,u,c): return {k.split('/')[-1]:v for k,v in STORE.items() if k.startswith(c+'/') and k.count('/')==c.count('/')+1 and can_read(u,k)}
MOCK=r"""
(()=>{const U='__UID__';
const snap=(p,v)=>({id:p.split('/').pop(),exists:v!==null&&v!==undefined,data:()=>v,metadata:{fromCache:false,hasPendingWrites:false}});
const doc=(p)=>({id:p.split('/').pop(),path:p,get:async()=>snap(p,await window.__dbGet(U,p)),set:async(d)=>{try{await window.__dbSet(U,p,JSON.stringify(d))}catch(e){throw {code:'invalid_argument'}}},delete:async()=>{await window.__dbDel(U,p)}});
const coll=(c)=>({path:c,doc:(id)=>doc(c+'/'+id),onSnapshot:(next)=>{let last=null,on=true;const f=async()=>{if(!on)return;const m=await window.__dbList(U,c);const j=JSON.stringify(m);if(j!==last){last=j;next({docs:Object.keys(m).map(k=>snap(c+'/'+k,m[k]))})}setTimeout(f,120)};f();return()=>{on=false}}});
window.claude={use:async(n)=>n==='db'?{doc,collection:coll}:n==='user'?{id:async()=>U,can:async()=>true}:null};})();
"""
res=[]
def ok(name,cond,extra=""):
    res.append((name,bool(cond),extra)); print(("PASS" if cond else "FAIL"),name,extra if not cond else "")
def act(p,act_,**kw):
    sel=f'[data-act="{act_}"]'+''.join(f'[data-{k}="{v}"]' for k,v in kw.items())
    p.locator(sel).first.click()
def S(p): return p.evaluate("JSON.parse(JSON.stringify(window.__vouz.S))")
def onboard(p,social=False,account=False):
    act(p,"obNext"); assert p.locator('[data-act="obNext"]').is_disabled()
    act(p,"obAdult"); act(p,"obNext")
    if account: act(p,"obMode",mode="account")
    p.fill("#ob-name","Sid")
    if social: act(p,"obSocial")
    act(p,"obNext")
errs=[]
def newctx(b,uid=None,motion="reduce"):
    ctx=b.new_context(viewport={"width":390,"height":844},reduced_motion=motion)
    if uid:
        ctx.expose_binding("__dbGet",db_get); ctx.expose_binding("__dbSet",db_set); ctx.expose_binding("__dbDel",db_del); ctx.expose_binding("__dbList",db_list)
        ctx.add_init_script(MOCK.replace("__UID__",uid))
    p=ctx.new_page(); p.on("pageerror",lambda e:errs.append(str(e)))
    p.on("console",lambda m: errs.append(m.text) if m.type=="error" and "ERR_" not in m.text and "Failed to load" not in m.text else None)
    return ctx,p
def log(p,title,mins,**kw):
    act(p,"tab",tab="track"); act(p,"manual"); p.fill("#d-title",title); p.fill("#d-min",str(mins))
    if "notes" in kw: p.fill("#d-notes",kw["notes"])
    if "hr" in kw: p.fill("#d-hra",kw["hr"])
    if "cat" in kw: act(p,"dCat",v=kw["cat"])
    if "mood" in kw: act(p,"dMood",v=kw["mood"])
    if "tag" in kw: p.fill("#d-tag",kw["tag"]); p.press("#d-tag","Enter")
    act(p,"saveSession"); p.wait_for_selector("text=Saved privately"); act(p,"back")
def feed(p):
    act(p,"tab",tab="social"); act(p,"socSeg",v="feed"); p.wait_for_timeout(700); return p.inner_text(".scroll")
with sync_playwright() as pw:
    b=pw.chromium.launch(executable_path="/usr/bin/google-chrome",args=["--no-sandbox"])
    # ---------- local mode ----------
    ctx,p=newctx(b); p.goto(URL); p.wait_for_selector(".ob")
    ok("onboarding is 3 steps with required 18+ acknowledgment",p.locator(".steps i").count()==3)
    onboard(p)
    s=S(p); ok("onboarding: social off by default, local mode",s["onboarded"] and not s["settings"]["social"] and s["user"]["mode"]=="local")
    ok("nav: social tab hidden when off",p.locator(".tab").count()==4)
    ok("home: empty state, ring present, no fabricated stats",p.locator("text=Nothing logged yet").count()==1 and p.locator(".trio").count()==0 and p.locator('.stage g[data-act="pickDay"]').count()==7)
    act(p,"start"); p.wait_for_timeout(2100); act(p,"pause"); p.wait_for_timeout(1000)
    t_paused=p.inner_text("#clock"); p.wait_for_timeout(1100)
    ok("timer: paused clock does not advance",p.inner_text("#clock")==t_paused,t_paused)
    act(p,"resume"); p.reload(); p.wait_for_selector("#clock"); p.wait_for_timeout(1200)
    ok("timer: active session survives reload",p.inner_text("#clock")>="00:00:03",p.inner_text("#clock"))
    act(p,"finish"); p.fill("#d-title","Friday"); p.fill("#d-notes","SECRETNOTE"); p.fill("#d-hra","111"); act(p,"dCat",v="duo"); act(p,"dMood",v="Tender")
    p.reload(); p.wait_for_timeout(300); act(p,"resumeDraft")
    ok("draft survives reload",p.input_value("#d-notes")=="SECRETNOTE")
    act(p,"saveSession"); p.wait_for_selector("text=Saved privately")
    s=S(p); ok("J1 new session saved",len(s["sessions"])==1 and 3<=s["sessions"][0]["durationSec"]<=6 and len(s["sessions"][0]["segments"])==2 and s["active"] is None)
    sid=s["sessions"][0]["id"]
    ok("replay: milestones and interactive timeline",p.locator("text=First Round").count()>=1 and p.locator('[data-act="rSeg"]').count()==2)
    act(p,"rSeg",i="1"); ok("replay: tapping a part shows its detail","Part 2 of 2" in p.inner_text(".scroll"))
    p.fill("#rf-text","REFLECTTEXT"); act(p,"rSave"); act(p,"rMood",v="Playful")
    e=S(p)["sessions"][0]; ok("replay: reflection and mood saved privately",e["reflection"]=="REFLECTTEXT" and e["mood"]=="Playful")
    act(p,"back"); act(p,"tab",tab="track"); act(p,"manual"); p.fill("#d-min","0"); p.fill("#d-sec","0"); act(p,"saveSession")
    ok("validation: zero duration rejected",p.locator(".err").count()==1 and len(S(p)["sessions"])==1)
    p.fill("#d-min","40"); act(p,"dCat",v="solo"); act(p,"saveSession"); p.wait_for_selector("text=Saved privately")
    ok("replay: history comparison appears with 2+ sessions","your average" in p.inner_text(".scroll") and "Session 1 of 2" in p.inner_text(".scroll"))
    act(p,"back"); act(p,"tab",tab="home")
    tiles=[t.inner_text() for t in p.locator(".trio b").all()]
    ok("home stats computed from records",tiles[0]=="2" and tiles[1].startswith("40"),str(tiles))
    todayI=p.evaluate("(new Date().getDay()+6)%7"); other=(todayI+3)%7
    p.locator(f'.stage g[data-i="{other}"]').focus(); p.keyboard.press("Enter")
    ok("home ring: day arcs selectable by keyboard",p.locator(f'.stage g[data-i="{other}"]').get_attribute("aria-pressed")=="true")
    act(p,"openReplay",id=sid) if p.locator(f'[data-act="openReplay"][data-id="{sid}"]').count() else None
    act(p,"editSession",id=sid); p.fill("#d-min","10"); p.fill("#d-sec","0"); act(p,"saveSession"); p.wait_for_timeout(200)
    e=[x for x in S(p)["sessions"] if x["id"]==sid][0]
    ok("J2 edit updates record, keeps private fields",e["durationSec"]==600 and e["notes"]=="SECRETNOTE" and e["reflection"]=="REFLECTTEXT")
    act(p,"back"); act(p,"tab",tab="insights"); act(p,"insRange",v="year")
    tl=[t.inner_text() for t in p.locator(".tile b").all()]
    ok("J4 analytics reflect edit",tl[0]=="2" and tl[1]=="50m" and tl[3].startswith("40m"),str(tl[:4]))
    act(p,"insCat",v="solo"); ok("filter: category",p.locator(".tile b").first.inner_text()=="1")
    act(p,"insCat",v="all"); act(p,"insTab",v="patterns"); t=p.inner_text(".scroll")
    ok("insights: time-of-day and weekday patterns","time of day" in t.lower() and "most often in the" in t.lower() and "categories" in t.lower())
    act(p,"insTab",v="mood"); t=p.inner_text(".scroll"); ok("insights: mood and reflections","Playful" in t and "REFLECTTEXT" in t)
    ok("insights copy never frames more as better",not re.search(r"\b(better than|keep it up|great job|improve|goal reached|up from)\b",p.inner_text("body"),re.I))
    act(p,"insTab",v="overview"); act(p,"insRange",v="custom"); p.fill("#i-from","2020-01-01"); p.dispatch_event("#i-from","change"); p.fill("#i-to","2020-01-31"); p.dispatch_event("#i-to","change")
    ok("filter: custom range",p.locator(".tile b").first.inner_text()=="0")
    act(p,"tab",tab="home"); act(p,"page",page="history"); act(p,"openReplay",id=sid); act(p,"editSession",id=sid); act(p,"askDelete"); ok("delete asks for confirmation",p.locator(".sheet").count()==1 and len(S(p)["sessions"])==2)
    p.keyboard.press("Escape"); ok("sheets close with Escape",p.locator(".sheet").count()==0)
    act(p,"askDelete"); act(p,"confirmYes"); ok("J3 delete removes record and leaves a tombstone",len(S(p)["sessions"])==1 and sid in S(p)["deleted"])
    act(p,"tab",tab="home"); ok("J4 analytics reflect delete",p.locator(".trio b").first.inner_text()=="1")
    act(p,"tab",tab="profile"); ok("social toggle unavailable without account",p.locator('[data-act="toggleSocial"]').is_disabled())
    small=p.evaluate("""()=>Array.from(document.querySelectorAll('button,[role=button],input,textarea')).filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&(r.height<43.5)}).map(e=>(e.dataset.act||e.id||e.tagName)+':'+Math.round(e.getBoundingClientRect().height))""")
    ok("touch targets at least 44px (profile)",not small,str(small))
    act(p,"togglePin"); p.fill("#pin-new","1234"); act(p,"pinSave"); p.wait_for_timeout(600)
    ok("passcode stored as slow salted hash, not the code",S(p)["settings"]["pinAlg"]=="pbkdf2" and len(S(p)["settings"]["pinHash"])==64)
    p.reload(); p.wait_for_selector("#pin-in")
    ok("lock screen renders no session data",p.locator(".scroll").count()==0 and "SECRETNOTE" not in p.inner_text("body") and "Session" not in p.inner_text("body"))
    for i in range(5): p.fill("#pin-in","0000"); act(p,"unlock"); p.wait_for_timeout(350)
    ok("passcode: five wrong tries start a wait","Wait" in p.inner_text("body") and p.locator("#pin-in").is_disabled())
    p.evaluate("()=>{const s=JSON.parse(localStorage.getItem('vouz.v1'));s.settings.pinUntil=0;localStorage.setItem('vouz.v1',JSON.stringify(s))}"); p.reload(); p.wait_for_selector("#pin-in")
    p.fill("#pin-in","1234"); act(p,"unlock"); p.wait_for_selector(".tabs"); ok("passcode: right code unlocks",True)
    act(p,"tab",tab="profile"); act(p,"loadDemo"); act(p,"tab",tab="home"); ok("demo data is labelled",p.locator(".banner").count()==1)
    act(p,"tab",tab="profile"); act(p,"exportData"); p.wait_for_selector("#exp-out"); ex=p.input_value("#exp-out")
    ok("export: own sessions only, no passcode or keys",'"sessions"' in ex and '"pinHash": null' in ex and '"demo": true' not in ex and '"keys"' not in ex); act(p,"closeSheet")
    act(p,"removeDemo"); ok("demo removed, own data kept",len(S(p)["sessions"])==1)
    act(p,"sheet",s="deleteAccount"); act(p,"deleteAccountYes"); ok("delete account needs typed confirm",S(p)["onboarded"])
    p.fill("#del-in","DELETE"); act(p,"deleteAccountYes"); p.wait_for_selector(".ob")
    ok("J10 local: storage wiped",p.evaluate("localStorage.getItem('vouz.v1')") is None)
    ctx.close()
    # ---------- two real users over a shared rule-enforcing store ----------
    ca,a=newctx(b,"alice"); cb,bb=newctx(b,"bob"); cc,c=newctx(b,"carol")
    for pg,nm in ((a,"ali"),(bb,"bobby"),(c,"caz")):
        pg.goto(URL); pg.wait_for_timeout(400); onboard(pg,account=(pg is a))
    log(a,"PRIVATETITLE",33,notes="SECRETNOTE",hr="123",cat="duo",mood="Electric",tag="SECRETTAG"); a.wait_for_timeout(1700)
    ok("account sync: only the private vault is written",set(STORE.keys())=={"data/users/alice/vault"},str(list(STORE.keys())))
    ok("private vault unreadable by another user",db_get(None,"bob","data/users/alice/vault") is None)
    for pg,nm in ((a,"ali"),(bb,"bobby"),(c,"caz")):
        act(pg,"tab",tab="profile"); act(pg,"toggleSocial"); pg.fill("#s-handle",nm); act(pg,"sheetPrivate"); act(pg,"socialOnYes"); pg.wait_for_selector('.tab[data-tab="social"]'); pg.wait_for_timeout(300)
    ok("J5 enable social: profile + keys created, nothing posted","profiles/alice" in STORE and "data/users/alice/keys" in STORE and "posts/alice" not in STORE and a.locator(".tab").count()==5)
    # connect alice<->bob ; carol stays unconnected
    act(a,"socSeg",v="people"); a.wait_for_timeout(500); act(a,"request",id="bob"); a.wait_for_timeout(500)
    links=json.dumps(STORE["links/alice"]); ok("connection list stores opaque labels, not user ids","bob" not in links and "alice" not in links,links[:120])
    sid=S(a)["sessions"][0]["id"]
    act(a,"tab",tab="home"); act(a,"page",page="history"); act(a,"openReplay",id=sid); act(a,"composeRecap",id=sid); a.fill("#c-cap","CONNCAPTION")
    ok("composer defaults to connections audience",a.locator('[data-act="cAud"][data-v="all"]').get_attribute("aria-pressed")=="true")
    act(a,"composeStep",v="preview"); ok("J6 preview required before share",a.locator('[data-act="publish"]').count()==1 and "posts/alice" not in STORE)
    a.screenshot(path=SH+"preview.png"); act(a,"publish"); a.wait_for_timeout(900)
    raw=json.dumps(STORE["posts/alice"])
    ok("J6/J9 connections-only card is ciphertext in storage",not any(w in raw for w in ["CONNCAPTION","About 35","SECRETNOTE","SECRETTAG","PRIVATETITLE","Electric","bpm","recap",sid]) and '"c":' in raw,raw[:200])
    ok("J7 one-sided request grants no key",list(STORE["posts/alice"]["items"][0]["wk"].keys())==["self"])
    ok("bob (pending) and carol cannot see it","CONNCAPTION" not in feed(bb) and "CONNCAPTION" not in feed(c))
    act(bb,"socSeg",v="people"); bb.wait_for_timeout(400); act(bb,"approve",id="alice"); bb.wait_for_timeout(1500); a.wait_for_timeout(1200)
    ok("after both approve, exactly one recipient key is added",len(STORE["posts/alice"]["items"][0]["wk"])==2)
    ok("J7 approved connection can open the card","CONNCAPTION" in feed(bb))
    ok("unconnected user still cannot","CONNCAPTION" not in feed(c))
    tk=bb.locator('[data-act="comment"]').first.get_attribute("data-k"); bb.fill(f'[id="c-{tk}"]',"SECRETCOMMENT"); act(bb,"comment",k=tk); act(bb,"react",k=tk,e="🔥"); bb.wait_for_timeout(900)
    ok("comment on a connections-only card is encrypted, and unlinkable to the card","SECRETCOMMENT" not in json.dumps(STORE["comments/bob"]) and STORE["posts/alice"]["items"][0]["id"] not in json.dumps(STORE["comments/bob"])+json.dumps(STORE["reactions/bob"]))
    ok("author reads the comment and reaction","SECRETCOMMENT" in feed(a) and "🔥 1" in a.inner_text(".scroll"))
    # public card
    act(a,"tab",tab="home"); act(a,"page",page="history"); act(a,"openReplay",id=sid); act(a,"composeRecap",id=sid); a.fill("#c-cap","PUBLICCAP"); act(a,"cAud",v="everyone"); act(a,"composeStep",v="preview"); act(a,"publish"); a.wait_for_timeout(800)
    pub=json.dumps([i for i in STORE["posts/alice"]["items"] if i.get("vis")=="everyone"])
    ok("everyone-card is sanitized whitelist only","PUBLICCAP" in pub and "About 35 min" in pub and not any(w in pub for w in ["SECRETNOTE","SECRETTAG","PRIVATETITLE","Electric","123",sid]),pub)
    ok("everyone-card visible to unconnected user","PUBLICCAP" in feed(c))
    # permission off -> key withdrawn
    act(a,"tab",tab="social"); act(a,"socSeg",v="people"); a.wait_for_timeout(400); act(a,"sheet",s="conn",id="bob"); act(a,"permRecaps",id="bob"); a.wait_for_timeout(1300)
    ok("turning a permission off removes the recipient key",len([i for i in STORE["posts/alice"]["items"] if i.get("c")][0]["wk"])==1)
    ok("and the connection loses the card","CONNCAPTION" not in feed(bb))
    act(a,"permRecaps",id="bob"); a.wait_for_timeout(1300); act(a,"closeSheet"); ok("turning it back on restores access","CONNCAPTION" in feed(bb))
    # ---------- adding people to a saved session ----------
    def replay(pg,i): act(pg,"tab",tab="home"); act(pg,"page",page="history"); act(pg,"openReplay",id=i); pg.wait_for_timeout(200)
    def home(pg):
        while pg.locator('[data-act="back"]').count(): act(pg,"back")
        act(pg,"tab",tab="home"); pg.wait_for_timeout(700); return pg.inner_text(".scroll")
    replay(a,sid); act(a,"addPeople"); names=[x.locator("b").inner_text().strip() for x in a.locator('[data-act="inviteAsk"]').all()]
    ok("people: only my connections are offered",names==["bobby"],str(names))
    act(a,"inviteAsk",id="bob"); ok("people: sending asks first and says what is shown","date, time, length and category (Duo)" in a.inner_text(".sheet") and "invites/alice" not in STORE); a.screenshot(path=SH+"ppl_confirm.png")
    act(a,"confirmYes"); a.wait_for_timeout(900); raw=json.dumps(STORE["invites/alice"]); st=str(S(a)["sessions"][0]["start"])
    ok("people: the invite is sealed in storage",len(STORE["invites/alice"]["items"])==1 and not any(w in raw for w in ["bob","alice",sid,st,"duo","1980","PRIVATETITLE","SECRETNOTE"]),raw[:200])
    ok("people: sender sees Invited","Invited" in a.inner_text(".scroll") and S(a)["sessions"][0]["people"][0]["id"]=="bob"); a.screenshot(path=SH+"ppl_replay.png")
    hb=home(bb); bb.screenshot(path=SH+"ppl_inbox.png")
    ok("people: the invited person is asked, nothing is added yet","ali added you to a session" in hb and "Duo" in hb and len(S(bb)["sessions"])==0,hb[:200])
    ok("people: nobody else can see the invite","added you" not in home(c) and c.evaluate("window.__vouz.Soc.inbox.length")==0)
    act(bb,"invYes"); bb.wait_for_timeout(900); bs=S(bb)["sessions"]
    ok("people: accepting saves a private copy with time, length and category only",len(bs)==1 and bs[0]["durationSec"]==1980 and bs[0]["category"]=="duo" and bs[0]["start"]==S(a)["sessions"][0]["start"] and bs[0]["notes"]=="" and bs[0]["title"]=="" and bs[0]["mood"]=="" and bs[0]["tags"]==[] and bs[0]["hrAvg"]=="" and "Added you" in bb.inner_text(".scroll"),str(bs)[:300])
    ok("people: the invite leaves the inbox once answered","added you" not in home(bb))
    a.wait_for_timeout(600); ok("people: sender sees Confirmed","Confirmed" in a.inner_text(".scroll"))
    card=a.evaluate("JSON.stringify(window.__vouz.buildCard({kind:'recap',style:0,title:'t',showDuration:true,showCategory:true},window.__vouz.S.sessions[0]))")
    ok("people: a shared card never carries who was there","bob" not in card and "people" not in card,card)
    replay(bb,bs[0]["id"]); act(bb,"personOff"); bb.wait_for_timeout(900); a.wait_for_timeout(600)
    ok("people: either side can step out, and the sender is told","Declined" in a.inner_text(".scroll") and S(bb)["sessions"][0].get("people")==[] )
    act(a,"personOff"); a.wait_for_timeout(900)
    ok("people: removing someone withdraws the invite",STORE["invites/alice"]["items"]==[] and S(a)["sessions"][0]["people"]==[])
    home(a); home(bb); log(bb,"BOBS",10); bid=[x for x in S(bb)["sessions"] if x["title"]=="BOBS"][0]["id"]; replay(bb,bid); act(bb,"addPeople"); act(bb,"inviteAsk",id="alice"); act(bb,"confirmYes"); bb.wait_for_timeout(900)
    ok("people: invite arrives on Home","bobby added you" in home(a)); act(a,"invNo"); a.wait_for_timeout(900); bb.wait_for_timeout(600)
    ok("people: declining saves nothing, and the sender sees Declined",len(S(a)["sessions"])==1 and "added you" not in home(a) and "Declined" in bb.inner_text(".scroll"))
    act(bb,"editSession",id=bid); act(bb,"askDelete"); act(bb,"confirmYes"); bb.wait_for_timeout(900)
    ok("people: deleting a session withdraws its invites",STORE["invites/bob"]["items"]==[])
    home(a); home(bb); act(a,"tab",tab="social"); act(a,"socSeg",v="people"); a.wait_for_timeout(300); feed(c)
    # tamper: bob cannot write alice's docs
    try: db_set(None,"bob","posts/alice",'{"items":[]}'); tam=False
    except Exception: tam=True
    ok("another user cannot overwrite someone's cards",tam)
    # block
    act(a,"sheet",s="conn",id="bob"); act(a,"block",id="bob"); a.wait_for_timeout(1300)
    ok("block removes the key and the link",len([i for i in STORE["posts/alice"]["items"] if i.get("c")][0]["wk"])==1 and STORE["links/alice"]["out"]=={} and "CONNCAPTION" not in feed(bb))
    act(a,"socSeg",v="people"); act(a,"unblock",id="bob"); a.wait_for_timeout(300)
    # report
    act(c,"postMenu",a="alice"); act(c,"report",a="alice"); act(c,"reportWhy",v="Harassment"); act(c,"reportSend"); c.wait_for_timeout(400)
    ok("report filed, unreadable by the reported user",len(STORE["reports/carol"]["items"])==1 and db_get(None,"alice","reports/carol") is None)
    # J8 social off (keep) -> nothing left in shared storage, stashed privately; back on -> restored
    act(a,"tab",tab="profile"); act(a,"toggleSocial"); act(a,"socialOffYes"); a.wait_for_timeout(900)
    ok("J8 Social off: nothing of mine left in shared storage, tracking intact",not any(k.endswith("/alice") and not k.startswith("data/") for k in STORE) and "data/users/alice/stash" in STORE and a.locator(".tab").count()==4 and len(S(a)["sessions"])==1,str([k for k in STORE if "alice" in k]))
    ok("others no longer see my cards","PUBLICCAP" not in feed(c))
    act(a,"toggleSocial"); a.fill("#s-handle","ali"); act(a,"socialOnYes"); a.wait_for_selector('.tab[data-tab="social"]'); a.wait_for_timeout(900)
    ok("Social back on restores my cards","posts/alice" in STORE and "data/users/alice/stash" not in STORE and "PUBLICCAP" in feed(c))
    act(a,"tab",tab="profile"); act(a,"toggleSocial"); act(a,"sheetWipe"); act(a,"socialOffYes"); a.wait_for_timeout(900)
    ok("J8 Social off with delete: shared content, stash and keys gone",not any("alice" in k for k in STORE if k!="data/users/alice/vault"),str([k for k in STORE if "alice" in k]))
    # sync merge across devices
    ca2,a2=newctx(b,"alice"); a2.goto(URL); a2.wait_for_timeout(400); act(a2,"obNext"); act(a2,"obAdult"); act(a2,"obNext"); act(a2,"obMode",mode="account"); a2.wait_for_selector('[data-act="obRestore"]'); act(a2,"obRestore"); a2.wait_for_timeout(300)
    ok("second device restores from private sync",len(S(a2)["sessions"])==1 and S(a2)["sessions"][0]["notes"]=="SECRETNOTE")
    log(a2,"fromdevice2",12); a2.wait_for_timeout(1700)
    act(a,"tab",tab="home"); act(a,"page",page="history"); act(a,"openReplay",id=sid); act(a,"editSession",id=sid); act(a,"askDelete"); act(a,"confirmYes"); a.wait_for_timeout(1700)
    a.reload(); a.wait_for_timeout(2200); a2.reload(); a2.wait_for_timeout(2200)
    t1=sorted(x["title"] for x in S(a)["sessions"]); t2=sorted(x["title"] for x in S(a2)["sessions"])
    ok("sync merges: new session arrives, deletion propagates",t1==["fromdevice2"] and t2==["fromdevice2"],f"{t1} {t2}")
    # J10
    act(a,"tab",tab="profile"); act(a,"sheet",s="deleteAccount"); a.fill("#del-in","DELETE"); act(a,"deleteAccountYes"); a.wait_for_selector(".ob"); a.wait_for_timeout(600)
    ok("J10 account deletion removes vault and every document of mine",not any("alice" in k for k in STORE),str([k for k in STORE if "alice" in k]))
    for x in (ca,cb,cc,ca2): x.close()

    # ---------- categories: existing data, every category, filters ----------
    LEG={"v":1,"onboarded":True,"stamp":1,"user":{"name":"Sid","mode":"local","createdAt":1},"settings":{"social":False,"privateProfile":True,"defaultVis":"connections","regular":None,"pinHash":None,"pinSalt":None},
         "sessions":[{"id":"old1","title":"OLDSOLO","start":int(time.time()*1000)-3*86400000,"durationSec":900,"segments":None,"category":"solo","tags":[],"mood":"","notes":"keepme","hrAvg":"","hrPeak":"","createdAt":1,"updatedAt":1},
                     {"id":"old2","title":"OLDPARTNERED","start":int(time.time()*1000)-2*86400000,"durationSec":1800,"segments":None,"category":"partnered","tags":["x"],"mood":"Tender","notes":"","hrAvg":"","hrPeak":"","createdAt":1,"updatedAt":1}],
         "active":None,"draft":None,"blocks":[],"ignored":[]}
    ctx=b.new_context(viewport={"width":390,"height":844},reduced_motion="reduce"); ctx.add_init_script("if(!localStorage.getItem('vouz.v1'))localStorage.setItem('vouz.v1',"+json.dumps(json.dumps(LEG))+")")
    p=ctx.new_page(); p.on("pageerror",lambda e:errs.append(str(e))); p.goto(URL); p.wait_for_selector(".tabs")
    ok("cat: app opens on saved data from the earlier version",p.locator(".trio b").first.inner_text()=="2")
    act(p,"page",page="history"); h=p.inner_text(".scroll")
    ok("cat: earlier solo and partnered sessions still listed with their labels","OLDSOLO" in h and "OLDPARTNERED" in h and "Partnered" in h and "Solo" in h)
    act(p,"openReplay",id="old2"); ok("cat: Replay works for an earlier partnered session",p.locator(".pill.c").first.inner_text()=="Partnered")
    act(p,"editSession",id="old2"); ok("cat: edit form keeps Partnered selected for an earlier session",p.locator('[data-act="dCat"][data-v="partnered"]').get_attribute("aria-pressed")=="true" and p.locator('[data-act="dCat"]').count()==5)
    p.fill("#d-title","OLDPARTNERED2"); act(p,"saveSession"); p.wait_for_timeout(200)
    raw=json.loads(p.evaluate("localStorage.getItem('vouz.v1')")); by={x["id"]:x for x in raw["sessions"]}
    ok("cat: editing an earlier session does not reclassify it",by["old2"]["category"]=="partnered" and by["old2"]["title"]=="OLDPARTNERED2" and by["old1"]["category"]=="solo" and by["old1"]["notes"]=="keepme")
    act(p,"back")
    act(p,"tab",tab="track"); act(p,"manual"); ok("cat: new sessions offer Solo, Duo, Trio, Group only",[x.inner_text() for x in p.locator('[data-act="dCat"]').all()]==["Solo","Duo","Trio","Group"]); act(p,"back")
    for cat in ("solo","duo","trio"): log(p,"NEW"+cat,10,cat=cat)
    act(p,"tab",tab="track"); act(p,"manual"); p.fill("#d-title","NEWgroup"); act(p,"dCat",v="group"); p.fill("#d-gsize","3"); act(p,"saveSession")
    ok("cat: group count below 4 is rejected",p.locator(".err").count()==1)
    p.fill("#d-gsize","5"); act(p,"saveSession"); p.wait_for_selector("text=Saved privately")
    ok("cat: Replay shows the group size privately",p.locator(".pill.c").first.inner_text()=="Group of 5"); gid=S(p)["sessions"][-1]["id"]; act(p,"back")
    log(p,"NEWgroupblank",10,cat="group"); log(p,"NEWnone",10)
    ss={x["title"]:x for x in S(p)["sessions"]}
    ok("cat: every category saves; count optional; category optional",ss["NEWsolo"]["category"]=="solo" and ss["NEWduo"]["category"]=="duo" and ss["NEWtrio"]["category"]=="trio" and ss["NEWgroup"]["groupSize"]==5 and ss["NEWgroupblank"]["groupSize"] is None and ss["NEWnone"]["category"] is None)
    # timer-based save with a category
    act(p,"tab",tab="track"); act(p,"start"); p.wait_for_timeout(1200); act(p,"pause"); act(p,"resume"); p.wait_for_timeout(300); act(p,"finish"); act(p,"dCat",v="trio"); act(p,"saveSession"); p.wait_for_selector("text=Saved privately"); act(p,"back")
    ok("cat: timer start, pause, resume, finish saves with a category",S(p)["sessions"][-1]["category"]=="trio" and len(S(p)["sessions"][-1]["segments"])==2)
    act(p,"tab",tab="home"); act(p,"page",page="history"); h=p.inner_text(".scroll")
    ok("cat: history shows all labels",all(w in h for w in ["Solo","Duo","Trio","Group of 5","Group","Partnered"]))
    act(p,"openReplay",id=gid); act(p,"rScope",v="cat"); ok("cat: Replay same-category comparison works for Group","your average" in p.inner_text(".scroll")); act(p,"back"); act(p,"back")
    act(p,"tab",tab="insights"); act(p,"insRange",v="year"); cnt={}
    for cat in ("all","solo","duo","trio","group","partnered"): act(p,"insCat",v=cat); cnt[cat]=p.locator(".tile b").first.inner_text()
    ok("cat: Insights filters count each category",cnt=={"all":"9","solo":"2","duo":"1","trio":"2","group":"2","partnered":"1"},str(cnt))
    act(p,"insCat",v="all"); act(p,"insTab",v="patterns"); t=p.inner_text(".scroll")
    ok("cat: Insights category breakdown lists all, plus not set",all(w in t for w in ["Solo 2","Duo 1","Trio 2","Group 2","Partnered 1","Not set 1"]))
    card=p.evaluate("id=>JSON.stringify(window.__vouz.buildCard({kind:'recap',showCategory:true,showDuration:true,style:0},window.__vouz.S.sessions.find(s=>s.id===id)))",gid)
    ok("cat: a shared card says Group and never the head count",'"category":"Group"' in card and "5" not in card.replace("About 5 min","").replace('"arc":5',""),card)
    p.reload(); p.wait_for_selector(".tabs"); ok("cat: all data still there after reload, key unchanged",len(S(p)["sessions"])==9 and p.evaluate("Object.keys(localStorage).join()")=="vouz.v1")
    act(p,"tab",tab="profile"); ok("cat: privacy settings unchanged (Social off, tab hidden)",S(p)["settings"]["social"] is False and p.locator(".tab").count()==4)
    p.screenshot(path=SH+"cat_profile.png"); act(p,"tab",tab="track"); act(p,"manual"); act(p,"dCat",v="group"); p.screenshot(path=SH+"cat_form.png")
    # quick category on the Track screen
    act(p,"back"); act(p,"tab",tab="track")
    ok("quick: Track offers the four categories before starting",[x.inner_text() for x in p.locator('[data-act="tCat"]').all()]==["Solo","Duo","Trio","Group"])
    act(p,"tCat",v="duo"); p.screenshot(path=SH+"cat_track.png"); act(p,"start"); p.wait_for_timeout(1100)
    ok("quick: choice made before start is carried into the running session",S(p)["active"]["category"]=="duo" and p.locator('[data-act="tCat"][data-v="duo"]').get_attribute("aria-pressed")=="true")
    act(p,"pause"); act(p,"tCat",v="trio"); act(p,"resume"); p.screenshot(path=SH+"cat_live.png"); p.reload(); p.wait_for_selector(".tabs"); act(p,"tab",tab="track")
    ok("quick: change during a session survives a reload, timer intact",S(p)["active"]["category"]=="trio" and len(S(p)["active"]["segments"])==2)
    act(p,"finish"); ok("quick: save form opens with it selected, category first",p.locator('[data-act="dCat"][data-v="trio"]').get_attribute("aria-pressed")=="true" and p.locator(".scroll h3").first.inner_text().startswith("CATEGORY") or p.locator(".scroll h3").first.inner_text().lower().startswith("category"))
    p.screenshot(path=SH+"cat_save.png"); act(p,"saveSession"); p.wait_for_selector("text=Saved privately"); act(p,"back")
    ok("quick: timer session saved with the Track choice",S(p)["sessions"][-1]["category"]=="trio" and len(S(p)["sessions"][-1]["segments"])==2)
    act(p,"tab",tab="track"); act(p,"start"); p.wait_for_timeout(1100); act(p,"finish"); act(p,"saveSession"); p.wait_for_selector("text=Saved privately"); act(p,"back")
    ok("quick: skipping it still saves with no category, and the earlier pick does not stick",S(p)["sessions"][-1]["category"] is None)
    ctx.close()
    # screenshots with motion on
    ctx,p=newctx(b,motion="no-preference"); p.goto(URL); p.wait_for_timeout(700); p.screenshot(path=SH+"ob.png"); onboard(p); act(p,"loadDemo"); p.wait_for_timeout(3600); p.screenshot(path=SH+"home.png")
    ok("count-up settles on the true value",p.locator(".trio b").first.inner_text()=="12")
    sid=S(p)["sessions"][0]["id"]; act(p,"page",page="history"); act(p,"openReplay",id=sid); p.wait_for_timeout(1500); p.screenshot(path=SH+"replay.png"); p.locator(".scroll").evaluate("e=>e.scrollTop=560"); p.wait_for_timeout(200); p.screenshot(path=SH+"replay2.png")
    act(p,"back"); act(p,"back"); act(p,"tab",tab="insights"); act(p,"insRange",v="year"); act(p,"insTab",v="patterns"); p.wait_for_timeout(3400); p.screenshot(path=SH+"patterns.png"); act(p,"insTab",v="mood"); p.screenshot(path=SH+"mood.png")
    ok("no page overflow sideways",p.evaluate("document.documentElement.scrollWidth<=window.innerWidth"))
    ctx.close(); b.close()
    ok("no uncaught page errors",not errs,str(errs[:5]))
srv.terminate()
f=[r for r in res if not r[1]]
print(f"\n{len(res)-len(f)}/{len(res)} passed"); sys.exit(1 if f else 0)
