from app import config as C

SUPPORT = C.SUPPORT_URL or "администратору"


def foot_html():
    return f'<p class="foot">Поддержка: {SUPPORT}</p>' if C.SUPPORT_URL else ''


FONT = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">')

MARK = ('<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">'
        '<path d="M20.5 13.8A8.5 8.5 0 1 1 10.2 3.5 6.7 6.7 0 0 0 20.5 13.8Z" fill="#F5C451"/></svg>')


def _ic(p):
    return ('<svg class="ic" viewBox="0 0 24 24" width="15" height="15" fill="none" '
            'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" '
            'aria-hidden="true">' + p + '</svg>')


IC = {
    "traffic": _ic('<path d="M3 12h4l2.5-7 5 14 2.5-7H21"/>'),
    "online": _ic('<path d="M12 12.5v.01"/><path d="M8.8 9.3a4.5 4.5 0 0 0 0 6.4"/><path d="M15.2 9.3a4.5 4.5 0 0 1 0 6.4"/><path d="M6.3 6.8a8 8 0 0 0 0 11.4"/><path d="M17.7 6.8a8 8 0 0 1 0 11.4"/>'),
    "devices": _ic('<rect x="3" y="5" width="13" height="9.5" rx="1.6"/><path d="M7.5 18.5h7"/><rect x="17.5" y="9" width="4" height="9.5" rx="1.2"/>'),
    "connect": _ic('<path d="M10 14l4-4"/><path d="M11.5 6.8l1-1a3.6 3.6 0 0 1 5.1 5.1l-1 1"/><path d="M12.5 17.2l-1 1a3.6 3.6 0 0 1-5.1-5.1l1-1"/>'),
    "copy": _ic('<rect x="9" y="9" width="11" height="11" rx="2.2"/><path d="M5 15V6.5A2.5 2.5 0 0 1 7.5 4H16"/>'),
    "trash": _ic('<path d="M4.5 7h15"/><path d="M9 7V5.2A1.2 1.2 0 0 1 10.2 4h3.6A1.2 1.2 0 0 1 15 5.2V7"/><path d="M6.5 7l.8 12a2 2 0 0 0 2 1.9h5.4a2 2 0 0 0 2-1.9L17.5 7"/>'),
    "download": _ic('<path d="M12 4v10"/><path d="M8 10.5l4 3.5 4-3.5"/><path d="M5 19.5h14"/>'),
}


_GH = "https://github.com/Happ-proxy/happ-desktop/releases/latest/download"
HAPP_LINKS = [
    ("iOS", "https://apps.apple.com/ru/app/happ-proxy-utility-plus/id6746188973"),
    ("Android", "https://play.google.com/store/apps/details?id=com.happproxy"),
    ("Windows", _GH + "/setup-Happ.x64.exe"),
    ("macOS", _GH + "/Happ.macOS.universal.dmg"),
    ("Linux", _GH + "/Happ.linux.x64.deb"),
]

