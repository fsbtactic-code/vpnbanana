from backend import cabinet_ui as ui

SDK = '<script src="https://telegram.org/js/telegram-web-app.js"></script>'

TPL = '''<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>__TITLE__</title>__SDK____FONT____STYLE__</head><body>
<div class="wrap">
__HEADER__
<div class="center" id="loading">Загрузка...</div>
<div class="center" id="err" style="display:none"></div>
<div class="center" id="nosub" style="display:none">У тебя пока нет активной подписки.<br>Напиши __SUPPORT__.</div>
<div id="content" style="display:none">
<div class="banner" id="banner"></div>
__CARDS__
</div>
__FOOT__
</div>
<div class="toast" id="toast">Скопировано</div>
<script>
__RENDERJS__
 var tg=window.Telegram?window.Telegram.WebApp:null, CONNECT="";
 function initData(){return tg?tg.initData:"";}
 function post(path,extra){
   var b=Object.assign({initData:initData()}, extra||{});
   return fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(b)})
     .then(function(r){if(r.status===403)throw "forbidden";return r.json();});
 }
 function onState(s){
   $("loading").style.display="none";$("err").style.display="none";
   if(s.no_sub){$("content").style.display="none";$("nosub").style.display="block";return false;}
   $("nosub").style.display="none";$("content").style.display="block";
   CONNECT=s.landing_url||"";if($("c_sub"))$("c_sub").textContent=s.sub_url||"";
   return true;
 }
 function showErr(e){$("loading").style.display="none";$("content").style.display="none";$("nosub").style.display="none";
   var er=$("err");er.style.display="block";er.textContent=(e==="forbidden")?"Открой кабинет через бота (внутри Telegram).":"Не удалось загрузить, попробуй позже.";}
 function load(){post("/app/state").then(render).catch(showErr);}
 function connect(){if(CONNECT){if(tg&&tg.openLink)tg.openLink(CONNECT);else window.open(CONNECT,"_blank");}}
 function delDev(hwid){if(!confirm("Удалить это устройство? Слот освободится."))return;post("/app/device/delete",{hwid:hwid}).then(render).catch(showErr);}
 if(tg){tg.ready();tg.expand();try{tg.setHeaderColor("#0a0a0b");tg.setBackgroundColor("#0a0a0b");}catch(e){}}
 bindCopy();load();setInterval(load,30000);
</script></body></html>'''


def render(title):
    connect_inner = '<button class="btn primary" onclick="connect()">Подключить в Happ</button>'
    return (TPL.replace("__SDK__", SDK).replace("__FONT__", ui.FONT).replace("__STYLE__", ui.STYLE)
            .replace("__HEADER__", ui.header_html(title)).replace("__CARDS__", ui.cards_html(connect_inner))
            .replace("__RENDERJS__", ui.render_js())
            .replace("__FOOT__", ui.foot_html()).replace("__SUPPORT__", ui.SUPPORT)
            .replace("__TITLE__", title).replace("__SUBURL__", ""))
