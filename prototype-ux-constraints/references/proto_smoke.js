/**
 * proto_smoke.js — 单文件 HTML 原型自动化冒烟测试（泰小虎原型交付强制 Loop）
 *
 * 用途：替代"人工肉眼自查"，用 jsdom 真实执行原型 JS，捕获人工 Loop 漏掉的几类致命 bug：
 *   1) 独立页写在 </main> 之外 → 点击跳转后空白页
 *   2) go('X') 目标视图不存在 / 渲染后无内容（空白页）
 *   3) 点击按钮/链接时 JS 抛错（如 undefined.trim()）
 *   4) onclick 引用的函数未定义
 *
 * 用法（在原型所在目录执行）：
 *   NODE_PATH="<jsdom 所在 node_modules>" node proto_smoke.js <原型.html>
 * 例：
 *   NODE_PATH="C:\Users\13364\.workbuddy\binaries\node\workspace/node_modules" "C:\Users\13364\.workbuddy\binaries\node\versions\22.22.2\node.exe" proto_smoke.js 平台端后台原型.html
 *
 * 退出码：0=全部通过；1=有失败项；2=参数错误。
 * 任何失败项都必须修复后才能交付原型。
 */
const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync } = require('child_process');

function loadJsdom() {
  try { return require('jsdom'); }
  catch (e) {
    const tmp = path.join(os.tmpdir(), 'proto_smoke_jsdom');
    console.log('  ⚠ jsdom 缺失，尝试安装到', tmp);
    try { execSync('npm install jsdom --prefix "' + tmp + '" --no-save --silent', { stdio: 'inherit' }); }
    catch (e2) { console.error('  ✗ jsdom 安装失败，请手动 npm install jsdom'); process.exit(1); }
    return require(path.join(tmp, 'node_modules', 'jsdom'));
  }
}
const { JSDOM, VirtualConsole } = loadJsdom();

const FILE = process.argv[2];
if (!FILE || !fs.existsSync(FILE)) { console.error('用法: node proto_smoke.js <原型.html>'); process.exit(2); }
const html = fs.readFileSync(FILE, 'utf8');

const errors = [];
const vc = new VirtualConsole();
vc.on('jsdomError', e => errors.push('jsdomError: ' + (e.stack || e.detail || e.message)));
vc.on('error', (...a) => errors.push('console.error: ' + a.join(' ')));

const dom = new JSDOM(html, {
  runScripts: 'dangerously',
  virtualConsole: vc,
  pretendToBeVisual: true,
  // 注入浏览器环境 shim，消除 jsdom 不支持项带来的误报（真实浏览器中均正常）：
  //  - window.confirm / alert / prompt：jsdom 未实现，原型用 confirm 做删除二次确认属正常
  //  - window.$ / window.toast：页面以 const 定义的助手，jsdom 内联 handler 作用域看不到，
  //    但真实浏览器中脚本级 const 对 inline handler 可见；这里补到 window 上避免误报
  beforeParse(window) {
    window.confirm = () => true;
    window.alert = () => {};
    window.prompt = () => '';
    window.$ = id => window.document.getElementById(id);
    window.toast = () => {};
  }
});
const { window } = dom;
const { document } = window;

let fails = 0;
const fail = m => { console.log('  ✗ ' + m); fails++; };
const ok = m => console.log('  ✓ ' + m);

const main = document.querySelector('main') || document.getElementById('mainArea');
if (!main) fail('未找到 <main> 布局容器（无法校验视图归属）');
const mainContains = el => { let p = el && el.parentElement; while (p) { if (p === main) return true; p = p.parentElement; } return false; };

