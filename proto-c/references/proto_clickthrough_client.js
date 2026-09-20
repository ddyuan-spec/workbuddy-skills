// proto_clickthrough_client.js  (proto-c skill · PROTO-SMK-006)
// 真实点击穿透测试：用 jsdom 加载原型，模拟真人「点击每个按钮」并断言状态真的变了——
// 虎力值/待发放虎力值有无累加、任务卡片有无打勾、页面有无切换、弹窗有无出现、入口卡片/顶部Tab有无死交互。
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
  // 返回最上层 active overlay（DOM 中靠后的覆盖前者）
  const o = [...doc.querySelectorAll('.overlay.active')].pop();
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
  assert(text('#home-task-title') === '开启健康打卡', '首页任务卡初始文案正确 (实=' + text('#home-task-title') + ')');
  assert(activePage() === 'page-notification', '首屏=消息通知 (实=' + activePage() + ')');
  const notis = doc.querySelectorAll('#page-notification .notification-item');
  assert(notis.length >= 5, '消息列表含微信+4条泰小虎分支 (实=' + notis.length + ')');

  // ---- Step 1: 点分支A（有睡眠数据）→ 进首页 ----
  console.log('[Step 1] 点泰小虎推送通知（分支A：有睡眠数据）');
  const branchA = notis[1];
  assert(branchA.textContent.trim().includes('早安，昨晚你睡了'), '分支A为睡眠日报PUSH');
  click(branchA);
  await wait(100);
  assert(activePage() === 'page-home', '分支A点击后进入首页 (实=' + activePage() + ')');

  // ---- Step 2: 首页日报弹窗「立即查看」→ 我的睡眠 ----
  console.log('[Step 2] 点首页弹窗「立即查看」');
  assert(overlayVisible() === 'overlay-daily-report', '首页自动弹出日报弹窗');
  clickSel('#overlay-daily-report .btn-blue');
  await wait(100);
  assert(overlayVisible() === null, '弹窗关闭');
  assert(activePage() === 'page-sleep', '进入我的睡眠 (实=' + activePage() + ')');

  // ---- Step 3: 我的睡眠「去开启健康打卡」→ 领取任务页 ----
  console.log('[Step 3] 我的睡眠「去开启健康打卡」');
  assert(text('#sleep-task-btn') === '去开启健康打卡', '睡眠按钮=去开启健康打卡 (实=' + text('#sleep-task-btn') + ')');
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

  // ---- Step 5b: 健康打卡页常态显示统计条，点击进独立日历页 ----
  console.log('[Step 5b] 健康打卡页统计条 + 进日历页 + 月份切换');
  assert(!exists('#calendar-card .calendar-header'), '健康打卡页默认不展示日历');
  const statsBar = doc.querySelector('#page-tasks #task-stats-bar');
  assert(!!statsBar, '健康打卡页存在常态统计条');
  const totalText = text('#bar-total');
  const streakText = text('#bar-streak');
  assert(totalText && +totalText >= 0, '统计条显示累计打卡天数 (实=' + totalText + ')');
  assert(streakText && +streakText >= 0, '统计条显示连续打卡天数 (实=' + streakText + ')');
  click(statsBar);
  await wait(80);
  assert(activePage() === 'page-calendar', '点击统计条进入每日打卡独立页 (实=' + activePage() + ')');
  const calTitle = text('.calendar-header .title');
  assert(calTitle && calTitle.includes('每日打卡'), '日历页标题为每日打卡 (实=' + calTitle + ')');
  const calSubtitle = text('.calendar-header .subtitle');
  assert(calSubtitle && calSubtitle.includes('连续打卡') && calSubtitle.includes('累计打卡'), '日历页副标题含统计 (实=' + calSubtitle + ')');
  assert(exists('.calendar-nav'), '日历页月份切换器渲染');
  assert(exists('.calendar-day.today'), '今天日期高亮');
  // 月份切换
  const monthBefore = text('.calendar-nav span');
  const nextArrow = doc.querySelector('.calendar-nav .arrow:last-child');
  click(nextArrow);
  await wait(60);
  const monthAfter = text('.calendar-nav span');
  assert(monthAfter && monthAfter !== monthBefore, '点击右箭头切换月份 (前=' + monthBefore + ' 后=' + monthAfter + ')');
  // 返回健康打卡页继续后续流程
  const calMenu = doc.querySelector('#page-calendar .app-header .menu');
  click(calMenu);
  await wait(80);
  assert(activePage() === 'page-tasks', '从日历页返回健康打卡 (实=' + activePage() + ')');
  const tipText = text('#task-tip-bar');
  assert(tipText && tipText.includes('完成今日健康打卡并分享可获得虎力值'), '未完成时提示文案正确 (实=' + tipText + ')');

  // ---- Step 6: 点任务卡片直接完成 → pendingHuLi 累加（虎力值尚未到账） ----
  console.log('[Step 6] 点任务卡片完成(非详情任务)');
  const beforePending = window.STATE.pendingHuLi;
  const beforeHuLi = window.STATE.huLi;
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
  const afterPending = window.STATE.pendingHuLi;
  const afterHuLi = window.STATE.huLi;
  assert(afterPending > beforePending, '待发放虎力值累加 (' + beforePending + ' → ' + afterPending + ')');
  assert(afterHuLi === beforeHuLi, '分享前虎力值不变 (' + beforeHuLi + ' → ' + afterHuLi + ')');
  assert(window.STATE.completedToday.includes(nonDetailId), '任务标记为已完成');
  assert(doc.querySelectorAll('#tasks-content .task-item.done').length >= 1, '至少1张卡片变已完成态');
  assert(window.STATE.todayChecked === true, '首次完成后 todayChecked=true');
  assert(window.STATE.checkInDates.includes(window.todayStr()), '今天被加入打卡日期');

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

  // ---- Step 8: 从「太棒了」弹窗打开分享海报 → 微信好友分享 → 虎力值到账 ----
  console.log('[Step 8] 分享海报与虎力值发放');
  const pendingBeforeShare = window.STATE.pendingHuLi;
  const huLiBeforeShare = window.STATE.huLi;
  assert(pendingBeforeShare > 0, '分享前有待发放虎力值 (pending=' + pendingBeforeShare + ')');
  clickSel('#overlay-completion .btn-green');
  await wait(100);
  assert(overlayVisible() === 'overlay-share-poster', '分享海报弹窗弹出 (实=' + overlayVisible() + ')');
  assert(text('#poster-title').includes('我已坚持健康打卡'), '海报标题包含坚持打卡文案 (实=' + text('#poster-title') + ')');
  assert(exists('#poster-screenshot .shot-item'), '海报中渲染今日任务列表截图');
  assert(exists('#poster-qr svg'), '海报中包含二维码占位');
  clickSel('#overlay-share-poster .opt.wechat');
  await wait(100);
  assert(overlayVisible() === null, '分享后弹窗收起');
  assert(window.STATE.huLi === huLiBeforeShare + pendingBeforeShare, '分享后虎力值到账 (' + huLiBeforeShare + ' → ' + window.STATE.huLi + ')');
  assert(window.STATE.pendingHuLi === 0, '分享后待发放虎力值清零');
  assert(window.STATE.sharedToday === true, '今日已分享标记为 true');

  // ---- Step 9: 首页无任务态卡片点击(关键回归点) ----
  console.log('[Step 9] 首页无任务态卡片点击(关键回归点)');
  window.STATE.myTasks = [];
  window.STATE.completedToday = [];
  window.STATE.pendingHuLi = 0;
  window.STATE.sharedToday = false;
  window.STATE.todayChecked = false;
  window.STATE.dailyReportShown = true;
  window.STATE.completionShown = false;
  window.go('page-home');
  await wait(100);
  assert(text('#home-task-title') === '开启健康打卡', '重置后首页回到无任务态');
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
  window.STATE.myTasks = ['t7'];
  window.STATE.completedToday = [];
  window.STATE.pendingHuLi = 0;
  window.STATE.sharedToday = false;
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
  assert(window.STATE.pendingHuLi >= 5, '详情任务奖励进入待发放 (pending=' + window.STATE.pendingHuLi + ')');
  // 关闭可能弹出的 completion 弹窗，避免影响后续 Step 的 overlay 断言
  doc.querySelectorAll('.overlay.active').forEach(o => o.classList.remove('active'));
  await wait(50);

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

  // ---- Step 14: 全部完成后显示「分享获得虎力值」入口 ----
  console.log('[Step 14] 全部完成后分享入口');
  window.STATE.myTasks = ['t1','t2'];
  window.STATE.completedToday = ['t1','t2'];
  window.STATE.pendingHuLi = 4;
  window.STATE.sharedToday = false;
  window.go('page-tasks');
  await wait(100);
  const shareBtn = [...doc.querySelectorAll('#tasks-content button')].find(b => b.textContent.includes('分享获得虎力值'));
  assert(!!shareBtn, '全部完成后显示「分享获得虎力值」按钮');
  const before = window.STATE.huLi;
  click(shareBtn);
  await wait(100);
  assert(overlayVisible() === 'overlay-share-poster', '点击分享按钮→海报弹窗出现 (实=' + overlayVisible() + ')');
  clickSel('#overlay-share-poster .opt.save');
  await wait(100);
  assert(overlayVisible() === null, '保存本地后弹窗收起');
  assert(window.STATE.huLi > before, '保存本地分享后虎力值到账 (' + before + ' → ' + window.STATE.huLi + ')');

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
