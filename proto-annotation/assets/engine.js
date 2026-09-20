
(function(){
  "use strict";
  /* v4：本地优先 —— 去掉 github.io/?anno=1 门禁，本地 file:// 直接可批注/同步。
     角标改为独立浮层 #__anno_layer（z-index 低于弹窗遮罩），不再 appendChild 进宿主，
     一次性消灭「select/input 宿主 0 尺寸不可见」「弹窗穿透」「飘到左上角」这一整类问题。 */
  var canAnnotate = true;
  var fileKey = location.pathname.split('/').pop() || 'proto';
  var LS_KEY = '__anno__' + fileKey;
  var seed = [];
  try { seed = JSON.parse((document.getElementById('__anno_seed')||{}).textContent || '[]'); } catch(e){ seed = []; }
  var _cached;
  try { _cached = JSON.parse(localStorage.getItem(LS_KEY) || 'null'); } catch(e){ _cached = null; }
  /* 文件 seed 优先：仅当缓存是数组且与文件 seed 的 id+sel+text 完全一致（合法编辑）时才用缓存；
     否则用文件 seed 并重写缓存 —— 避免旧缓存覆盖修复后的 seed 导致「打开即失联 / 旧文案不刷新」。
     text 必须参与比对：seed 文案更新后，同 id+sel 的旧缓存不应继续生效。 */
  var _sameData = Array.isArray(_cached) && _cached.length === seed.length &&
    seed.every(function(s){ return _cached.some(function(c){ return c.id === s.id && c.sel === s.sel && c.text === s.text; }); });
  var data = (_cached && _sameData) ? _cached.slice() : seed.slice();
  if (!_sameData) { try { localStorage.setItem(LS_KEY, JSON.stringify(data)); } catch(e){} }
  data.forEach(function(a,i){ if (typeof a.no !== 'number') a.no = i+1; if (typeof a.view !== 'string') a.view = 'global'; });
  var mode = false, hidden = false, openId = null, hoverEl = null, relocating = null;
  function nextNo(){ var m=0; data.forEach(function(a){ if(a.no>m)m=a.no; }); return m+1; }
  function uid(){ return 'a' + Date.now().toString(36) + Math.random().toString(36).slice(2,6); }
  function save(){ try { localStorage.setItem(LS_KEY, JSON.stringify(data)); } catch(e){} }
  function toast(msg){ var t=document.createElement('div'); t.textContent=msg; t.style.cssText='position:fixed;left:50%;bottom:72px;transform:translateX(-50%);background:#1f1f2e;color:#fff;padding:9px 16px;border-radius:20px;font-size:12px;z-index:99999;box-shadow:0 4px 16px rgba(0,0,0,.3);font-family:inherit;max-width:80%;text-align:center'; document.body.appendChild(t); setTimeout(function(){ t.style.transition='opacity .3s'; t.style.opacity='0'; },2200); setTimeout(function(){ if(t.parentNode) t.parentNode.removeChild(t); },2600); }
  function download(name, text, mime){ var blob=new Blob([text],{type:mime||'application/json'}); var url=URL.createObjectURL(blob); var a=document.createElement('a'); a.href=url; a.download=name; a.click(); setTimeout(function(){URL.revokeObjectURL(url);},1000); }

  /* 定位：修正同标签序号 bug + 视图隔离 */
  function cssPath(el){
    if (!el || el === document.body) return 'body';
    var parts = []; var cur = el; var anchored = false;
    while (cur && cur !== document.body){
      var tag = cur.tagName.toLowerCase();
      if (cur.id){ parts.unshift(tag + '#' + cur.id); anchored = true; break; }
      var cls = '';
      if (cur.className && typeof cur.className === 'string'){
        var cs = cur.className.trim().split(/\s+/).filter(function(c){ return c && c.indexOf('__anno')!==0; });
        if (cs.length) cls = '.' + cs.join('.');
      }
      var parent = cur.parentNode;
      if (parent){
        var sameTag = Array.prototype.filter.call(parent.children, function(ch){ return ch.tagName === cur.tagName; });
        var idx = sameTag.indexOf(cur) + 1;
        var suffix = (cls && sameTag.length > 1) ? cls + ':nth-of-type(' + idx + ')' : (cls || ':nth-of-type(' + idx + ')');
        parts.unshift(tag + suffix);
      } else { parts.unshift(tag + cls); }
      cur = parent;
    }
    /* 停在 id 锚点时不能再拼 body 前缀：真实页面里 .view 嵌在 main>div.workspace 下，锚点不是 body 直接子级 */
    return (anchored ? '' : 'body > ') + parts.join(' > ');
  }
  function currentView(){ var act = document.querySelector('.view.active, .page.active'); return act ? (act.id || 'global') : 'global'; }
  function rootOf(view){ if (!view || view === 'global') return document; var n = document.getElementById(view); return n || document; }
  function isVisible(el){ if(!el) return false; var p=el; while(p){ if(p.style&&p.style.display==='none')return false; if(getComputedStyle(p).display==='none')return false; p=p.parentElement; } return true; }
  /* 弹窗感知：判定元素所属弹窗容器、弹窗是否打开（用于「关闭的弹窗内字段不显示角标、打开时仅显示该弹窗内字段角标」） */
  var MODAL_SEL = '.cf-mask,.cf-modal,.wct-mask,.wct-modal,.mask,.modal,.dialog,.overlay,.popup';
  function modalOf(el){ if(!el || !el.closest) return null; try { var m = el.closest(MODAL_SEL); if(!m) return null; /* 归并到最外层弹窗根容器：穿透内容框(.wct-modal/.cf-modal)到遮罩层(.wct-mask/.cf-mask)，否则 modalOf 返回内容框而 topOpenModal 取遮罩层，两者不同对象 → 误判 hidden-modal（本次实战 bug） */ while (m.parentNode && m.parentNode.closest && m.parentNode.closest(MODAL_SEL)) m = m.parentNode.closest(MODAL_SEL); return m; } catch(e){ return null; } }
  function isModalOpen(m){ if(!m) return false; if(getComputedStyle(m).display==='none') return false; var r=m.getBoundingClientRect(); return (r.width>0 && r.height>0); }
  function textOf(el){ var t=''; try{ t=(el.innerText||el.textContent||'').replace(/\s+/g,' ').trim().slice(0,40); }catch(e){} return t; }
  /* 定位时优先返回「可见」的那个；全不可见才返回 null（交给失联/重定位处理），避免命中隐藏重复节点被误判 */
  function locate(sel, root){
    if (!sel) return null;
    var base = String(sel);
    while (/^\s*body\s*>\s*/.test(base)) base = base.replace(/^\s*body\s*>\s*/, ''); /* 兼容老版本错前缀 */
    var cands = [base];
    var sans = base.replace(/:nth-of-type\(\d+\)/g, '').replace(/:nth-child\(\d+\)/g, '');
    if (sans !== base) cands.push(sans);
    for (var i=0;i<cands.length;i++){
      var hits;
      try { hits = document.querySelectorAll(cands[i]); } catch(e){ hits = []; }
      if (!hits || hits.length === 0) continue;
      if (hits.length === 1) return hits[0];
      /* 多命中：优先可见的；都没有可见则返回 null（失联） */
      for (var j=0;j<hits.length;j++){ if (isVisible(hits[j])) return hits[j]; }
      return null;
    }
    return null;
  }
  function esc(s){ return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }
  function fmt(d){ function p(n){return (n<10?'0':'')+n;} return p(d.getMonth()+1)+'-'+p(d.getDate())+' '+p(d.getHours())+':'+p(d.getMinutes()); }
  function flash(el){ if(!el)return; var pv=el.style.outline; el.style.outline='3px solid #7C5CFC'; setTimeout(function(){ el.style.outline=pv; },1200); }
  /* 角标挂载点：粒度从精到粗「三级降级」。v4 角标在独立浮层，宿主能否容纳子节点已无关紧要，
     这里只决定「角标贴在哪个元素的角上」与「小元素右侧外挂」两种位置策略。 */
  var ATOM_RE = /^(label|button|a|input|select|textarea|img|svg|i|em|strong|code|span|td|th|dt|dd|li|p|h[1-6])$/;
  var CONTAINER_SEL = '.fr,.ctl,.form-item,.el-form-item,.row,.item,.cell,.field,.col,tr,li,td,th,.box,.card,section,article,form';
  function isAtom(el){
    if (!el || !el.tagName || !el.getBoundingClientRect) return false;
    if (!ATOM_RE.test(el.tagName.toLowerCase())) return false;
    var r = el.getBoundingClientRect();
    return r.height > 0 && r.height <= 44;   /* 限单行 */
  }
  function anchorOf(el){
    if (!el || !el.closest) return el;
    var k = el.closest('[data-anno]'); if (k) return k;
    var core = el;
    if (/^input$/i.test(el.tagName) && /^(radio|checkbox)$/i.test(el.type || '')) core = el.closest('label') || el;
    if (isAtom(core)) return core;
    var p = core.parentElement;
    while (p && p !== document.body){
      if (p.matches && p.matches(CONTAINER_SEL)){
        var r = p.getBoundingClientRect();
        if (r.height > 0 && r.height <= 220) return p;
        break;
      }
      p = p.parentElement;
    }
    return core;
  }
  function viewOf(el){ if(!el) return 'global'; var v = el.closest && el.closest('[data-view]'); if(v) return v.getAttribute('data-view'); v = el.closest && el.closest('.view,.page'); return v ? (v.id || 'global') : 'global'; }
  /* 通用激活钩子：a.activates 是字符串 —— 若为全局函数名(window[code] 是函数)则直接调用，否则当 JS 片段执行。
     用于「条件字段需先触发某交互才出现」的原型（如选水卡才显示水卡设置）。原型在 seed 里写 activates:'syncWaterCards' 等，
     引擎不耦合任何具体业务（本次去硬编码 watercard 分支，做成通用）。 */
  function runActivate(code){
    if (!code) return;
    try {
      if (typeof code === 'string'){
        if (typeof window[code] === 'function'){ window[code](); return; }
        (new Function(code))();
      }
    } catch(e){ /* 静默：原型未实现该钩子时不报错 */ }
  }
  /* 初始化时跑各批注的 activates，让「条件字段」（需先触发某交互才出现的字段）在 init 时就渲染出来，
     以便角标能定位；默认不打开弹窗（保持默认全量显示）。若某条批注希望在 init 就展开弹窗，
     把它对应的 open 函数写进 activates 即可（如 activates:'openCardTpl'）。引擎不耦合任何具体业务。 */
  function autoActivate(){
    try { data.forEach(function(a){ if (a.activates) runActivate(a.activates); }); } catch(e){}
  }
  /* 列表/气泡「定位」：弹窗内字段批注先跑通用激活钩子让字段出现，再尝试打开对应弹窗聚焦（data-open 钩子） */
  function revealAnno(a){
    var el=locate(a.sel, rootOf(a.view));
    var m = el ? modalOf(el) : null;
    if ((!el) || (m && !isModalOpen(m))){
      /* 待激活：先跑通用激活钩子（如选水卡/选模板），再尝试打开对应弹窗聚焦 */
      runActivate(a.activates);
      var targetM = m || (a.view==='global' ? document.querySelector(MODAL_SEL.split(',')[0]) : null);
      if(targetM && !isModalOpen(targetM)){ var of=targetM.getAttribute('data-open'); if(of){ try{ (new Function(of))(); }catch(e){} } }
      renderThrottled();
      setTimeout(function(){
        var el2=locate(a.sel, rootOf(a.view));
        if(!el2){ toast('定位失败：原型可能已改版，请「重定位」或删除'); return; }
        var m2=modalOf(el2);
        function go(){ el2.scrollIntoView({block:'center'}); flash(el2); }
        if(m2 && !isModalOpen(m2)){ var of2=m2.getAttribute('data-open'); if(of2){ try{ (new Function(of2))(); }catch(e){} } setTimeout(function(){ renderThrottled(); setTimeout(go,40); },40); return; }
        go();
      }, 180);
      return;
    }
    function go(){ el.scrollIntoView({block:'center'}); flash(el); }
    go();
  }

  /* ===== 工具栏 / 列表面板（这些保持在超高 z-index，弹窗开启时仍可操作） ===== */
  var tb=document.createElement('div'); tb.className='__anno-tb'; document.body.appendChild(tb);
  var listPanel=document.createElement('div'); listPanel.className='__anno-list'; document.body.appendChild(listPanel);
  function btn(label,cls){ var b=document.createElement('button'); b.textContent=label; if(cls)b.className=cls; return b; }
  var bMode=btn('批注'), bHide=btn('隐藏'), bList=btn('列表'), bSave=btn('保存原型'), bPush=btn('保存并推送'), bClear=btn('清空');
  tb.appendChild(bMode); tb.appendChild(bHide); tb.appendChild(bList); tb.appendChild(bSave); tb.appendChild(bPush); tb.appendChild(bClear);

  /* ===== 角标独立浮层（z-index 低于弹窗遮罩，弹窗开启时整层隐藏，不穿透） ===== */
  var layer=document.createElement('div'); layer.id='__anno_layer'; document.body.appendChild(layer);
  var flagEls = [];   /* {flag, el, pos} —— 用于滚动/resize 时重算坐标 */
  function clearFlags(){ flagEls=[]; while(layer.firstChild) layer.removeChild(layer.firstChild); }
  function closeBubble(){ var b=document.getElementById('__anno_bubble'); if(b&&b.parentNode)b.parentNode.removeChild(b); openId=null; }

  /* 分类：ok=可见可标；hidden-modal=弹窗关闭内(延后不显示)；pending=因交互未激活而隐藏/未生成(待激活灰标)；lost=锚点彻底失效(红标失联) */
  /* 顶层弹窗：遍历所有弹窗容器，归并到最外层根容器（去重）后取「开着且堆叠最高」的那一个（zIndex 大者优先）。
     无弹窗开着装 null。必须与 modalOf 同层级（都归并到根），否则 m===top 不成立误判 hidden-modal。（本次实战沉淀） */
  function topOpenModal(){
    try {
      var ms = document.querySelectorAll(MODAL_SEL);
      var roots = [];
      for (var i=0;i<ms.length;i++){
        var m = ms[i];
        while (m.parentNode && m.parentNode.closest && m.parentNode.closest(MODAL_SEL)) m = m.parentNode.closest(MODAL_SEL);
        if (roots.indexOf(m) === -1) roots.push(m);
      }
      var best = null, bestZ = -1;
      for (var j=0;j<roots.length;j++){
        var r = roots[j];
        if (!isModalOpen(r)) continue;
        var z = parseInt(getComputedStyle(r).zIndex || '0', 10) || 0;
        if (z > bestZ){ best = r; bestZ = z; }
      }
      return best;
    } catch(e){ return null; }
  }
  /* 分类：ok=可见可标；hidden-modal=被别的弹窗/背景遮挡（有弹窗开着时只显示顶层弹窗内，防穿透）；
     pending=条件未激活 / 关着的弹窗内字段（待激活灰标，不判失联）；lost=锚点彻底失效(红标失联)。
     默认全量：无弹窗开着时，关着的弹窗内字段不隐藏、落 pending，打开即看全量 19 条。 */
  function classify(a){
    var el = locate(a.sel, rootOf(a.view));
    if (el){
      var m = modalOf(el);
      var top = topOpenModal();
      if (top){
        /* 有弹窗开着：只显示顶层弹窗内的角标；背景与下层被盖弹窗的字段一律隐藏防穿透 */
        if (m === top) return isVisible(el) ? 'ok' : 'pending';
        return 'hidden-modal';
      }
      /* 无弹窗：关着的弹窗内字段不隐藏，落 pending（全量可见） */
      if (isVisible(el)) return 'ok';
      return 'pending';
    }
    var fb = a.fallback ? locate(a.fallback, rootOf(a.view)) : null;
    if (fb) return 'pending';
    return 'lost';
  }
  function render(){
    clearFlags();
    document.body.classList.toggle('__anno-hidden', hidden);
    if (hidden) return;
    var cv = currentView();
    var map = new Map();
    var miss = [];
    var pending = [];
    data.forEach(function(a){
      if (a.view && a.view !== 'global' && a.view !== cv) return;
      var c = classify(a);
      if (c === 'hidden-modal') return;
      if (c === 'ok'){
        var el = locate(a.sel, rootOf(a.view));
        var block = anchorOf(el);
        if (!map.has(block)) map.set(block, []);
        map.get(block).push(a);
        return;
      }
      if (c === 'pending'){ pending.push(a); return; }
      if (c === 'lost'){ miss.push(a); return; }
    });
    map.forEach(function(annos, block){
      var multi = annos.length > 1;
      var flag=document.createElement('div'); flag.className='__anno-flag';
      var br = block.getBoundingClientRect ? block.getBoundingClientRect() : null;
      var pos = (br && br.height > 0 && (br.height < 22 || br.width < 22)) ? 'side' : 'corner';
      if (multi) flag.setAttribute('data-multi','1');
      flag.textContent = multi ? annos.length : annos[0].no;
      if (multi){
        flag.addEventListener('click', function(ev){ ev.stopPropagation(); openMulti(block, annos); });
      } else {
        flag.setAttribute('data-id', annos[0].id);
        flag.addEventListener('click', function(ev){ ev.stopPropagation(); openBubble(annos[0].id, flag); });
      }
      layer.appendChild(flag);
      flagEls.push({flag:flag, el:block, pos:pos});
    });
    /* 待激活角标（灰标）：因交互未激活而隐藏/未生成，点击自动展开对应交互后定位 */
    pending.forEach(function(a,i){
      var flag=document.createElement('div'); flag.className='__anno-flag __anno-pending'; flag.setAttribute('data-pending','1');
      flag.textContent = a.no;
      flag.style.left='auto'; flag.style.right='16px'; flag.style.top=(60+i*22)+'px';
      flag.addEventListener('click', function(ev){ ev.stopPropagation(); openBubble(a.id, null); });
      layer.appendChild(flag);
    });
    /* 失联角标：固定堆在右上角（红底），仅锚点彻底失效才出现 */
    miss.forEach(function(a,i){
      var flag=document.createElement('div'); flag.className='__anno-flag'; flag.setAttribute('data-missing','1');
      flag.textContent = a.no;
      flag.style.left='auto'; flag.style.right='16px'; flag.style.top=(60+pending.length+i*22)+'px';
      flag.addEventListener('click', function(ev){ ev.stopPropagation(); openBubble(a.id, null); });
      layer.appendChild(flag);
    });
    positionFlags();
  }
  /* 按元素实时 rect 计算角标坐标；元素不可见/0尺寸则隐藏。
     弹窗感知：打开某弹窗时，仅显示「该弹窗内」字段的角标，弹窗外（被遮住）的角标隐藏；
     关闭的弹窗内字段角标不显示、也不算失联。 */
  function positionFlags(){
    layer.style.display='';
    var anyOpen = modalOpen();
    var vw=window.innerWidth, vh=window.innerHeight;
    flagEls.forEach(function(o){
      var el=o.el;
      if(!el || !el.getBoundingClientRect){ o.flag.style.display='none'; return; }
      var r=el.getBoundingClientRect();
      if ((r.width===0 && r.height===0) || !isVisible(el)){ o.flag.style.display='none'; return; }
      /* 方案A：元素完全滚出视口则隐藏角标，滚回再出现；避免 v4 的 clamp 把角标吸附钉在屏幕边缘 */
      if (r.bottom < 0 || r.top > vh || r.right < 0 || r.left > vw){ o.flag.style.display='none'; return; }
      o.flag.style.display='';
      var left, top;
      if (o.pos==='side'){ left=r.right+3; top=r.top+r.height/2-9; }
      else { left=r.right-9; top=r.top-9; }
      if (left<4) left=4; if (top<4) top=4;
      if (left>vw-22) left=vw-22; if (top>vh-22) top=vh-22;
      o.flag.style.left=left+'px'; o.flag.style.top=top+'px';
    });
  }
  function modalOpen(){
    var sel='.__anno_layer,.cf-mask,.cf-modal,.wct-mask,.wct-modal,.mask,.modal,.dialog,.overlay,.popup,[class*="mask"],[class*="modal"],[class*="dialog"],[class*="overlay"],[class*="popup"]';
    var ms=document.querySelectorAll(sel);
    for (var i=0;i<ms.length;i++){
      var m=ms[i];
      if(m.id==='__anno_layer')continue;
      if(getComputedStyle(m).display==='none') continue;
      var r=m.getBoundingClientRect();
      if(r.width>0 && r.height>0) return true;   /* fixed 定位模态 offsetParent 为 null，改用尺寸判定可见 */
    }
    return false;
  }

  function openBubble(id, flag){
    closeBubble();
    var a=data.filter(function(x){return x.id===id;})[0]; if(!a) return;
    openId=id;
    var b=document.createElement('div'); b.className='__anno-bubble'; b.id='__anno_bubble';
    var head=document.createElement('div'); head.className='b-head'; head.innerHTML='<span>批注 #'+a.no+'</span><span class="x">×</span>';
    var body=document.createElement('div'); body.className='b-body'; body.textContent=a.text;
    var actions=document.createElement('div'); actions.className='b-actions';
    var jump=btn('定位','ghost'), del=btn('删除','ghost'); actions.appendChild(jump); actions.appendChild(del);
    b.appendChild(head); b.appendChild(body); b.appendChild(actions); document.body.appendChild(b);
    head.querySelector('.x').addEventListener('click',closeBubble);
    jump.addEventListener('click',function(){ revealAnno(a); });
    del.addEventListener('click',function(){ removeAnno(a.id, null); });
    if(flag){ var r=flag.getBoundingClientRect(); var bw=b.offsetWidth,bh=b.offsetHeight; var left=r.left; if(left+bw>window.innerWidth-8)left=window.innerWidth-8-bw; if(left<8)left=8; var top=r.bottom+6; if(top+bh>window.innerHeight-8)top=r.top-bh-6; if(top<8)top=8; b.style.left=left+'px'; b.style.top=top+'px'; }
    else { b.style.left=Math.min(Math.max(window.innerWidth/2-142,8),window.innerWidth-300)+'px'; b.style.top='90px'; }
  }
  function openMulti(block, annos){
    closeBubble(); openId='__multi';
    var b=document.createElement('div'); b.className='__anno-bubble'; b.id='__anno_bubble';
    var head=document.createElement('div'); head.className='b-head'; head.innerHTML='<span>该位置 '+annos.length+' 条批注</span><span class="x">×</span>';
    var body=document.createElement('div'); body.className='b-body';
    annos.slice().sort(function(x,y){return x.no-y.no;}).forEach(function(a){
      var row=document.createElement('div'); row.className='m-item';
      var txt=document.createElement('div'); txt.className='m-txt'; txt.textContent='#'+a.no+' '+a.text;
      txt.addEventListener('click', function(){ openBubble(a.id, null); });
      var del=document.createElement('button'); del.className='m-del'; del.textContent='删除';
      del.title='删除这条批注';
      del.addEventListener('click', function(ev){ ev.stopPropagation(); ev.preventDefault(); removeAnno(a.id, null); });
      row.appendChild(txt); row.appendChild(del); body.appendChild(row);
    });
    var foot=document.createElement('div'); foot.className='b-actions';
    var delAll=btn('删除全部 '+annos.length+' 条','ghost');
    delAll.addEventListener('click', function(ev){
      ev.stopPropagation();
      if (!confirm('删除这 '+annos.length+' 条批注？')) return;
      var ids=annos.map(function(x){ return x.id; });
      data=data.filter(function(x){ return ids.indexOf(x.id)===-1; });
      save(); closeBubble(); render(); toast('已删除 '+ids.length+' 条批注');
    });
    foot.appendChild(delAll);
    b.appendChild(head); b.appendChild(body); b.appendChild(foot); document.body.appendChild(b);
    head.querySelector('.x').addEventListener('click',closeBubble);
    var r=block.getBoundingClientRect(); b.style.left=Math.min(Math.max(r.left,8),window.innerWidth-300)+'px'; b.style.top=Math.min(r.bottom+6,window.innerHeight-200)+'px';
  }
  /* 删一条 */
  function removeAnno(id, anchorEl){
    var a=data.filter(function(x){return x.id===id;})[0]; if(!a) return;
    if(!confirm('删除批注 #'+a.no+'？')) return;
    data=data.filter(function(x){return x.id!==id;});
    save(); render(); toast('已删除批注 #'+a.no);
    closeBubble();
  }
  /* 重定位：进入拾取模式，下一步点击原型元素即把该批注锚点换到新位置（编号/文字不变） */
  function startRelocate(id){
    relocating=id; mode=false; document.body.classList.remove('__anno-mode-on'); bMode.classList.remove('on'); bMode.textContent='批注';
    document.body.classList.add('__anno-relocating');
    var a=data.filter(function(x){return x.id===id;})[0];
    toast('点击正确的元素，把批注 #'+(a?a.no:'?')+' 重新定位到这里');
  }
  document.addEventListener('click', function(e){
    if(!relocating) return;
    var t=e.target;
    if(t.closest && t.closest('.__anno-tb,.__anno-list,.__anno-bubble')) return;
    e.preventDefault(); e.stopPropagation();
    var a=data.filter(function(x){return x.id===relocating;})[0];
    if(a){ a.sel=cssPath(t); a.view=viewOf(t); a.valid=true; save(); }
    relocating=null; document.body.classList.remove('__anno-relocating');
    closeBubble(); render(); toast('已重新定位');
  }, true);

  function renderList(){
    listPanel.innerHTML='';
    var lost = data.filter(function(a){ return classify(a)==='lost'; });
    var head=document.createElement('div'); head.className='l-head';
    head.innerHTML='<span>批注列表 ('+data.length+(lost.length?' · 失联 '+lost.length:'')+')</span><span class="x">×</span>';
    listPanel.appendChild(head);
    if (lost.length){
      var bar=document.createElement('div'); bar.className='l-bar';
      var cleanBtn=btn('清理失联 ('+lost.length+')','l-clean');
      cleanBtn.addEventListener('click', function(){
        if(!confirm('删除这 '+lost.length+' 条失联批注？')) return;
        var ids=lost.map(function(x){return x.id;});
        data=data.filter(function(x){return ids.indexOf(x.id)===-1;});
        save(); renderList(); render(); toast('已清理 '+ids.length+' 条失联批注');
      });
      bar.appendChild(cleanBtn);
      listPanel.appendChild(bar);
    }
    if(!data.length){ var e=document.createElement('div'); e.className='empty'; e.textContent='暂无批注。开启「批注」模式后点击原型元素即可添加。'; listPanel.appendChild(e); }
    data.slice().sort(function(x,y){return x.no-y.no;}).forEach(function(a){
      var c=classify(a);
      var it=document.createElement('div'); it.className='item'+(c==='lost'?' miss':(c==='pending'?' pending':''));
      var row=document.createElement('div'); row.className='i-main';
      var el = locate(a.sel, rootOf(a.view));
      var atxt = el ? textOf(el).slice(0,12) : '';
      var tag = c==='lost'?' 失联':(c==='pending'?' 待激活':'');
      row.innerHTML='<span class="n">'+a.no+'</span><span class="v">'+(a.view&&a.view!=='global'?'['+a.view+']':'')+'</span>'+esc(a.text)+(atxt?'<span class="a">'+esc(atxt)+'</span>':'')+'<span class="t">'+fmt(new Date(a.ts||Date.now()))+tag+'</span>';
      row.addEventListener('click',function(){ revealAnno(a); if(hidden){hidden=false;document.body.classList.remove('__anno-hidden');bHide.textContent='隐藏';} var f=document.querySelector('.__anno-flag[data-id="'+a.id+'"]'); if(f)openBubble(a.id,f); else if(c==='lost') toast('该批注已失联，可「重定位」或删除'); });
      it.appendChild(row);
      var acts=document.createElement('div'); acts.className='i-acts';
      if (c==='lost'){
        var reBtn=btn('重定位','mini'); reBtn.addEventListener('click', function(ev){ ev.stopPropagation(); startRelocate(a.id); });
        acts.appendChild(reBtn);
      } else if (c==='pending'){
        var loBtn=btn('定位','mini'); loBtn.addEventListener('click', function(ev){ ev.stopPropagation(); revealAnno(a); });
        acts.appendChild(loBtn);
      } else {
        var jBtn=btn('定位','mini'); jBtn.addEventListener('click', function(ev){ ev.stopPropagation(); var e2=locate(a.sel, rootOf(a.view)); if(e2){e2.scrollIntoView({block:'center'});flash(e2);} });
        acts.appendChild(jBtn);
      }
      var dBtn=btn('删除','mini danger'); dBtn.addEventListener('click', function(ev){ ev.stopPropagation(); removeAnno(a.id, null); });
      acts.appendChild(dBtn);
      it.appendChild(acts);
      listPanel.appendChild(it);
    });
    head.querySelector('.x').addEventListener('click',function(){ listPanel.style.display='none'; });
    listPanel.style.display='block';
  }
  function setMode(on){
    mode=on; relocating=null; document.body.classList.remove('__anno-relocating');
    document.body.classList.toggle('__anno-mode-on',on);
    bMode.classList.toggle('on',on);
    bMode.textContent = on ? '批注中' : '批注';
    if(!on){ if(hoverEl){hoverEl.classList.remove('__anno-hover');hoverEl=null;} closeBubble(); }
    render();
  }
  function clearHover(){ if(hoverEl){ hoverEl.classList.remove('__anno-hover'); hoverEl=null; } }
  document.addEventListener('mouseover',function(e){ if(!mode)return; var el=e.target; if(el.closest&&el.closest('.__anno-tb,.__anno-list,.__anno-bubble'))return; if(hoverEl&&hoverEl!==el)hoverEl.classList.remove('__anno-hover'); hoverEl=el; el.classList.add('__anno-hover'); });
  document.addEventListener('mouseout',function(e){ if(!mode)return; if(hoverEl&&e.target===hoverEl)hoverEl.classList.remove('__anno-hover'); });
  document.addEventListener('click',function(e){
    if(!mode)return;
    var t=e.target;
    if(t.closest&&t.closest('.__anno-tb,.__anno-list,.__anno-bubble,.__anno-flag'))return;
    e.preventDefault(); e.stopPropagation(); clearHover(); openEditor(t);
  }, true);
  function openEditor(el){
    closeBubble();
    var b=document.createElement('div'); b.className='__anno-bubble'; b.id='__anno_bubble';
    var head=document.createElement('div'); head.className='b-head'; head.innerHTML='<span>新增批注 · '+(viewOf(el))+'</span><span class="x">×</span>';
    var ta=document.createElement('textarea'); ta.placeholder='写下你的批注…（Enter 换行，保存即生效）';
    var actions=document.createElement('div'); actions.className='b-actions';
    var saveBtn=btn('保存'), cancelBtn=btn('取消','ghost'); actions.appendChild(saveBtn); actions.appendChild(cancelBtn);
    b.appendChild(head); b.appendChild(ta); b.appendChild(actions); document.body.appendChild(b);
    head.querySelector('.x').addEventListener('click',closeBubble);
    cancelBtn.addEventListener('click',closeBubble);
    saveBtn.addEventListener('click',function(){ var txt=ta.value.trim(); if(!txt){closeBubble();return;} data.push({id:uid(),no:nextNo(),view:viewOf(el),sel:cssPath(el),text:txt,ts:Date.now(),valid:true}); save(); closeBubble(); render(); toast('已添加批注 #'+data[data.length-1].no); });
    var r=el.getBoundingClientRect();
    b.style.left=Math.min(Math.max(r.left,8),window.innerWidth-264)+'px';
    b.style.top=Math.min(r.bottom+6,window.innerHeight-150)+'px';
    setTimeout(function(){ ta.focus(); },30);
  }
  bMode.addEventListener('click',function(){ setMode(!mode); });
  bHide.addEventListener('click',function(){ hidden=!hidden; document.body.classList.toggle('__anno-hidden',hidden); bHide.textContent=hidden?'显示':'隐藏'; render(); });
  bList.addEventListener('click',function(){ if(listPanel.style.display==='block')listPanel.style.display='none'; else renderList(); });
  /* 保存为带批注的完整 HTML：把当前批注写回 __anno_seed，导出整页（剔除运行时 UI）。
     用户覆盖回本地原型文件，WorkBuddy 直接把该 HTML 推 GitHub，无需 JSON 中转。 */
  /* 构造带批注的完整 HTML（写回 __anno_seed + 剥离运行时 UI）。保存原型 / 保存并推送 共用 */
  function buildAnnotatedHtml(){
    var out=data.map(function(a){ var el=locate(a.sel, rootOf(a.view)); return {id:a.id,no:a.no,view:a.view,sel:a.sel,text:a.text,ts:a.ts,valid:!!el&&isVisible(el)}; });
    var seedEl=document.getElementById('__anno_seed');
    if(!seedEl){ seedEl=document.createElement('script'); seedEl.type='application/json'; seedEl.id='__anno_seed'; document.head.appendChild(seedEl); }
    seedEl.textContent=JSON.stringify(out);
    var detached=[];
    [layer, tb, listPanel, document.getElementById('__anno_bubble')].forEach(function(n){ if(n&&n.parentNode){ n.parentNode.removeChild(n); detached.push(n); } });
    document.querySelectorAll('[data-__pactive]').forEach(function(n){ n.removeAttribute('data-__pactive'); });
    var html='<!DOCTYPE html>\n'+document.documentElement.outerHTML;
    detached.forEach(function(n){ document.body.appendChild(n); });
    return html;
  }
  bSave.addEventListener('click',function(){
    var html=buildAnnotatedHtml();
    var dlName=/\.html?$/i.test(fileKey)?fileKey:fileKey+'.html';
    download(dlName, html, 'text/html');
    if(navigator.clipboard){ navigator.clipboard.writeText(dlName).catch(function(){}); }
    toast('已保存带批注的原型：'+dlName+'（覆盖回本地原型文件，然后告诉我，我直接推 GitHub）');
  });
  /* 保存并推送：把带批注 HTML POST 给本地后台服务（anno_push_server.py），由其用 gh CLI 推 GitHub。
     需先双击运行 anno_push_server；服务只在 127.0.0.1 监听，不外网暴露。 */
  bPush.addEventListener('click',function(){
    var old=bPush.textContent; bPush.disabled=true; bPush.textContent='推送中…';
    var html=buildAnnotatedHtml();
    var payload=JSON.stringify({file:fileKey, html:html, message:'批注保存并推送 ' + new Date().toLocaleString('zh-CN')});
    fetch('http://127.0.0.1:8765/push', {method:'POST', headers:{'Content-Type':'application/json'}, body:payload})
      .then(function(r){ return r.json(); })
      .then(function(j){
        bPush.disabled=false; bPush.textContent=old;
        if(j && j.ok) toast('已推送到 GitHub ✓（本地原型也同步更新）');
        else toast('推送失败：' + ((j&&(j.error||j.stderr))||'未知错误'));
      })
      .catch(function(){ bPush.disabled=false; bPush.textContent=old; toast('连不上本地服务，请先双击运行 anno_push_server'); });
  });
  bClear.addEventListener('click',function(){ if(confirm('清空全部批注？本地操作不可撤销（GitHub 上的种子需同步清理）。')){ data=[]; save(); closeBubble(); render(); toast('已清空'); } });

  /* 滚动/resize/视图切换 → 角标重算坐标；弹窗开启 → 浮层隐藏 */
  var _pt;
  function posThrottled(){ clearTimeout(_pt); _pt=setTimeout(positionFlags, 30); }
  window.addEventListener('scroll', posThrottled, true);
  window.addEventListener('resize', posThrottled);
  window.addEventListener('scroll', function(){ var b=document.getElementById('__anno_bubble'); if(b&&openId&&openId!=='__multi'){ var f=document.querySelector('.__anno-flag[data-id="'+openId+'"]'); if(f){ var r=f.getBoundingClientRect(); var bw=b.offsetWidth,bh=b.offsetHeight; var left=r.left; if(left+bw>window.innerWidth-8)left=window.innerWidth-8-bw; if(left<8)left=8; var top=r.bottom+6; if(top+bh>window.innerHeight-8)top=r.top-bh-6; if(top<8)top=8; b.style.left=left+'px'; b.style.top=top+'px'; } } }, true);
  var _vt;
  function renderThrottled(){ clearTimeout(_vt); _vt=setTimeout(render, 40); }
  document.addEventListener('anno:viewchange', renderThrottled);
  document.querySelectorAll('.view,.page').forEach(function(v){ v.setAttribute('data-__pactive', v.classList.contains('active')?'1':'0'); });
  var vo=new MutationObserver(function(muts){
    var hit=false;
    for(var i=0;i<muts.length;i++){
      var t=muts[i].target;
      if(t&&t.classList&&(t.classList.contains('view')||t.classList.contains('page'))){
        var now=t.classList.contains('active')?'1':'0';
        if(t.getAttribute('data-__pactive')!==now){ t.setAttribute('data-__pactive',now); hit=true; }
      }
    }
    if(hit) renderThrottled();
    posThrottled();
  });
  vo.observe(document.body, {attributes:true, attributeFilter:['class'], subtree:true});
  /* 弹窗显隐（运行时点击打开/关闭）必须重新分类：重算 topOpenModal，否则「只显顶层弹窗内字段」不生效。
     用 renderThrottled（含 positionFlags），且 body 的 __anno-hidden 切换是幂等的，不会触发死循环。 */
  var vmodal=new MutationObserver(function(){ renderThrottled(); });
  vmodal.observe(document.body, {attributes:true, attributeFilter:['style','class'], subtree:true});

  autoActivate();
  render();
  bHide.textContent = '隐藏';
})();