// --- 提取 go() 视图映射 ---
function extractMap() {
  const m = html.match(/const\s+map\s*=\s*\{([\s\S]*?)\};/) || html.match(/map\s*=\s*\{([\s\S]*?)\};/);
  const map = {};
  if (m) {
    const re = /(\w+)\s*:\s*['"]([\w-]+)['"]/g; let x;
    while ((x = re.exec(m[1]))) map[x[1]] = x[2];
  }
  return map;
}
const map = extractMap();
const pageKeys = Object.keys(map);
const viewIds = [...new Set(Object.values(map))];

// 兜底：若解析不到 map，则用 id 形如 view* 的元素作为视图集合
if (viewIds.length === 0) {
  [...document.querySelectorAll('[id]')].forEach(e => { if (/^view/i.test(e.id)) viewIds.push(e.id); });
  [...html.matchAll(/go\(\s*['"]([\w-]+)['"]\s*\)/g)].forEach(x => { if (!pageKeys.includes(x[1])) pageKeys.push(x[1]); });
}

console.log('=== [A] 视图容器归属 <main> 校验（空白页根因） ===');
if (main) {
  const checkSet = new Set(viewIds);
  [...document.querySelectorAll('[id]')].forEach(e => { if (/view/i.test(e.id)) checkSet.add(e.id); });
  [...checkSet].forEach(v => {
    const el = document.getElementById(v);
    if (!el) { fail('视图 #' + v + ' 在 DOM 中不存在'); return; }
    if (mainContains(el)) ok('#' + v + ' 在 <main> 内');
    else fail('#' + v + ' 写在 </main> 之外 → 跳转后空白页');
  });
} else { /* 上面已 fail */ }

console.log('\n=== [B] go() 可达性 + 空白校验 ===');
if (typeof window.go === 'function' && pageKeys.length) {
  pageKeys.forEach(pk => {
    try { window.go(pk); }
    catch (e) { fail(`go('${pk}') 抛错: ${e.message}`); return; }
    const vid = map[pk] || null;
    if (!vid) { /* 无 map 时只校验"有视图可见" */ }
    const target = vid ? document.getElementById(vid) : null;
    const visible = [...document.querySelectorAll('[id]')].filter(e => /view/i.test(e.id) && !e.classList.contains('hidden'));
    const textLen = target ? (target.innerText || target.textContent || '').trim().length : 0;
    if (vid && target) {
      if (target.classList.contains('hidden')) fail(`go('${pk}') → #${vid} 仍隐藏（空白页）`);
      else if (textLen === 0) fail(`go('${pk}') → #${vid} 可见但无内容（空白页）`);
      else ok(`go('${pk}') → #${vid} 可见且有内容(${textLen})`);
    } else {
      if (visible.length === 0) fail(`go('${pk}') 后无任何视图可见（空白页）`);
      else ok(`go('${pk}') 后有 ${visible.length} 个视图可见`);
    }
  });
} else {
  console.log('  （未检测到 go() 导航函数，跳过可达性校验，仅做结构 + 点击校验）');
}

console.log('\n=== [C] 真实点击每个可交互元素（捕获 JS 运行期错误） ===');
const clickables = [...document.querySelectorAll('[onclick]')];
let clicked = 0, clickErr = 0;
clickables.forEach(el => {
  try { el.click(); clicked++; }
  catch (e) { clickErr++; fail(`点击 <${el.tagName}>#${el.id || ''} onclick="${el.getAttribute('onclick')}" 抛错: ${e.message}`); }
});
if (clickErr === 0) ok(`点击 ${clicked} 个可交互元素，无 JS 错误`);

console.log('\n=== [D] onclick 函数未定义扫描 ===');
const knownHelpers = new Set(['$', 'go', 'toast']);
const definedFns = new Set();
[...html.matchAll(/function\s+([A-Za-z_$][\w$]*)\s*\(/g)].forEach(x => definedFns.add(x[1]));
// window 上的全局函数（含函数声明提升）
try { Object.getOwnPropertyNames(window).forEach(n => { if (typeof window[n] === 'function') definedFns.add(n); }); } catch (e) {}
let undef = 0;
clickables.forEach(el => {
  const expr = el.getAttribute('onclick') || '';
  const fm = expr.match(/([A-Za-z_$][\w$]*)\s*\(/);
  if (fm && !definedFns.has(fm[1]) && !knownHelpers.has(fm[1])) { undef++; fail(`onclick 引用未定义函数 ${fm[1]} @ <${el.tagName}>#${el.id || ''}`); }
});
if (undef === 0) ok('所有 onclick 处理函数均已定义');

console.log('\n=== [E] JS 运行期错误汇总 ===');
if (errors.length) errors.forEach(e => fail(e)); else ok('无 JS 运行期错误');

console.log('\n=== [F] 表单选项去重 / 错漏校验 ===');
let dupCount = 0;
// F1: <select> 下拉选项去重
document.querySelectorAll('select').forEach(sel => {
  const opts = [...sel.options].filter(o => o.value !== ''); // 排除 placeholder
  const labels = opts.map(o => (o.textContent || '').trim());
  const seen = new Set();
  labels.forEach((lbl, i) => {
    if (seen.has(lbl)) {
      dupCount++;
      fail(`<select>#${sel.id || '(无id)'} 重复选项「${lbl}」(第 ${seen.size + 1} 次出现)`);
    }
    seen.add(lbl);
  });
});
// F2: radio group / checkbox label 去重
document.querySelectorAll('input[type=radio], input[type=checkbox]').forEach(el => {
  const name = el.getAttribute('name');
  if (!name) return;
  // 同 name 组内检查相邻 label 文本重复（简化：检查同组 label）
  const group = document.querySelectorAll(`input[name="${name}"]`);
  const labels = [...group].map(inp => {
    // 找关联 label：for 属性 或 父级 <label> 文本
    const forLabel = inp.id ? document.querySelector(`label[for="${inp.id}"]`) : null;
    if (forLabel) return (forLabel.textContent || '').trim();
    const parentLabel = inp.closest('label');
    if (parentLabel) return (parentLabel.textContent || '').replace(/[✓☐]\s*/, '').trim();
    return '';
  }).filter(Boolean);
  const seen = new Set();
  labels.forEach(lbl => {
    if (seen.has(lbl)) { dupCount++; fail(`radio/checkbox[name="${name}"] 重复标签「${lbl}」`); }
    seen.add(lbl);
  });
});
if (dupCount === 0) ok('所有下拉 / 单选 / 复选选项无重复');

console.log('\n' + (fails === 0 ? '✅ 冒烟测试全部通过，可交付' : `❌ 共 ${fails} 项不通过，禁止交付，先修复`));
process.exit(fails === 0 ? 0 : 1);
