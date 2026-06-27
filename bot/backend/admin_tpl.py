from backend import cabinet_ui as ui

SDK = '<script src="https://telegram.org/js/telegram-web-app.js"></script>'

EXTRA = '''<style>
 .sum{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:0 0 14px}
 .scell{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:12px 8px;text-align:center}
 .scell .v{font-size:20px;font-weight:600;font-variant-numeric:tabular-nums}
 .scell .k{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin-top:3px}
 .arow{padding:14px 16px}
 .atop{display:flex;align-items:center;justify-content:space-between;gap:8px}
 .aname{font-size:15px;font-weight:600}
 .badge{font-size:10.5px;font-weight:500;padding:3px 9px;border-radius:99px;border:1px solid var(--line);color:var(--muted)}
 .badge.active{color:var(--green);border-color:rgba(52,211,153,.3);background:rgba(52,211,153,.08)}
 .badge.expired,.badge.disabled{color:var(--red);border-color:rgba(243,117,107,.3);background:rgba(243,117,107,.08)}
 .ameta{font-size:12px;color:var(--muted);margin-top:6px;font-variant-numeric:tabular-nums;line-height:1.5}
 .aacts{display:flex;gap:7px;margin-top:11px;flex-wrap:wrap}
 .ab{flex:1;min-width:84px;border:1px solid var(--line2);background:transparent;color:var(--text);border-radius:10px;
   padding:9px 6px;font-size:12.5px;font-weight:500;font-family:inherit;cursor:pointer}
 .ab:active{transform:scale(.96)}
 .ab.warn{color:var(--red);border-color:rgba(243,117,107,.35)}
 .ab.ok{color:var(--green);border-color:rgba(52,211,153,.35)}
</style>'''

TPL = '''<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>__TITLE__ admin</title>__SDK____FONT____STYLE____EXTRA__</head><body>
<div class="wrap">
<div class="hd"><div class="brand">__MARK__<span>Админка</span></div><div class="pill" id="pill">—</div></div>
<div class="center" id="loading">Загрузка...</div>
<div class="center" id="err" style="display:none"></div>
<div id="content" style="display:none">
  <div class="sum">
    <div class="scell"><div class="v" id="s_active">0</div><div class="k">активных</div></div>
    <div class="scell"><div class="v" id="s_total">0</div><div class="k">всего</div></div>
    <div class="scell"><div class="v" id="s_online">0</div><div class="k">онлайн</div></div>
    <div class="scell"><div class="v" id="s_gb">0</div><div class="k">ГБ всего</div></div>
  </div>
  <div id="users"></div>
</div>
<p class="foot">Только админ. Действия применяются сразу на обе локации.</p>
</div>
<div class="toast" id="toast">Готово</div>
<script>
 var tg=window.Telegram?window.Telegram.WebApp:null;
 function $(id){return document.getElementById(id);}
 function esc(s){return (""+s).replace(/[&<>"]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;"}[c];});}
 function initData(){return tg?tg.initData:"";}
 function post(path,extra){
   var b=Object.assign({initData:initData()}, extra||{});
   return fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(b)})
     .then(function(r){if(r.status===403)throw "forbidden";if(!r.ok)throw "err";return r.json();});
 }
 function toast(t){var e=$("toast");e.textContent=t;e.classList.add("on");setTimeout(function(){e.classList.remove("on");},1300);}
 function showErr(e){$("loading").style.display="none";$("content").style.display="none";var x=$("err");x.style.display="block";
   x.textContent=(e==="forbidden")?"Доступ только для администратора.":"Не удалось загрузить.";}
 function load(){post("/admin/state").then(render).catch(showErr);}
 function act(token,type,name){
   var msg={extend:"Продлить +30 дней?",disable:"Отключить "+name+"?",enable:"Включить "+name+"?",delete:"УДАЛИТЬ "+name+" полностью?"}[type];
   if(!confirm(msg))return;
   post("/admin/action",{action:type,token:token}).then(function(s){toast("Готово");render(s);}).catch(function(e){toast(e==="forbidden"?"Нет прав":"Ошибка");});
 }
 function render(s){
   $("loading").style.display="none";$("err").style.display="none";$("content").style.display="block";
   $("pill").textContent="админ";$("pill").className="pill ok";
   $("s_active").textContent=s.active;$("s_total").textContent=s.count;
   $("s_online").textContent=s.online_total;$("s_gb").textContent=s.total_gb;
   var box=$("users");box.innerHTML="";
   if(!s.users.length){box.innerHTML='<p class="empty">Подписок нет.</p>';return;}
   s.users.forEach(function(u){
     var c=document.createElement("div");c.className="card arow";
     var nm="@"+esc(u.username)+" <span class=\\"muted\\" style=\\"font-size:11px\\">id "+esc(u.tg_id)+"</span>";
     var meta=u.used_gb+" / "+esc(u.limit_label)+" ГБ · устройств "+u.devices+"/"+u.device_limit+" · онлайн "+u.online+" · "+u.days_left+" дн · торрент "+(u.torrent_block?"режется":"ок");
     c.innerHTML='<div class="atop"><div class="aname">'+nm+'</div><span class="badge '+esc(u.status)+'">'+esc(u.status)+'</span></div><div class="ameta">'+meta+'</div>';
     var acts=document.createElement("div");acts.className="aacts";
     var label=esc("@"+u.username);
     var b1=mkbtn("+30 дней","ab",function(){act(u.token,"extend",label);});
     var toggle=(u.status==="active")?mkbtn("Отключить","ab warn",function(){act(u.token,"disable",label);})
                                      :mkbtn("Включить","ab ok",function(){act(u.token,"enable",label);});
     var del=mkbtn("Удалить","ab warn",function(){act(u.token,"delete",label);});
     acts.appendChild(b1);acts.appendChild(toggle);acts.appendChild(del);c.appendChild(acts);box.appendChild(c);
   });
 }
 function mkbtn(text,cls,fn){var b=document.createElement("button");b.className=cls;b.textContent=text;b.onclick=fn;return b;}
 if(tg){tg.ready();tg.expand();try{tg.setHeaderColor("#0a0a0b");tg.setBackgroundColor("#0a0a0b");}catch(e){}}
 load();
</script></body></html>'''


def render(title):
    return (TPL.replace("__SDK__", SDK).replace("__FONT__", ui.FONT)
            .replace("__STYLE__", ui.STYLE).replace("__EXTRA__", EXTRA)
            .replace("__MARK__", ui.MARK).replace("__TITLE__", title))
