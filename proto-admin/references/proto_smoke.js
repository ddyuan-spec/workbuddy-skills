/**
 * proto_smoke.js — 单文件 HTML 原型自动化冒烟测试（泰小虎原型交付强制 Loop）
 *
 * ⚠️ 2026-08-12 升级：默认用【真实浏览器 playwright chromium】跑，不再只用 jsdom。
 *    根因：此前一次改后台原型时 viewEdit 漏了一个闭合 </div>，导致后续所有视图
 *    (viewPool/viewRule/...) 被浏览器嵌套进 hidden 的 viewEdit 内 → 整页空白。
 *    jsdom 只检查元素自身 classList 是否含 hidden，不检查祖先隐藏，漏报了这次事故。
 *    真实浏览器 + getComputedStyle + 布局包围盒才能稳定拦住「被隐藏祖先吞掉」类 bug。
 *
 * 强制校验（真实浏览器模式）：
 *   [A] 视图容器归属 <main>：所有 view* 必须在 <main> 内（写在 </main> 外 → 跳转空白）
 *   [B] go() 逐页点击 + 真实可见性：每个目标视图 computed display!=='none'、有可见包围盒、
 *       有可见文本；且祖先链无 display:none（拦「嵌套进隐藏容器」致命 bug）
 *   [C] 真实点击每个可交互元素（[onclick]），捕获运行期 pageerror
 *   [D] onclick 引用函数未定义扫描（静态）
 *   [E] JS 运行期错误汇总（pageerror / console.error）
 *   [F] 表单选项去重 / 错漏（select / radio / checkbox）
 *   [G] 主区可滚动性（2026-09-03 新增）：内容超出视口却无任何容器可滚 → 下方内容被裁剪、用户滚不动。
 *       真实浏览器量 clientHeight/scrollHeight 并对第一个可滚容器强设 scrollTop=999999 验证。
 *       典型根因：html,body{overflow:hidden} + .main{height:固定} 而 <main> 漏挂滚动容器类
 *       （本项目后台框架是 class="content" → flex:1 + overflow-y:auto），见 PROTO-SCROLL-001。
 *
 * 用法（在原型所在目录执行）：
 *   NODE_PATH="<node_modules 含 playwright>" node proto_smoke.js <原型.html>
 * 例：
 *   NODE_PATH="C:\Users\13364\.workbuddy\binaries\node\workspace/node_modules" \
 *     "C:\Users\13364\.workbuddy\binaries\node\versions\22.22.2\node.exe" proto_smoke.js 后台原型.html
 *
 * 退出码：0=全部通过；1=有失败项；2=参数错误；3=真实浏览器不可用（回退 jsdom，见 stderr）
 * 任何失败项都必须修复后才能交付原型。
 */
const fs = require('fs');
const path = require('path');
const os = require('os');
const url = require('url');
const { execSync } = require('child_process');

const FILE = process.argv[2];
if (!FILE || !fs.existsSync(FILE)) { console.error('用法: node proto_smoke.js <原型.html>'); process.exit(2); }
const html = fs.readFileSync(FILE, 'utf8');

let fails = 0;
const fail = m => { console.log('  ✗ ' + m); fails++; };
const ok = m => console.log('  ✓ ' + m);

