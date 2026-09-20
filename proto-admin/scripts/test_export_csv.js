#!/usr/bin/env node
/**
 * 后台原型「导出」功能回归校验（CSV）
 * 用途：验证原型里的导出按钮真的产出 CSV（而非占位 toast），且列/行/内容符合预期。
 *       典型场景：验证「记录条数无上限」「全量导出（不受筛选/分页影响）」这类口径。
 *
 * 用法（NODE_PATH 指向 managed node_modules，勿用全局安装）:
 *   NODE_PATH="<managed node_modules>" node test_export_csv.js \
 *     --proto "<原型.html 绝对路径>" \
 *     --click "text=导出" \
 *     [--seed "<JS 字符串：点击导出前在页面里执行，可用来造数据/改筛选>"] \
 *     [--expect-cols <N>]        期望表头总列数
 *     [--expect-rows <N>]        期望数据行数（不含表头）
 *     [--expect-contains "A;B"]  分号分隔，每个关键词都必须出现在 CSV 中
 *     [--expect-absent "A;B"]    分号分隔，每个关键词都必须不出现
 *     [--dump "<输出 csv 路径>"]
 *     [--capabilities]           打印本脚本已支持能力并退出（自检是否满足需求）
 *     [--log / --no-log]         运行经验库 jsonl（默认写脚本同目录 test_export_csv.runs.jsonl）
 *
 * 自优化闭环：每次运行都会把『参数+成败+失败原因+缺口提示』写入经验库 jsonl。
 * 若某次校验报错或需求超出能力清单，把错误反馈给我，我会在当回合内**扩展本脚本**（而非另写临时代码）。
 *
 * 退出码：0=PASS，1=FAIL（任何断言不通过或未触发下载）
 */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

// 本脚本已支持能力清单——调用方可先 --capabilities 自检是否满足需求。
const CAPABILITIES = [
  'download   真实触发下载并落盘（验证导出不是占位 toast）',
  'parse      解析 CSV（支持格内换行/逗号的引号转义）',
  'cols/rows  断言表头列数 / 数据行数（--expect-cols / --expect-rows）',
  'contains   断言内容必含关键词（--expect-contains "A;B"，分号分隔）',
  'absent     断言内容不得含关键词（--expect-absent "A;B"）',
  'seed       点击导出前注入 JS 造数据 / 改筛选 / 翻页（--seed "JS"）',
  'dump       导出 CSV 落盘留证（--dump <path>）',
  'log        运行经验库 jsonl（--log / --no-log）',
];

function parseArgs(argv) {
  const a = { proto: null, click: 'text=导出', seed: null, dump: null, expectContains: [], expectAbsent: [], log: true };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (k === '--proto') a.proto = argv[++i];
    else if (k === '--click') a.click = argv[++i];
    else if (k === '--seed') a.seed = argv[++i];
    else if (k === '--dump') a.dump = argv[++i];
    else if (k === '--expect-cols') a.expectCols = Number(argv[++i]);
    else if (k === '--expect-rows') a.expectRows = Number(argv[++i]);
    else if (k === '--expect-contains') a.expectContains = argv[++i].split(';').filter(Boolean);
    else if (k === '--expect-absent') a.expectAbsent = argv[++i].split(';').filter(Boolean);
    else if (k === '--capabilities') a.capabilities = true;
    else if (k === '--log') a.log = true;
    else if (k === '--no-log') a.log = false;
  }
  return a;
}

function writeRunLog(record, enabled) {
  if (!enabled) return;
  try {
    const p = path.join(__dirname, 'test_export_csv.runs.jsonl');
    fs.appendFileSync(p, JSON.stringify(record) + '\n', 'utf8');
  } catch (e) { console.error('[log] 写运行经验库失败(不影响结果): ' + e.message); }
}