STYLE = '''<style>
 *{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
 :root{
   --bg:#0a0a0b;--surface:rgba(255,255,255,.032);--surface2:rgba(255,255,255,.055);
   --line:rgba(255,255,255,.08);--line2:rgba(255,255,255,.14);
   --text:#f1f1f3;--muted:#8c8c94;--faint:#5b5b63;
   --gold:#f5c451;--gold-soft:rgba(245,196,81,.12);--green:#34d399;--red:#f3756b;
 }
 html,body{margin:0}
 body{font-family:"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
   color:var(--text);background:var(--bg);min-height:100vh;
   display:flex;justify-content:center;padding:26px 16px 36px;letter-spacing:-.01em;
   -webkit-font-smoothing:antialiased}
 body::before{content:"";position:fixed;inset:0;z-index:0;pointer-events:none;
   background:radial-gradient(60% 38% at 50% -8%,rgba(245,196,81,.07),transparent 70%)}
 .wrap{position:relative;z-index:1;width:100%;max-width:430px;
   opacity:0;transform:translateY(8px);animation:in .5s cubic-bezier(.2,.7,.2,1) .04s forwards}
 @keyframes in{to{opacity:1;transform:none}}
 .hd{display:flex;align-items:center;justify-content:space-between;margin:2px 2px 20px}
 .brand{display:flex;align-items:center;gap:9px;font-size:16px;font-weight:600}
 .pill{font-size:11px;font-weight:500;padding:5px 11px;border-radius:99px;border:1px solid var(--line);
   color:var(--muted);background:var(--surface)}
 .pill.ok{color:var(--green);border-color:rgba(52,211,153,.3);background:rgba(52,211,153,.08)}
 .pill.bad{color:var(--red);border-color:rgba(243,117,107,.32);background:rgba(243,117,107,.08)}
 .card{background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:18px 18px 19px;margin:11px 0}
 .lbl{display:flex;align-items:center;gap:7px;font-size:11px;letter-spacing:.04em;text-transform:uppercase;
   color:var(--muted);font-weight:600;margin-bottom:15px}
 .lbl .ic{color:var(--faint)}
 .metric{display:flex;align-items:baseline;gap:8px;margin-bottom:14px}
 .num{font-size:32px;font-weight:600;line-height:1;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
 .unit{font-size:14px;color:var(--muted);font-weight:500}
 .aside{margin-left:auto;font-size:12px;color:var(--muted);font-weight:500;font-variant-numeric:tabular-nums}
 .track{height:6px;background:rgba(255,255,255,.07);border-radius:99px;overflow:hidden}
 .fill{height:100%;width:0;border-radius:99px;background:var(--gold);
   transition:width .7s cubic-bezier(.2,.7,.2,1)}
 .fill.warn{background:var(--red)}
 .fill.inf{background:linear-gradient(90deg,rgba(245,196,81,.5),var(--gold),rgba(245,196,81,.5));
   background-size:200% 100%;animation:shimmer 3.5s linear infinite}
 @keyframes shimmer{to{background-position:-200% 0}}
 .hint{font-size:12px;color:var(--muted);margin-top:11px}
 .hint b{color:var(--text);font-weight:600}
 .row2{display:flex;padding:0}
 .cell{flex:1;padding:18px 18px 19px}
 .cell+.cell{border-left:1px solid var(--line)}
 .cnum{display:flex;align-items:center;gap:9px;font-size:26px;font-weight:600;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
 .cnum .slash{color:var(--faint);font-weight:500}
 .dot{width:8px;height:8px;border-radius:50%;background:var(--faint);flex:none}
 .dot.on{background:var(--green);animation:breathe 2.4s ease-in-out infinite}
 @keyframes breathe{0%,100%{opacity:1}50%{opacity:.45}}
 .btn{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;border:0;cursor:pointer;
   font-family:inherit;font-weight:600;font-size:15px;padding:14px;border-radius:13px;margin:0 0 9px;
   transition:transform .14s ease,background .14s ease;letter-spacing:-.01em}
 .btn:active{transform:scale(.985)}
 .btn.primary{background:var(--gold);color:#1a1505}
 .btn.primary:hover{background:#f7cd62}
 .btn.ghost{background:transparent;color:var(--text);border:1px solid var(--line2)}
 .btn.ghost:hover{background:var(--surface2)}
 .suprow{display:flex;gap:8px;align-items:center;margin-top:5px}
 .suprow code{flex:1;font-size:11.5px;color:var(--muted);background:rgba(255,255,255,.04);
   border:1px solid var(--line);border-radius:10px;padding:10px 11px;overflow:hidden;
   text-overflow:ellipsis;white-space:nowrap;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
 .copy{flex:none;display:flex;align-items:center;justify-content:center;width:40px;height:40px;
   border:1px solid var(--line2);background:transparent;color:var(--muted);border-radius:10px;cursor:pointer}
 .copy:active{transform:scale(.94)}
 .apps{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:4px}
 .app{display:flex;align-items:center;justify-content:center;text-decoration:none;font-size:13px;font-weight:500;
   padding:11px 8px;border-radius:11px;background:var(--surface2);border:1px solid var(--line);color:var(--text)}
 .app:active{transform:scale(.96)}
 .ol{display:none;font-size:12.5px;color:#f0c98a;background:rgba(245,196,81,.07);
   border:1px solid rgba(245,196,81,.22);border-radius:12px;padding:11px 13px;margin-bottom:13px;line-height:1.5}
 .dev{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:13px 0;border-top:1px solid var(--line)}
 .dev:first-of-type{border-top:0;padding-top:2px}
 .dn{font-size:14px;font-weight:500;letter-spacing:-.01em}
 .dm{font-size:11.5px;color:var(--faint);margin-top:3px;font-variant-numeric:tabular-nums}
 .del{flex:none;display:flex;align-items:center;gap:6px;background:transparent;color:var(--muted);
   border:1px solid var(--line);border-radius:10px;padding:8px 12px;font-size:12.5px;font-weight:500;
   font-family:inherit;cursor:pointer;transition:.14s}
 .del:hover{color:var(--red);border-color:rgba(243,117,107,.4)}
 .del:active{transform:scale(.95)}
 .empty{font-size:12.5px;color:var(--faint);padding:4px 0 2px;line-height:1.5}
 .banner{display:none;font-size:13px;font-weight:500;text-align:center;border-radius:13px;padding:12px 14px;margin:0 0 13px;
   color:var(--red);background:rgba(243,117,107,.08);border:1px solid rgba(243,117,107,.28)}
 .center{text-align:center;padding:54px 18px;color:var(--muted);font-size:14px;line-height:1.65}
 .center a,.foot a{color:var(--gold);text-decoration:none}
 .foot{font-size:11.5px;color:var(--faint);text-align:center;margin:20px 4px 0;line-height:1.6}
 .toast{position:fixed;left:50%;bottom:26px;transform:translateX(-50%) translateY(16px);background:var(--text);color:#0a0a0b;
   font-weight:600;font-size:13px;padding:10px 18px;border-radius:11px;opacity:0;transition:.25s;z-index:20}
 .toast.on{opacity:1;transform:translateX(-50%)}
</style>'''


