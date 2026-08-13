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

console.log('\n=== [G] 交互逻辑反模式扫描（冒烟测不到的「结果正确性」硬伤） ===');
/* 背景：A~F 只验证「DOM 结构 / 跳转目标存在 / JS 不报错 / 函数已定义」，
   完全不验证「交互结果对不对」。本环节专门卡住三类曾漏过的真 bug：
   G1 数值累加函数定义了却从不调用（如虎力值永远不变）
   G2 完成/跳转用 Math.random() 决定（详情页随机跳、完成态随机化）
   G3 完成处理器只翻显示态、不碰真实任务数据（假完成，状态互相脱钩） */
let gwarn = 0;
const accKw = 'HuLi|huli|Tiger|tiger|Value|value|Score|score|Point|point|Coin|coin|Energy|energy|Exp|exp';
const accDefRe = new RegExp('(?:function\\s+(\\w*(?:' + accKw + ')\\w*)\\s*\\(|const\\s+(\\w*(?:' + accKw + ')\\w*)\\s*=\\s*(?:function|\\([^)]*\\)\\s*=>))', 'g');
const accDefs = [];
let am;
while ((am = accDefRe.exec(html))) accDefs.push(am[1] || am[2]);
if (accDefs.length === 0) console.log('  （未检测到数值/积分累加函数，跳过 G1）');
else accDefs.forEach(name => {
  const callRe = new RegExp('\\b' + name + '\\s*\\(', 'g');
  const calls = [...html.matchAll(callRe)];
  const realCalls = calls.filter(c => {
    const before = html.slice(Math.max(0, c.index - 30), c.index).trim();
    return !/((?:function|const|let|var|=>)\s*)$/.test(before);
  });
  if (realCalls.length === 0) { fails++; console.log('  ✗ [G1] 数值累加函数 ' + name + '() 已定义但从未被调用 → 数值永远不更新（如虎力值/积分始终不变）'); }
  else ok('[G1] 累加函数 ' + name + '() 有 ' + realCalls.length + ' 处真实调用');
});

