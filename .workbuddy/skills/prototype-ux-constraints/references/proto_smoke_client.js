/**
 * proto_smoke_client.js — C 端（App / 小程序 / H5）原型自动化冒烟测试
 *
 * 后台原型用 proto_smoke.js（view/main 结构）。C 端原型用 .phone 外壳 + .page 容器切换，
 * 没有 <main> 与 view* 独立页，故本脚本做结构适配：
 *   1) [A] 所有 .page 必须在某个 .phone 容器内（视图归属，避免写在壳外导致异常）
 *   2) [B] go('p_xxx') 目标页面切换为 active 且非空（空白页校验）
 *   3) [C] 真实点击每个可交互元素，捕获 JS 运行期错误
 *   4) [D] onclick 引用的函数必须已定义
 *   5) [E] JS 运行期错误汇总（virtualConsole）
 *   6) [F] 表单选项去重 / 错漏校验（select / radio / checkbox）
 *
 * 用法（在原型所在目录执行）：
 *   NODE_PATH="<jsdom 所在 node_modules>" node proto_smoke_client.js <原型.html>
 * 例：
 *   NODE_PATH="C:\Users\13364\.workbuddy\binaries\node\workspace/node_modules" "C:\Users\13364\.workbuddy\binaries\node\versions\22.22.2\node.exe" proto_smoke_client.js App端原型.html
 *
 * 退出码：0=全部通过；1=有失败项；2=参数错误。
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
if (!FILE || !fs.existsSync(FILE)) { console.error('用法: node proto_smoke_client.js <原型.html>'); process.exit(2); }
const html = fs.readFileSync(FILE, 'utf8');

const errors = [];
const vc = new VirtualConsole();
vc.on('jsdomError', e => errors.push('jsdomError: ' + (e.stack || e.detail || e.message)));
vc.on('error', (...a) => errors.push('console.error: ' + a.join(' ')));

const dom = new JSDOM(html, {
  runScripts: 'dangerously',
  virtualConsole: vc,
  pretendToBeVisual: true,
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

// --- 提取 go() 页面集合 ---
const pageKeys = [...new Set([...html.matchAll(/go\(\s*['"]([\w-]+)['"]\s*\)/g)].map(x => x[1]))];
const pageIds = [...new Set([...document.querySelectorAll('.page')].map(p => p.id))];

console.log('=== [A] 页面容器归属 .phone 校验 ===');
const phones = [...document.querySelectorAll('.phone')];
if (phones.length === 0) {
  // 无 .phone 壳也允许（裸页面），跳过归属
  console.log('  （未检测到 .phone 外壳，跳过归属校验）');
} else {
  pageIds.forEach(pid => {
    const el = document.getElementById(pid);
    if (!el) { fail('页面 #' + pid + ' 在 DOM 中不存在'); return; }
    let p = el.parentElement, inPhone = false;
    while (p) { if (p.classList && p.classList.contains('phone')) { inPhone = true; break; } p = p.parentElement; }
    if (inPhone) ok('#' + pid + ' 在 .phone 容器内');
    else fail('#' + pid + ' 写在 .phone 外壳之外 → 可能渲染异常');
  });
}

console.log('\n=== [B] go() 可达性 + 空白校验 ===');
if (typeof window.go === 'function' && pageKeys.length) {
  pageKeys.forEach(pk => {
    try { window.go(pk); }
    catch (e) { fail(`go('${pk}') 抛错: ${e.message}`); return; }
    const target = document.getElementById(pk);
    if (!target) { fail(`go('${pk}') → #${pk} 不存在`); return; }
    const active = target.classList.contains('active') || target.style.display !== 'none';
    const textLen = (target.innerText || target.textContent || '').trim().length;
    if (!active) fail(`go('${pk}') → #${pk} 未激活（空白页）`);
    else if (textLen === 0) fail(`go('${pk}') → #${pk} 激活但无内容（空白页）`);
    else ok(`go('${pk}') → #${pk} 可见且有内容(${textLen})`);
  });
} else {
  console.log('  （未检测到 go() 导航函数或页面，仅做结构 + 点击校验）');
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
document.querySelectorAll('select').forEach(sel => {
  const opts = [...sel.options].filter(o => o.value !== '');
  const labels = opts.map(o => (o.textContent || '').trim());
  const seen = new Set();
  labels.forEach(lbl => {
    if (seen.has(lbl)) { dupCount++; fail(`<select>#${sel.id || '(无id)'} 重复选项「${lbl}」`); }
    seen.add(lbl);
  });
});
document.querySelectorAll('input[type=radio], input[type=checkbox]').forEach(el => {
  const name = el.getAttribute('name');
  if (!name) return;
  const group = document.querySelectorAll(`input[name="${name}"]`);
  const labels = [...group].map(inp => {
    const forLabel = inp.id ? document.querySelector(`label[for="${inp.id}"]`) : null;
    if (forLabel) return (forLabel.textContent || '').trim();
    const parentLabel = inp.closest('label');
    if (parentLabel) return (parentLabel.textContent || '').replace(/[✓☐]\s*/, '').trim();
    return '';
  }).filter(Boolean);
  const seen = new Set();
  labels.forEach(lbl => { if (seen.has(lbl)) { dupCount++; fail(`radio/checkbox[name="${name}"] 重复标签「${lbl}」`); } seen.add(lbl); });
});
if (dupCount === 0) ok('所有下拉 / 单选 / 复选选项无重复');

console.log('\n' + (fails === 0 ? '✅ 冒烟测试全部通过，可交付' : `❌ 共 ${fails} 项不通过，禁止交付，先修复`));
process.exit(fails === 0 ? 0 : 1);
