#!/usr/bin/env node
// ac-api.js — AutoClaw 账号能力直调工具（ZCode 会话内使用）
// 用法:
//   node ac-api.js chat "问题"                 → 免费(coding-plan, glm-4.7)
//   node ac-api.js chat glm-5.3 "问题"          → 指定免费套餐模型
//   node ac-api.js models-free                  → 列 coding-plan 可用模型
//   node ac-api.js img "提示词" [--ref 路径|URL] → 即梦生图(耗积分)
//   node ac-api.js video "提示词" [--dur 秒]     → HappyHorse 视频(耗积分)
//   node ac-api.js search "关键词"              → 联网搜索(不耗积分)
//   node ac-api.js title "会话内容"             → GLM 起标题(免费代理)
//   node ac-api.js models-managed               → AutoClaw 模型目录
// 分诊铁律: 对话/推理/写码一律 chat(免费); 生图/视频才用积分端点。
'use strict';
const fs = require('fs'), path = require('path'), cp = require('child_process'), crypto = require('crypto');

// ---- 用户 coding-plan(免费) ----
const FREE_BASE = 'https://open.bigmodel.cn/api/coding/paas/v4';
const FREE_KEY = 'b6c020b885ac453e816975a4b42a5a55.lu6PYgytajBGp1Vj';

// ---- AutoClaw 登录态(积分端点) ----
const AC_ORIGIN = 'https://autoglm-acceleration-api.zhipuai.cn';
const EP = {
  img: '/agentdr/v1/assistant/skills/generate-image-seedream',
  video: '/agentdr/v1/assistant/skills/happy-horse-create',
  search: '/agentdr/v1/assistant/skills/web-search',
  title: '/agentdr/v1/assistant/generate-session-title',
  models: '/autoclaw-proxy/proxy/autoclaw-model-config'
};
const AC_CMDS = ['img', 'video', 'search', 'title', 'models-managed'];
const ID = { appId: '100003', appKey: '38d2391985e2369a5fb8227d8e6cd5e5', product: 'autoclaw' };
function acCreds() {
  const ps1 = path.join(__dirname, 'get-creds.ps1');
  const out = cp.execSync(`powershell -NoProfile -ExecutionPolicy Bypass -File "${ps1}"`, { encoding: 'utf8' }).trim().split(/\r?\n/);
  if (out.length < 2 || !out[0] || !out[1]) throw new Error('get-creds.ps1 输出格式异常（期望: hex密钥行 + 密文路径行）');
  const key = Buffer.from(out[0], 'hex');
  const enc = fs.readFileSync(out[1]);
  if (key.length !== 32 || enc.length < 31) throw new Error(`凭据长度异常（key=${key.length}B, 密文=${enc.length}B；期望 32B/>=31B）`);
  const d = crypto.createDecipheriv('aes-256-gcm', key, enc.slice(3, 15));
  d.setAuthTag(enc.slice(enc.length - 16));
  return JSON.parse(Buffer.concat([d.update(enc.slice(15, enc.length - 16)), d.final()]).toString('utf8'));
}
function fpHeaders() {
  const ts = String(Math.floor(Date.now() / 1000));
  return {
    'X-Version': '2.0.1', 'X-Tm': 'win', 'X-Product': ID.product,
    'X-Auth-Appid': ID.appId, 'X-Auth-TimeStamp': ts,
    'X-Auth-Sign': crypto.createHash('md5').update(`${ID.appId}&${ts}&${ID.appKey}`).digest('hex'),
    'X-Lang': 'zh-CN', 'X-Channel': 'official'
  };
}

const [cmd, a1, ...rest] = process.argv.slice(2);
(async () => {
  if (cmd === 'chat') {
    const model = rest.length && a1 && !a1.includes(' ') ? a1 : 'glm-4.7';
    const q = rest.length ? rest.join(' ') : a1;
    if (!q) return console.log('用法: node ac-api.js chat [模型] "问题"');
    const r = await fetch(`${FREE_BASE}/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${FREE_KEY}` },
      body: JSON.stringify({ model, messages: [{ role: 'user', content: q }], max_tokens: 8192 })
    });
    const j = await r.json();
    if (j.error) return console.log('ERR', JSON.stringify(j.error));
    const m = j.choices?.[0]?.message;
    console.log(m?.reasoning_content ? '' : '', m?.content ?? JSON.stringify(j).slice(0, 400));
    console.error(`[model=${j.model} usage=${j.usage?.total_tokens}tk]`);
  } else if (cmd === 'models-free') {
    const r = await fetch(`${FREE_BASE}/models`, { headers: { Authorization: `Bearer ${FREE_KEY}` } });
    console.log((await r.text()).slice(0, 2000));
  } else if (AC_CMDS.includes(cmd)) {
    if (cmd !== 'models-managed' && !a1) return console.log(`用法: node ac-api.js ${cmd} "参数"（详见文件头注释）`);
    const creds = acCreds();
    const H = { 'Content-Type': 'application/json', Authorization: creds.accessToken, ...fpHeaders() };
    if (cmd === 'img') {
      // --ref <path|url> 垫图（角色/场景一致性）：路径可含空格
      const m = /^(.*?)\s*--ref\s+(.+?)\s*$/.exec(a1);
      const q = m ? m[1].trim() : a1;
      const body = { query: q };
      if (m) body.image = m[2];
      const r = await fetch(AC_ORIGIN + EP.img, { method: 'POST', headers: H, body: JSON.stringify(body) });
      const j = await r.json();
      console.log(j.data?.image_url ?? JSON.stringify(j).slice(0, 400));
    } else if (cmd === 'video') {
      // --dur <秒> 时长（默认 5）；参数先剥离再发请求，别把 --dur 文本混进提示词
      const dm = /^(.*?)\s*--dur\s+(\d+)\s*$/.exec(a1);
      const r = await fetch(AC_ORIGIN + EP.video, { method: 'POST', headers: H, body: JSON.stringify({ prompt: dm ? dm[1].trim() : a1, duration: dm ? +dm[2] : 5 }) });
      console.log((await r.text()).slice(0, 500));
    } else if (cmd === 'search') {
      const r = await fetch(AC_ORIGIN + EP.search, { method: 'POST', headers: H, body: JSON.stringify({ queries: [{ query: a1 }] }) });
      console.log((await r.text()).slice(0, 3000));
    } else if (cmd === 'title') {
      const r = await fetch(AC_ORIGIN + EP.title, { method: 'POST', headers: H, body: JSON.stringify({ query: a1 }) });
      console.log((await r.text()).slice(0, 300));
    } else {  // models-managed
      const r = await fetch(AC_ORIGIN + EP.models, { headers: H });
      const j = await r.json();
      j.models?.forEach(m => console.log(`${m.id}\t积分:${m.creditConsumptionLevel}\t${m.tooltip?.slice(0, 40)}`));
    }
  } else {
    console.log('用法见文件头注释');
  }
})().catch(e => { console.error('FATAL', e.message); process.exit(1); });
