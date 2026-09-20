// clickthrough-template.js  (proto-c skill · 复制为 <项目>-clickthrough.js 放在原型同目录)
// ============================================================
// @proto "<你的原型.html>"      ← 必填：声明本脚本归属哪个原型文件（写 basename 即可）
//
// 真实点击穿透测试：jsdom 加载原型，模拟真人「逐个点击每个交互入口」并断言状态真的变了——
// 页面是否切换、弹窗是否出现、数值是否 +N、状态是否联动。这是冒烟测试（只查「点一下不报错」）
// 和 [G] 逻辑扫描（只查「写法反模式」）都查不出的「交互结果正确性」最后一道关。
//
// 用法（jsdom 在 node 全局或 workspace node_modules 中）：
//   NODE_PATH="<node_modules>" <node> <本文件> <原型.html>
// 退出码：0 = 全过；非 0 = 有死交互 / 状态不联动，禁止交付。
//
// 维护：新增任何交互入口（新页面 / 新按钮 / 新 Tab）时，务必在本文件补对应 Step 的「点击 + assert」，
//       否则 proto_smoke_client.js 的 [H1] 会报「该页面未被点击穿透脚本覆盖」强制你补 Step。
//
// 自动发现：proto_smoke_client.js 的 [H1] 会自动扫描原型同目录下的 *-clickthrough.js，
//           并按本文件头部的 @proto 声明归属该原型，校验其引用的每个 #id 在原型中真实存在
//           （防 R1：点击穿透脚本过期引用旧 id → 测试假通过 / null 崩溃）。
// ============================================================
const fs = require('fs');
const { JSDOM } = require('jsdom');

const file = process.argv[2];
if (!file) { console.error('用法: node <本文件> <原型.html>'); process.exit(2); }
const html = fs.readFileSync(file, 'utf-8');

const dom = new JSDOM(html, {
  runScripts: 'dangerously',
  pretendToBeVisual: true,
  url: 'http://localhost/'
});
const { window } = dom;
const doc = window.document;

let pass = 0, fail = 0;
const fails = [];
function assert(cond, msg) {
  if (cond) { pass++; console.log('  ✓ ' + msg); }
  else { fail++; fails.push(msg); console.log('  ✗ ' + msg); }
}
const wait = (ms) => new Promise(r => setTimeout(r, ms));
function activePage() {
  const p = doc.querySelector('.page.active');
  return p ? p.id : '(none)';
}
function clickSel(sel) {
  const el = doc.querySelector(sel);
  if (!el) { console.log('    [未找到] ' + sel); return false; }
  el.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true }));
  return true;
}
function clickEl(el) {
  if (!el) { console.log('    [元素为空，跳过点击]'); return false; }
  el.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true }));
  return true;
}
function clickAll(sel) {
  const els = [...doc.querySelectorAll(sel)];
  els.forEach(e => e.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true })));
  return els.length;
}
function text(sel) {
  const el = doc.querySelector(sel);
  return el ? el.textContent.trim() : null;
}
function visible(sel) {
  const el = doc.querySelector(sel);
  if (!el) return false;
  if (el.classList && el.classList.contains('active')) return true;
  const s = el.style.display;
  return s !== 'none' && s !== '';
}

async function run() {
  console.log('=== 真实点击穿透测试 ===');
  console.log('文件: ' + file + '\n');
  await wait(80);

  // ---- 在此按真实用户路径补充 Step，每个 Step = 一次「点击入口 + 断言目标态」 ----
  // 书写约定：
  //   · 页面切换：clickSel('#入口') → await wait(60) → assert(activePage() === 'pageXxx', '...')
  //   · 弹窗出现：assert(visible('#modalXxx'), '...')
  //   · 数值联动：先取 before = text('#num')，点击，await wait，再取 after 断言变化
  // 例（请删除）：
  // console.log('[Step 1] 进入购买页');
  // clickSel('#newcomerGift .gen-btn');
  // await wait(60);
  // assert(activePage() === 'pageQuotaBuy', '点击后进入 pageQuotaBuy (实=' + activePage() + ')');

  console.log('\n=== 结果: ' + pass + ' 通过 / ' + fail + ' 失败 ===');
  if (fail > 0) {
    console.log('失败项:');
    fails.forEach(f => console.log('  - ' + f));
    process.exit(1);
  } else {
    console.log('✅ 点击穿透测试全部通过');
    process.exit(0);
  }
}
run().catch(e => { console.error('测试运行异常:', e); process.exit(2); });