def header_html(title):
    return (f'<div class="hd"><div class="brand">{MARK}<span>{title}</span></div>'
            f'<div class="pill" id="statusPill">—</div></div>')


def cards_html(connect_inner):
    apps = "".join('<a class="app" href="%s" target="_blank" rel="noopener">%s</a>' % (u, n) for n, u in HAPP_LINKS)
    return f'''
  <div class="card">
    <div class="lbl">{IC["traffic"]} Трафик</div>
    <div class="metric"><span class="num" id="tUsed">0</span><span class="unit">/ <span id="tLimit">—</span></span><span class="aside" id="tPct"></span></div>
    <div class="track"><div class="fill" id="bar"></div></div>
    <div class="hint">Осталось <b id="days">—</b> дн.</div>
  </div>
  <div class="card row2">
    <div class="cell"><div class="lbl">{IC["online"]} Онлайн</div><div class="cnum"><span class="dot" id="dot"></span><span id="online">0</span></div></div>
    <div class="cell"><div class="lbl">{IC["devices"]} Устройства</div><div class="cnum"><span id="devN">0</span><span class="slash">/<span id="devLim">0</span></span></div></div>
  </div>
  <div class="card">
    <div class="lbl">{IC["connect"]} Подключение</div>
    {connect_inner}
    <div class="suprow"><code id="c_sub">__SUBURL__</code><button class="copy" data-c="c_sub" aria-label="Копировать">{IC["copy"]}</button></div>
  </div>
  <div class="card">
    <div class="lbl">{IC["download"]} Установить Happ</div>
    <div class="apps">{apps}</div>
    <p class="muted">iOS - «Happ Proxy Utility Plus» из App Store РФ (без смены региона). Windows/macOS/Linux - прямая загрузка (x64 .exe / .dmg / .deb). Другие сборки (arm64, rpm) - <a href="https://github.com/Happ-proxy/happ-desktop/releases" target="_blank" rel="noopener">на GitHub</a>.</p>
  </div>
  <div class="card">
    <div class="lbl">{IC["devices"]} Мои устройства</div>
    <div class="ol" id="ol">Лимит устройств исчерпан. Удали неиспользуемое, чтобы подключить новое.</div>
    <div id="devs"></div>
  </div>'''


RENDER_JS = '''
 var TRASH='__TRASH__';
 function $(id){return document.getElementById(id);}
 function esc(s){return (""+s).replace(/[&<>"]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;"}[c];});}
 function render(s){
   if(typeof onState==="function" && onState(s)===false) return;
   var p=$("statusPill");
   if(s.status==="active"){p.textContent="активна";p.className="pill ok";}
   else{p.textContent=(s.status==="expired")?"приостановлена":"отключена";p.className="pill bad";}
   var ban=$("banner");
   if(ban){if(s.status!=="active"){ban.style.display="block";ban.textContent="Подписка "+(s.status==="expired"?"приостановлена (лимит или срок)":"отключена")+". Напиши __SUPPORT__.";}else ban.style.display="none";}
   $("tUsed").textContent=s.used_gb;$("tLimit").textContent=s.limit_label;
   var bar=$("bar");bar.className="fill";
   if(s.unlimited){bar.style.width="100%";bar.classList.add("inf");$("tPct").textContent="∞";}
   else{bar.style.width=Math.min(100,s.pct)+"%";$("tPct").textContent=s.pct+"%";if(s.pct>=85)bar.classList.add("warn");}
   $("days").textContent=s.days_left;$("online").textContent=s.online;
   $("dot").className="dot"+(s.online>0?" on":"");
   $("devN").textContent=s.device_count;$("devLim").textContent=s.device_limit;
   $("ol").style.display=(s.device_count>=s.device_limit)?"block":"none";
   var list=$("devs");list.innerHTML="";
   if(!s.devices.length){list.innerHTML='<p class="empty">Пока нет подключенных устройств.</p>';}
   s.devices.forEach(function(d){
     var name=[d.os,d.model].filter(Boolean).join(" ")||d.short;
     var row=document.createElement("div");row.className="dev";
     row.innerHTML='<div><div class="dn">'+esc(name)+'</div><div class="dm">'+esc(d.last_seen_h)+' · '+esc(d.short)+'</div></div>';
     var b=document.createElement("button");b.className="del";b.innerHTML=TRASH+'<span>Удалить</span>';
     b.onclick=function(){delDev(d.hwid);};row.appendChild(b);list.appendChild(row);
   });
 }
 function bindCopy(){document.querySelectorAll("button[data-c]").forEach(function(b){b.addEventListener("click",function(){
   navigator.clipboard.writeText($(b.getAttribute("data-c")).textContent);
   var t=$("toast");t.classList.add("on");setTimeout(function(){t.classList.remove("on");},1200);});});}
'''


def render_js():
    return RENDER_JS.replace("__TRASH__", IC["trash"].replace("'", "\\'")).replace("__SUPPORT__", SUPPORT)
