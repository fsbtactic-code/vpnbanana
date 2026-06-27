import json

from backend import cabinet_ui as ui

TPL = '''<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>__TITLE__</title>__FONT____STYLE__</head><body>
<div class="wrap">
__HEADER__
<div class="banner" id="banner"></div>
__CARDS__
__FOOT__
</div>
<div class="toast" id="toast">Скопировано</div>
<script>
__RENDERJS__
 var TOKEN="__TOKEN__", S=__STATE__, onState=null;
 function delDev(hwid){
   if(!confirm("Удалить это устройство? Слот освободится, устройство переподключать заново."))return;
   fetch("/u/"+TOKEN+"/device/delete",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({hwid:hwid})})
     .then(function(r){return r.json();}).then(render).catch(function(){});
 }
 function refresh(){fetch("/u/"+TOKEN+"/state").then(function(r){return r.json();}).then(render).catch(function(){});}
 render(S);bindCopy();setInterval(refresh,30000);
</script></body></html>'''


def render(title, token, oneclick, routing, suburl, state):
    if oneclick:
        b1 = f'<a class="btn primary" href="{oneclick}">Подключить в один клик</a>'
    else:
        b1 = '<p class="empty">Кнопка соберётся при обновлении страницы. Пока добавь по ссылке-подписке ниже.</p>'
    b2 = f'<a class="btn ghost" href="{routing}">Обход RU-сайтов</a>' if routing else ""

    sj = (json.dumps(state, ensure_ascii=False)
          .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))
    return (TPL.replace("__FONT__", ui.FONT).replace("__STYLE__", ui.STYLE)
            .replace("__HEADER__", ui.header_html(title)).replace("__CARDS__", ui.cards_html(b1 + b2))
            .replace("__RENDERJS__", ui.render_js())
            .replace("__FOOT__", ui.foot_html())
            .replace("__TITLE__", title).replace("__TOKEN__", token)
            .replace("__SUBURL__", suburl).replace("__STATE__", sj))
