(function () {
  const registry = { en: {
    'nav.scores':'Scores','nav.compare':'Compare','nav.ui':'UI','nav.api':'API','lang.english':'English','lang.chinese':'中文',
    'range.7d':'7d','range.30d':'30d','range.90d':'90d','range.all':'all','footer.dataset':'Dataset','footer.lastRun':'Last finished run',
    'status.loading':'Loading…','status.noData':'No data.','status.noDataRange':'No data in this range.','status.noFinishedRuns':'No finished runs yet.',
    'status.loadData':'Unable to load monitor data.','status.loadSeries':'Unable to load data.','status.noDataRangeShort':'no data in range',
    'compare.legend':'Bar = score (0–100). Dot = time to solve; text shows score, judged quality, time and cost.','compare.rated':'{n} rated','compare.judged':'judged',
    'ui.ratingKey':'Rating key','ui.unlock':'Unlock','ui.accepted':'key accepted','ui.notAccepted':'key not accepted','ui.notRated':'Not rated','ui.invalid':'Invalid or replaced sample',
    'ui.svgSample':'SVG sample','ui.stars':'{n} of 10 stars','ui.starCount':'{n} stars','chart.score':'Score','chart.time':'Time to solve (s)','chart.quality':'Quality (judged)',
    'availability':'availability {n}% · last run {date}','effort.low':'low','effort.medium':'medium','effort.high':'high',
    'dim.reasoning.name':'Reasoning','dim.reasoning.use':'Multi-step reasoning, avoiding common-sense traps, reading tables and figures, not making things up',
    'dim.code.name':'Code','dim.code.use':'Writing a function, reading code, fixing a bug','dim.instruction.name':'Instruction following','dim.instruction.use':'Following a strict output format, extracting fields into JSON',
    'dim.write_zh.name':'Writing · 中文','dim.write_zh.use':'Chinese marketing copy','dim.write_en.name':'Writing · English','dim.write_en.use':'English marketing copy',
    'dim.ui.name':'Drawing (SVG)','dim.ui.use':'Drawing and visual layout, shown as SVG'
  }, zh: {
    'nav.scores':'评分','nav.compare':'比较','nav.ui':'绘图','nav.api':'API','lang.english':'English','lang.chinese':'中文',
    'range.7d':'7天','range.30d':'30天','range.90d':'90天','range.all':'全部','footer.dataset':'数据集','footer.lastRun':'最近完成运行',
    'status.loading':'加载中…','status.noData':'暂无数据。','status.noDataRange':'此范围内暂无数据。','status.noFinishedRuns':'尚无已完成的运行。',
    'status.loadData':'无法加载监控数据。','status.loadSeries':'无法加载数据。','status.noDataRangeShort':'此范围内无数据',
    'compare.legend':'条形图 = 分数（0–100）。圆点 = 解题时间；文字显示分数、评审质量、时间和成本。','compare.rated':'已评 {n} 个','compare.judged':'评审',
    'ui.ratingKey':'评分密钥','ui.unlock':'解锁','ui.accepted':'密钥有效','ui.notAccepted':'密钥无效','ui.notRated':'未评分','ui.invalid':'无效或已替换的样本',
    'ui.svgSample':'SVG 样本','ui.stars':'{n}/10 星','ui.starCount':'{n} 星','chart.score':'分数','chart.time':'解题时间（秒）','chart.quality':'质量（评审）',
    'availability':'可用率 {n}% · 最近运行 {date}','effort.low':'低','effort.medium':'中','effort.high':'高',
    'dim.reasoning.name':'推理','dim.reasoning.use':'多步推理、避开常识陷阱、读表格和数据、不胡编乱造','dim.code.name':'代码','dim.code.use':'写函数、读代码、修 bug',
    'dim.instruction.name':'指令遵循','dim.instruction.use':'严格遵守输出格式、把信息抽取成 JSON','dim.write_zh.name':'写作 · 中文','dim.write_zh.use':'中文营销文案',
    'dim.write_en.name':'写作 · English','dim.write_en.use':'英文营销文案','dim.ui.name':'绘图（SVG）','dim.ui.use':'绘图与视觉布局，以 SVG 展示'
  }};
  let current=localStorage.getItem('lang'); if(current!=='en'&&current!=='zh') current=(navigator.language||'').toLowerCase().startsWith('zh')?'zh':'en';
  function t(key,vars){const text=registry[current][key]||registry.en[key]||key;return text.replace(/\{(\w+)\}/g,(_,n)=>vars&&vars[n]!=null?vars[n]:`{${n}}`);}
  function apply(root){root=root||document;root.querySelectorAll('[data-i18n]').forEach(el=>{el.textContent=t(el.dataset.i18n);});root.querySelectorAll('[data-i18n-attr]').forEach(el=>el.dataset.i18nAttr.split(',').forEach(pair=>{const [attr,key]=pair.split(':');if(attr&&key)el.setAttribute(attr,t(key));}));document.documentElement.lang=current==='zh'?'zh-CN':'en';root.querySelectorAll('#lang-switch [data-lang]').forEach(el=>el.setAttribute('aria-pressed',String(el.dataset.lang===current)));}
  window.i18n={lang:()=>current,setLang:l=>{if(l!=='en'&&l!=='zh')return;current=l;localStorage.setItem('lang',l);apply();document.dispatchEvent(new CustomEvent('langchange',{detail:{lang:l}}));},t,add:dict=>['en','zh'].forEach(l=>Object.assign(registry[l],dict[l]||{})),apply};
  document.addEventListener('click',e=>{const button=e.target.closest('#lang-switch [data-lang]');if(button)window.i18n.setLang(button.dataset.lang);});window.i18n.apply();
}());
