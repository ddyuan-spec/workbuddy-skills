// proto_clickthrough_client.js  (proto-c skill · PROTO-SMK-006)
// 真实点击穿透测试：用 jsdom 加载原型，模拟真人「点击每个按钮」并断言状态真的变了——
// 虎力值有无累加、任务卡片有无打勾、页面有无切换、弹窗有无出现、入口卡片/顶部Tab有无死交互。
// 这是冒烟测试(A~F)与[G]逻辑扫描都查不出的「交互结果正确性」最后一道关：
//   冒烟只查「点一下不报错」，[G]只查「写法反模式」；本测试查「点完之后对不对」。
//
// 用法（jsdom 在 node 全局/workspace node_modules 中）：
//   NODE_PATH="<node_modules>" <node> references/proto_clickthrough_client.js <原型.html>
// 退出码 0 = 全过；非 0 = 有死交互或状态不联动，禁止交付。
//
// 维护：新增交互入口（如新页面/新按钮）时，务必在本文件补充对应 Step 的点击+断言。
const fs = require('fs');
const { JSDOM } = require('jsdom');

const file = process.argv[2];
if (!file) { console.error('用法: node proto_clickthrough_client.js <原型.html>'); process.exit(2); }
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
function overlayVisible() {
  const o = doc.querySelector('.overlay.active');
  return o ? o.id : null;
}
function click(el) {
  if (!el) return false;
  el.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true }));
  return true;
}
function clickSel(sel) {
  const el = doc.querySelector(sel);
  if (!el) { console.log('    [未找到] ' + sel); return false; }
  return click(el);
}
function clickAll(sel) {
  const els = [...doc.querySelectorAll(sel)];
  els.forEach(e => click(e));
  return els.length;
}
function text(sel) {
  const el = doc.querySelector(sel);
  return el ? el.textContent.trim() : null;
}
function exists(sel) { return !!doc.querySelector(sel); }