// ---------- 工具：从 HTML 抽导航目标 ----------
function extractNavTargets() {
  const pageKeys = new Set();
  // 1) NAV_OF / map 的 key
  let m = html.match(/(?:var|const|let)\s+NAV_OF\s*=\s*\{([^}]*)\}/);
  if (m) [...m[1].matchAll(/(\w+)\s*:/g)].forEach(x => pageKeys.add(x[1]));
  // 2) 所有 go('x') / go("x")
  [...html.matchAll(/go\(\s*['"]([\w-]+)['"]\s*\)/g)].forEach(x => pageKeys.add(x[1]));
  // 3) VIEWS 数组里的 viewXxx → 反推 page key（首字母小写）
  const vm = html.match(/(?:var|const|let)\s+VIEWS\s*=\s*\[([^\]]*)\]/);
  if (vm) [...vm[1].matchAll(/view([A-Z]\w*)/g)].forEach(x => pageKeys.add(x[1].charAt(0).toLowerCase() + x[1].slice(1)));
  return [...pageKeys];
}
function viewIdOf(pk) { return 'view' + pk.charAt(0).toUpperCase() + pk.slice(1); }

// ============================================================
// 真实浏览器模式（playwright chromium）
// ============================================================
function loadPlaywright() {
  try { return require('playwright'); }
  catch (e) {
    console.error('  ✗ 找不到 playwright，请先 NODE_PATH 指向含 playwright 的 node_modules');
    return null;
  }
}

async function runBrowser() {
  const pw = loadPlaywright();
  if (!pw) process.exit(3);
  let browser;
  try { browser = await pw.chromium.launch({ args: ['--no-sandbox'] }); }
  catch (e) {
    console.error('  ✗ chromium 启动失败：' + (e.message.split('\n')[0]) + '\n    请运行：npx playwright install chromium');
    return false; // 交由调用方回退 jsdom
  }
  const page = await browser.newPage();
  const pageErrors = [];
  page.on('pageerror', e => pageErrors.push('pageerror: ' + (e.message || e)));
  page.on('console', msg => { if (msg.type() === 'error') pageErrors.push('console.error: ' + msg.text()); });

  const fileUrl = url.pathToFileURL(FILE).href;
  await page.goto(fileUrl, { waitUntil: 'load' });
  await page.waitForTimeout(300);

  const pageKeys = extractNavTargets();
  const viewIds = [...new Set(pageKeys.map(viewIdOf))];

  console.log('=== [A] 视图容器归属 <main> 校验（空白页根因） ===');
  const mainInfo = await page.evaluate(() => {
    const main = document.querySelector('main') || document.getElementById('mainArea');
    return main ? { exists: true } : { exists: false };
  });
  if (!mainInfo.exists) fail('未找到 <main> 布局容器（无法校验视图归属）');
  else {
    for (const vid of viewIds) {
      const r = await page.evaluate(v => {
        const el = document.getElementById(v);
        if (!el) return { exists: false };
        let p = el.parentElement, inMain = false;
        while (p) { if (p.tagName === 'MAIN' || p.id === 'mainArea') { inMain = true; break; } p = p.parentElement; }
        return { exists: true, inMain };
      }, vid);
      if (!r.exists) fail('视图 #' + vid + ' 在 DOM 中不存在');
      else if (r.inMain) ok('#' + vid + ' 在 <main> 内');
      else fail('#' + vid + ' 写在 </main> 之外 → 跳转后空白页');
    }
  }

  console.log('\n=== [B] go() 逐页点击 + 真实可见性（含祖先隐藏检测） ===');
  for (const pk of pageKeys) {
    const vid = viewIdOf(pk);
    await page.evaluate(k => { try { window.go(k); } catch (e) { throw e; } }, pk);
    await page.waitForTimeout(120);
    const r = await page.evaluate(arg => {
      const v = arg.vid, k = arg.pk;
      const el = document.getElementById(v);
      if (!el) return { exists: false };
      // 祖先链是否有人 display:none（致命：被隐藏容器吞掉）
      let p = el.parentElement, ancestorHidden = false, hiddenAncestorId = '';
      while (p) {
        const cs = getComputedStyle(p);
        if (cs.display === 'none') { ancestorHidden = true; hiddenAncestorId = p.id || p.tagName; break; }
        p = p.parentElement;
      }
      const cs = getComputedStyle(el);
      const display = cs.display;
      const textLen = (el.innerText || el.textContent || '').trim().length;
      const rect = el.getBoundingClientRect();
      const boxW = Math.round(rect.width), boxH = Math.round(rect.height);
      return { exists: true, display, ancestorHidden, hiddenAncestorId, textLen, boxW, boxH };
    }, { vid, pk });
    if (!r.exists) { fail(`go('${pk}') → #${vid} 目标视图不存在`); continue; }
    if (r.ancestorHidden) { fail(`go('${pk}') → #${vid} 被隐藏祖先 #${r.hiddenAncestorId} 吞掉（整页空白）`); continue; }
    if (r.display === 'none') { fail(`go('${pk}') → #${vid} 自身隐藏（空白页）`); continue; }
    if (r.boxW === 0 || r.boxH === 0) { fail(`go('${pk}') → #${vid} 无可见布局包围盒 ${r.boxW}x${r.boxH}（空白页）`); continue; }
    if (r.textLen === 0) { fail(`go('${pk}') → #${vid} 可见但无文本（空白页）`); continue; }
    ok(`go('${pk}') → #${vid} 可见(${r.boxW}x${r.boxH}) 有文本(${r.textLen})`);
  }

  console.log('\n=== [C] 真实点击每个可交互元素（捕获运行期错误） ===');
  const handles = await page.$$('[onclick]');
  let clicked = 0, clickErr = 0;
  for (const h of handles) {
    try {
      await h.evaluate(el => { try { el.click(); } catch (e) { throw e; } });
      clicked++;
    } catch (e) {
      clickErr++;
      const tag = await h.evaluate(el => el.tagName).catch(() => '?');
      const id = await h.evaluate(el => el.id || '').catch(() => '');
      fail(`点击 <${tag}>#${id} onclick="${await h.evaluate(el => el.getAttribute('onclick')).catch(() => '')}" 抛错: ${e.message}`);
    }
  }
  if (clickErr === 0) ok(`真实点击 ${clicked} 个可交互元素，无 JS 运行期错误`);

  console.log('\n=== [D] onclick 函数未定义扫描 ===');
  const undef = await page.evaluate(() => {
    const defined = new Set();
    [...document.scripts].forEach(s => {
      [...(s.textContent || '').matchAll(/function\s+([A-Za-z_$][\w$]*)\s*\(/g)].forEach(x => defined.add(x[1]));
    });
    const known = new Set(['$', 'go', 'toast', 'confirm', 'alert', 'parseInt', 'parseFloat', 'setTimeout', 'console', 'window', 'document']);
    // 取 onclick 里第一个「全局函数调用」名：先剥离 a.b.c(...) 形式的方法调用，
    // 避免把 this.classList.toggle(...) / document.getElementById(...) 误判为未定义函数（PROTOSMK-D 误报修复）
    const firstFnCall = (expr) => {
      const clean = String(expr || '').replace(/[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+\s*\(/g, '(');
      const m = clean.match(/(?:^|[^.\w$])([A-Za-z_$][\w$]*)\s*\(/);
      return m ? m[1] : null;
    };
    const bad = [];
    document.querySelectorAll('[onclick]').forEach(el => {
      const expr = el.getAttribute('onclick') || '';
      const fm = firstFnCall(expr);
      if (fm && !defined.has(fm) && !known.has(fm)) bad.push(fm + ' @ <' + el.tagName + '>#' + (el.id || '') + '>');
    });
    return bad;
  });
  if (undef.length === 0) ok('所有 onclick 处理函数均已定义');
  else undef.forEach(u => fail('onclick 引用未定义函数 ' + u));

  console.log('\n=== [E] JS 运行期错误汇总 ===');
  if (pageErrors.length) pageErrors.forEach(e => fail(e)); else ok('无 JS 运行期错误（pageerror / console.error）');

  console.log('\n=== [F] 表单选项去重 / 错漏校验 ===');
  const dup = await page.evaluate(() => {
    const out = [];
    document.querySelectorAll('select').forEach(sel => {
      const opts = [...sel.options].filter(o => o.value !== '');
      const seen = new Set();
      opts.forEach(o => { const l = (o.textContent || '').trim(); if (seen.has(l)) out.push(`<select>#${sel.id || ''} 重复「${l}」`); seen.add(l); });
    });
    document.querySelectorAll('input[type=radio], input[type=checkbox]').forEach(el => {
      const name = el.getAttribute('name'); if (!name) return;
      const group = document.querySelectorAll(`input[name="${name}"]`);
      const seen = new Set();
      [...group].forEach(inp => {
        const forL = inp.id ? document.querySelector(`label[for="${inp.id}"]`) : null;
        const lbl = forL ? (forL.textContent || '').trim() : (inp.closest('label') ? (inp.closest('label').textContent || '').replace(/[✓☐]\s*/, '').trim() : '');
        if (lbl && seen.has(lbl)) out.push(`radio/checkbox[name="${name}"] 重复标签「${lbl}」`);
        if (lbl) seen.add(lbl);
      });
    });
    return out;
  });
  if (dup.length === 0) ok('所有下拉 / 单选 / 复选选项无重复');
  else dup.forEach(d => fail(d));

  // ---------- [G] 主区可滚动性（内容被裁剪根因，2026-09-03 新增） ----------
  console.log('\n=== [G] 主区可滚动性校验（内容被裁剪、滚不动） ===');
  // 判定思路：body/html 或任何主区容器若 overflow-y:hidden 且 scrollHeight > clientHeight，
  // 说明它把溢出内容硬裁掉了且自身滚不动 → 用户看不到下方内容（典型：漏挂 .content 滚动容器类）。
  // 注：overflow:hidden 元素的 scrollHeight 仍会包含后代溢出内容，所以这一条能稳定命中。
  const sc = await page.evaluate(() => {
    const desc = (el) => el.tagName.toLowerCase() +
      (el.id ? '#' + el.id : '') +
      (el.className ? '.' + el.className.toString().trim().split(/\s+/).slice(0, 2).join('.') : '');
    const isScrollable = (el) => {
      if (!el) return false;
      const cs = getComputedStyle(el);
      return (cs.overflowY === 'auto' || cs.overflowY === 'scroll') && el.scrollHeight > el.clientHeight + 2;
    };

    const res = { viewportH: window.innerHeight, clipped: [], scrollers: [], scrolledTo: 0, target: '' };

    // 1) 找「硬裁剪点」：overflow-y:hidden 且内容溢出
    const all = [...document.querySelectorAll('html, body, main, #mainArea, .content, .main-content, .main-body, .page-body, .view, section')];
    for (const el of all) {
      if (el.scrollHeight > el.clientHeight + 2) {
        const oy = getComputedStyle(el).overflowY;
        if (oy === 'hidden') {
          res.clipped.push({ desc: desc(el), scrollH: el.scrollHeight, clientH: el.clientHeight });
        }
      }
    }

    // 2) 找真正可滚的容器（用于正向确认 + 实测滚到底）
    ['body', 'main', '.content', '.main-content', '#mainArea', '.main-body', '.page-body'].forEach(s => {
      document.querySelectorAll(s).forEach(el => {
        if (isScrollable(el)) res.scrollers.push({ desc: desc(el), scrollH: el.scrollHeight, clientH: el.clientHeight });
      });
    });

    // 3) 真滚一次
    let t = null;
    if (isScrollable(document.body)) t = document.body;
    else {
      for (const s of ['main', '.content', '.main-content', '#mainArea', '.main-body']) {
        const el = document.querySelector(s);
        if (isScrollable(el)) { t = el; break; }
      }
    }
    if (t) {
      t.scrollTop = 999999;
      res.scrolledTo = t.scrollTop;
      res.target = t === document.body ? 'body' : desc(t);
      t.scrollTop = 0;
    }
    return res;
  });

  if (sc.clipped.length) {
    sc.clipped.forEach(c => fail(
      `容器「${c.desc}」内容 ${c.scrollH}px 超出可视 ${c.clientH}px，但 overflow-y:hidden 【硬裁剪且滚不动】` +
      `→ 下方 ${c.scrollH - c.clientH}px 用户永远看不到`));
    fail(`修复: 给主区 <main> 挂上滚动容器类（本项目后台框架是 class="content"，即 flex:1 + overflow-y:auto），` +
         `且不要把它嵌套在 <section> 内部的 div 上，见 PROTO-SCROLL-001`);
  } else if (sc.scrollers.length) {
    ok(`主区可滚：容器「${sc.target}」实测滚到底 ${sc.scrolledTo}px（${sc.scrollers.map(s => `${s.desc} ${s.scrollH}/${s.clientH}`).join(' | ')}）`);
  } else {
    ok(`无内容溢出（视口 ${sc.viewportH}px），滚动正常`);
  }

  await browser.close();
  return true;
}

// ============================================================
// jsdom 回退模式（仅在真实浏览器不可用，可见性校验为浅层，会告警）
// ============================================================
function runJsdom() {
  console.error('\n⚠️ 真实浏览器不可用，回退 jsdom 浅层校验：祖先隐藏类 bug 可能漏报！');
  let jsdom;
  try { jsdom = require('jsdom'); }
  catch (e) {
    console.error('  ✗ jsdom 也缺失，请安装 playwright 或 jsdom 后重跑');
    process.exit(3);
  }
  const { JSDOM, VirtualConsole } = jsdom;
  const errors = [];
  const vc = new VirtualConsole();
  vc.on('jsdomError', e => errors.push('jsdomError: ' + (e.stack || e.detail || e.message)));
  vc.on('error', (...a) => errors.push('console.error: ' + a.join(' ')));
  const dom = new JSDOM(html, {
    runScripts: 'dangerously', virtualConsole: vc, pretendToBeVisual: true,
    beforeParse(window) {
      window.confirm = () => true; window.alert = () => {}; window.prompt = () => '';
      window.$ = id => window.document.getElementById(id); window.toast = () => {};
    }
  });
  const { window } = dom; const { document } = window;

  const main = document.querySelector('main') || document.getElementById('mainArea');
  if (!main) fail('未找到 <main> 布局容器');
  const mainContains = el => { let p = el && el.parentElement; while (p) { if (p.tagName === 'MAIN' || p.id === 'mainArea') return true; p = p.parentElement; } return false; };

  const pageKeys = extractNavTargets();
  const viewIds = [...new Set(pageKeys.map(viewIdOf))];

  console.log('=== [A] 视图容器归属 <main> 校验 ===');
  if (main) viewIds.forEach(v => {
    const el = document.getElementById(v);
    if (!el) fail('视图 #' + v + ' 在 DOM 中不存在');
    else if (mainContains(el)) ok('#' + v + ' 在 <main> 内');
    else fail('#' + v + ' 写在 </main> 之外 → 跳转后空白页');
  });

  console.log('\n=== [B] go() 可达性 + 空白校验（浅层：不含祖先隐藏检测） ===');
  if (typeof window.go === 'function' && pageKeys.length) pageKeys.forEach(pk => {
    try { window.go(pk); } catch (e) { fail(`go('${pk}') 抛错: ${e.message}`); return; }
    const vid = viewIdOf(pk); const target = document.getElementById(vid);
    const textLen = target ? (target.innerText || target.textContent || '').trim().length : 0;
    if (!target) fail(`go('${pk}') → #${vid} 不存在`);
    else if (target.classList.contains('hidden')) fail(`go('${pk}') → #${vid} 仍隐藏（空白页）`);
    else if (textLen === 0) fail(`go('${pk}') → #${vid} 无内容（空白页）`);
    else ok(`go('${pk}') → #${vid} 可见且有内容(${textLen})`);
  });

  console.log('\n=== [C] 真实点击每个可交互元素 ===');
  const clickables = [...document.querySelectorAll('[onclick]')];
  let clicked = 0, clickErr = 0;
  clickables.forEach(el => { try { el.click(); clicked++; } catch (e) { clickErr++; fail(`点击 <${el.tagName}>#${el.id || ''} 抛错: ${e.message}`); } });
  if (clickErr === 0) ok(`点击 ${clicked} 个可交互元素，无 JS 错误`);

  console.log('\n=== [D] onclick 函数未定义扫描 ===');
  const definedFns = new Set();
  [...html.matchAll(/function\s+([A-Za-z_$][\w$]*)\s*\(/g)].forEach(x => definedFns.add(x[1]));
  try { Object.getOwnPropertyNames(window).forEach(n => { if (typeof window[n] === 'function') definedFns.add(n); }); } catch (e) {}
  const knownHelpers = new Set(['$', 'go', 'toast', 'confirm', 'alert', 'parseInt', 'parseFloat', 'setTimeout', 'console', 'window', 'document']);
  // 同上：先剥离 a.b.c(...) 方法调用，避免 classList.toggle / document.getElementById 误报
  const firstFnCall = (expr) => {
    const clean = String(expr || '').replace(/[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+\s*\(/g, '(');
    const m = clean.match(/(?:^|[^.\w$])([A-Za-z_$][\w$]*)\s*\(/);
    return m ? m[1] : null;
  };
  let undef = 0;
  clickables.forEach(el => {
    const expr = el.getAttribute('onclick') || '';
    const fm = firstFnCall(expr);
    if (fm && !definedFns.has(fm) && !knownHelpers.has(fm)) { undef++; fail(`onclick 引用未定义函数 ${fm}`); }
  });
  if (undef === 0) ok('所有 onclick 处理函数均已定义');

  console.log('\n=== [E] JS 运行期错误汇总 ===');
  if (errors.length) errors.forEach(e => fail(e)); else ok('无 JS 运行期错误');

  console.log('\n=== [F] 表单选项去重 / 错漏校验 ===');
  let dupCount = 0;
  document.querySelectorAll('select').forEach(sel => {
    const opts = [...sel.options].filter(o => o.value !== '');
    const seen = new Set();
    opts.forEach(o => { const l = (o.textContent || '').trim(); if (seen.has(l)) { dupCount++; fail(`<select>#${sel.id || ''} 重复「${l}」`); } seen.add(l); });
  });
  if (dupCount === 0) ok('所有下拉选项无重复');
}

(async () => {
  let usedBrowser = false;
  try { usedBrowser = await runBrowser(); }
  catch (e) {
    console.error('  ⚠ 真实浏览器模式异常：' + (e.message || e).split('\n')[0] + '，回退 jsdom');
    usedBrowser = false;
  }
  if (!usedBrowser) runJsdom();
  console.log('\n' + (fails === 0 ? '✅ 冒烟测试全部通过，可交付' : `❌ 共 ${fails} 项不通过，禁止交付，先修复`));
  process.exit(fails === 0 ? 0 : 1);
})();