const randAll = [...html.matchAll(/Math\.random\(\)/g)];
if (randAll.length === 0) console.log('  （无 Math.random()，跳过 G2）');
else {
  let randBad = 0;
  randAll.forEach(r => {
    // 仅当 random 被用于「阈值比较决定分支」（如 Math.random() > 0.7 决定跳不跳详情/完没完成）才视为反模式；
    // 纯洗牌（Math.random() - 0.5 用于 sort）不算，那是合法的随机展示
    const isThreshold = /Math\.random\(\)\s*[<>]=?\s*[\d.]/.test(html.slice(r.index, r.index + 60));
    const before = html.slice(Math.max(0, r.index - 400), r.index);
    const inHandler = /(onclick=|function\s+\w*(?:complete|finish|done|record|submit|claim|check|mark|go|navigate|task|detail)\w*\s*\()/i.test(before);
    if (isThreshold && inHandler) {
      randBad++; fails++;
      console.log('  ✗ [G2] 完成/跳转逻辑中用 Math.random() 阈值比较决定分支（详情跳转/完成态随机化），必须确定性（固定某类任务才有详情页）');
    }
  });
  if (randBad === 0) ok('Math.random() 共 ' + randAll.length + ' 处，均无「阈值比较决定分支」用法，安全（随机洗牌展示除外）');
}

const dataArrRe = /myTasks|completedToday|tasks\b|taskList|doneList|selectedTasks|state\.tasks|store\.tasks/i;
const compFns = [...html.matchAll(/function\s+(\w*(?:complete|finish|done|record|submit|claim|check|mark|task)\w*)\s*\(/gi)].map(x => x[1]);
if (compFns.length === 0) console.log('  （未检测到完成类函数，跳过 G3）');
else {
  let fakeWarn = 0;
  compFns.forEach(fn => {
    const start = html.search(new RegExp('function\\s+' + fn + '\\s*\\('));
    if (start < 0) return;
    const end = html.indexOf('function', start + 10);
    const body = html.slice(start, end < 0 ? start + 1500 : end);
    const flipsDisplay = /State\s*=\s*[0-9]|classList\.(add|remove|toggle)\(\s*['"]?(?:done|active|completed|finished)/.test(body);
    const touchesData = dataArrRe.test(body) || /complete(?:Task|HTask|ById|TaskById)\s*\(/.test(body);
    if (flipsDisplay && !touchesData) { fakeWarn++; gwarn++; console.log('  ⚠ [G3] 完成处理器 ' + fn + '() 翻转了显示态但未触及真实任务数据 → 疑似「假完成」，请人工核对 C24/C25'); }
  });
  if (fakeWarn === 0) ok('完成类函数均触及真实任务数据（无假完成）');
}

console.log('\n=== [H] 引用完整性 / dead-reference 扫描（防「脚本过期漏检」与「删定义留调用/样式」三类回归） ===');
/* 背景：本次（睡眠任务闭环 v7）迭代实测踩中三类真 bug——
   R1 点击穿透脚本断言的是历史旧 id，与原型对不上 → 测试假通过/假失败，漏检真交互
   R2 删了函数定义却残留调用（如 renderHuli()）→ 运行期 ReferenceError，主流程弹窗弹不出
   R3 删了 CSS 类定义却残留 class 引用（如 .huli-btn）→ 按钮样式崩
   本环节把「人工同步 Step / 人工核对」升级成机器门禁：
   H1 = 点击穿透脚本引用的元素 id 必须在原型中存在（否则该 Step 会 null 崩溃，正是 R1）
   H2 = 原型脚本调用的函数必须已定义（否则 ReferenceError，正是 R2）
   H3 = 原型使用的组件类必须在 <style> 有规则（否则样式崩，正是 R3，WARN 不阻断）
   [H1][H2] 为 BLOCKER（计入 fails），[H3] 为 WARN（计入 gwarn）。 */

// --- [H1] 点击穿透脚本 ↔ 原型 元素 id 一致性 ---
const CT_PATH = process.argv[3] || path.join(__dirname, 'proto_clickthrough_client.js');
if (fs.existsSync(CT_PATH)) {
  const ctText = fs.readFileSync(CT_PATH, 'utf8');
  const ctAnchors = new Set();
  [...ctText.matchAll(/['"`]#([\w-]+)/g)].forEach(m => ctAnchors.add(m[1]));
  [...ctText.matchAll(/getElementById\(\s*['"]([\w-]+)['"]\s*\)/g)].forEach(m => ctAnchors.add(m[1]));
  if (ctAnchors.size === 0) {
    console.log('  （点击穿透脚本未检出 #id 选择器，跳过 H1）');
  } else {
    let h1bad = 0;
    [...ctAnchors].forEach(id => {
      const el = document.getElementById(id) || document.querySelector('[data-page="' + id + '"]');
      if (!el) { h1bad++; fail('[H1] 点击穿透脚本引用 #' + id + '，原型中不存在该元素 → 该 Step 会 null 崩溃（R1 根因）'); }
    });
    // 反向覆盖：原型每个 .page 是否被点击穿透脚本覆盖
    let uncovered = 0;
    pageIds.forEach(pid => {
      const covered = ctText.includes("'" + pid + "'") || ctText.includes('"' + pid + '"') || ctText.includes('#' + pid);
      if (!covered) { uncovered++; gwarn++; console.log('  ⚠ [H1] 原型页面 #' + pid + ' 未被点击穿透脚本覆盖（无 go/选择器引用）→ 可能漏测，请补 Step'); }
    });
    if (h1bad === 0) ok('[H1] 点击穿透脚本引用的 ' + ctAnchors.size + ' 个元素 id 均存在于原型（无 dead selector）');
    if (uncovered === 0) ok('[H1] 原型全部 ' + pageIds.length + ' 个页面均被点击穿透脚本覆盖');
  }
} else {
  console.log('  （未找到点击穿透脚本 ' + CT_PATH + '，跳过 H1；可传 argv[3] 指定）');
}

// --- [H2] 原型脚本调用函数未定义扫描（dead reference） ---
const scriptText = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/gi)].map(m => m[1]).join('\n');
if (scriptText.trim()) {
  // 先剥离注释，避免注释里的 "page (" / "stop-propagation (" 等被误判为函数调用
  const scriptStripped = scriptText
    .replace(/\/\*[\s\S]*?\*\//g, ' ')
    .replace(/\/\/[^\n]*/g, ' ');
  const jsDefs = new Set([...scriptStripped.matchAll(/function\s+([A-Za-z_$][\w$]*)\s*\(/g)].map(m => m[1]));
  [...scriptStripped.matchAll(/(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:function|\([^)]*\)\s*=>)/g)].forEach(m => jsDefs.add(m[1]));
  const jsBuiltins = new Set(['go','toast','taskById','$','console','Math','Set','Map','Array','Object','JSON','String','Number','Boolean','Date','RegExp','Error','Promise','parseInt','parseFloat','isNaN','setTimeout','clearTimeout','setInterval','clearInterval','requestAnimationFrame','encodeURI','decodeURI','eval','window','document','alert','confirm','prompt','Function','Symbol','Proxy','Reflect']);
  const jsKw = new Set(['if','for','while','switch','catch','function','return','typeof','new','do','else','await','throw','void','delete','in','of','with','case','default','yield','class','extends','super','this','finally','try','break','continue']);
  const jsCalls = [...scriptStripped.matchAll(/(?<![.\w$])(\w+)\s*\(/g)].map(m => m[1]);
  const deadCalls = new Set();
  jsCalls.forEach(n => {
    if (jsBuiltins.has(n) || jsDefs.has(n) || jsKw.has(n)) return;
    deadCalls.add(n);
  });
  if (deadCalls.size === 0) ok('[H2] 原型脚本调用的函数均已定义（无 dead reference，防 R2）');
  else [...deadCalls].forEach(n => fail('[H2] 原型脚本调用了未定义函数 ' + n + '() → 运行期 ReferenceError（R2 根因，删定义须同步删调用）'));
} else {
  console.log('  （原型未检出 <script>，跳过 H2）');
}

// --- [H3] 组件类样式缺失扫描（WARN，防 R3） ---
const styleText = [...html.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/gi)].map(m => m[1]).join('\n');
const styleClasses = new Set([...styleText.matchAll(/\.([\w-]+)/g)].map(m => m[1]));
const usedClasses = new Set([...html.matchAll(/class\s*=\s*["']([^"']*)["']/gi)].flatMap(m => m[1].split(/\s+/).filter(Boolean)));
[...html.matchAll(/classList\.(?:add|remove|toggle)\(\s*['"]([\w-]+)['"]/g)].forEach(m => usedClasses.add(m[1]));
const H3_STATE_DENY = new Set(['active','done','selected','hidden','none','block','blue','green','disabled','show','open','close','on','off','first','last','current','error','focus','hover','empty','full','half','loading','checked']);
const H3_COMP = /-(?:btn|card|item|header|tab|list|badge|chip|bar|sheet|modal|overlay|page|field|tag|pill|section|content|container|stack|wrap|title|meta|score|reward|cta|action|row|cell|box|panel|nav|menu|icon|mask|layer|footer|body|head)$/;
let h3warn = 0;
[...usedClasses].forEach(c => {
  if (H3_STATE_DENY.has(c) || styleClasses.has(c)) return;
  if (H3_COMP.test(c) || /^(?:btn|card|tab|list|page|overlay|modal|sheet)-/.test(c)) {
    h3warn++; gwarn++; console.log('  ⚠ [H3] 组件类 .' + c + ' 被使用但 <style> 无对应规则 → 可能样式崩（R3 根因，删样式须同步删 class）');
  }
});
if (h3warn === 0) ok('[H3] 原型使用的组件类均能在 <style> 找到规则（无 dead 样式，WARN）');

console.log('\n' + (fails === 0 ? '✅ 冒烟测试全部通过（含 [A]–[H] 八段扫描），可交付' : `❌ 共 ${fails} 项不通过，禁止交付，先修复`));
if (gwarn > 0) console.log(`⚠ 另有 ${gwarn} 处逻辑警告（[G3]），交付前必须人工核对 checklist C24/C25 确认非假完成`);
process.exit(fails === 0 ? 0 : 1);
