const { chromium } = require('playwright');
const path = require('path');

const BASE = 'C:\\项目目录';       // ← 改为实际路径
const OUT  = path.join(BASE, 'coupon-prd-assets');  // ← 截图输出目录

const JOBS = [
  {
    file: '平台端后台原型.html',    // ← 原型文件名
    label: '平台端',
    pages: [
      { fn: null,              waitSel: '#viewList',        out: 'pf-p1-list.png',       desc: 'P1 列表' },
      { fn: 'go("detail")',    waitSel: '#viewCouponDetail',out: 'pf-d1-detail.png',     desc: 'D1 详情' },
      // ... 每个页面一个条目：fn=导航函数, waitSel=目标view的ID, out=输出文件名
      // 弹窗用 modalId: 'stockModal' 强制显示
    ],
  },
  // ... 更多原型文件
];

(async () => {
  const browser = await chromium.launch({ headless: true });
  for (const job of JOBS) {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    await page.goto(`file:///${path.join(BASE, job.file).replace(/\\/g, '/')}`, { waitUntil: 'networkidle' });
    await page.waitForSelector('.main', { timeout: 10000 });
    for (const p of job.pages) {
      if (p.fn) { await page.evaluate(p.fn); await page.waitForSelector(p.waitSel, { timeout: 5000 }); }
      if (p.modalId) { await page.evaluate((id)=>{document.getElementById(id).style.display='block'}, p.modalId); }
      const el = await page.$('.main');
      (el ? el : page).screenshot({ path: path.join(OUT, p.out) });
    }
    await page.close();
  }
  await browser.close();
})();