// 支持引号内换行/逗号的最小 CSV 解析器（导出格内常有换行堆叠，必须正确解析）
function parseCsv(text) {
  const rows = [];
  let row = [], cell = '', inQ = false;
  const s = text.replace(/^\uFEFF/, '');
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (inQ) {
      if (c === '"') {
        if (s[i + 1] === '"') { cell += '"'; i++; } else { inQ = false; }
      } else cell += c;
    } else {
      if (c === '"') inQ = true;
      else if (c === ',') { row.push(cell); cell = ''; }
      else if (c === '\r') { /* skip */ }
      else if (c === '\n') { row.push(cell); rows.push(row); row = []; cell = ''; }
      else cell += c;
    }
  }
  if (cell !== '' || row.length) { row.push(cell); rows.push(row); }
  return rows.filter(r => r.length > 1 || (r[0] || '').trim() !== '');
}

(async () => {
  const a = parseArgs(process.argv.slice(2));
  if (a.capabilities) {
    console.log('test_export_csv.js 已支持能力：');
    CAPABILITIES.forEach(c => console.log('  - ' + c));
    console.log('\n缺什么能力直接说，我扩展本脚本（不要另写临时脚本，见 PROTO-MOD-002）。');
    process.exit(0);
  }
  if (!a.proto) { console.error('缺少 --proto'); process.exit(1); }

  const fails = [];
  const ok = (cond, label) => { console.log((cond ? '  ✓ ' : '  ✗ ') + label); if (!cond) fails.push(label); };
  const logBase = { ts: new Date().toISOString(), proto: a.proto, click: a.click, seed: !!a.seed, expectCols: a.expectCols, expectRows: a.expectRows, expectContains: a.expectContains, expectAbsent: a.expectAbsent };

  const b = await chromium.launch({ args: ['--no-sandbox'] });
  const ctx = await b.newContext({ acceptDownloads: true });
  const p = await ctx.newPage();
  const url = 'file:///' + path.resolve(a.proto).replace(/\\/g, '/');
  await p.goto(url, { waitUntil: 'networkidle' });

  if (a.seed) { await p.evaluate(new Function(a.seed)); await p.waitForTimeout(300); }

  let csv = '';
  try {
    const [dl] = await Promise.all([
      p.waitForEvent('download', { timeout: 8000 }),
      p.click(a.click)
    ]);
    const out = a.dump ? path.resolve(a.dump) : path.join(require('os').tmpdir(), 'proto_export_check.csv');
    await dl.saveAs(out);
    csv = fs.readFileSync(out, 'utf8');
    console.log('下载文件: ' + dl.suggestedFilename() + '  (' + Buffer.byteLength(csv) + ' 字节)');
  } catch (e) {
    ok(false, '触发下载并拿到 CSV（未触发下载 = 导出是假的/占位 toast）');
    await b.close();
    writeRunLog(Object.assign({}, logBase, { result: 'FAIL', reason: '未触发下载', fails }), a.log);
    console.log('\nFAIL\n- ' + fails.join('\n- '));
    process.exit(1);
  }

  const rows = parseCsv(csv);
  const head = rows[0] || [];
  const data = rows.slice(1);
  console.log('表头列数: ' + head.length + ' | 数据行数: ' + data.length);
  console.log('表头: ' + head.join(' | '));
  if (data[0]) {
    const preview = data[0].slice(0, 5).concat(head.length > 5 ? ['…'] : []).join(' | ');
    console.log('首行预览: ' + preview);
  }

  if (a.expectCols != null) ok(head.length === a.expectCols, '表头列数 = ' + a.expectCols + '（实际 ' + head.length + '）');
  if (a.expectRows != null) ok(data.length === a.expectRows, '数据行数 = ' + a.expectRows + '（实际 ' + data.length + '）');
  a.expectContains.forEach(k => ok(csv.indexOf(k) > -1, 'CSV 含「' + k + '」'));
  a.expectAbsent.forEach(k => ok(csv.indexOf(k) === -1, 'CSV 不含「' + k + '」'));

  await b.close();
  writeRunLog(Object.assign({}, logBase, { result: fails.length ? 'FAIL' : 'PASS', cols: head.length, rows: data.length, fails }), a.log);
  if (fails.length) { console.log('\nFAIL\n- ' + fails.join('\n- ')); process.exit(1); }
  console.log('\nPASS');
})();