async function run() {
  console.log('=== 真实点击穿透测试 ===');
  console.log('文件: ' + file + '\n');
  await wait(100);

  // ---- Step 0: 初始状态 ----
  console.log('[Step 0] 初始状态');
  assert(text('#home-task-title') === '领取任务开启健康打卡', '首页任务卡初始文案正确 (实=' + text('#home-task-title') + ')');
  assert(activePage() === 'page-notification', '首屏=消息通知 (实=' + activePage() + ')');
  assert(doc.querySelectorAll('#page-notification .notification-item').length >= 2, '消息列表>=2条');

  // ---- Step 1: 点泰小虎推送 → 进首页 ----
  console.log('[Step 1] 点泰小虎推送通知');
  clickAll('#page-notification .notification-item');
  await wait(100);
  assert(activePage() === 'page-home', '点击后进入首页 (实=' + activePage() + ')');

  // ---- Step 2: 首页日报弹窗「立即查看」→ 我的睡眠 ----
  console.log('[Step 2] 点首页弹窗「立即查看」');
  // daily report modal should auto-show on first home entry
  assert(overlayVisible() === 'overlay-daily-report', '首页自动弹出日报弹窗');
  clickSel('#overlay-daily-report .btn-blue');
  await wait(100);
  assert(overlayVisible() === null, '弹窗关闭');
  assert(activePage() === 'page-sleep', '进入我的睡眠 (实=' + activePage() + ')');

  // ---- Step 3: 我的睡眠「去领取」→ 领取任务页 ----
  console.log('[Step 3] 我的睡眠「去领取」');
  assert(text('#sleep-task-btn') === '去领取', '睡眠按钮=去领取 (实=' + text('#sleep-task-btn') + ')');
  clickSel('#sleep-task-banner');
  await wait(100);
  assert(activePage() === 'page-claim', '进入领取任务页 (实=' + activePage() + ')');

  // ---- Step 4: 领取页渲染 ----
  console.log('[Step 4] 领取任务页渲染');
  const claimItems = doc.querySelectorAll('#claim-list .claim-item');
  assert(claimItems.length === 5, '领取页渲染5个任务 (实=' + claimItems.length + ')');
  const preSelected = doc.querySelectorAll('#claim-list .claim-item.selected').length;
  assert(preSelected >= 0 && preSelected < 5, '预选数量合理(0-4个) (实=' + preSelected + ')');
  assert(/已选 \d+ 个/.test(text('#claim-confirm')), '底部按钮显示已选计数 (实=' + text('#claim-confirm') + ')');

  // ---- Step 5: 全选并提交 ----
  console.log('[Step 5] 全选并提交');
  doc.querySelectorAll('#claim-list .claim-item:not(.selected)').forEach(e => click(e));
  await wait(50);
  const allSel = doc.querySelectorAll('#claim-list .claim-item.selected').length;
  assert(allSel === 5, '全选后5个均选中 (实=' + allSel + ')');
  clickSel('#claim-confirm');
  await wait(100);
  assert(activePage() === 'page-tasks', '提交后进入健康打卡 (实=' + activePage() + ')');
  const htCards = doc.querySelectorAll('#tasks-content .task-item');
  assert(htCards.length === 5, '健康打卡列表填充5个任务 (实=' + htCards.length + ')');

  // ---- Step 6: 点任务卡片直接完成 → 虎力值+ ----
  console.log('[Step 6] 点任务卡片完成(非详情任务)');
  const before = window.STATE.huLi;
  const undoneIds = window.STATE.myTasks.filter(id => !window.STATE.completedToday.includes(id));
  const nonDetailId = undoneIds.find(id => {
    const t = window.taskById(id);
    return t && !t.hasDetail;
  });
  assert(!!nonDetailId, '存在未完成的非详情任务');
  const nonDetailIndex = window.STATE.myTasks.indexOf(nonDetailId);
  const cards = doc.querySelectorAll('#tasks-content .task-item');
  const targetCard = cards[nonDetailIndex];
  assert(!!targetCard, '找到非详情任务对应的卡片');
  click(targetCard);
  await wait(400);
  const after = window.STATE.huLi;
  assert(after > before, '虎力值累加 (' + before + ' → ' + after + ')');
  assert(doc.querySelectorAll('#tasks-content .task-item.done').length >= 1, '至少1张卡片变已完成态');

  // ---- Step 7: 完成剩余全部 → 太棒了弹窗 ----
  console.log('[Step 7] 完成全部 → 太棒了弹窗');
  let guard = 0;
  while (doc.querySelector('#tasks-content .task-item:not(.done)') && guard < 20) {
    const card = doc.querySelector('#tasks-content .task-item:not(.done)');
    const undoneId = window.STATE.myTasks.find(id => !window.STATE.completedToday.includes(id));
    const t = window.taskById(undoneId);
    if (t && t.hasDetail) {
      click(card);
      await wait(100);
      clickSel('#page-detail .btn-block');
      await wait(400);
    } else {
      click(card);
      await wait(350);
    }
    guard++;
  }
  await wait(600);
  assert(overlayVisible() === 'overlay-completion', '全部完成→「太棒了」弹窗出现 (实=' + overlayVisible() + ')');

  // ---- Step 8: 分享面板 ----
  console.log('[Step 8] 分享面板');
  clickSel('#overlay-completion .btn-green');
  await wait(100);
  assert(overlayVisible() === 'overlay-share', '分享面板弹出 (实=' + overlayVisible() + ')');
  clickSel('#overlay-share .cancel');
  await wait(100);
  assert(overlayVisible() === null, '取消后分享面板收起');

  // ---- Step 9: 首页无任务态卡片点击(关键回归点) ----
  console.log('[Step 9] 首页无任务态卡片点击(关键回归点)');
  window.STATE.myTasks = [];
  window.STATE.completedToday = [];
  window.STATE.dailyReportShown = true;
  window.STATE.completionShown = false;
  window.go('page-home');
  await wait(100);
  assert(text('#home-task-title') === '领取任务开启健康打卡', '重置后首页回到无任务态');
  const card = doc.querySelector('#home-task-card');
  const hadHandler = card.onclick !== null || card.getAttribute('onclick');
  click(card);
  await wait(100);
  assert(hadHandler && activePage() === 'page-claim', '无任务态点卡片→进入领取任务页 (handler=' + hadHandler + ', 页=' + activePage() + ')');

  // ---- Step 10: 首页「健康」Tab 切换 ----
  console.log('[Step 10] 首页「健康」Tab 切换');
  window.go('page-home');
  await wait(50);
  const healthTab = doc.querySelector('#page-home .tabs .tab');
  click(healthTab);
  await wait(100);
  assert(activePage() === 'page-sleep', '点「健康」Tab→进入健康页(sleep) (实=' + activePage() + ')');

  // ---- Step 11: 我的睡眠/健康打卡子Tab互跳 ----
  console.log('[Step 11] 子Tab互跳');
  window.go('page-sleep');
  await wait(50);
  clickSel('#page-sleep .sub-tabs .tab:nth-child(3)');
  await wait(100);
  assert(activePage() === 'page-tasks', '睡眠页点「健康打卡」→进入健康打卡 (实=' + activePage() + ')');
  clickSel('#page-tasks .sub-tabs .tab:nth-child(2)');
  await wait(100);
  assert(activePage() === 'page-sleep', '健康打卡点「我的睡眠」→进入我的睡眠 (实=' + activePage() + ')');

  // ---- Step 12: 详情任务跳转 & 完成 ----
  console.log('[Step 12] 详情任务跳转并完成');
  // force a detail task into active list
  window.STATE.myTasks = ['t7'];
  window.STATE.completedToday = [];
  window.go('page-tasks');
  await wait(100);
  const detailCard = doc.querySelector('#tasks-content .task-item:not(.done)');
  assert(!!detailCard, '详情任务卡片存在');
  assert(window.taskById('t7').hasDetail, 't7 是详情任务');
  click(detailCard);
  await wait(100);
  assert(activePage() === 'page-detail', '点详情任务→进入任务详情 (实=' + activePage() + ')');
  clickSel('#page-detail .btn-block');
  await wait(400);
  assert(window.STATE.completedToday.includes('t7'), '参与后任务标记完成');
  assert(window.STATE.huLi >= 5, '详情任务奖励生效 (huLi=' + window.STATE.huLi + ')');

  // ---- Step 13: 添加自定义任务入口 ----
  console.log('[Step 13] 添加自定义任务入口');
  window.go('page-tasks');
  await wait(50);
  const customBtn = [...doc.querySelectorAll('#tasks-content button')].find(b => b.textContent.includes('添加自定义任务'));
  assert(!!customBtn, '存在「添加自定义任务」按钮');
  click(customBtn);
  await wait(100);
  assert(activePage() === 'page-custom', '进入添加自定义任务页 (实=' + activePage() + ')');
  clickSel('#page-custom .btn-blue');
  await wait(100);
  assert(activePage() === 'page-tasks', '返回→健康打卡 (实=' + activePage() + ')');

  // ---- Step 14: 赚取更多虎力值入口 ----
  console.log('[Step 14] 赚取更多虎力值入口');
  window.STATE.myTasks = ['t1','t2'];
  window.STATE.completedToday = ['t1','t2'];
  window.go('page-tasks');
  await wait(100);
  const huliBtn = [...doc.querySelectorAll('#tasks-content button')].find(b => b.textContent.includes('赚取更多虎力值'));
  assert(!!huliBtn, '全部完成后显示「赚取更多虎力值」按钮');
  click(huliBtn);
  await wait(100);
  assert(activePage() === 'page-tasks', '点击后不跳转(仍在健康打卡页) (实=' + activePage() + ')');
  const toastEl = doc.getElementById('toast');
  assert(toastEl && toastEl.style.display === 'block' && toastEl.textContent.includes('虎力值'), '弹出跳转虎力值任务页提示 (实=' + (toastEl ? toastEl.textContent : '无') + ')');

  // ---- 汇总 ----
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
