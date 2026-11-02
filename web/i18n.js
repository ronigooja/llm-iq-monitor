(function () {
  const registry = { en: {
    'nav.scores':'Scores','nav.compare':'Compare','nav.ui':'UI','nav.api':'API','lang.english':'English','lang.chinese':'中文',
    'range.7d':'7d','range.30d':'30d','range.90d':'90d','range.all':'all','footer.dataset':'Dataset','footer.lastRun':'Last finished run',
    'status.loading':'Loading…','status.noData':'No data.','status.noDataRange':'No data in this range.','status.noFinishedRuns':'No finished runs yet.',
    'status.loadData':'Unable to load monitor data.','status.loadSeries':'Unable to load data.','status.noDataRangeShort':'no data in range',
    'compare.legend':'Bar = score (0–100). Dot = time to solve; text shows score, judged quality, time and cost.','compare.rated':'{n} rated','compare.judged':'judged',
    'ui.ratingKey':'Rating key','ui.unlock':'Unlock','ui.accepted':'key accepted','ui.notAccepted':'key not accepted','ui.notRated':'Not rated','ui.invalid':'Invalid or replaced sample',
     'ui.svgSample':'SVG sample','ui.stars':'{n} of 10 stars','ui.starCount':'{n} stars','ui.subject.classic':'A pelican riding a bicycle','ui.subject.variant':'A penguin driving a tractor','chart.score':'Score','chart.time':'Time to solve (s)','chart.quality':'Quality (judged)',
    'availability':'availability {n}% · last run {date}','effort.low':'low','effort.medium':'medium','effort.high':'high',
    'dim.reasoning.name':'Reasoning','dim.reasoning.use':'Multi-step reasoning, avoiding common-sense traps, reading tables and figures, not making things up',
    'dim.code.name':'Code','dim.code.use':'Writing a function, reading code, fixing a bug','dim.instruction.name':'Instruction following','dim.instruction.use':'Following a strict output format, extracting fields into JSON',
    'dim.write_zh.name':'Writing · 中文','dim.write_zh.use':'Chinese marketing copy','dim.write_en.name':'Writing · English','dim.write_en.use':'English marketing copy',
    'dim.ui.name':'Drawing (SVG)','dim.ui.use':'Drawing and visual layout, shown as SVG',
     'meta.title':'LLM IQ Monitor · Model scores by capability','meta.description':'Scheduled LLM benchmark by capability: reasoning, code, instruction following, writing, drawing.',
     'admin.title':'Admin console · LLM IQ Monitor','admin.login':'Admin sign in','admin.token':'Admin password','admin.signIn':'Sign in','admin.signOut':'Sign out','admin.locked':'Locked, retry in {n} min','admin.unauthorized':'Please sign in again.','admin.gateway':'Gateway','admin.baseUrl':'Base URL','admin.modelsUrl':'Models URL','admin.gatewayKey':'Gateway key','admin.keySet':'set','admin.keyNotSet':'not set','admin.keyPlaceholder':'Leave blank to keep the current key','admin.testConnection':'Test connection','admin.testing':'Testing…','admin.connectionOk':'Connection succeeded: {status}; {models} models','admin.connectionFailed':'Connection failed: {message}','admin.models':'Models','admin.search':'Search models','admin.refresh':'Refresh models','admin.refreshing':'Refreshing…','admin.noPrice':'no price','admin.priced':'priced','admin.enabled':'Enabled','admin.model':'Model','admin.price':'Price','admin.interval':'Interval (hours)','admin.dimensions':'Dimensions','admin.efforts':'Efforts','admin.selected':'{n} selected','admin.bulkApply':'Apply interval/dimensions/efforts to {n} selected','admin.apply':'Apply','admin.defaults':'Defaults and heartbeat','admin.heartbeat':'Heartbeat cron','admin.nextTicks':'Next five ticks','admin.defaultInterval':'Default interval (hours)','admin.defaultDimensions':'Default dimensions','admin.defaultEfforts':'Default efforts','admin.runLimits':'Run limits','admin.parallelModels':'Parallel models','admin.timeout':'Timeout (seconds)','admin.maxTokens':'Max tokens','admin.rttFallback':'RTT fallback (ms)','admin.replyRetention':'Reply retention (days)','admin.judge':'Judge model','admin.judgeModel':'Model','admin.judgeEffort':'Effort','admin.overview':'Overview','admin.runsPerDay':'Estimated runs per day','admin.tokensPerDay':'Estimated tokens per day','admin.save':'Save','admin.discard':'Discard','admin.unsaved':'unsaved changes','admin.saved':'Saved; the runner picks it up automatically','admin.saveSummary':'Please fix the highlighted fields.','admin.saveFailed':'Unable to save settings.','admin.discarded':'Changes discarded.','admin.required':'Required','admin.invalid':'Invalid value','admin.loading':'Loading…','admin.loadFailed':'Unable to load admin state.','admin.loggedOut':'Signed out.'
  }, zh: {
    'nav.scores':'评分','nav.compare':'比较','nav.ui':'绘图','nav.api':'API','lang.english':'English','lang.chinese':'中文',
    'range.7d':'7天','range.30d':'30天','range.90d':'90天','range.all':'全部','footer.dataset':'数据集','footer.lastRun':'最近完成运行',
    'status.loading':'加载中…','status.noData':'暂无数据。','status.noDataRange':'此范围内暂无数据。','status.noFinishedRuns':'尚无已完成的运行。',
    'status.loadData':'无法加载监控数据。','status.loadSeries':'无法加载数据。','status.noDataRangeShort':'此范围内无数据',
    'compare.legend':'条形图 = 分数（0–100）。圆点 = 解题时间；文字显示分数、评审质量、时间和成本。','compare.rated':'已评 {n} 个','compare.judged':'评审',
    'ui.ratingKey':'评分密钥','ui.unlock':'解锁','ui.accepted':'密钥有效','ui.notAccepted':'密钥无效','ui.notRated':'未评分','ui.invalid':'无效或已替换的样本',
     'ui.svgSample':'SVG 样本','ui.stars':'{n}/10 星','ui.starCount':'{n} 星','ui.subject.classic':'鹈鹕骑自行车','ui.subject.variant':'企鹅开拖拉机','chart.score':'分数','chart.time':'解题时间（秒）','chart.quality':'质量（评审）',
    'availability':'可用率 {n}% · 最近运行 {date}','effort.low':'低','effort.medium':'中','effort.high':'高',
    'dim.reasoning.name':'推理','dim.reasoning.use':'多步推理、避开常识陷阱、读表格和数据、不胡编乱造','dim.code.name':'代码','dim.code.use':'写函数、读代码、修 bug',
    'dim.instruction.name':'指令遵循','dim.instruction.use':'严格遵守输出格式、把信息抽取成 JSON','dim.write_zh.name':'写作 · 中文','dim.write_zh.use':'中文营销文案',
    'dim.write_en.name':'写作 · English','dim.write_en.use':'英文营销文案','dim.ui.name':'绘图（SVG）','dim.ui.use':'绘图与视觉布局，以 SVG 展示',
     'meta.title':'LLM IQ Monitor · 大模型分项能力评分','meta.description':'按能力定时评测大模型：推理、代码、指令遵循、写作、绘图，含耗时与成本。',
     'admin.title':'管理控制台 · LLM IQ Monitor','admin.login':'管理员登录','admin.token':'管理员密码','admin.signIn':'登录','admin.signOut':'退出登录','admin.locked':'已锁定，请在 {n} 分钟后重试','admin.unauthorized':'请重新登录。','admin.gateway':'网关','admin.baseUrl':'基础 URL','admin.modelsUrl':'模型 URL','admin.gatewayKey':'网关密钥','admin.keySet':'已设置','admin.keyNotSet':'未设置','admin.keyPlaceholder':'留空以保留当前密钥','admin.testConnection':'测试连接','admin.testing':'测试中…','admin.connectionOk':'连接成功：{status}；{models} 个模型','admin.connectionFailed':'连接失败：{message}','admin.models':'模型','admin.search':'搜索模型','admin.refresh':'刷新模型','admin.refreshing':'刷新中…','admin.noPrice':'无价格','admin.priced':'有价格','admin.enabled':'启用','admin.model':'模型','admin.price':'价格','admin.interval':'间隔（小时）','admin.dimensions':'维度','admin.efforts':'推理档位','admin.selected':'已选择 {n} 个','admin.bulkApply':'将间隔/维度/推理档位应用到已选的 {n} 个模型','admin.apply':'应用','admin.defaults':'默认值和心跳','admin.heartbeat':'心跳 cron','admin.nextTicks':'接下来五次运行','admin.defaultInterval':'默认间隔（小时）','admin.defaultDimensions':'默认维度','admin.defaultEfforts':'默认推理档位','admin.runLimits':'运行限制','admin.parallelModels':'并行模型数','admin.timeout':'超时（秒）','admin.maxTokens':'最大 token 数','admin.rttFallback':'RTT 回退（毫秒）','admin.replyRetention':'回复保留（天）','admin.judge':'评审模型','admin.judgeModel':'模型','admin.judgeEffort':'推理档位','admin.overview':'概览','admin.runsPerDay':'预计每日运行次数','admin.tokensPerDay':'预计每日 token 数','admin.save':'保存','admin.discard':'放弃','admin.unsaved':'有未保存更改','admin.saved':'已保存；运行器会自动读取','admin.saveSummary':'请修正标记的字段。','admin.saveFailed':'无法保存设置。','admin.discarded':'已放弃更改。','admin.required':'必填','admin.invalid':'值无效','admin.loading':'加载中…','admin.loadFailed':'无法加载管理状态。','admin.loggedOut':'已退出登录。'
  }};
  const pageMeta = {
    admin: {
      en: { title:'Admin console · LLM IQ Monitor', description:'Private administration console for the LLM IQ Monitor scheduler.' },
      zh: { title:'管理控制台 · LLM IQ Monitor', description:'LLM IQ Monitor 调度器的私有管理控制台。' }
    },
    scores: {
      en: { title:'LLM IQ Monitor · Model scores by capability', description:'Scheduled LLM benchmark by capability: reasoning, code, instruction following, writing, drawing.' },
      zh: { title:'LLM IQ Monitor · 大模型分项能力评分', description:'按能力定时评测大模型：推理、代码、指令遵循、写作、绘图，含耗时与成本。' }
    },
    compare: {
      en: { title:'Compare models · LLM IQ Monitor', description:'Side-by-side score, time to solve and cost per model and effort.' },
      zh: { title:'模型对比 · LLM IQ Monitor', description:'按模型和推理档位并排对比分数、解题时间和成本。' }
    },
    ui: {
      en: { title:'SVG drawing samples · LLM IQ Monitor', description:'SVG drawings by each model, such as a pelican riding a bicycle.' },
      zh: { title:'SVG 绘图样本 · LLM IQ Monitor', description:'各模型生成的 SVG 绘图样本，例如骑自行车的鹈鹕。' }
    },
    api: {
      en: { title:'API reference · LLM IQ Monitor', description:'Public read-only JSON API for scores, history and dimensions.' },
      zh: { title:'API 参考 · LLM IQ Monitor', description:'公开只读 JSON 接口：评分、历史、能力维度。' }
    }
  };
  const page = location.pathname === '/admin/' || location.pathname === '/admin' ? 'admin' : location.pathname === '/compare' ? 'compare' : location.pathname === '/ui' ? 'ui' : location.pathname === '/api' ? 'api' : 'scores';
  ['en','zh'].forEach(language => { registry[language]['meta.title'] = pageMeta[page][language].title; registry[language]['meta.description'] = pageMeta[page][language].description; });
  let current=localStorage.getItem('lang'); if(current!=='en'&&current!=='zh') current=(navigator.language||'').toLowerCase().startsWith('zh')?'zh':'en';
  function t(key,vars){const text=registry[current][key]||registry.en[key]||key;return text.replace(/\{(\w+)\}/g,(_,n)=>vars&&vars[n]!=null?vars[n]:`{${n}}`);}
  function apply(root){root=root||document;root.querySelectorAll('[data-i18n]').forEach(el=>{el.textContent=t(el.dataset.i18n);});root.querySelectorAll('[data-i18n-attr]').forEach(el=>el.dataset.i18nAttr.split(',').forEach(pair=>{const [attr,key]=pair.split(':');if(attr&&key)el.setAttribute(attr,t(key));}));const title=root.querySelector('title');const description=root.querySelector('meta[name="description"]');if(title)title.textContent=t('meta.title');if(description)description.setAttribute('content',t('meta.description'));document.documentElement.lang=current==='zh'?'zh-CN':'en';root.querySelectorAll('#lang-switch [data-lang]').forEach(el=>el.setAttribute('aria-pressed',String(el.dataset.lang===current)));}
  window.i18n={lang:()=>current,setLang:l=>{if(l!=='en'&&l!=='zh')return;current=l;localStorage.setItem('lang',l);apply();document.dispatchEvent(new CustomEvent('langchange',{detail:{lang:l}}));},t,add:dict=>['en','zh'].forEach(l=>Object.assign(registry[l],dict[l]||{})),apply};
  document.addEventListener('click',e=>{const button=e.target.closest('#lang-switch [data-lang]');if(button)window.i18n.setLang(button.dataset.lang);});window.i18n.apply();
}());
