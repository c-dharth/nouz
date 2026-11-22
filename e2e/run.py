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
    if s[0]=='reports': return s[1]==u or u=='dave'   # dave plays the artifact owner (admin)
    return True
def can_write(u,p):
    s=p.split('/')
    if p.startswith('data/users/'): return s[2]==u
    if u=='dave' and s[0]=='posts': return True   # the owner can moderate
    return s[0] in('profiles','posts','reactions','comments','links','invites','spaces','exps','match','consent','reports','couples','media','prefs','fcheck','fcast','astro') and s[1]==u
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
const yelpSchema={type:'object',additionalProperties:false,properties:{is_open_now:{type:'boolean'},latitude:{anyOf:[{type:'number',minimum:-90,maximum:90},{type:'null'}]},limit:{type:'integer',minimum:3,maximum:8},location:{anyOf:[{type:'string',maxLength:250},{type:'null'}]},longitude:{anyOf:[{type:'number'},{type:'null'}]},query:{anyOf:[{type:'string',maxLength:250},{type:'null'}]}}};
window.__yelpCalls=[];
const biz=(q,i,o)=>Object.assign({id:'t-'+q.replace(/\W/g,'')+'-'+i,name:'TEST '+q.toUpperCase().slice(0,14)+' '+i,rating:3.6+i*.3,review_count:20+i,is_closed:false,categories:[{alias:q.split(' ')[0]}],url:'https://www.yelp.com/biz/test-'+i,image_url:'https://example.com/p'+i+'.jpg',location:{address1:(100+i)+' Test St\nTestville, CA 90000',city:'Testville'},price:['$','$$','$$$'][i%3],distance_meters:0.2},o||{});
// Mapbox, AllTrails and AccuWeather stand-ins return the same shapes the real tools returned on 19 Nov 2026 (names are made up).
window.__mcpCalls=[];
const C0={lat:37.757,lon:-122.419},near=(i,d)=>({longitude:C0.lon+0.002*(i+1)*(d||1),latitude:C0.lat+0.002*(i+1)});
const allDay={periods:[0,1,2,3,4,5,6].map(d=>({open:{day:d,time:'0700'},close:{day:d,time:'2300'}}))},never={periods:[{open:{day:0,time:'0000'},close:{day:0,time:'0001'}}]};
const mbFeat=(name,i,cats,hours)=>{const c=near(i,cats[0]==='cafe'?1:-1);return{type:'Feature',geometry:{type:'Point',coordinates:[c.longitude,c.latitude]},properties:{name,mapbox_id:'mb-'+name.replace(/\W/g,''),feature_type:'poi',full_address:(200+i)+' Map St, Testville, California 90000, United States',coordinates:c,poi_category:cats,poi_category_ids:cats,metadata:{website:'http://example.com/'+i,open_hours:hours},distance:200*(i+1)}}};
const tools={
  Mapbox:{
    category_search_tool:i=>{window.__mcpCalls.push(['Mapbox','category',i]);const k=i.category;const f=k==='cafe'?[mbFeat('TEST COFFEE 0',0,['café','coffee'],allDay),mbFeat('MAPBOX ONLY CAFE',1,['café','coffee'],never)]:[mbFeat('MB '+k.toUpperCase()+' A',2,[k],allDay),mbFeat('MB '+k.toUpperCase()+' B',3,[k],null)];return JSON.stringify({type:'FeatureCollection',features:f,attribution:'© Mapbox'},null,2)},
    search_and_geocode_tool:i=>{window.__mcpCalls.push(['Mapbox','geocode',i]);return '1. Mission District\n   Address: San Francisco, California, United States\n   Coordinates: 37.757046, -122.41892\n   Type: neighborhood\n\nIf the user wants to see this on a map, pass this ref unchanged to render_map_tool:\n   render_map_tool({ "payload_refs": ["x"] })'},
    directions_tool:i=>{window.__mcpCalls.push(['Mapbox','directions',i]);return JSON.stringify({routes:[{duration:481,distance:673}],waypoints:[]},null,2)+'\n\nIf the user wants to see this on a map, pass this ref unchanged to render_map_tool (not static_map_image_tool):\n   render_map_tool({ "payload_refs": ["mapbox://x"] })'}},
  AllTrails:{find_trails_near_location:i=>{window.__mcpCalls.push(['AllTrails','trails',i]);return{trails:[{id:1,name:'TEST RIDGE LOOP',alltrails_web_url:'https://www.alltrails.com/trail/test',profile_photo_url:'https://www.alltrails.com/p.jpg',avg_rating:4.7,duration_minutes:52,elevation_gain_feet:314,length_miles:1.9,location_label:'Test Park, California',trail_head_distance_meters:2773,difficulty:'Moderate',route_type:'Loop'}],message:null}}},
  AccuWeather:{'widgets-search-claude':i=>{window.__mcpCalls.push(['AccuWeather','search',i]);return{results:[{name:'Test District, CA',locationKey:'123'}]}},
    'widgets-current-claude':i=>{window.__mcpCalls.push(['AccuWeather','current',i]);return{currentConditions:{phrase:window.__wxPhrase||'Cloudy',temperatureValue:52,realFeelPhrase:'Chilly'},alerts:[{name:'Coastal Flood Advisory',isActive:true}],location:{}}}}};
const mcp={listTools:async()=>({servers:[{server:'Yelp',authStatus:'connected',tools:[{name:'yelp_search_local_businesses',description:''}]}].concat(window.__onlyYelp?[]:Object.keys(tools).map(k=>({server:k,authStatus:'unknown',tools:Object.keys(tools[k]).map(n=>({name:n,description:''}))})))}),
  // Like the platform: no description until the viewer has allowed the connector, which the first call asks for.
  describeTool:async(s,t)=>{if(!window.__yelpAllowed)throw{code:'not_in_manifest'};return{name:t,description:'',inputSchema:yelpSchema}},
  callTool:async(s,t,input)=>{if(window.__yelpFail)throw{code:window.__yelpFail};if(s!=='Yelp'){if(!tools[s]||!tools[s][t])throw{code:'server_not_connected'};return{content:[],payload:tools[s][t](input)}}
    if(window.__yelpFail)throw{code:window.__yelpFail};window.__yelpAllowed=true;window.__yelpCalls.push(input);const q=input.query||'x';return{content:[],payload:{businesses:[biz(q,0),biz(q,1),biz(q,2,{is_closed:true,name:'TEST CLOSED '+q}),biz(q,3,{price:null})],status:'ok',error:null}}},
  invalidate:async()=>{}};
window.claude={use:async(n)=>n==='mcp'&&U==='erin'?mcp:n==='db'?{doc,collection:coll}:n==='user'?{id:async()=>U,can:async()=>true,isOwner:async()=>U==='dave'}:null};})();
"""
res=[]
def ok(name,cond,extra=""):
    res.append((name,bool(cond),extra)); print(("PASS" if cond else "FAIL"),name,extra if not cond else "")
def act(p,act_,**kw):
    sel=f'[data-act="{act_}"]'+''.join(f'[data-{k}="{v}"]' for k,v in kw.items())
    p.locator(sel).first.click()
def S(p): return p.evaluate("JSON.parse(JSON.stringify(window.__vouz.S))")
def dob(p,pre,y,m,d):
    p.select_option(f"#{pre}-m",str(m)); p.select_option(f"#{pre}-d",str(d)); p.select_option(f"#{pre}-y",str(y)); p.wait_for_timeout(50)
def onboard(p,social=False,account=False,born=(1995,11,8),deeper=None):
    act(p,"obNext"); assert p.locator('[data-act="obNext"]').is_disabled()
    dob(p,"ob",*born); act(p,"obNext"); act(p,"obNext")
    if deeper: deeper(p)
    else: act(p,"obSkipDeeper")
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
    p=ctx.new_page(); p.on("pageerror",lambda e:errs.append(str(e)+" @ "+str(getattr(e,"stack",""))[:600]))
    p.on("console",lambda m: errs.append(m.text) if m.type=="error" and "ERR_" not in m.text and "Failed to load" not in m.text else None)
    return ctx,p
def log(p,title,mins,**kw):
    nav(p,"track"); act(p,"manual"); p.fill("#d-title",title); p.fill("#d-min",str(mins))
    if "notes" in kw: p.fill("#d-notes",kw["notes"])
    if "hr" in kw: p.fill("#d-hra",kw["hr"])
    if "cat" in kw: act(p,"dCat",v=kw["cat"])
    if "mood" in kw: act(p,"dMood",v=kw["mood"])
    if "tag" in kw: p.fill("#d-tag",kw["tag"]); p.press("#d-tag","Enter")
    act(p,"saveSession"); p.wait_for_selector("text=Saved privately"); act(p,"back")
def nav(p,t):
    for _ in range(6):
        if p.locator(".tabs").count(): break
        if p.locator(".sheet").count(): act(p,"closeSheet")
        act(p,"back")
    if t in ("track","history"): nav(p,"intimacy"); act(p,"iSeg",v=t)
    elif t=="insights": act(p,"tab",tab="insights")
    elif t=="analytics": act(p,"tab",tab="insights"); act(p,"page",page="analytics")
    elif t=="forecast": act(p,"tab",tab="insights"); p.wait_for_selector(".ihero .fw:not(.shimmer)"); act(p,"page",page="forecast")
    elif t=="guide": act(p,"tab",tab="insights"); act(p,"page",page="guide")
    elif t=="social": nav(p,"home"); act(p,"page",page="social")
    elif t=="feed": act(p,"tab",tab="home")
    elif t in ("ideas","planner","match","plans"): nav(p,"discover"); act(p,"discSeg",v=t)
    elif t in ("discover","story"): act(p,"tab",tab="home"); act(p,"tab",tab=t)
    else: act(p,"tab",tab=t)
def feed(p,seg=None):
    """Everything this person can see: Friends feed, Explore (latest), then their own posts. Ends on Friends > My posts, or on seg if given."""
    nav(p,"feed"); p.wait_for_timeout(700); t=""
    for v in ("friends","explore"):
        if p.locator('[data-act="feedSeg"]').count(): act(p,"feedSeg",v=v); p.wait_for_timeout(150); t+=p.inner_text(".scroll")
    if seg: act(p,"feedSeg",v=seg); return t
    act(p,"page",page="social"); act(p,"socSeg",v="mine"); p.wait_for_timeout(150); return t+p.inner_text(".scroll")
with sync_playwright() as pw:
    b=pw.chromium.launch(executable_path="/usr/bin/google-chrome",args=["--no-sandbox"])
    # ---------- local mode ----------
    ctx,p=newctx(b); p.goto(URL); p.wait_for_selector(".ob")
    # ---------- 18+ gate ----------
    cx,q=newctx(b); q.goto(URL); q.wait_for_selector(".ob"); act(q,"obNext")
    t=q.inner_text(".ob"); ok("age: its own step, asks for a birthday, says 18+","when were you born" in t.lower() and "18 and older" in t and q.locator('[data-act="obNext"]').is_disabled())
    dob(q,"ob",2007,2,31); ok("age: impossible dates are caught","doesn't exist" in q.inner_text(".ob"))
    import datetime as _dt; td=_dt.date.today(); tm=td+_dt.timedelta(days=1)
    dob(q,"ob",tm.year-18,tm.month,tm.day); ok("age: one day short of 18 is under 18, shown live","only for people 18 and older" in q.inner_text(".ob"))
    act(q,"obNext"); ok("age: under-18 is turned away and the birthday isn't kept","isn't for you yet" in q.inner_text("#app").lower() and S(q).get("age") is None and S(q).get("ageBlock"))
    q.reload(); q.wait_for_timeout(400); ok("age: still turned away after reloading","isn't for you yet" in q.inner_text("#app").lower())
    cx.close()
    cx,q=newctx(b); q.goto(URL); q.wait_for_selector(".ob"); act(q,"obNext"); dob(q,"ob",td.year-18,td.month,td.day)
    ok("age: an 18th birthday today is allowed",("You're 18" in q.inner_text(".ob")) and not q.locator('[data-act="obNext"]').is_disabled()); cx.close()
    ok("onboarding: welcome, birthday, sign, optional details, setup",p.locator(".steps i").count()==5)
    act(p,"obNext"); dob(p,"ob",1995,11,8); act(p,"obNext")
    t=p.inner_text(".ob"); ok("sign: worked out from the birthday, shown as a cosmic identity, framed as for fun","SCORPIO" in t and "Unapologetically deep" in t and "not a personality test" in t)
    act(p,"obNext"); t=p.inner_text(".ob"); ok("go deeper: optional, skippable, explains what Rising needs","go deeper" in t.lower() and p.locator('[data-act="obSkipDeeper"]').count()==1 and "Rising" in t)
    p.fill("#as-time","14:30"); act(p,"obDeeper"); p.fill("#ob-name","Sid"); act(p,"obNext")
    a0=S(p); ok("age record and astrology kept apart; birthday private",a0["age"]["dob"]=="1995-11-08" and a0["age"]["method"]=="self-declared" and a0["astro"]["time"]=="14:30" and "dob" not in a0["astro"])
    s=S(p); ok("onboarding: social off by default, local mode",s["onboarded"] and not s["settings"]["social"] and s["user"]["mode"]=="local")
    ok("nav: five tabs: Home, Sessions, Insights, Share, Profile",[x.inner_text().strip() for x in p.locator(".tab").all()]==["Home","Sessions","Insights","Share","Profile"] and p.locator(".feedsec").count()==1)
    t=p.inner_text(".scroll"); ok("home: a new account gets one welcome card, no fabricated stats","Start your" in t and "story." in t and p.locator(".trio").count()==0 and p.locator(".sec").count()==0)
    top=p.evaluate("()=>{const c=document.querySelector('.scroll').cloneNode(true);c.querySelector('.feedsec')?.remove();return c.innerText}")
    ok("home: the part above the feed is kept short",len(top.split())<=45,str(len(top.split())))
    ok("home: the feed section explains itself briefly when Connections are off","Turn on Connections" in t and len(p.inner_text(".feedsec").split())<=40)
    ok("brand: old tagline gone","cardio" not in p.content().lower())
    nav(p,"history"); ok("history: empty state, no fabricated stats",p.locator("text=Nothing logged yet").count()==1 and p.locator(".trio").count()==0)
    nav(p,"track"); act(p,"start"); p.wait_for_timeout(2100); act(p,"pause"); p.wait_for_timeout(1000)
    t_paused=p.inner_text("#clock"); p.wait_for_timeout(1100)
    ok("timer: paused clock does not advance",p.inner_text("#clock")==t_paused,t_paused)
    act(p,"resume"); p.reload(); p.wait_for_selector("#clock"); p.wait_for_timeout(1200)
    ok("timer: active session survives reload",p.inner_text("#clock")>="00:00:03",p.inner_text("#clock"))
    act(p,"finish"); p.fill("#d-title","Friday"); p.fill("#d-notes","SECRETNOTE"); p.fill("#d-hra","111"); act(p,"dCat",v="couple"); act(p,"dMood",v="Tender")
    p.reload(); p.wait_for_timeout(300); act(p,"resumeDraft")
    ok("draft survives reload",p.input_value("#d-notes")=="SECRETNOTE")
    act(p,"saveSession"); p.wait_for_selector("text=Saved privately")
    s=S(p); ok("J1 new session saved",len(s["sessions"])==1 and 3<=s["sessions"][0]["durationSec"]<=6 and len(s["sessions"][0]["segments"])==2 and s["active"] is None)
    sid=s["sessions"][0]["id"]
    ok("replay: milestones and interactive timeline",p.locator("text=First Round").count()>=1 and p.locator('[data-act="rSeg"]').count()==2)
    act(p,"rSeg",i="1"); ok("replay: tapping a part shows its detail","Part 2 of 2" in p.inner_text(".scroll"))
    p.fill("#rf-text","REFLECTTEXT"); act(p,"rSave"); act(p,"rMood",v="Playful")
    e=S(p)["sessions"][0]; ok("replay: reflection and mood saved privately",e["reflection"]=="REFLECTTEXT" and e["mood"]=="Playful")
    act(p,"back"); nav(p,"track"); act(p,"manual"); p.fill("#d-min","0"); p.fill("#d-sec","0"); act(p,"saveSession")
    ok("validation: zero duration rejected",p.locator(".err").count()==1 and len(S(p)["sessions"])==1)
    p.fill("#d-min","40"); act(p,"dCat",v="poly"); act(p,"saveSession"); p.wait_for_selector("text=Saved privately")
    ok("replay: history comparison appears with 2+ sessions","your average" in p.inner_text(".scroll") and "Session 1 of 2" in p.inner_text(".scroll"))
    act(p,"back"); nav(p,"history")
    tiles=[t.inner_text() for t in p.locator(".trio b").all()]
    ok("history stats computed from records",tiles[0]=="2" and tiles[1].startswith("40"),str(tiles))
    todayI=p.evaluate("(new Date().getDay()+6)%7"); other=(todayI+3)%7
    p.locator(f'.stage g[data-i="{other}"]').focus(); p.keyboard.press("Enter")
    ok("history ring: day arcs selectable by keyboard",p.locator(f'.stage g[data-i="{other}"]').get_attribute("aria-pressed")=="true")
    act(p,"openReplay",id=sid) if p.locator(f'[data-act="openReplay"][data-id="{sid}"]').count() else None
    act(p,"editSession",id=sid); p.fill("#d-min","10"); p.fill("#d-sec","0"); act(p,"saveSession"); p.wait_for_timeout(200)
    e=[x for x in S(p)["sessions"] if x["id"]==sid][0]
    ok("J2 edit updates record, keeps private fields",e["durationSec"]==600 and e["notes"]=="SECRETNOTE" and e["reflection"]=="REFLECTTEXT")
    act(p,"back"); nav(p,"analytics"); act(p,"insRange",v="year")
    tl=[t.inner_text() for t in p.locator(".tile b").all()]
    ok("J4 analytics reflect edit",tl[0]=="2" and tl[1]=="50m" and tl[3].startswith("40m"),str(tl[:4]))
    act(p,"insCat",v="poly"); ok("filter: Couple or Poly",p.locator(".tile b").first.inner_text()=="1")
    act(p,"insCat",v="all"); act(p,"insTab",v="patterns"); t=p.inner_text(".scroll")
    ok("insights: time-of-day and weekday patterns","time of day" in t.lower() and "most often in the" in t.lower() and "couple and poly" in t.lower())
    act(p,"insTab",v="mood"); t=p.inner_text(".scroll"); ok("insights: mood and reflections","Playful" in t and "REFLECTTEXT" in t)
    ok("insights copy never frames more as better",not re.search(r"\b(better than|keep it up|great job|improve|goal reached|up from)\b",p.inner_text("body"),re.I))
    act(p,"insTab",v="overview"); act(p,"insRange",v="custom"); p.fill("#i-from","2020-01-01"); p.dispatch_event("#i-from","change"); p.fill("#i-to","2020-01-31"); p.dispatch_event("#i-to","change")
    ok("filter: custom range",p.locator(".tile b").first.inner_text()=="0")
    nav(p,"history"); act(p,"openReplay",id=sid); act(p,"editSession",id=sid); act(p,"askDelete"); ok("delete asks for confirmation",p.locator(".sheet").count()==1 and len(S(p)["sessions"])==2)
    p.keyboard.press("Escape"); ok("sheets close with Escape",p.locator(".sheet").count()==0)
    act(p,"askDelete"); act(p,"confirmYes"); ok("J3 delete removes record and leaves a tombstone",len(S(p)["sessions"])==1 and sid in S(p)["deleted"])
    nav(p,"history"); ok("J4 analytics reflect delete",p.locator(".trio b").first.inner_text()=="1")
    nav(p,"profile"); ok("social toggle unavailable without account",p.locator('[data-act="toggleSocial"]').is_disabled())
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
    nav(p,"profile"); act(p,"loadDemo"); nav(p,"home"); ok("demo data is labelled",p.locator(".banner").count()==1)
    nav(p,"profile"); act(p,"exportData"); p.wait_for_selector("#exp-out"); ex=p.input_value("#exp-out")
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
    log(a,"PRIVATETITLE",33,notes="SECRETNOTE",hr="123",cat="couple",mood="Electric",tag="SECRETTAG"); a.wait_for_timeout(1700)
    ok("account sync: only the private vault is written",set(STORE.keys())=={"data/users/alice/vault"},str(list(STORE.keys())))
    ok("private vault unreadable by another user",db_get(None,"bob","data/users/alice/vault") is None)
    for pg,nm in ((a,"ali"),(bb,"bobby"),(c,"caz")):
        nav(pg,"profile"); act(pg,"toggleSocial"); pg.fill("#s-handle",nm); act(pg,"sheetPrivate"); act(pg,"socialOnYes"); pg.wait_for_function("window.__vouz.S.settings.social===true"); pg.wait_for_timeout(300)
    ok("J5 enable social: profile + keys created, nothing posted","profiles/alice" in STORE and "data/users/alice/keys" in STORE and "posts/alice" not in STORE)
    # connect alice<->bob ; carol stays unconnected
    act(a,"socSeg",v="people"); a.wait_for_timeout(500); act(a,"request",id="bob"); a.wait_for_timeout(500)
    links=json.dumps(STORE["links/alice"]); ok("connection list stores opaque labels, not user ids","bob" not in links and "alice" not in links,links[:120])
    sid=S(a)["sessions"][0]["id"]
    nav(a,"history"); act(a,"openReplay",id=sid); act(a,"composeRecap",id=sid); a.fill("#c-cap","CONNCAPTION")
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
    feed(bb,"friends"); tk=bb.locator('[data-act="cmOpen"]').first.get_attribute("data-k"); act(bb,"cmOpen",k=tk); bb.fill(f'[id="c-{tk}"]',"SECRETCOMMENT"); act(bb,"comment",k=tk); act(bb,"like",k=tk); bb.wait_for_timeout(900)
    ok("comment on a connections-only card is encrypted, and unlinkable to the card","SECRETCOMMENT" not in json.dumps(STORE["comments/bob"]) and STORE["posts/alice"]["items"][0]["id"] not in json.dumps(STORE["comments/bob"])+json.dumps(STORE["reactions/bob"]))
    feed(a); act(a,"cmOpen",k=a.locator('[data-act="cmOpen"]').first.get_attribute("data-k")); a.wait_for_timeout(200)
    ok("author reads the comment and the like","SECRETCOMMENT" in a.inner_text(".scroll") and a.locator('[data-act="like"]').first.get_attribute("aria-label").endswith("1 likes"))
    # public card: only achievement cards can go to everyone
    nav(a,"history"); act(a,"openReplay",id=sid); act(a,"composeRecap",id=sid)
    ok("a session card can never be shared with everyone",a.locator('[data-act="cAud"][data-v="everyone"]').count()==0)
    a.evaluate("()=>{}"); nav(a,"profile"); act(a,"page",page="achievements"); act(a,"composeAch",id="first"); a.fill("#c-cap","PUBLICCAP"); act(a,"cAud",v="everyone"); act(a,"composeStep",v="preview"); act(a,"publish"); a.wait_for_timeout(800)
    pub=json.dumps([{k:v for k,v in i.items() if k not in ("postedAt","id")} for i in STORE["posts/alice"]["items"] if i.get("vis")=="everyone"])
    ok("everyone-card is sanitized whitelist only","PUBLICCAP" in pub and not any(w in pub for w in ["SECRETNOTE","SECRETTAG","PRIVATETITLE","Electric","123","About",sid]),pub)
    ok("everyone-card visible to unconnected user","PUBLICCAP" in feed(c))
    # permission off -> key withdrawn
    nav(a,"social"); act(a,"socSeg",v="people"); a.wait_for_timeout(400); act(a,"sheet",s="conn",id="bob"); act(a,"permRecaps",id="bob"); a.wait_for_timeout(1300)
    ok("turning a permission off removes the recipient key",len([i for i in STORE["posts/alice"]["items"] if i.get("c")][0]["wk"])==1)
    ok("and the connection loses the card","CONNCAPTION" not in feed(bb))
    act(a,"permRecaps",id="bob"); a.wait_for_timeout(1300); act(a,"closeSheet"); ok("turning it back on restores access","CONNCAPTION" in feed(bb))
    # ---------- adding people to a saved session ----------
    def replay(pg,i): nav(pg,"history"); act(pg,"openReplay",id=i); pg.wait_for_timeout(200)
    def home(pg):
        while pg.locator('[data-act="back"]').count(): act(pg,"back")
        nav(pg,"home"); pg.wait_for_timeout(700); return pg.inner_text(".scroll")
    replay(a,sid); act(a,"addPeople"); names=[x.locator("b").inner_text().strip() for x in a.locator('[data-act="inviteAsk"]').all()]
    ok("people: only my connections are offered",names==["bobby"],str(names))
    act(a,"inviteAsk",id="bob"); ok("people: sending asks first and says what is shown","date, time, length, Couple" in a.inner_text(".sheet") and "invites/alice" not in STORE); a.screenshot(path=SH+"ppl_confirm.png")
    act(a,"confirmYes"); a.wait_for_timeout(900); raw=json.dumps(STORE["invites/alice"]); st=str(S(a)["sessions"][0]["start"])
    ok("people: the invite is sealed in storage",len(STORE["invites/alice"]["items"])==1 and not any(w in raw for w in ["bob","alice",sid,st,"duo","1980","PRIVATETITLE","SECRETNOTE"]),raw[:200])
    ok("people: sender sees Invited","Invited" in a.inner_text(".scroll") and S(a)["sessions"][0]["people"][0]["id"]=="bob"); a.screenshot(path=SH+"ppl_replay.png")
    hb=home(bb); bb.screenshot(path=SH+"ppl_inbox.png")
    ok("people: the invited person is asked, nothing is added yet","ali added you to a session" in hb and "Couple" in hb and len(S(bb)["sessions"])==0,hb[:200])
    ok("people: nobody else can see the invite","added you" not in home(c) and c.evaluate("window.__vouz.Soc.inbox.length")==0)
    act(bb,"invYes"); bb.wait_for_timeout(900); bs=S(bb)["sessions"]
    ok("people: accepting saves a private copy with time, length and category only",len(bs)==1 and bs[0]["durationSec"]==1980 and bs[0]["category"]=="couple" and bs[0]["participants"]==2 and bs[0]["start"]==S(a)["sessions"][0]["start"] and bs[0]["notes"]=="" and bs[0]["title"]=="" and bs[0]["mood"]=="" and bs[0]["tags"]==[] and bs[0]["hrAvg"]=="" and "you confirmed" in bb.inner_text(".scroll") and "Mutually confirmed" in bb.inner_text(".scroll"),str(bs)[:300])
    ok("people: the invite leaves the inbox once answered","added you" not in home(bb))
    a.wait_for_timeout(600); ok("people: sender sees Mutually confirmed","Mutually confirmed" in a.inner_text(".scroll"))
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
    home(a); home(bb); nav(a,"social"); act(a,"socSeg",v="people"); a.wait_for_timeout(300); feed(c)
    # ---------- shared spaces and Mutual Match (alice and bob connected, carol not) ----------
    def sp_of(pg): return pg.evaluate("Object.values(window.__vouz.Soc.sp).map(x=>({id:x.id,name:x.name,role:x.role,members:x.members,invited:x.invited}))")
    nav(a,"profile"); act(a,"page",page="spaces"); ok("spaces: only connections can be invited",[x.inner_text() for x in a.locator('[data-act="spPick"]').all()]==["bobby"])
    act(a,"spCreate"); ok("spaces: a name and a person are required",a.locator(".err").count()==1)
    a.fill("#sp-name","OURSPACE"); act(a,"spPick",v="bob"); act(a,"spCreate"); a.wait_for_timeout(900)
    raw=json.dumps(STORE["spaces/alice"]); ok("spaces: name and members are encrypted in storage",len(STORE["spaces/alice"]["items"])==1 and not any(w in raw for w in ["OURSPACE","bob","alice"]),raw[:160])
    hb=home(bb); ok("spaces: the invited person is asked first","invited you to OURSPACE" in hb and sp_of(bb)[0]["role"]=="invited")
    ok("spaces: someone not invited sees nothing",sp_of(c)==[] and "OURSPACE" not in home(c))
    act(bb,"spAccept"); bb.wait_for_timeout(900); a.wait_for_timeout(1200)
    ok("spaces: accepting makes them a member",sp_of(a)[0]["members"]==["bob"] and sp_of(a)[0]["invited"]==[] and sp_of(bb)[0]["role"] in ("member","joining"))
    spid=sp_of(a)[0]["id"]
    # a memory shared into the space, and one kept private
    nav(a,"story"); act(a,"expNew",kind="done"); a.fill("#x-title","BEACHDAY"); a.fill("#x-notes","PRIVNOTE"); act(a,"xSpace",v=spid); a.fill("#x-shared","SHAREDNOTE"); act(a,"expSave"); a.wait_for_timeout(300)
    nav(a,"story"); act(a,"expNew",kind="done"); a.fill("#x-title","SECRETDINNER"); act(a,"expSave"); a.wait_for_timeout(1200)
    raw=json.dumps(STORE.get("exps/alice",{})); ok("story: a shared memory is ciphertext in storage, and private ones aren't stored at all",len(STORE["exps/alice"]["items"])==1 and not any(w in raw for w in ["BEACHDAY","PRIVNOTE","SECRETDINNER","SHAREDNOTE"]),raw[:160])
    bb.wait_for_timeout(600); nav(bb,"story"); t=bb.inner_text(".scroll")
    ok("story: the partner sees what was shared to the space, not what was kept private","BEACHDAY" in t and "from ali" in t and "SECRETDINNER" not in t)
    xid=[e for e in S(a)["exps"] if e["title"]=="BEACHDAY"][0]["id"]; act(bb,"expOpen",id=xid,a="alice"); t=bb.inner_text(".scroll")
    ok("story: the shared note is visible, private notes are not","SHAREDNOTE" in t and "PRIVNOTE" not in t and bb.locator('[data-act="expEdit"]').count()==0)
    nav(c,"story"); ok("story: someone outside the space sees nothing","BEACHDAY" not in c.inner_text(".scroll") and c.evaluate("window.__vouz.Soc.shared.length")==0)
    # Mutual Match
    nav(a,"match"); [act(a,"pickToggle",v=v) for v in ("hike","cook","picnic")]; a.wait_for_timeout(1000)
    ok("match: waiting until everyone has picked","Waiting for bobby" in a.inner_text(".scroll") and a.locator('[data-act="matchSave"]').count()==0)
    raw=json.dumps(STORE["match/alice"]); ok("match: picks are encrypted in storage",not any(w in raw for w in ["hike","cook","picnic"]),raw[:120])
    mem=bb.evaluate("JSON.stringify([window.__vouz.Soc.mres,window.__vouz.Soc.mdocs,Object.values(window.__vouz.Soc.cache).filter(v=>v&&typeof v==='object'&&('own' in v||'fwd' in v))])")
    ok("match: the partner's browser holds only blinded numbers, never the other's picks",not any(w in mem for w in ["hike","cook","picnic"]) and len(mem)>100,mem[:120])
    nav(bb,"match"); ok("match: the partner can't see the other's picks","Go hiking" not in "".join(x.inner_text() for x in bb.locator(".idea").all()) and bb.locator('[data-act="pickToggle"][aria-pressed="true"]').count()==0)
    [act(bb,"pickToggle",v=v) for v in ("cook","picnic","museum")]; bb.wait_for_timeout(1000); a.wait_for_timeout(800)
    ma=sorted(x.inner_text() for x in a.locator(".idea .it").all()); mb=sorted(x.inner_text() for x in bb.locator(".idea .it").all())
    ok("match: only ideas everyone picked are revealed, to both sides",ma==mb==["Cook something new together","Pack a picnic"],f"{ma} {mb}")
    for v in ("museum","stars","bike","garden","brunch"): act(a,"pickToggle",v=v)
    a.wait_for_timeout(400)
    ok("match: picks are capped at 8, so nobody can pick everything",len(S(a)["picks"][spid])==8 and a.locator('[data-act="pickToggle"][data-v="dance"]').is_disabled())
    a.wait_for_timeout(1500); bb.wait_for_timeout(800)
    ma=sorted(x.inner_text() for x in a.locator(".idea .it").all())
    ok("match: changing picks updates the result privately (museum now shared)",ma==["Cook something new together","Pack a picnic","Visit a museum or gallery"],str(ma))
    act(a,"matchSave",v="cook"); a.wait_for_timeout(1000); bb.wait_for_timeout(600)
    ok("match: a matched idea becomes a plan the partner sees","Cook something new together" in home(bb) and "from ali" in bb.inner_text(".scroll"))
    # sharing a memory that belongs to a space needs everyone's agreement
    nav(a,"story"); act(a,"expOpen",id=xid); act(a,"mcOpen"); a.wait_for_timeout(400)
    ok("consent: a space memory can't be shared until everyone agrees",a.locator('[data-act="mcShare"]').is_disabled() and a.locator('[data-act="mcSave"]').first.is_disabled() and "Not asked" in a.inner_text(".scroll"))
    act(a,"mcAsk"); a.wait_for_timeout(1200); raw=json.dumps(STORE.get("consent/alice",{}))
    ok("consent: the request is encrypted in storage",'"req"' in raw and "BEACHDAY" not in raw and xid not in raw,raw[:120])
    hb=home(bb); ok("consent: the other person is asked on Home","would like to share a card of" in hb and "BEACHDAY" in hb)
    ok("consent: someone outside the space isn't asked","would like to share" not in home(c))
    act(bb,"consentAns",v=bb.evaluate("window.__vouz.Soc.creq[0].id"),ok="1"); bb.wait_for_timeout(1200); a.wait_for_timeout(1200)
    ok("consent: once everyone agrees, sharing unlocks",not a.locator('[data-act="mcShare"]').is_disabled() and "Agreed" in a.inner_text(".scroll"))
    nav(bb,"profile"); act(bb,"page",page="spaces"); act(bb,"consentAns",ok="0"); bb.wait_for_timeout(1200); a.wait_for_timeout(1200)
    ok("consent: agreement can be withdrawn, and sharing locks again",a.locator('[data-act="mcShare"]').is_disabled() and "Didn't agree" in a.inner_text(".scroll"))
    nav(bb,"story"); act(bb,"expOpen",id=xid,a="alice"); act(bb,"mcOpen"); bb.wait_for_timeout(400)
    ok("consent: the partner can't share your memory without asking you",bb.locator('[data-act="mcShare"]').is_disabled() and "ali" in bb.inner_text(".scroll"))
    home(a); home(bb)
    # leaving: key rotates, shared content disappears
    nav(bb,"profile"); act(bb,"page",page="spaces"); act(bb,"spLeave",id=spid); act(bb,"confirmYes"); bb.wait_for_timeout(1000); a.wait_for_timeout(1500)
    ok("spaces: leaving takes them out and the space gets a new key",sp_of(a)[0]["members"]==[] and list(STORE["spaces/alice"]["items"][0]["wk"].keys())==["self"])
    bb.wait_for_timeout(800); nav(bb,"story"); ok("spaces: after leaving, shared memories are gone for them","BEACHDAY" not in bb.inner_text(".scroll") and bb.evaluate("window.__vouz.Soc.shared.length")==0)
    home(bb); feed(c); nav(a,"social"); act(a,"socSeg",v="people"); a.wait_for_timeout(300)
    # tamper: bob cannot write alice's docs
    try: db_set(None,"bob","posts/alice",'{"items":[]}'); tam=False
    except Exception: tam=True
    ok("another user cannot overwrite someone's cards",tam)
    # block
    act(a,"sheet",s="conn",id="bob"); act(a,"block",id="bob"); a.wait_for_timeout(1300)
    ok("block removes the key and the link",len([i for i in STORE["posts/alice"]["items"] if i.get("c")][0]["wk"])==1 and STORE["links/alice"]["out"]=={} and "CONNCAPTION" not in feed(bb))
    act(a,"socSeg",v="people"); act(a,"unblock",id="bob"); a.wait_for_timeout(300)
    # report
    feed(c,"explore"); act(c,"postMenu",a="alice"); act(c,"report",a="alice"); act(c,"reportWhy",v="Harassment"); act(c,"reportSend"); c.wait_for_timeout(400)
    ok("report filed, unreadable by the reported user",len(STORE["reports/carol"]["items"])==1 and db_get(None,"alice","reports/carol") is None)
    # ---------- Feed: Explore & Friends ----------
    nav(a,"social"); act(a,"socSeg",v="people"); a.wait_for_timeout(300); act(a,"approve" if a.locator('[data-act="approve"][data-id="bob"]').count() else "request",id="bob"); a.wait_for_timeout(1500); bb.wait_for_timeout(800)
    ok("feed: friends again after unblock",a.evaluate("!!(window.__vouz.Soc.rel.bob||{}).mutual"))
    def newpost(pg,kind,cap,vis="friends",loc=""):
        nav(pg,"feed"); act(pg,"postNew"); act(pg,"pcKind",v=kind); pg.fill("#pc-cap",cap)
        if loc: pg.fill("#pc-loc",loc)
        act(pg,"pcVis",v=vis)
    newpost(a,"photo","FRIENDPHOTO caption for the friends feed",loc="123 Main St")
    a.set_input_files("#pc-file",os.path.join(HERE,"fixtures","")+"gps.jpg"); a.wait_for_selector(".phs img"); a.locator("#pc-cap").click()
    ok("feed: an address-like place tag blocks posting",a.locator('[data-act="pcPost"]').is_disabled() and a.locator(".err").count()==1)
    a.fill("#pc-loc","Mission District"); a.wait_for_timeout(500)
    ok("feed: nothing is stored before Post",not any(k.startswith("media/alice") for k in STORE))
    a.screenshot(path=SH+"feed-compose.png"); act(a,"pcPost"); a.wait_for_timeout(1500)
    chunks=[k for k in STORE if k.startswith("media/alice/")]
    rawp=json.dumps(STORE["posts/alice"])
    ok("feed: friends photo stored encrypted, caption sealed",len(chunks)>=1 and all(STORE[k]["e"] for k in chunks) and "FRIENDPHOTO" not in rawp and "Mission" not in rawp)
    tb=feed(bb,"friends"); bb.wait_for_selector(".pm.ok img",timeout=8000)
    ok("feed: a friend sees the photo, caption and place in Friends","FRIENDPHOTO" in tb and "Mission District" in tb and bb.locator(".pm.ok img").count()>=1)
    bb.screenshot(path=SH+"feed-friends.png")
    gps=bb.evaluate("""()=>{const s=document.querySelector('.pm.ok img').src;const b=atob(s.split(',')[1]);return {exif:b.includes('Exif'),gps:b.includes('GPS')}}""")
    ok("feed: uploaded photo carries no EXIF/GPS",not gps["exif"] and not gps["gps"],str(gps))
    ok("feed: a non-friend can't see it","FRIENDPHOTO" not in feed(c))
    # video: GPS atom scrubbed before upload
    newpost(a,"video","VIDEOCLIP",vis="private"); act(a,"pcPick",v="bob"); a.set_input_files("#pc-file",os.path.join(HERE,"fixtures","")+"gps.mp4"); a.wait_for_timeout(400); act(a,"pcPost"); a.wait_for_timeout(1500)
    vid=a.evaluate("""async()=>{const V=window.__vouz,x=V.Soc.items.find(i=>i.it.caption==='VIDEOCLIP');const m=V.Soc.media[x.a+'|'+x.it.media[0].id];const b=new Uint8Array(await (await V.Media.blob(x.a,m)).arrayBuffer());let s='';for(const c of b)s+=String.fromCharCode(c);return {xyz:s.includes('\\u00a9xyz'),coord:s.includes('+37.7749'),n:b.length}}""")
    ok("feed: video location atom and coordinates removed",not vid["xyz"] and not vid["coord"] and vid["n"]>2000,str(vid))
    ok("feed: private post reaches the chosen friend only","VIDEOCLIP" in feed(bb,"friends") and "Private" in bb.inner_text(".scroll") and "VIDEOCLIP" not in feed(c))
    # public post, Explore ranking, search, likes, saves
    newpost(a,"idea","PUBLICIDEA worth trying this weekend together",vis="public",loc="Oakland"); act(a,"pcIdea",v=a.locator('[data-act="pcIdea"]').first.get_attribute("data-v")); act(a,"pcPost"); a.wait_for_timeout(1200)
    tc=feed(c,"explore")
    ok("explore: public post visible to anyone, with transparent ranking","PUBLICIDEA" in tc and c.locator('[data-act="why"]').count()>=1)
    c.screenshot(path=SH+"feed-explore.png"); k=c.locator('[data-act="like"]').first.get_attribute("data-k")
    act(c,"why",k=k); ok("explore: 'why this post' shows every factor","Why you're seeing this" in c.inner_text(".scroll") and "engagement" in c.inner_text(".scroll"))
    act(c,"feedMode"); ok("explore: Latest is newest first with no personalization","no personalization" in c.inner_text(".scroll") and c.locator('[data-act="why"]').count()==0); act(c,"feedMode")
    c.fill("#f-q","oakland"); c.wait_for_timeout(500); ok("explore: search matches place tags","PUBLICIDEA" in c.inner_text(".scroll") and "PUBLICCAP" not in c.inner_text(".scroll"))
    c.fill("#f-q","zzzz"); c.wait_for_timeout(500); ok("explore: search empty state","Nothing matches" in c.inner_text(".scroll")); c.fill("#f-q",""); c.wait_for_timeout(500)
    act(c,"feedKind",v="idea"); ok("explore: kind filter","PUBLICIDEA" in c.inner_text(".scroll") and "PUBLICCAP" not in c.inner_text(".scroll")); act(c,"feedKind",v="all")
    act(c,"like",k=k); act(c,"savePost",k=k); c.wait_for_timeout(700)
    ok("likes: one per person, stored with time",isinstance(STORE["reactions/carol"]["r"][k],dict) and c.locator(f'[data-act="like"][data-k="{k}"]').get_attribute("aria-pressed")=="true")
    ok("saved: kept in the private vault only",k in S(c)["saved"] and '"saved"' not in json.dumps({x:STORE[x] for x in STORE if not x.startswith("data/")}))
    nav(c,"feed"); act(c,"page",page="saved"); ok("saved page lists it","PUBLICIDEA" in c.inner_text(".scroll"))
    a.wait_for_timeout(600); nav(a,"feed"); ok("notifications: bell shows unread",a.locator('[data-page="notifs"] .dot').count()==1)
    act(a,"page",page="notifs"); ok("notifications: like listed","caz liked" in a.inner_text(".scroll"))
    # edit own post
    feed(a); pid=[i for i in STORE["posts/alice"]["items"] if i.get("vis")=="everyone" and "PUBLICIDEA" in i.get("caption","")][0]["id"]
    act(a,"postMenu",a="alice",id=pid); act(a,"editPost",id=pid); a.fill("#ep-cap","EDITEDCAP"); act(a,"editPostSave"); a.wait_for_timeout(900)
    ok("edit: author can change the caption","EDITEDCAP" in feed(c,"explore") and "edited" in c.inner_text(".scroll"))
    # profile
    nav(a,"profile"); act(a,"page",page="user"); act(a,"page",page="meEdit"); a.fill("#me-b","BIOTEXT"); act(a,"meSave"); a.wait_for_timeout(500)
    ok("profile: bio saved, key kept",STORE["profiles/alice"].get("bio")=="BIOTEXT" and STORE["profiles/alice"].get("pub"))
    # couple profile: needs both
    nav(a,"profile"); act(a,"page",page="couple"); act(a,"cpEdit"); act(a,"cpWith",v="bob"); a.fill("#cp-name","Ali and Bobby"); act(a,"cpSave"); a.wait_for_timeout(1200)
    ok("couple: proposal alone is not public",c.evaluate("Object.keys(window.__vouz.Soc.couplesLive).length")==0)
    nav(bb,"profile"); act(bb,"page",page="couple"); bb.wait_for_timeout(300); act(bb,"cpApprove",id=bb.locator('[data-act="cpApprove"]').first.get_attribute("data-id")); bb.wait_for_timeout(1500); c.wait_for_timeout(600)
    ok("couple: live once both approve the same version",c.evaluate("Object.values(window.__vouz.Soc.couplesLive).map(x=>x.data.name)")==["Ali and Bobby"])
    newpost(a,"idea","JOINTPOST from the two of us",vis="public"); act(a,"pcIdea",v=a.locator('[data-act="pcIdea"]').first.get_attribute("data-v")); act(a,"pcCo"); act(a,"pcPost"); a.wait_for_timeout(1200)
    ok("couple: joint post hidden until the partner approves","JOINTPOST" not in feed(c,"explore"))
    nav(bb,"profile"); act(bb,"page",page="couple"); bb.wait_for_timeout(300); act(bb,"jointOk",k=bb.locator('[data-act="jointOk"]').first.get_attribute("data-k")); bb.wait_for_timeout(1300)
    tc=feed(c,"explore"); c.screenshot(path=SH+"feed-couple.png"); ok("couple: approved joint post shows under the couple's name","JOINTPOST" in tc and "Ali and Bobby" in tc)
    # block hides both ways
    act(c,"postMenu",a="alice",id=pid); act(c,"block",id="alice"); c.wait_for_timeout(1300); a.wait_for_timeout(900)
    ok("block: blocker stops seeing them","EDITEDCAP" not in feed(c))
    ok("block: blocked person can't see the blocker's profile",a.evaluate("window.__vouz.Soc.blockedMe('carol')"))
    nav(c,"social"); act(c,"socSeg",v="people"); act(c,"unblock",id="alice"); c.wait_for_timeout(1300); a.wait_for_timeout(600)
    ok("unblock restores",not a.evaluate("window.__vouz.Soc.blockedMe('carol')") and "EDITEDCAP" in feed(c))
    # moderation by the owner
    feed(c,"explore"); act(c,"postMenu",a="alice",id=pid); act(c,"report",a="alice"); act(c,"reportWhy",v="Something else"); act(c,"reportSend"); c.wait_for_timeout(500)
    cd,d=newctx(b,"dave"); d.goto(URL); d.wait_for_timeout(400); onboard(d,account=True); nav(d,"profile"); act(d,"toggleSocial"); d.fill("#s-handle","mod"); act(d,"sheetPrivate"); act(d,"socialOnYes"); d.wait_for_function("window.__vouz.S.settings.social===true"); d.wait_for_timeout(1200)
    nav(d,"profile"); nav(c,"profile"); ok("moderation: only the owner gets the page",d.locator('[data-page="mod"]').count()==1 and c.locator('[data-page="mod"]').count()==0)
    act(d,"page",page="mod"); d.wait_for_timeout(300); act(d,"modRemove",id=pid); d.wait_for_timeout(700)
    ok("moderation: owner removes a reported public post",not any(i.get("id")==pid for i in STORE["posts/alice"]["items"]))
    cd.close()
    # Forecast together: both opt in, same words, partner's answers stay theirs
    nav(a,"forecast"); a.wait_for_selector(".fcard .fw:not(.shimmer)"); act(a,"fcTogether"); a.wait_for_timeout(600)
    act(a,"fcE",v="Playful"); act(a,"fcCkSave"); a.wait_for_timeout(600)
    nav(bb,"forecast"); bb.wait_for_selector(".fcard .fw:not(.shimmer)"); act(bb,"fcTogether"); bb.wait_for_timeout(600); act(bb,"fcShowE"); act(bb,"fcE",v="Reflective"); act(bb,"fcCkSave"); bb.wait_for_timeout(1500)
    nav(bb,"home"); nav(bb,"forecast"); bb.wait_for_timeout(1200); a.wait_for_timeout(600); nav(a,"home"); nav(a,"forecast"); a.wait_for_timeout(1500)
    wa=a.inner_text(".fcard .fw"); wb=bb.inner_text(".fcard .fw")
    ok("together: both partners see the same forecast",wa==wb and "Together" in a.inner_text(".fcard") and a.inner_text(".fsec")==bb.inner_text(".fsec"),wa+" / "+wb)
    raw=json.dumps({k:STORE[k] for k in STORE if k.startswith("fcheck/") or k.startswith("fcast/")})
    ok("together: check-ins and forecasts are stored encrypted",("fcheck/alice" in STORE and "fcast/" in raw) and not any(x in raw for x in ["Playful","Reflective",wa]))
    ok("pulse: shows their energy only because they allowed it","REFLECTIVE" in a.inner_text(".pulse") and "PRIVATE" in bb.inner_text(".pulse"))
    ok("together: the forecast never draws on intimacy records","Just for you two" not in a.inner_text(".scroll"))
    act(a,"fcTogether"); a.wait_for_timeout(600); ok("together: turning it off removes what was shared",STORE.get("fcheck/alice") in (None,{}) and STORE.get("fcast/alice") in (None,{}))
    # couple astrology: alice shares her Sun only, and allows it on cards; bob shares nothing
    nav(a,"profile"); act(a,"page",page="astro"); act(a,"asShare",id="bob",v="sun"); a.wait_for_timeout(400); act(a,"asCards",id="bob"); a.wait_for_timeout(900); bb.wait_for_timeout(600)
    raw=json.dumps(STORE.get("astro/alice"))
    ok("couple astro: shared encrypted, never the birthday",STORE.get("astro/alice") and not any(x in raw for x in ["Scorpio","1995","dob","14:30"]))
    nav(bb,"insights"); bb.wait_for_timeout(300); act(bb,"page",page="cosmic"); bb.wait_for_timeout(1200); t=bb.inner_text(".scroll")
    ok("couple astro: partner sees the pairing and themes, from only the Sun sign alice chose to share","cosmic connection" in t.lower() and "Scorpio" in t and "Romance" in t and "Moons in" not in t)
    act(bb,"back"); nav(bb,"share"); bb.wait_for_timeout(1500); nav(bb,"home"); nav(bb,"share"); bb.wait_for_timeout(600)
    ok("couple astro: her sign can go on bob's cards only because she allowed it",bb.locator('.shtile[data-k="compat"]').count()==1 and bb.locator('.shtile[data-k="couplehoro"]').count()==1)
    nav(a,"profile"); act(a,"page",page="astro"); act(a,"asShare",id="bob",v=""); a.wait_for_timeout(800)
    ok("couple astro: sharing can be stopped",STORE.get("astro/alice") in (None,{}))
    # J8 social off (keep) -> nothing left in shared storage, stashed privately; back on -> restored
    nav(a,"profile"); act(a,"toggleSocial"); act(a,"socialOffYes"); a.wait_for_timeout(900)
    ok("J8 Social off: nothing of mine left in shared storage, tracking intact",not any(k.endswith("/alice") and not k.startswith("data/") for k in STORE) and "data/users/alice/stash" in STORE and a.locator('[data-page="spaces"]').count()==0 and len(S(a)["sessions"])==1,str([k for k in STORE if "alice" in k]))
    ok("others no longer see my cards","PUBLICCAP" not in feed(c))
    act(a,"toggleSocial"); a.fill("#s-handle","ali"); act(a,"socialOnYes"); a.wait_for_function("window.__vouz.S.settings.social===true"); a.wait_for_timeout(900)
    ok("Social back on restores my cards","posts/alice" in STORE and "data/users/alice/stash" not in STORE and "PUBLICCAP" in feed(c))
    nav(a,"profile"); act(a,"toggleSocial"); act(a,"sheetWipe"); act(a,"socialOffYes"); a.wait_for_timeout(900)
    ok("J8 Social off with delete: shared content, stash and keys gone",not any("alice" in k for k in STORE if k!="data/users/alice/vault"),str([k for k in STORE if "alice" in k]))
    # sync merge across devices
    ca2,a2=newctx(b,"alice"); a2.goto(URL); a2.wait_for_timeout(400); act(a2,"obNext"); dob(a2,"ob",1990,1,1); act(a2,"obNext"); act(a2,"obNext"); act(a2,"obSkipDeeper"); act(a2,"obMode",mode="account"); a2.wait_for_selector('[data-act="obRestore"]'); act(a2,"obRestore"); a2.wait_for_timeout(300)
    ok("second device restores from private sync",len(S(a2)["sessions"])==1 and S(a2)["sessions"][0]["notes"]=="SECRETNOTE")
    log(a2,"fromdevice2",12); a2.wait_for_timeout(1700)
    nav(a,"history"); act(a,"openReplay",id=sid); act(a,"editSession",id=sid); act(a,"askDelete"); act(a,"confirmYes"); a.wait_for_timeout(1700)
    a.reload(); a.wait_for_timeout(2200); a2.reload(); a2.wait_for_timeout(2200)
    t1=sorted(x["title"] for x in S(a)["sessions"]); t2=sorted(x["title"] for x in S(a2)["sessions"])
    ok("sync merges: new session arrives, deletion propagates",t1==["fromdevice2"] and t2==["fromdevice2"],f"{t1} {t2}")
    # J10
    nav(a,"profile"); act(a,"sheet",s="deleteAccount"); a.fill("#del-in","DELETE"); act(a,"deleteAccountYes"); a.wait_for_selector(".ob"); a.wait_for_timeout(600)
    ok("J10 account deletion removes vault and every document of mine",not any("alice" in k for k in STORE),str([k for k in STORE if "alice" in k]))
    for x in (ca,cb,cc,ca2): x.close()

    # ---------- earlier data: conversion to Couple/Poly and removal of Solo/Partnered ----------
    NOW=int(time.time()*1000); D=86400000
    def L(i,cat,days,**kw): return {"id":i,"title":i.upper(),"start":NOW-days*D,"durationSec":900,"segments":None,"category":cat,"tags":[],"mood":"","notes":"keep-"+i,"hrAvg":"","hrPeak":"","createdAt":1,"updatedAt":1,**kw}
    LEG={"v":1,"onboarded":True,"stamp":1,"user":{"name":"Sid","mode":"local","createdAt":1},"settings":{"social":False,"privateProfile":True,"defaultVis":"connections","regular":None,"pinHash":None,"pinSalt":None},
         "sessions":[L("osolo","solo",3),L("opart","partnered",2),L("oduo","duo",4),L("otrio","trio",5),L("ogrp","group",6,groupSize=6),L("ogrpx","group",7),L("onone",None,8)],
         "active":None,"draft":None,"blocks":[],"ignored":[]}
    ctx=b.new_context(viewport={"width":390,"height":844},reduced_motion="reduce"); ctx.add_init_script("if(!localStorage.getItem('vouz.v1'))localStorage.setItem('vouz.v1',"+json.dumps(json.dumps(LEG))+")")
    p=ctx.new_page(); p.on("pageerror",lambda e:errs.append(str(e)+" @ "+str(getattr(e,"stack",""))[:600])); p.goto(URL); p.wait_for_timeout(400)
    ok("existing accounts: asked for a birthday once before going in","when were you born" in p.inner_text("#app").lower() and p.locator(".tabs").count()==0)
    dob(p,"gate",1990,5,5); act(p,"gateNext"); p.wait_for_selector(".sheet")
    ok("existing accounts: in after a valid birthday",S(p)["age"]["dob"]=="1990-05-05")
    t=p.inner_text(".sheet"); ok("legacy: a notice explains the change before anything is removed","1 Solo session and 1 Partnered session" in t and len(S(p)["sessions"])==7,t[:160])
    by={x["id"]:x for x in S(p)["sessions"]}
    ok("legacy: Duo becomes Couple, Trio and Group become Poly with their head count",[by[k]["category"] for k in ("oduo","otrio","ogrp","ogrpx")]==["couple","poly","poly","poly"] and [by[k]["participants"] for k in ("oduo","otrio","ogrp","ogrpx")]==[2,3,6,4] and "groupSize" not in by["ogrp"])
    ok("legacy: sessions with no mode stay unset, private fields kept",by["onone"]["category"] is None and by["oduo"]["notes"]=="keep-oduo")
    p.keyboard.press("Escape"); p.wait_for_timeout(100); ok("legacy: the notice can't be skipped",p.locator(".sheet").count()==1)
    act(p,"legacyExport"); p.wait_for_selector("#exp-out"); ok("legacy: a copy can be downloaded first, including the sessions about to go","OSOLO" in p.input_value("#exp-out") and "OPART" in p.input_value("#exp-out")); act(p,"closeSheet"); p.wait_for_selector('[data-act="legacyRemove"]')
    act(p,"legacyRemove"); p.wait_for_timeout(200); st=S(p)
    ok("legacy: Solo and Partnered removed, with tombstones so other devices remove them too",len(st["sessions"])==5 and "osolo" in st["deleted"] and "opart" in st["deleted"] and p.locator(".sheet").count()==0)
    p.reload(); p.wait_for_selector(".tabs"); ok("legacy: removal is final and the storage key is unchanged",p.locator(".sheet").count()==0 and len(S(p)["sessions"])==5 and p.evaluate("Object.keys(localStorage).join()")=="vouz.v1")
    # ---------- Couple and Poly ----------
    nav(p,"track"); act(p,"manual")
    ok("modes: only Couple and Poly are offered, Couple by default",[x.inner_text() for x in p.locator('[data-act="dCat"]').all()]==["Couple","Poly"] and p.locator('[data-act="dCat"][data-v="couple"]').get_attribute("aria-pressed")=="true" and "Who was involved?".upper() in p.inner_text(".scroll").upper())
    act(p,"dCat",v="poly"); ok("modes: Poly starts at 3 and can't go below",p.locator(".stepper b").inner_text()=="3" and p.locator('[data-act="dP"][data-d="-1"]').is_disabled())
    for _ in range(25):
        if p.locator('[data-act="dP"][data-d="1"]').is_disabled(): break
        act(p,"dP",d="1")
    ok("modes: Poly stops at the maximum of 20",p.locator(".stepper b").inner_text()=="20")
    for _ in range(16): act(p,"dP",d="-1")
    p.fill("#d-title","NEWPOLY"); act(p,"dSat",v="4"); p.fill("#d-shared","SHAREDLINE"); act(p,"saveSession"); p.wait_for_selector("text=Saved privately")
    x=S(p)["sessions"][-1]; ok("modes: Poly saves its head count, satisfaction and shared note",x["category"]=="poly" and x["participants"]==4 and x["satisfaction"]==4 and x["sharedNote"]=="SHAREDLINE")
    t=p.inner_text(".scroll"); ok("replay: mode, status, estimate label and satisfaction shown","Poly · 4" in t and "Self-reported" in t and "Estimated" in t and "4 of 5" in t)
    ok("replay: a Poly session can invite up to 3 others (Connections off: none offered)",p.locator('[data-act="addPeople"]').count()==1); act(p,"back")
    nav(p,"track"); act(p,"manual"); p.evaluate("()=>{const d=window.__vouz.S.draft;d.category='poly';d.participants=2}"); act(p,"saveSession")
    ok("modes: Poly with fewer than 3 people is refused",p.locator(".err").count()==1 and "3 to 20" in p.inner_text(".err"))
    p.evaluate("()=>{const d=window.__vouz.S.draft;d.category='trio'}"); act(p,"saveSession"); ok("modes: an unknown mode is refused",p.locator(".err").count()==1); act(p,"dCat",v="couple"); act(p,"saveSession"); p.wait_for_selector("text=Saved privately")
    ok("modes: Couple is always exactly 2",S(p)["sessions"][-1]["participants"]==2); act(p,"back")
    # timer with Poly chosen up front and changed mid-session
    nav(p,"track"); act(p,"tCat",v="poly"); act(p,"tP",d="1"); act(p,"start"); p.wait_for_timeout(1100)
    ok("timer: who-was-involved set before starting is kept",S(p)["active"]["category"]=="poly" and S(p)["active"]["participants"]==4)
    act(p,"pause"); act(p,"tCat",v="couple"); act(p,"resume"); p.reload(); p.wait_for_selector(".tabs")
    ok("timer: a change mid-session survives a reload",S(p)["active"]["category"]=="couple" and S(p)["active"]["participants"]==2 and len(S(p)["active"]["segments"])==2)
    act(p,"finish"); ok("timer: the save form opens with it selected",p.locator('[data-act="dCat"][data-v="couple"]').get_attribute("aria-pressed")=="true"); act(p,"saveSession"); p.wait_for_selector("text=Saved privately")
    ok("timer: saved as timed, with its pause",S(p)["sessions"][-1]["category"]=="couple" and len(S(p)["sessions"][-1]["segments"])==2 and "Timed" in p.inner_text(".scroll")); act(p,"back")
    # quick log: three taps
    nav(p,"home"); n0=len(S(p)["sessions"]); act(p,"quick"); ok("quick log: Save waits for a duration",p.locator('[data-act="qSave"]').is_disabled())
    act(p,"qDur",v="30"); act(p,"qSave"); p.wait_for_timeout(150); q=S(p)["sessions"][-1]
    ok("quick log: open, pick a length, save; stored as an estimate",len(S(p)["sessions"])==n0+1 and q["durationSec"]==1800 and q["segments"] is None and q["category"]=="couple")
    act(p,"quick"); act(p,"qDur",v="30"); act(p,"qSave"); p.wait_for_timeout(150); ok("quick log: an accidental second save is caught",len(S(p)["sessions"])==n0+1)
    # insights
    nav(p,"analytics"); act(p,"insRange",v="year"); cnt={}
    for cat in ("all","couple","poly"): act(p,"insCat",v=cat); cnt[cat]=p.locator(".tile b").first.inner_text()
    ok("insights: counts for All, Couple and Poly",cnt=={"all":"9","couple":"4","poly":"4"},str(cnt))
    act(p,"insCat",v="all"); t=p.inner_text(".scroll"); ok("insights: timed and estimated are kept apart","1 timed with VOUZ, 8 entered by hand" in t,t[t.find("timed")-40:t.find("timed")+60])
    act(p,"insTab",v="patterns"); t=p.inner_text(".scroll"); ok("insights: Couple and Poly compared, earlier unset sessions counted","COUPLE AND POLY" in t.upper() and "1 earlier session with no mode set" in t)
    sid=[x for x in S(p)["sessions"] if x.get("title")=="NEWPOLY"][0]["id"]
    card=p.evaluate("id=>JSON.stringify(window.__vouz.buildCard({kind:'recap',showCategory:true,showDuration:true,style:0},window.__vouz.S.sessions.find(s=>s.id===id)))",sid)
    ok("sharing: a card says Poly and never the head count, satisfaction or shared note",'"category":"Poly"' in card and "4" not in card.replace('"arc":15',"").replace("About 15 min","") and "SHAREDLINE" not in card,card)
    # ---------- Discover, plans, Our Story ----------
    nav(p,"ideas"); n_all=p.locator('[data-act="ideaSave"]').count(); act(p,"fOpen"); act(p,"fSet",k="b",v="0"); act(p,"fSet",k="ds",v="home")
    titles=[x.inner_text() for x in p.locator(".idea .it").all()]
    ok("discover: filters narrow the ideas to free, at-home ones",0<len(titles)<n_all and "Write each other letters" in titles and "Take a road trip" not in titles,str(titles))
    act(p,"fClear"); ok("discover: clearing filters brings everything back",p.locator('[data-act="ideaSave"]').count()==n_all)
    act(p,"ideaSave",v="picnic"); ok("discover: an idea saves to plans once",p.locator('[data-act="ideaSave"][data-v="picnic"]').is_disabled() and len([e for e in S(p)["exps"] if e["idea"]=="picnic"])==1)
    nav(p,"home"); ok("home: the plan shows under Coming up","Pack a picnic" in p.inner_text(".scroll") and "Unscheduled" in p.inner_text(".scroll"))
    pid=[e for e in S(p)["exps"] if e["idea"]=="picnic"][0]["id"]
    nav(p,"plans"); act(p,"planSched",id=pid); p.fill("#sch-in",time.strftime("%Y-%m-%dT18:30",time.localtime(time.time()+3*86400))); act(p,"schedSave"); ok("plans: scheduling sets the date",S(p)["exps"][-1]["date"] is not None and "6:30pm" in p.inner_text(".scroll"))
    act(p,"planDone",id=pid); ok("plans: marking done opens the memory form",p.locator("#x-title").input_value()=="Pack a picnic")
    p.fill("#x-fav","FAVMOMENT"); p.fill("#x-notes","PRIVNOTE"); act(p,"xMood",v="Relaxed"); act(p,"expSave"); p.wait_for_timeout(150); e=[x for x in S(p)["exps"] if x["id"]==pid][0]
    ok("plans: done moves it to Our Story with today's date",e["kind"]=="done" and e["favorite"]=="FAVMOMENT" and e["date"]<=time.time()*1000+86400000 and "Private: only you see this." in p.inner_text(".scroll"))
    nav(p,"story"); ok("story: the memory is on the timeline","Pack a picnic" in p.inner_text(".scroll"))
    act(p,"expNew",kind="done"); act(p,"expSave"); ok("memory: a title is required",p.locator(".err").count()==1)
    p.fill("#x-title","FUTURE"); p.fill("#x-date",time.strftime("%Y-%m-%d",time.localtime(time.time()+9*86400))); act(p,"expSave"); ok("memory: can't be dated in the future",p.locator(".err").count()==1 and "plan" in p.inner_text(".err"))
    ann=time.strftime("%Y-%m-%d",time.localtime(time.time()-365*86400+10*86400))
    p.fill("#x-title","MOVEDIN"); p.fill("#x-date",ann); act(p,"xCat",v="milestone"); act(p,"xAnniv")
    png=__import__("base64").b64decode("iVBORw0KGgoAAAANSUhEUgAAAAgAAAAGCAIAAABxZ0isAAAAEUlEQVR4nGM4YROFFTEMpAQAUDNBoan1CMYAAAAASUVORK5CYII=")
    p.set_input_files("#x-photo",files=[{"name":"a.png","mimeType":"image/png","buffer":png}]); p.wait_for_function("document.querySelectorAll('.ph img').length===1"); p.wait_for_timeout(300)
    ok("photos: added and shown from this device",p.evaluate("document.querySelector('.ph img').naturalWidth")>0)
    act(p,"expSave"); p.wait_for_timeout(200); m=[x for x in S(p)["exps"] if x["title"]=="MOVEDIN"][0]; ph=m["photos"][0]
    ok("photos: stored on the device, re-encoded",p.evaluate("id=>window.__vouz.Photos.get(id).then(b=>b&&b.type)",ph)=="image/jpeg")
    nav(p,"story"); ok("story: anniversary reminder from a milestone","first anniversary in 10 days" in p.inner_text(".scroll"),p.inner_text(".scroll")[:300])
    nav(p,"profile"); act(p,"exportData"); p.wait_for_selector("#exp-out"); ex=p.input_value("#exp-out")
    ok("export: memories included, notes kept, photos left out","MOVEDIN" in ex and "PRIVNOTE" in ex and ph not in ex); act(p,"closeSheet")
    nav(p,"story"); act(p,"expOpen",id=m["id"]); act(p,"expDelAsk",id=m["id"]); act(p,"confirmYes"); p.wait_for_timeout(300)
    ok("memory: deleting removes its photos from the device",p.evaluate("id=>window.__vouz.Photos.get(id).then(b=>b===undefined)",ph) and m["id"] in S(p)["deleted"])
    nav(p,"match"); ok("Mutual Match: explains it needs Connections when they're off","needs Connections" in p.inner_text(".scroll"))
    ctx.close()
    # ---------- Daily Forecast (Insights → Forecast) ----------
    ctx,p=newctx(b); p.goto(URL); p.wait_for_timeout(300); onboard(p); nav(p,"insights"); p.wait_for_selector(".ihero .fw:not(.shimmer)")
    th=p.inner_text(".scroll"); hw=p.inner_text(".ihero .fw")
    ok("insights: forecast is the centerpiece, then pulse, move, patterns and past words, nothing social",th.lower().index("today's energy")<th.lower().index("relationship pulse")<th.lower().index("today's move")<th.lower().index("patterns")<th.lower().index("past words") and p.locator(".post2").count()==0 and "%" not in th)
    ok("insights: patterns are honest when there's nothing yet","Nothing here is guessed" in th)
    act(p,"page",page="forecast"); p.wait_for_selector(".fcard .fw:not(.shimmer)")
    w0=p.inner_text(".fcard .fw"); t=p.inner_text(".scroll")
    ok("forecast: the full forecast opens from Insights with the same word, honest about having nothing to go on",w0==hw and w0 in ["UNWRITTEN","CURIOUS","OPEN","WARM","PLAYFUL","SERENE","ELECTRIC","BOLD","SPARKED","STEADY","DEVOTED","UNHURRIED","TENDER","INTIMATE","MAGNETIC"] and t.count("Not enough to go on")==4)
    ok("forecast: with no check-ins yet, the word comes from the stars and says so","Word from the stars" in t and "astrology, for fun" in t and "cosmic outlook" in t.lower())
    ok("forecast: three sections, each labelled observed, reflection or suggestion",all(x in t.lower() for x in ["your connection","what to embrace","what to watch"]) and p.locator(".fsec .ftag").count()==3)
    ok("forecast: no numbers on the energies","%" not in p.inner_text(".fdims") and not re.search(r"\d",p.inner_text(".fdims")))
    p.reload(); p.wait_for_timeout(400); nav(p,"forecast"); p.wait_for_selector(".fcard .fw:not(.shimmer)"); ok("forecast: same forecast after reopening (no re-roll)",p.inner_text(".fcard .fw")==w0 and len(S(p)["fc"]["hist"])==1)
    act(p,"fcE",v="Tender"); act(p,"fcC",v="5"); act(p,"fcW",v="closeness"); act(p,"fcCkSave"); p.wait_for_timeout(200)
    ok("check-in: saved on this device",S(p)["fc"]["checkins"][list(S(p)["fc"]["checkins"])[0]]["energy"]=="Tender")
    act(p,"fcUpdate"); p.wait_for_timeout(500); fc=[v for v in S(p)["fc"]["hist"].values()][0]["solo"]
    ok("check-in: one update to today's forecast, now shaped by it",fc.get("updated") and fc["dims"]["in"] is not None and "Not enough to go on" not in p.inner_text(".fdims").split("Intimacy")[1][:40] and p.locator('[data-act="fcUpdate"]').count()==0)
    act(p,"fcMove"); ok("today's move opens into questions and ideas",p.locator(".fq").count()==3 and p.locator('.ideal [data-act="ideaSave"]').count()>=1)
    ok("closeness ideas are off by default","Just for you two" not in p.inner_text(".scroll"))
    act(p,"fcFit",v="0"); alt=p.locator('[data-act="fcFix"]').first.get_attribute("data-v"); act(p,"fcFix",v=alt); fc=[v for v in S(p)["fc"]["hist"].values()][0]["solo"]
    ok("not quite: recorded with the better word, kept on the device",fc["rejected"]==fc["word"] and fc["corrected"]==alt)
    ok("history: today's word on the calendar",p.locator(".fcal.on").count()==1)
    act(p,"fcShareOpen"); p.wait_for_selector("#sh-prev canvas"); cv=p.evaluate("()=>{const c=document.querySelector('#sh-prev canvas');return [c.width,c.height,document.querySelector('#sh-prev').getBoundingClientRect().height]}")
    ok("share: the forecast's share button opens the studio editor, previewed, 9:16 by default",cv[0]==1080 and cv[1]==1920 and cv[2]>200 and "exactly what will be shared" in p.inner_text(".scroll"))
    act(p,"back"); act(p,"back"); nav(p,"share"); p.wait_for_selector("#sh-hero canvas")
    t=p.inner_text(".scroll")
    ok("share tab: today's card up top with Customize and Share",p.locator('[data-act="shEdit"][data-k="daily"]').count()>=1 and p.locator('[data-act="shQuick"]').count()==1)
    ok("share tab: only cards there's data for; the rest say what they need",p.locator('.shtile[data-k="daily"]').count()==1 and p.locator('.shtile.off').count()>=3 and "Turn on forecast together" in t and "Mark a memory as a milestone" in t)
    act(p,"shEdit",k="daily"); p.wait_for_selector("#sh-prev canvas"); h0=p.evaluate("document.querySelector('#sh-prev').dataset.n")
    act(p,"shSet",k="theme",v="minimal"); p.wait_for_timeout(300); act(p,"shSet",k="fmt",v="square"); p.wait_for_timeout(300); act(p,"shSet",k="type",v="sans"); p.wait_for_timeout(300); act(p,"shSet",k="brand",v="off"); p.wait_for_timeout(300)
    ok("editor: theme, size, type and branding change the real image",p.evaluate("document.querySelector('#sh-prev canvas').height")==1080 and p.evaluate("document.querySelector('#sh-prev').dataset.n")!=h0)
    ok("editor: names need a couple profile both approved",p.locator('[data-act="shSet"][data-k="names"][data-v="initials"][disabled]').count()==1 and "both approved" in p.inner_text(".scroll"))
    png=p.evaluate("async()=>{const c=await shRender('daily',{...S.shareDefaults,names:'',viz:false},null);return c.toDataURL('image/png').length}") if False else p.evaluate("async()=>{const V=window.__vouz;return (await V.shRender('daily',{theme:'editorial',type:'serif',bg:'wine',fmt:'story',brand:'full'},null)).toDataURL('image/png').length}")
    ok("export: a real high-resolution PNG is produced",png>20000,str(png))
    ok("editor: choices are remembered for next time",S(p)["shareDefaults"]["theme"]=="minimal" and S(p)["shareDefaults"]["fmt"]=="square")
    act(p,"shSave"); p.wait_for_selector(".toast"); ok("export: only on tap, with an honest message when saving isn't available",p.locator(".toast").count()==1)
    p.screenshot(path=SH+"share-edit.png"); act(p,"back"); p.wait_for_timeout(300); p.screenshot(path=SH+"share.png"); nav(p,"insights"); p.wait_for_timeout(300); p.screenshot(path=SH+"insights.png"); ctx.close()
    # ---------- astrology ----------
    ctx,p=newctx(b); p.goto(URL); p.wait_for_timeout(300)
    def deep(pg): pg.fill("#as-time","14:30"); pg.fill("#as-place","Mission District"); act(pg,"obDeeper")
    onboard(p,born=(1995,11,8),deeper=deep); nav(p,"profile"); act(p,"page",page="astro"); t=p.inner_text(".scroll")
    ok("astro: Sun, Moon, Venus, Mars from the birthday; Rising needs the place on a map",all(x in t for x in ["Scorpio","Gemini","Sagittarius"]) and "Needs your birthplace on the map" in t)
    act(p,"asUnknown"); act(p,"asSave"); p.wait_for_timeout(200); t=p.inner_text(".scroll")
    ok("astro: with birth time unknown, an uncertain Moon is shown as either sign, never guessed","Taurus or Gemini" in t and "Needs a birth time" in t)
    act(p,"asDelete"); act(p,"confirmYes"); a1=S(p)["astro"]; ok("astro: birth time and place can be deleted",a1["time"] is None and a1["place"] is None and S(p)["age"]["dob"]=="1995-11-08")
    act(p,"asFixDob"); dob(p,"dobFix",2012,1,1); act(p,"dobFixSave"); ok("birthday: a correction can't make someone under 18","under 18" in p.inner_text(".scroll") and S(p)["age"]["dob"]=="1995-11-08")
    act(p,"back"); nav(p,"insights"); p.wait_for_selector(".ihero .fw:not(.shimmer)"); t=p.inner_text(".scroll")
    ok("insights: cosmic outlook and real connection labelled separately","cosmic outlook" in t.lower() and "astrology · for fun" in t.lower() and "real connection" in t.lower())
    act(p,"page",page="cosmic"); t=p.inner_text(".scroll"); ok("cosmic page: horoscope, week of Moon signs, and how to add a partner","your horoscope" in t.lower() and t.count("Moon in")>=7 and "cosmic connection" in t.lower())
    act(p,"back"); nav(p,"share"); p.wait_for_timeout(400); t=p.inner_text(".scroll")
    ok("share: zodiac and weekly cosmic cards available; partner ones say what they need",p.locator('.shtile[data-k="zodiac"]').count()==1 and p.locator('.shtile[data-k="weeklycos"]').count()==1 and "When a partner lets you share their sign" in t)
    act(p,"shEdit",k="zodiac"); p.wait_for_selector("#sh-prev canvas"); ok("share: zodiac card renders",p.evaluate("document.querySelector('#sh-prev canvas').height")>=1080)
    ok("share: no birth details anywhere in the card data",p.evaluate("JSON.stringify(window.__vouz.shData?window.__vouz.shData('zodiac'):'')").find("1995")<0)
    nav(p,"profile"); act(p,"page",page="astro"); act(p,"asOn"); nav(p,"insights"); p.wait_for_timeout(300)
    ok("astro: can be turned off; nothing cosmic shows","cosmic outlook" not in p.inner_text(".scroll").lower()); ctx.close()
    # ---------- AI planner (Claude mocked: records exactly what would be sent) ----------
    PMOCK="""window.__prompts=[];window.__planFail=null;(()=>{const f=async()=>({text:''});f.json=async(input,opts)=>{window.__prompts.push({input,opts:Object.keys(opts||{})});if(String(input).includes('connection guide')&&!window.__planFail)return{answer:'You two tend to enjoy outdoor dates. https://evil.example/x',ideas:['hike','nope']};if(window.__planFail)throw {code:window.__planFail};
      return {suggestions:[{title:'<img src=x onerror="window.__xss=1">Sunset walk',why:'Easy and free',cost:'Free',time:'1 hour',setting:'Outdoors',steps:['Pick a spot','Bring a blanket']},{title:'Cook a new recipe',cost:'$',steps:[]},{bogus:1}]}};
      window.claude={use:async n=>n==='sample'?f:null}})();"""
    ctx=b.new_context(viewport={"width":390,"height":844},reduced_motion="reduce"); ctx.add_init_script(PMOCK); p=ctx.new_page(); p.on("pageerror",lambda e:errs.append(str(e)+" @ "+str(getattr(e,"stack",""))[:600]))
    p.goto(URL); p.wait_for_selector(".ob"); onboard(p)
    log(p,"SESSIONTITLE",20,notes="SESSIONSECRET",cat="poly"); nav(p,"story"); act(p,"expNew",kind="done"); p.fill("#x-title","MEMTITLE"); p.fill("#x-notes","MEMNOTE"); act(p,"expSave")
    nav(p,"planner"); ok("planner: offered in Discover, nothing sent until asked",p.locator('[data-act="plAsk"]').count()==1 and p.evaluate("window.__prompts.length")==0)
    act(p,"plEx",i="2"); act(p,"plSet",k="budget",v="50"); p.fill("#pl-area","Oakland"); act(p,"plAsk"); p.wait_for_selector(".idea .it")
    pr=p.evaluate("window.__prompts[0].input")
    ok("planner: sends the request, budget and the area typed",all(w in pr for w in ["Plan a date under $50","Under $50","Oakland"]))
    ok("planner: never sends intimacy records, notes or memories unless asked",not any(w in pr for w in ["SESSIONTITLE","SESSIONSECRET","Poly","MEMTITLE","MEMNOTE"]))
    ok("planner: told not to claim availability or bookings","availability" in pr and "booked" in pr)
    titles=[x.inner_text() for x in p.locator(".idea .it").all()]
    ok("planner: answers are cleaned up and shown safely",len(titles)==2 and titles[0].endswith("Sunset walk") and "<img" in titles[0] and p.evaluate("window.__xss")is None)
    ok("planner: says it hasn't checked availability and can't book","can't book" in p.inner_text(".scroll"))
    act(p,"plSave",i="1"); x=[e for e in S(p)["exps"] if e["title"]=="Cook a new recipe"]
    ok("planner: a suggestion saves to plans",len(x)==1 and x[0]["kind"]=="plan" and p.locator('[data-act="plSave"][data-i="1"]').is_disabled())
    act(p,"plHist"); act(p,"plAsk",again="1"); p.wait_for_timeout(300); pr=p.evaluate("window.__prompts[1].input")
    ok("planner: 'avoid repeats' adds memory titles only",("MEMTITLE" in pr) and "MEMNOTE" not in pr and "SESSIONTITLE" not in pr and "SESSIONSECRET" not in pr)
    ok("planner: 'try again' asks afresh",p.evaluate("window.__prompts[1].opts").count("cache")==1)
    p.evaluate("window.__planFail='rate_limited'"); act(p,"plAsk",again="1"); p.wait_for_selector(".err"); ok("planner: errors are explained, not retried",p.evaluate("window.__prompts.length")==3 and "Try again in a little while" in p.inner_text(".err"))
    p.evaluate("window.__planFail='not_granted'"); act(p,"plAsk",again="1"); p.wait_for_timeout(300); ok("planner: hides itself if Claude isn't allowed","isn't available here" in p.inner_text(".scroll"))
    # ---------- connection guide (Insights → Your connection) ----------
    p.evaluate("window.__planFail=null"); n0=p.evaluate("window.__prompts.length")
    nav(p,"guide")
    ok("guide: off until turned on, explains what it gets, sends nothing","Turn on the guide" in p.inner_text(".scroll") and "never gets" in p.inner_text(".scroll").lower() and p.evaluate("window.__prompts.length")==n0)
    act(p,"guideOn"); act(p,"guideEx",i="0"); act(p,"guideAsk"); p.wait_for_selector(".ga")
    pr=p.evaluate("window.__prompts.slice(-1)[0].input")
    ok("guide: sends totals across dates, memories and intimacy",all(w in pr for w in ["memoriesLogged","sessions","datesAndHowTheyFelt","How are we doing lately?"]))
    ok("guide: never sends titles, notes or individual records",not any(w in pr for w in ["SESSIONTITLE","SESSIONSECRET","MEMTITLE","MEMNOTE"]))
    ok("guide: told never to treat more as better or to act as a therapist","Never treat more intimacy" in pr and "not a therapist" in pr)
    t=p.inner_text(".ga")
    ok("guide: answer shown, links stripped, only real ideas offered","outdoor dates" in t and "evil.example" not in t and "Go hiking" in t and p.locator('.ga [data-act="ideaSave"]').count()==1)
    p.locator(".ga").scroll_into_view_if_needed(); p.screenshot(path=SH+"guide.png")
    ok("guide: shows exactly what it sees",p.locator(".gsum").count()==1 and "SESSIONTITLE" not in p.inner_text(".gsum"))
    p.fill("#g-q","I feel unsafe, he hurts me"); act(p,"guideAsk"); p.wait_for_timeout(300)
    ok("guide: points to help when someone may not be safe","1-800-799-7233" in p.inner_text(".scroll") and "988" in p.inner_text(".scroll"))
    act(p,"guideOff"); ok("guide: can be turned off, conversation cleared",not S(p)["settings"]["guide"] and "Turn on the guide" in p.inner_text(".scroll"))
    ctx.close()
    # ---------- rewards: points, caps, badges, challenges, redemption, switches ----------
    ctx,p=newctx(b); p.goto(URL); p.wait_for_selector(".ob"); onboard(p)
    def addmem(title,cat="dinner",loc="",space=None):
        nav(p,"story"); act(p,"expNew",kind="done"); p.fill("#x-title",title); act(p,"xCat",v=cat)
        if loc: p.fill("#x-loc",loc)
        act(p,"expSave"); p.wait_for_timeout(150)
    def R_(): return p.evaluate("(()=>{const r=window.__vouz.R();return {earned:r.earned,balance:r.balance,level:r.level.n,awards:r.awards.map(a=>[a.k,a.vp,a.why]),badges:r.badges.filter(b=>b.earnedAt).map(b=>b.id)}})()")
    nav(p,"home"); ok("rewards: Home shows level and points, starting from nothing",p.locator(".prog2").count()==1 and "Spark" in p.inner_text(".prog2") and "0 VP" in p.inner_text(".prog2") and R_()["earned"]==0)
    addmem("FIRSTDINNER","dinner","Corner bistro")
    ok("rewards: a memory earns 20, a first kind 50, and First Spark",R_()["earned"]==70 and "spark" in R_()["badges"])
    ok("rewards: earning celebrates, with the points and the badge",p.locator(".cel").count()==1 and "+70 VP" in p.inner_text(".cel") and "First Spark" in p.inner_text(".cel"))
    p.screenshot(path=SH+"celebrate.png"); act(p,"celClose")
    for i in range(3): addmem("MORE"+str(i),"dinner")
    r=R_(); counted=[a for a in r["awards"] if a[0].startswith("exp:") and a[1]>0]
    ok("rewards: only 3 memories a day earn points",len(counted)==3 and r["earned"]==3*20+50,str(r["earned"]))
    p.reload(); p.wait_for_selector(".tabs"); ok("rewards: nothing is awarded twice across a reload",R_()["earned"]==110 and p.locator(".cel").count()==0)
    mid=[e for e in S(p)["exps"] if e["title"]=="FIRSTDINNER"][0]["id"]; nav(p,"story"); act(p,"expOpen",id=mid); act(p,"expDelAsk",id=mid); act(p,"confirmYes"); p.wait_for_timeout(150)
    ok("rewards: deleting a memory takes its points back (the daily cap then lets the next one count)",not any(a[0]=="exp:"+mid for a in R_()["awards"]) and R_()["earned"]<=110 and "spark" in R_()["badges"])
    nav(p,"home"); act(p,"quick"); act(p,"qDur",v="20"); act(p,"qSave"); p.wait_for_timeout(200)
    celtxt=p.inner_text(".cel") if p.locator(".cel").count() else ""
    ok("rewards: an intimacy log earns 10 and is celebrated only as 'Private log'","+10 VP" in celtxt and "Private log" in celtxt and not any(w in celtxt for w in ["Couple","Poly","min","session"]),celtxt)
    e0=R_()["earned"]; nav(p,"track"); act(p,"manual"); p.fill("#d-min","45"); act(p,"dCat",v="poly"); act(p,"saveSession"); p.wait_for_selector("text=Saved privately")
    ok("rewards: more sessions, longer ones or more people earn nothing more that week",R_()["earned"]==e0)
    # weekly challenge
    nav(p,"profile"); act(p,"page",page="rewards"); ch=p.evaluate("window.__vouz.RW.challengesFor(window.__vouz.RW.week(Date.now()),window.__vouz.S.settings.chPrefs)[0]")
    addmem("CHALLENGEMEM",(ch.get("kinds") or ["other"])[0],"Brand new place "+str(time.time()))
    nav(p,"profile"); act(p,"page",page="rewards"); act(p,"chOpen",v=ch["id"]); act(p,"chPick")
    if ch.get("attest"): act(p,"chSave"); ok("challenge: a self-reported part must be ticked",p.locator(".sheet .err").count()==1); act(p,"chAttest")
    b0=R_()["earned"]; act(p,"chSave"); p.wait_for_timeout(200)
    ok("challenge: completing one earns 150 and the badge",R_()["earned"]==b0+150 and "challenger" in R_()["badges"] and p.locator('[data-act="chOpen"]').count()==0)
    # plans and level
    nav(p,"ideas"); act(p,"ideaSave",v="brunch"); pid=[e for e in S(p)["exps"] if e.get("idea")=="brunch"][0]["id"]; nav(p,"plans"); act(p,"planDone",id=pid); act(p,"expSave"); p.wait_for_timeout(200)
    ok("rewards: completing a planned date earns 75",any(a[0]=="plan:"+pid and a[1]==75 for a in R_()["awards"]))
    r=R_(); ok("rewards: the level follows points earned",r["level"]==3 and r["earned"]>=250,str(r["earned"]))
    # redemption
    nav(p,"profile"); act(p,"page",page="rewards"); act(p,"rwSeg",v="shop")
    ok("redeem: too-expensive rewards can't be redeemed",p.locator('[data-act="rwBuy"][data-v="th_champagne"]').is_disabled())
    ok("redeem: no fictional offers, coupons or discounts","no partner offers" in p.inner_text(".scroll") and not re.search(r"\b(coupon code|% off|discount code)\b",p.inner_text(".scroll"),re.I))
    bal=R_()["balance"]; lv=R_()["level"]; act(p,"rwBuy",v="th_bordeaux"); ok("redeem: asks first",p.locator(".sheet").count()==1 and R_()["balance"]==bal); act(p,"confirmYes"); p.wait_for_timeout(150)
    ok("redeem: spends points once, keeps the level, applies the theme",R_()["balance"]==bal-300 and R_()["level"]==lv and p.evaluate("document.body.className")=="th-bordeaux")
    ok("redeem: an owned reward can't be bought twice",p.locator('[data-act="rwBuy"][data-v="th_bordeaux"]').count()==0)
    act(p,"rwUse",v="th_bordeaux"); ok("redeem: a theme can be switched off and on",p.evaluate("document.body.className")=="")
    act(p,"rwSeg",v="history"); t=p.inner_text(".scroll"); ok("history: earnings, the daily limit and the redemption are listed","Redeemed: Bordeaux theme" in t and "not counted" in t and "Weekly challenge" in t)
    act(p,"rwSeg",v="badges"); ok("badges: earned, up next and private achievements are shown",p.locator(".btile.on").count()>=2 and "Up next".upper() in p.inner_text(".scroll").upper() and "Private achievements" in p.inner_text(".scroll")); p.screenshot(path=SH+"badges.png")
    # switches
    act(p,"rwSeg",v="progress"); act(p,"rwCel"); addmem("QUIETONE","celebration"); ok("switch: celebrations can be turned off",p.locator(".cel").count()==0 and R_()["earned"]>0)
    nav(p,"profile"); act(p,"page",page="rewards"); act(p,"rwCel"); act(p,"rwGames"); nav(p,"home")
    ok("switch: gamification off hides levels and points everywhere",p.locator(".prog2").count()==0 and "VP" not in p.inner_text(".scroll") and p.evaluate("document.body.className")=="")
    addmem("WHILEOFF","movie"); ok("switch: nothing celebrates while it's off",p.locator(".cel").count()==0)
    nav(p,"profile"); act(p,"page",page="rewards"); act(p,"rwGames"); nav(p,"home"); p.wait_for_timeout(200)
    ok("switch: turning it back on picks up quietly from the records",p.locator(".cel").count()==0 and p.locator(".prog2").count()==1)
    ctx.close()
    # ---------- shareable memory cards ----------
    CMOCK="""window.__saved=[];window.__dlFail=null;window.__shared=[];window.__copied=[];
      const dl={save:async({filename,data})=>{const buf=new Uint8Array(await data.arrayBuffer());let s='';for(let i=0;i<Math.min(buf.length,200000);i++)s+=String.fromCharCode(buf[i]);
        const bmp=await createImageBitmap(data);window.__saved.push({filename,size:buf.length,head:Array.from(buf.subarray(0,4)),exif:s.includes('Exif'),gps:s.includes('GPS'),w:bmp.width,h:bmp.height});
        if(window.__dlFail)throw {code:window.__dlFail};return {status:'saved'}}};
      window.__noDl=sessionStorage.getItem('noDl')==='1';window.claude={use:async n=>n==='downloads'?(window.__noDl?null:dl):null};"""
    ctx=b.new_context(viewport={"width":390,"height":844},reduced_motion="reduce"); ctx.add_init_script(CMOCK)
    ctx.route("**/index.html",lambda route:route.fulfill(response=route.fetch(),headers={**route.fetch().headers,"content-security-policy":"img-src 'self' data:"}))
    p=ctx.new_page(); p.on("pageerror",lambda e:errs.append(str(e)+" @ "+str(getattr(e,"stack",""))[:600]))
    p.goto(URL); p.wait_for_selector(".ob"); onboard(p)
    jpg=open(os.path.join(HERE,"fixtures","gps.jpg"),"rb").read()
    nav(p,"story"); act(p,"expNew",kind="done"); p.fill("#x-title","Sunset on the pier"); p.fill("#x-loc","Pier 7"); p.fill("#x-fav","FAVLINE"); p.fill("#x-notes","PRIVNOTE"); act(p,"xMood",v="Tender")
    p.set_input_files("#x-photo",files=[{"name":"g.jpg","mimeType":"image/jpeg","buffer":jpg},{"name":"g2.jpg","mimeType":"image/jpeg","buffer":jpg}]); p.wait_for_function("document.querySelectorAll('.ph img').length===2"); act(p,"expSave"); p.wait_for_timeout(200)
    from PIL import Image as _I; import io as _io; ok("cards: the original photo had camera and GPS data",b"Exif" in jpg and len(_I.open(_io.BytesIO(jpg)).getexif().get_ifd(0x8825))>0)
    mem=[e for e in S(p)["exps"] if e["title"]=="Sunset on the pier"][0]; up0=mem["updatedAt"]
    ok("cards: the stored photo already has no camera or location data",p.evaluate("id=>window.__vouz.Photos.get(id).then(b=>b.arrayBuffer()).then(a=>{const u=new Uint8Array(a);let s='';for(let i=0;i<u.length;i++)s+=String.fromCharCode(u[i]);return !s.includes('Exif')&&!s.includes('GPS')})",mem["photos"][0]))
    ok("cards: every memory has a Share button",p.locator('[data-act="mcOpen"]').count()==1); act(p,"mcOpen")
    p.wait_for_function("!!document.querySelector('#mc-prev canvas')",timeout=20000)
    ok("cards: the preview is the real 1080 × 1920 card, shown even where image addresses are blocked",p.evaluate("[document.querySelector('#mc-prev canvas').width,document.querySelector('#mc-prev canvas').height]")==[1080,1920] and "1080 × 1920" in p.inner_text("#mc-meta") and p.evaluate("document.querySelector('#mc-prev canvas').getBoundingClientRect().height")>300)
    ok("cards: memory photos still show with image addresses blocked",p.evaluate("Array.from(document.querySelectorAll('.pickph img')).every(i=>i.complete&&i.naturalWidth>0)"))
    p.screenshot(path=SH+"card_editor.png")
    content=json.dumps(p.evaluate("e=>window.__vouz.cardContent({showDate:true,showLoc:true,showBrand:true,caption:''},e)",mem))
    ok("cards: only the title, date, place and your caption can appear; never notes, mood or favorite unless chosen",not any(w in content for w in ["PRIVNOTE","Tender","FAVLINE"]) and "Sunset on the pier" in content and "Pier 7" in content)
    last={"src":None}
    def img_hash():
        p.wait_for_function("prev=>{const c=document.querySelector('#mc-prev canvas');return c&&c.dataset.n!==prev}",arg=last["src"],timeout=20000)
        last["src"]=p.evaluate("document.querySelector('#mc-prev canvas').dataset.n")
        return p.evaluate("crypto.subtle.digest('SHA-256',new TextEncoder().encode(document.querySelector('#mc-prev canvas').toDataURL())).then(h=>Array.from(new Uint8Array(h)).slice(0,8).join('.'))")
    h0=img_hash(); hs={"minimal":h0}
    for tp in ("cinematic","polaroid","editorial"): act(p,"mcTpl",v=tp); hs[tp]=img_hash()
    ok("cards: four templates, each a different image",len(set(hs.values()))==4)
    for tp in ("cinematic","polaroid","editorial","minimal"): act(p,"mcTpl",v=tp); img_hash(); p.locator("#mc-prev").screenshot(path=SH+f"card_{tp}.png")
    act(p,"mcFav"); h1=img_hash(); ok("cards: the caption changes the image, and can use the favorite moment",h1!=hs["minimal"] and p.input_value("#mc-cap")=="FAVLINE")
    p.fill("#mc-cap","Our quiet hour"); h2=img_hash(); ok("cards: typing a caption redraws it",h2!=h1)
    act(p,"mcDate"); h3=img_hash(); act(p,"mcLoc"); h4=img_hash(); act(p,"mcBrand"); h5=img_hash()
    ok("cards: date, place and branding can each be hidden",len({h2,h3,h4,h5})==4)
    act(p,"mcDate"); img_hash(); act(p,"mcLoc"); img_hash(); act(p,"mcBrand"); img_hash()
    act(p,"mcPhoto",v=mem["photos"][0]); h6=img_hash(); act(p,"mcPhoto",v=mem["photos"][0]); h7=img_hash()
    act(p,"mcTpl",v="polaroid"); h8=img_hash(); act(p,"mcPhoto",v=mem["photos"][1]); h9=img_hash()
    ok("cards: you choose which photos appear, and how many",len({h6,h7})==2 and h8!=h9 and len(S(p)["exps"][0]["photos"])==2)
    act(p,"mcTpl",v="minimal"); h7=img_hash()
    act(p,"mcBg",v="ivory"); ok("cards: backgrounds change the image",img_hash()!=h7)
    for fmt,(w,h) in (("square",(1080,1080)),("landscape",(1920,1080)),("portrait",(1080,1920))):
        act(p,"mcFmt",v=fmt); p.wait_for_function(f"document.querySelector('#mc-prev canvas')&&document.querySelector('#mc-prev canvas').width=={w}&&document.querySelector('#mc-prev canvas').height=={h}",timeout=20000)
        r=p.evaluate("(()=>{const b=document.querySelector('#mc-prev').getBoundingClientRect();return [b.width,b.height]})()")
        ok(f"cards: {fmt} preview is on screen at the right proportions",r[1]>150 and abs(r[0]/r[1]-w/h)<0.02,str(r))
    act(p,"mcSave",v="png"); p.wait_for_function("window.__saved.length===1"); sv=p.evaluate("window.__saved[0]")
    ok("save: a real PNG at full size",sv["head"]==[137,80,78,71] and [sv["w"],sv["h"]]==[1080,1920] and sv["filename"].endswith(".png") and sv["size"]>50000,str(sv))
    act(p,"mcSave",v="jpg"); p.wait_for_function("window.__saved.length===2"); sv=p.evaluate("window.__saved[1]")
    ok("save: a real JPEG, with no camera or location data",sv["head"][:3]==[255,216,255] and not sv["exif"] and not sv["gps"] and sv["filename"].endswith(".jpg"),str(sv))
    act(p,"mcFmt",v="landscape"); act(p,"mcSave",v="png"); p.wait_for_function("window.__saved.length===3"); sv=p.evaluate("window.__saved[2]")
    ok("save: the exported size matches the chosen shape",[sv["w"],sv["h"]]==[1920,1080])
    p.evaluate("window.__dlFail='declined'"); act(p,"mcSave",v="png"); p.wait_for_selector("text=Not saved."); ok("save: a declined save is reported plainly",True); p.evaluate("window.__dlFail=null")
    # native share sheet where the browser offers one
    p.evaluate("""()=>{navigator.canShare=f=>!!(f&&f.files&&f.files.length);navigator.share=async d=>{const f=d.files[0];window.__shared.push({name:f.name,type:f.type,size:f.size});if(window.__shareAbort)throw new DOMException('x','AbortError')}}""")
    n0=p.evaluate("window.__saved.length"); act(p,"mcShare"); p.wait_for_function("window.__shared.length===1"); sh=p.evaluate("window.__shared[0]")
    ok("share: opens the share sheet with the image file",sh["type"]=="image/png" and sh["name"].endswith(".png") and sh["size"]>50000 and p.evaluate("window.__saved.length")==n0)
    p.evaluate("window.__shareAbort=true"); act(p,"mcShare"); p.wait_for_timeout(600); ok("share: cancelling the sheet does nothing else",p.evaluate("window.__saved.length")==n0)
    p.evaluate("()=>{delete navigator.share;navigator.canShare=undefined}"); act(p,"mcShare"); p.wait_for_function(f"window.__saved.length==={n0+1}")
    ok("share: without a share sheet, it falls back to the save, which is the share sheet in the Claude iPhone app","Instagram" in p.inner_text(".toast"))
    p.evaluate("sessionStorage.setItem('noDl','1')"); p.reload(); p.wait_for_selector(".tabs"); nav(p,"story"); act(p,"expOpen",id=mem["id"]); act(p,"mcOpen"); p.wait_for_function("!!document.querySelector('#mc-prev canvas')",timeout=20000)
    p.evaluate("()=>{navigator.share=undefined;navigator.canShare=undefined}"); act(p,"mcShare"); p.wait_for_selector(".toast")
    ok("share: where nothing works, it says so instead of pretending","isn't available" in p.inner_text(".toast"))
    p.evaluate("()=>{window.ClipboardItem=window.ClipboardItem||function(o){this.o=o};navigator.clipboard.write=async items=>{window.__copied.push(items.length)}}"); p.reload(); p.wait_for_selector(".tabs"); nav(p,"story"); act(p,"expOpen",id=mem["id"]); act(p,"mcOpen"); p.wait_for_function("!!document.querySelector('#mc-prev canvas')",timeout=20000)
    p.evaluate("()=>{navigator.clipboard.write=async items=>{window.__copied.push(items.length)}}"); act(p,"mcCopy"); p.wait_for_selector("text=Image copied."); ok("copy: the image can be copied where allowed",p.evaluate("window.__copied")==[1])
    p.evaluate("()=>{navigator.clipboard.write=async()=>{throw new DOMException('no','NotAllowedError')}}"); act(p,"mcCopy"); p.wait_for_selector("text=Copying images isn't allowed here."); ok("copy: a refusal is explained",True); p.evaluate("sessionStorage.removeItem('noDl')")
    m2=[e for e in S(p)["exps"] if e["id"]==mem["id"]][0]; ok("cards: the memory itself is unchanged and still private",m2["updatedAt"]==up0 and m2["space"] is None and m2["notes"]=="PRIVNOTE")
    ctx.close()
    # ---------- Discover: For You, Nearby, Saved, Ask VOUZ (demo places, no connectors) ----------
    ctx,p=newctx(b); p.goto(URL); p.wait_for_timeout(300); onboard(p); nav(p,"discover")
    ok("discover: For You / Nearby / Saved, with Ideas, Plans, Match still there",[x.inner_text() for x in p.locator('.seg3 [data-act="discSeg"]').all()]==["For You","Nearby","Saved"] and p.locator('[data-act="discSeg"][data-v="match"]').count()==1)
    p.fill("#d-q","Find something romantic under $50"); act(p,"dAsk"); ok("discover: asks for an area before searching","Set an area first" in p.inner_text(".scroll"))
    p.fill("#d-area","Mission District"); act(p,"dLocSet"); act(p,"dAsk"); p.wait_for_selector(".rec")
    t=p.inner_text(".scroll"); ok("discover: with no connectors, places are clearly demo","Showing demo places" in t and all("demo place" in x.inner_text() for x in p.locator(".rec").all()))
    ok("discover: every card shows place, distance, cost and hours, with estimates labelled",all(all(k in x.inner_text() for k in ("Where","Distance","Cost","Hours")) for x in p.locator(".rec").all()) and p.locator(".rec .est").count()>=1 and "Not verified" in t)
    over=p.evaluate("window.__vouz.S&&[...document.querySelectorAll('.rec')].length")
    ok("discover: under $50 for two leaves out pricier places",p.evaluate("""()=>{const d=JSON.parse(JSON.stringify(window.__vouz.S.disc));return true}""") and "$90" not in t and "$180" not in t)
    p.fill("#d-q","What can we do within 2 miles?"); act(p,"dAsk"); p.wait_for_selector(".rec")
    ok("discover: 'within 2 miles' keeps everything within 2 miles",all(float(re.search(r"([\d.]+) mi",x.inner_text()).group(1))<=2.0 for x in p.locator(".rec").all()))
    vid=p.locator('.rec [data-act="dSave"]').first.get_attribute("data-id"); act(p,"dSave",id=vid)
    ok("saved: kept on the device",len(S(p)["disc"]["saved"])==1)
    did=p.locator('.rec [data-act="dSave"]').nth(1).get_attribute("data-id"); act(p,"dFb",id=did,v="-1")
    ok("feedback: 'not for us' removes it and learns",p.locator(f'[data-act="dSave"][data-id="{did}"]').count()==0 and any(v<0 for v in S(p)["disc"]["kinds"].values()))
    p.fill("#d-q","Plan our Saturday"); act(p,"dAsk"); p.wait_for_selector(".stops li")
    ok("ask vouz: a day plan with times, places and travel",p.locator(".stops li").count()>=3 and "Demo plan" in p.inner_text(".itin") and "estimate" in p.inner_text(".itin") and "Nothing is booked" in p.inner_text(".itin"))
    n0=p.locator(".stops li b").nth(1).inner_text(); act(p,"dSwap",i="1"); p.wait_for_timeout(300)
    ok("ask vouz: replace one stop, keep the rest",p.locator(".stops li b").nth(1).inner_text()!=n0)
    act(p,"dItinCal"); p.wait_for_selector(".toast"); ok("calendar: says so when saving files isn't available","isn't available" in p.inner_text(".toast"))
    act(p,"dItinSave"); pl=[e for e in S(p)["exps"] if e.get("stops")][0]
    ok("ask vouz: saved as a plan on Saturday, not booked",len(pl["stops"])>=3 and p.evaluate(f"new Date({pl['date']}).getDay()")==6 and "Not booked" in pl["notes"])
    p.fill("#d-q","Plan something"); act(p,"dAsk"); ok("ask vouz: asks only for the missing day","which day?" in p.inner_text(".scroll").lower()); act(p,"dNeed",k="day",v="today"); p.wait_for_selector(".stops li")
    p.evaluate(f"()=>{{const x=window.__vouz.S.exps.find(e=>e.id==='{pl['id']}');x.date=Date.now()-5*36e5}}"); nav(p,"home")
    ok("after the date: Home asks how it was","how was" in p.inner_text(".scroll").lower())
    act(p,"hwRate",id=pl["id"],v="4"); ok("rating is private, on the plan",[e for e in S(p)["exps"] if e["id"]==pl["id"]][0]["rating"]==4)
    act(p,"planDone",id=pl["id"]); act(p,"expSave"); p.wait_for_timeout(200); e2=[e for e in S(p)["exps"] if e["id"]==pl["id"]][0]
    ok("loop: done becomes a memory that keeps its places",e2["kind"]=="done" and e2.get("stops") and "the plan" in p.inner_text(".scroll").lower() and p.locator('[data-act="mcOpen"]').count()==1)
    nav(p,"discover"); act(p,"discSeg",v="saved"); ok("saved tab: places, plans and personalization controls","saved places" in p.inner_text(".scroll").lower() and "Reset personalization" in p.inner_text(".scroll"))
    act(p,"dReset"); act(p,"confirmYes"); act(p,"dWipeHist"); act(p,"confirmYes"); d=S(p)["disc"]
    ok("controls: reset personalization and delete history",d["fb"]=={} and d["kinds"]=={} and d["hist"]==[] and len(d["saved"])==1)
    act(p,"discSeg",v="nearby"); p.wait_for_selector(".rec"); act(p,"dNk",v="coffee"); p.wait_for_timeout(300)
    ok("nearby: filter by kind",p.locator(".rec").count()>=1 and all("coffee" in x.inner_text().lower() for x in p.locator(".rec").all()))
    p.screenshot(path=SH+"nearby.png"); ctx.close()
    # ---------- Discover with the Yelp connector (stand-in with Yelp's real input schema) ----------
    ctx,e=newctx(b,"erin"); e.goto(URL); e.wait_for_timeout(400); onboard(e,account=True); nav(e,"discover"); e.wait_for_timeout(300)
    e.fill("#d-area","Mission District"); act(e,"dLocSet"); e.fill("#d-q","Find something romantic under $50"); act(e,"dAsk"); e.wait_for_selector(".rec")
    calls=e.evaluate("window.__yelpCalls")
    ok("yelp: input matches Yelp's schema (coordinates from Mapbox, short query, limit 3-8, nothing else)",calls and all((c.get("location") or c.get("latitude")) and 3<=c.get("limit",0)<=8 and set(c)<= {"location","query","limit","is_open_now","latitude","longitude"} and len(c.get("query",""))<=60 for c in calls),str(calls[:2]))
    mc=e.evaluate("window.__mcpCalls")
    ok("mapbox: area geocoded once, then category searches near it",any(c[1]=="geocode" and c[2]["q"]=="Mission District" for c in mc) and any(c[1]=="category" and c[2]["proximity"]["latitude"]==37.757 and c[2]["format"]=="json_string" for c in mc))
    ok("accuweather: location key looked up, then current conditions",any(c[1]=="search" for c in mc) and any(c[1]=="current" and c[2]["queryParams"]["locationKey"]=="123" for c in mc))
    t=e.inner_text(".scroll")
    ok("live: results from several sources, labelled, nothing demo","Live from" in t and "demo" not in t.lower() and "TEST" in t and "MB " in t)
    ok("weather and alerts shown from AccuWeather","52°F" in t and "Coastal Flood Advisory in effect" in t)
    ok("yelp: permanently closed places are dropped","TEST CLOSED" not in t)
    ok("yelp-only places: distance and hours not claimed","Not provided; searched near" in t and "Not verified" in t)
    ok("yelp: address cleaned, photo shown with credit",", Testville" in t and e.locator(".recph img").count()>=1 and "Photo: Yelp" in t)
    e.screenshot(path=SH+"foryou-yelp.png")
    act(e,"discSeg",v="nearby"); e.wait_for_timeout(200); act(e,"dNk",v="coffee"); e.wait_for_timeout(500)
    ok("yelp: nearby asks Yelp for that kind",e.evaluate("window.__yelpCalls.slice(-1)[0].query")=="coffee")
    t=e.inner_text(".scroll"); card=[x.inner_text() for x in e.locator(".rec").all() if "TEST COFFEE 0" in x.inner_text()]
    ok("merge: the same café from Mapbox and Yelp is one card with both sources' facts",len(card)==1 and "Mapbox + Yelp" in card[0] and "★" in card[0] and "Yelp\nWebsite" in card[0] and "Open now" in card[0] and "per Mapbox" in card[0] and " mi" in card[0],str(card[:1]))
    ok("mapbox hours: a closed place says so",any("Closed now" in x.inner_text() for x in e.locator(".rec").all() if "MAPBOX ONLY CAFE" in x.inner_text()))
    act(e,"dNk",v="trail"); e.wait_for_timeout(500); t=e.inner_text(".scroll")
    ok("alltrails: trails with length, time, gain and distance to the trailhead","TEST RIDGE LOOP" in t and "1.9 mi" in t and "314 ft gain" in t and "to the trailhead" in t)
    act(e,"discSeg",v="foryou"); e.fill("#d-q","Plan our Saturday"); act(e,"dAsk"); e.wait_for_selector(".stops li")
    ok("day plan: Mapbox walking/driving times between stops",any(c[1]=="directions" for c in e.evaluate("window.__mcpCalls")) and "via Mapbox" in e.inner_text(".itin"))
    act(e,"discSeg",v="nearby"); e.evaluate("window.__yelpFail='approval_required'"); act(e,"dNk",v="food"); e.wait_for_timeout(500); t=e.inner_text(".scroll")
    ok("yelp: when Yelp fails, says why and shows labelled demo places","Couldn't get places from" in t and "needs your approval" in t and "demo place" in t)
    e.evaluate("window.__yelpFail=null"); act(e,"dRetry"); e.wait_for_timeout(500); ok("yelp: try again recovers","Couldn't get places" not in e.inner_text(".scroll") and "TEST" in e.inner_text(".scroll"))
    ctx.close()
    # screenshots with motion on
    ctx,p=newctx(b,motion="no-preference"); p.goto(URL); p.wait_for_timeout(700); p.screenshot(path=SH+"ob.png"); onboard(p); act(p,"loadDemo"); p.wait_for_timeout(600); p.screenshot(path=SH+"home.png"); nav(p,"history"); p.wait_for_timeout(1200)
    ok("count-up settles on the true value",p.locator(".trio b").first.inner_text()=="12")
    nav(p,"story"); p.screenshot(path=SH+"story.png"); nav(p,"ideas"); p.screenshot(path=SH+"ideas.png")
    sid=S(p)["sessions"][0]["id"]; nav(p,"history"); act(p,"openReplay",id=sid); p.wait_for_timeout(1500); p.screenshot(path=SH+"replay.png"); p.locator(".scroll").evaluate("e=>e.scrollTop=560"); p.wait_for_timeout(200); p.screenshot(path=SH+"replay2.png")
    nav(p,"analytics"); act(p,"insRange",v="year"); act(p,"insTab",v="patterns"); p.wait_for_timeout(3400); p.screenshot(path=SH+"patterns.png"); act(p,"insTab",v="mood"); p.screenshot(path=SH+"mood.png")
    ok("no page overflow sideways",p.evaluate("document.documentElement.scrollWidth<=window.innerWidth"))
    ctx.close(); b.close()
    ok("no uncaught page errors",not errs,str(errs[:5]))
srv.terminate()
f=[r for r in res if not r[1]]
print(f"\n{len(res)-len(f)}/{len(res)} passed"); sys.exit(1 if f else 0)
