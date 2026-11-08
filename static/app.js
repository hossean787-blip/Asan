/* MIZ Accounting Interview v2.1 — client contains NO answer key, grading, or solution. */
(() => {
'use strict';
const $=(s)=>document.querySelector(s);
const main=$('#main');
const esc=(s)=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fa=(n)=>new Intl.NumberFormat('fa-IR').format(Number(n)||0);
const ROLE={intern:'کارآموز حسابداری',assistant:'کمک‌حسابدار',accountant:'حسابدار'};
const DNAME={easy:'آسان',medium:'متوسط',hard:'سخت'};
const state={meta:null,admin:false,view:'dashboard',exams:[],bank:null,report:null,reportId:null,
   created:null,bankQuestions:[],bankFilter:'all',bankSearch:'',bankLimit:12,candidateDraft:'',reviewTarget:null,reviewEvents:[],reviewerName:'',selectedRole:'accountant',candidateMode:location.pathname==='/candidate',
   candidateCode:sessionStorage.getItem('miz_candidate_code')||'',question:null,choice:null,reviewVisible:false,error:'',busy:false};
let toastId;
function toast(message){const el=$('#toast');el.textContent=message;el.classList.add('show');clearTimeout(toastId);toastId=setTimeout(()=>el.classList.remove('show'),3300);}
async function api(path,opts={}){
 const headers={'Accept':'application/json',...(opts.body?{'Content-Type':'application/json'}:{}),...(opts.headers||{})};
 const r=await fetch(path,{credentials:'same-origin',cache:'no-store',...opts,headers});
 let data;try{data=await r.json();}catch(e){data={error:'پاسخ سرور قابل خواندن نیست.'};}
 if(!r.ok)throw new Error(data.error||'ارتباط با سرور برقرار نشد.');
 return data;
}
function title(t,sub,kicker='سامانه ارزیابی استخدام'){return `<div class="page-kicker">${esc(kicker)}</div><h1 class="page-title">${esc(t)}</h1><p class="page-sub">${esc(sub)}</p>`;}
function button(t,action='dashboard',klass='btn-primary'){return `<button class="btn ${klass}" data-action="${action}">${t}</button>`;}
function stat(label,value,caption,icon='▤'){return `<div class="stat-card"><div class="stat-label">${esc(label)}</div><div class="stat-icon">${icon}</div><strong>${esc(value)}</strong><div class="stat-caption">${esc(caption)}</div></div>`;}
function navState(){
 document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('is-active',b.dataset.view===state.view));
 $('#breadcrumb-title').textContent={dashboard:'داشبورد',create:'ساخت آزمون',reports:'گزارش‌ها',bank:'بانک سؤالات',report:'نتیجه آزمون'}[state.view]||'سامانه ارزیابی';
 $('#logout-btn').hidden=!state.admin;
 $('#sidebar').classList.toggle('open',false);
 document.body.classList.toggle('candidate-mode',state.candidateMode);
 $('#sidebar').style.display=state.candidateMode?'none':'';
 document.querySelector('.mobile-menu').style.display=state.candidateMode?'none':'';
}
function show(html){navState();main.innerHTML=html;main.focus({preventScroll:true});window.scrollTo(0,0);}
function errorMarkup(){return state.error?`<div class="form-error" role="alert">${esc(state.error)}</div>`:'';}
function loginView(initial){
 return `<div class="center-box"><div class="big-icon">♙</div><div class="page-kicker">${initial?'راه‌اندازی اولیه':'دسترسی اختصاصی'}</div>
 <h1>${initial?'ساخت حساب مسئول استخدام':'ورود مسئول استخدام'}</h1><p>${initial?'برای محافظت از کلید سؤالات، یک رمز قوی حداقل ۱۰ نویسه‌ای بسازید.':'کلید پاسخ، امتیازها و اطلاعات داوطلبان فقط پس از ورود مسئول مجاز نمایش داده می‌شود.'}</p>
 ${errorMarkup()}<form id="admin-auth-form"><div class="form-group"><label class="form-label" for="admin-password">گذرواژه</label><input class="field" id="admin-password" type="password" autocomplete="${initial?'new-password':'current-password'}" minlength="10" required placeholder="••••••••••••"></div>
 ${initial?'<div class="form-group"><label class="form-label" for="admin-password2">تکرار گذرواژه</label><input class="field" id="admin-password2" type="password" autocomplete="new-password" minlength="10" required placeholder="••••••••••••"></div>':''}
 <button class="btn btn-primary" type="submit">${initial?'ثبت گذرواژه و ایجاد پنل':'ورود امن به پنل'} <span>←</span></button></form>
 <div class="notice"><strong>نکته امنیتی:</strong> داده‌های آزمون و پاسخنامه روی سرور محلی نگهداری می‌شوند. برای استفاده روی اینترنت، HTTPS و زیرساخت ایمن لازم است.</div></div>`;
}
function homeView(){
 const completed=state.exams.filter(e=>e.status==='completed').length;
 const active=state.exams.filter(e=>e.status==='active').length;
 return `<div class="hero"><div class="hero-copy"><span class="eyebrow">✦ سیستم هوشمند سنجش شغلی</span>
 <h1>انتخاب یک حسابدار خوب،<br><span>از یک ارزیابی دقیق شروع می‌شود.</span></h1><p>آزمون ۱۰۰ سؤالی با سختی تطبیقی، پوشش ۲۵ حوزه تخصصی حسابداری و گزارش محرمانه ویژه مسئول استخدام.</p>
 ${button('ساخت آزمون استخدامی جدید ←','create')}</div><div class="hero-art" aria-hidden="true"><div class="art-ring"></div><span class="tiny-star">✧</span><div class="art-card"><div class="art-line"></div><div class="art-line small"></div><div class="art-bars"><i></i><i></i><i></i><i></i></div></div></div></div>
 <div class="stats-grid">${stat('جلسات ثبت‌شده',fa(state.exams.length),'در همین پایگاه داده','▧')}${stat('آزمون‌های پایان‌یافته',fa(completed),'آماده بررسی نتایج','◉')}${stat('آزمون‌های در جریان',fa(active),'در حال پاسخ‌گویی','◷')}${stat('بانک فعال',fa(state.meta.total_questions),'از هدف ۳٬۰۰۰ سؤال','▤')}</div>
 <div class="section-heading"><div><h2>موقعیت شغلی را انتخاب کنید</h2><p>همه نقش‌ها از تمام ۲۵ حوزه سؤال دریافت می‌کنند؛ نقطه شروع سختی متفاوت است.</p></div></div>
 <div class="role-grid">${roleCard('intern','✦','ورود به حرفه، اصول حسابداری و تشخیص رویدادهای مالی','mint')}${roleCard('assistant','▦','ثبت‌های مالی، کنترل اسناد، حقوق و نرم‌افزار','lav')}${roleCard('accountant','◈','تحلیل حرفه‌ای، مسائل چندمرحله‌ای و گزارشگری','orange')}</div>
 <div class="section-heading"><div><h2>آخرین آزمون‌ها</h2><p>تاریخچه شرکت، نتیجه و روند تکمیل آزمون‌ها</p></div><button class="text-link" data-action="reports">مشاهده همه ←</button></div>
 ${state.exams.length?tableExams(state.exams.slice(0,5)):`<div class="empty-box"><span class="empty-icon">▣</span><strong>هنوز آزمونی ساخته نشده</strong><p>برای شروع، یکی از موقعیت‌های شغلی را انتخاب کنید.</p>${button('شروع اولین آزمون ←','create','btn-soft')}</div>`}
 <div class="notice"><strong>نسخه آزمایشی:</strong> بانک فعلی ${fa(state.meta.total_questions)} سؤال اولیه با وضعیت «پیش‌نویس» دارد؛ آزمون تطبیقی هنوز کالیبراسیون علمی نشده است.</div>`;
}
function roleCard(role,icon,desc,c){return `<article class="role-card"><div class="role-circle ${c==='mint'?'':c}">${icon}</div><h3>${ROLE[role]}</h3><p>${desc}</p><div class="role-bottom"><span>۱۰۰ سؤال • تمامی حوزه‌ها</span><button data-action="choose-role" data-role="${role}">ساخت آزمون ←</button></div></article>`;}
function date(v){if(!v)return '—';try{return new Intl.DateTimeFormat('fa-IR',{dateStyle:'medium'}).format(new Date(v));}catch(e){return v.slice(0,10)}}
function tableExams(items){return `<div class="table-wrap"><table class="data-table"><thead><tr><th>داوطلب</th><th>موقعیت</th><th>تاریخ ایجاد</th><th>پیشرفت</th><th>وضعیت</th><th>اقدام</th></tr></thead><tbody>${items.map(e=>`<tr><td><strong>${esc(e.candidate)}</strong></td><td>${esc(e.role_title)}</td><td class="muted">${date(e.created_at)}</td><td style="min-width:140px"><div class="progress-flex"><div class="progress-rail"><div class="progress-fill" style="width:${e.answered}%"></div></div><span>${fa(e.answered)}٪</span></div></td><td><span class="tag ${e.status==='completed'?'complete':'pending'}">${e.status==='completed'?'پایان‌یافته':e.status==='revoked'?'باطل‌شده':'در جریان'}</span></td><td><button class="text-link" data-action="open-report" data-id="${esc(e.id)}">گزارش ←</button>${e.status==='active'?` <button class="text-link text-danger" data-action="revoke-exam" data-id="${esc(e.id)}">ابطال کد</button>`:''}</td></tr>`).join('')}</tbody></table></div>`;}
function createView(){
 return `${title('آزمون استخدامی جدید','نام داوطلب و موقعیت موردنظر را وارد کنید؛ سامانه به‌صورت خودکار یک آزمون تطبیقی ۱۰۰ سؤالی می‌سازد.','مرحله ۰۱ / تنظیمات آزمون')}
 <div class="two-col"><section class="panel">${errorMarkup()}<form id="new-exam-form">
 <div class="form-group"><label class="form-label" for="candidate-name">نام و نام خانوادگی داوطلب</label><input class="field" id="candidate-name" maxlength="100" minlength="2" required placeholder="مثلاً: مریم احمدی" value="${esc(state.candidateDraft)}" autocomplete="off"><div class="helper">نام فقط در گزارش و فهرست شرکت ذخیره می‌شود.</div></div>
 <div class="form-group"><span class="form-label">موقعیت شغلی</span><div class="role-options">${Object.entries(ROLE).map(([k,r])=>`<button type="button" class="radio-role ${state.selectedRole===k?'is-selected':''}" data-action="select-role" data-role="${k}"><span class="role-em">${k==='intern'?'✦':k==='assistant'?'▦':'◈'}</span>${r}</button>`).join('')}</div></div>
 <div class="form-group"><span class="form-label">تنظیمات قفل‌شده آزمون</span><div class="bank-rows"><div class="report-topic"><span>تعداد سؤالات</span><strong>۱۰۰ سؤال</strong></div><div class="report-topic"><span>پوشش تخصصی</span><strong>۲۵ حوزه</strong></div><div class="report-topic"><span>الگوریتم انتخاب</span><strong>۵۰ پایه + ۵۰ تطبیقی</strong></div><div class="report-topic"><span>نمایش پاسخ</span><strong>فقط مسئول استخدام</strong></div></div></div>
 <button type="submit" class="btn btn-primary">صدور کد اختصاصی داوطلب ←</button></form>
 ${state.created?createdView(state.created):''}</section>
 <aside class="side-panel"><div class="role-circle">♙</div><h3>درباره امنیت آزمون</h3><p class="fineprint">هر داوطلب یک کد اختصاصی با احتمال حدس پایین دریافت می‌کند. کلید پاسخ و منطق تصحیح فقط روی سرور است؛ به مرورگر داوطلب ارسال نمی‌شود.</p>
 <ul class="mini-list"><li><b>✓</b> پاسخ هر سؤال پس از ارسال نهایی است.</li><li><b>✓</b> سطح دشواری به‌صورت پویا تغییر می‌کند.</li><li><b>✓</b> سؤالات همه ۲۵ حوزه پوشش داده می‌شوند.</li><li><b>✓</b> نمره و پاسخنامه فقط داخل پنل مسئول است.</li></ul><div class="notice"><strong>پایلوت:</strong> در استفاده استخدامی واقعی، سؤالات باید توسط متخصص تأیید و سطح دشواری کالیبره شوند.</div></aside></div>`;
}
function createdView(o){return `<div class="created-panel"><span class="tag complete">✓ آزمون ساخته شد</span><h3>کد اختصاصی ${esc(o.candidate)}</h3><p>این کد را فقط به داوطلب تحویل دهید؛ پس از خروج از صفحه، خود کد در گزارش قابل بازیابی نیست.</p>
 <div class="code-box"><strong id="exam-code">${esc(o.code)}</strong><button type="button" data-action="copy-code">کپی کد</button></div>
 <div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:15px"><button type="button" class="btn btn-outline btn-sm" data-action="copy-link">کپی لینک ورود داوطلب</button><button type="button" class="btn btn-soft btn-sm" data-action="candidate-preview">نمایش صفحه ورود داوطلب ←</button></div></div>`;}
function reportsView(){return `${title('گزارش‌های استخدام','فهرست همه آزمون‌ها؛ نتایج و پاسخ‌های صحیح فقط برای شما نمایش داده می‌شوند.')}
 <div class="stats-grid">${stat('کل آزمون‌ها',fa(state.exams.length),'ثبت‌شده در سامانه')}${stat('پایان‌یافته',fa(state.exams.filter(x=>x.status==='completed').length),'قابل تحلیل')}${stat('در حال اجرا',fa(state.exams.filter(x=>x.status==='active').length),'پاسخ‌های در جریان')}${stat('سؤالات هر آزمون','۱۰۰','چهارگزینه‌ای')}</div>
 ${state.exams.length?tableExams(state.exams):`<div class="empty-box"><span class="empty-icon">▤</span><strong>هنوز گزارشی وجود ندارد</strong><p>پس از ساخت آزمون، رکورد آن در این صفحه ظاهر می‌شود.</p>${button('ساخت آزمون ←','create','btn-soft')}</div>`}`;}
function bankView(){const d=state.bank;
 return `${title('بانک تخصصی سؤالات','سهمیه‌های مصوب برای ۳٬۰۰۰ سؤال و وضعیت واقعی پیشرفت نگارش بانک.','مدیریت محتوای آزمون')}
 <div class="stats-grid">${stat('هدف بانک',fa(d.target),'سؤال چهارگزینه‌ای')}${stat('واقعاً آماده‌شده',fa(d.actual),'پیش‌نویس اولیه')}${stat('تأیید مسئول',fa(d.reviewed),'ثبت‌شده با نام بررسی‌کننده')}${stat('حوزه‌های تعریف‌شده',fa(d.categories.length),'پوشش جامع')}</div>
 <div class="panel"><div class="section-heading"><div><h2>پیشرفت نگارش حوزه‌ها</h2><p>نوار پیشرفت، تعداد واقعی نسبت به سهمیه هدف را نشان می‌دهد.</p></div><span class="tag pending">${fa(Math.round(d.actual/d.target*100))}٪ از هدف</span></div><div class="bank-rows">${d.categories.map(c=>`<div class="bank-row"><strong>${esc(c.name)}</strong><div class="progress-rail"><div class="progress-fill" style="width:${Math.min(100,100*(c.actual.easy+c.actual.medium+c.actual.hard)/c.target.total)}%"></div></div><span class="muted">${fa(c.actual.easy+c.actual.medium+c.actual.hard)} / ${fa(c.target.total)}</span></div>`).join('')}</div></div>
 <div class="section-heading"><div><h2>مدیریت سؤالات</h2><p>نمایش پرسش‌ها و پاسخ صحیح فقط برای مسئول استخدام؛ افزودن گروهی با فایل JSON.</p></div><label class="btn btn-soft btn-sm" for="import-file" style="cursor:pointer">+ وارد کردن سؤالات</label><input id="import-file" type="file" accept=".json,application/json" hidden></div>
 <div class="notice"><strong>فرمت ورود:</strong> هر فایل حداکثر ۲۰۰ سؤال جدید؛ پس از ورود همه در وضعیت پیش‌نویس قرار می‌گیرند. <a href="/static/import-template.json" download="question_import_template_FA.json">دریافت قالب نمونه JSON</a></div>
 <div class="panel"><div class="bank-search"><input class="field" id="bank-search" placeholder="جست‌وجو در متن سؤالات..." value="${esc(state.bankSearch)}" /><select class="field" id="bank-filter"><option value="all">همه حوزه‌ها</option>${d.categories.map(c=>`<option value="${esc(c.id)}" ${state.bankFilter===c.id?'selected':''}>${esc(c.name)}</option>`).join('')}</select></div><div id="question-preview">${questionPreview()}</div></div>
 <div class="notice"><strong>گردش بررسی:</strong> ${fa(d.draft)} سؤال پیش‌نویس، ${fa(d.reviewed)} تأیید مسئول و ${fa(d.rejected)} ردشده. تأیید در این پنل به‌معنای تأیید مستقل علمی نیست. ${d.require_approved?'حالت عملیاتی محدود به سؤالات تأییدشده فعال است.':'در حالت آزمایشی، سؤالات پیش‌نویس هم در آزمون استفاده می‌شوند.'}</div>
 ${state.reviewTarget?reviewForm(state.reviewTarget):''}`;
}
function questionPreview(){
 const filtered=state.bankQuestions.filter(q=>(state.bankFilter==='all'||q.category_id===state.bankFilter)&&(!state.bankSearch||((q.stem+' '+q.category).toLowerCase().includes(state.bankSearch.toLowerCase()))));
 return `<p class="helper">${fa(filtered.length)} سؤال از بانک نمایش داده می‌شود.</p>${filtered.slice(0,state.bankLimit).map(q=>`<article class="review-question"><div class="review-top"><span class="tag ${q.difficulty}">${esc(q.category)} • ${esc(DNAME[q.difficulty])}</span><span class="tag ${q.review_status==='approved'?'complete':q.review_status==='rejected'?'hard':'pending'}">${q.review_status==='approved'?'تأیید مسئول':q.review_status==='rejected'?'ردشده':'پیش‌نویس'}</span></div><h4>${esc(q.stem)}</h4><ol class="bank-options">${q.options.map((a,i)=>`<li class="${i===q.correct_index?'answer-key':''}">${esc(a)}${i===q.correct_index?' ✓':''}</li>`).join('')}</ol><div class="review-rationale">${esc(q.rationale)}</div><p class="helper">منبع: ${esc(q.source_reference||'—')} ${q.reviewer_id?' • آخرین بررسی: '+esc(q.reviewer_id):''}</p><button class="btn btn-outline btn-sm" data-action="review-question" data-id="${esc(q.id)}">بررسی تخصصی / تعیین وضعیت</button></article>`).join('')}
 ${filtered.length>state.bankLimit?'<div style="text-align:center;margin-top:15px"><button class="btn btn-muted btn-sm" data-action="more-bank">نمایش سؤال‌های بیشتر</button></div>':''}`;
}
function reviewForm(id){
 const q=state.bankQuestions.find(q=>q.id===id);
 if(!q)return '';
 return `<div class="review-modal-backdrop"><section class="review-modal" role="dialog" aria-modal="true" aria-label="بررسی سؤال"><div class="review-top"><h2>ثبت نتیجه بررسی سؤال</h2><button class="btn btn-muted btn-sm" data-action="cancel-review">بستن ✕</button></div><p class="fineprint">${esc(q.category)} — ${esc(q.stem)}</p>
 <form id="question-review-form"><input type="hidden" name="question_id" value="${esc(id)}" />
 <div class="form-group"><label class="form-label" for="reviewer-name">نام بررسی‌کننده</label><input required minlength="2" maxlength="80" class="field" id="reviewer-name" value="${esc(state.reviewerName)}" placeholder="نام کارشناس بررسی" /></div>
 <div class="form-group"><label class="form-label" for="review-status">نتیجه بررسی</label><select id="review-status" class="field"><option value="approved">تأیید توسط مسئول</option><option value="rejected">رد سؤال</option><option value="draft">بازگشت به پیش‌نویس</option></select></div>
 <div class="form-group"><label class="form-label" for="review-note">مستندات و دلیل بررسی</label><textarea required minlength="12" maxlength="1000" rows="3" id="review-note" class="field" placeholder="صحت محاسبه، روش حل، بررسی گزینه‌ها و منبع را ثبت کنید."></textarea></div>
 <div class="notice"><strong>توجه:</strong> امضای دیجیتال/احراز هویت کارشناسی در این نسخه وجود ندارد؛ تأیید این بخش جایگزین ممیزی علمی مستقل نمی‌شود.</div>
 <button type="submit" class="btn btn-primary">ثبت بررسی و نگهداری سوابق ←</button></form>
 <div class="review-history"><h3>سوابق ثبت‌شده</h3>${state.reviewEvents.length?state.reviewEvents.map(e=>`<div class="history-item"><strong>${esc(e.review_status==='approved'?'تأیید':e.review_status==='rejected'?'رد':'پیش‌نویس')}</strong> • ${esc(e.reviewer)} • ${esc(e.reviewed_at)}<p>${esc(e.note)}</p></div>`).join(''):'<p class="helper">هنوز سابقه‌ای ثبت نشده است.</p>'}</div></section></div>`;
}
function reportView(r){
 const done=r.status==='completed';
 return `${title('گزارش محرمانه داوطلب',`${r.candidate} • ${r.role_title} • ${date(r.created_at)}`,'پنل مسئول استخدام / نتیجه آزمون')}
 <div class="report-actions"><button class="btn btn-muted" data-action="reports">← بازگشت به فهرست</button><button class="btn btn-outline" data-action="print">چاپ / ذخیره PDF</button><button class="btn btn-soft" data-action="csv">دریافت CSV</button></div>
 <div class="result-top">${stat('پاسخ‌داده‌شده',`${fa(r.answered)} / ۱۰۰`,'مجموع سؤالات')}${stat('پاسخ صحیح',fa(r.correct),'از موارد پاسخ‌داده‌شده')}${stat('درصد پاسخ صحیح',`${fa(r.raw_percent)}٪`,'بدون تعدیل دشواری')}${stat('امتیاز وزنی آزمایشی',`${fa(r.weighted_percent)}٪`,'غیرکالیبره و غیرقطعی')}</div>
 <div class="notice"><strong>${done?'آزمون تکمیل شده است.':r.status==='revoked'?'آزمون باطل شده است.':'آزمون هنوز در جریان است.'}</strong> ${esc(r.warning)} از نتیجه به‌تنهایی برای پذیرش یا رد استخدام استفاده نکنید.</div>
 <div class="section-heading"><div><h2>عملکرد در ۲۵ حوزه</h2><p>تعداد پاسخ صحیح نسبت به سؤالات ارائه‌شده در هر حوزه</p></div></div>
 <div class="report-area">${r.areas.map(a=>`<div class="report-topic"><span>${esc(a.category)}</span><strong>${fa(a.correct)} / ${fa(a.answered)}</strong></div>`).join('')}</div>
 <div class="section-heading"><div><h2>پاسخنامه محرمانه</h2><p>گزینه انتخابی، گزینه صحیح و توضیح هر سؤال فقط در این پنل است.</p></div><button class="btn btn-soft btn-sm" data-action="toggle-review">${state.reviewVisible?'بستن پاسخنامه':'نمایش جزئیات پاسخنامه'}</button></div>
 ${state.reviewVisible?`<div class="reviews">${r.details.map(q=>`<article class="review-question"><div class="review-top"><span class="tag ${q.difficulty}">سؤال ${fa(q.position)} • ${esc(DNAME[q.difficulty])}</span><span class="tag ${q.is_correct?'complete': 'hard'}">${q.is_correct?'صحیح':q.choice_index===null?'بی‌پاسخ':'نادرست'}</span></div><h4>${esc(q.stem)}</h4><div class="review-answer ${q.is_correct?'correct':'wrong'}">پاسخ داوطلب: ${q.choice_index===null?'بی‌پاسخ':esc(q.options[q.choice_index])}</div><div class="review-answer correct">پاسخ صحیح: ${esc(q.options[q.correct_index])}</div><div class="review-rationale">${esc(q.rationale)}</div></article>`).join('')}</div>`:''}`;
}
function candidateLoginView(){return `<div class="center-box"><div class="big-icon">▤</div><div class="page-kicker">ورود داوطلب</div><h1>آزمون استخدامی حسابداری</h1><p>کد اختصاصی را از مسئول استخدام دریافت کنید. آزمون ۱۰۰ سؤال است؛ پس از ثبت هر پاسخ، به سؤال بعد می‌روید.</p>${errorMarkup()}<form id="candidate-login-form"><div class="form-group"><label class="form-label" for="candidate-code">کد آزمون</label><input class="field" id="candidate-code" style="direction:ltr;text-align:center;letter-spacing:3px;font:700 18px Arial" maxlength="40" autocomplete="off" required placeholder="XXXXXXXXXXXX"></div><button type="submit" class="btn btn-primary">ورود به آزمون ←</button></form><div class="notice"><strong>محرمانگی:</strong> پاسخ صحیح و نمره آزمون در صفحه داوطلب نمایش داده نمی‌شوند.</div></div>`;}
function candidateCompletedView(){return `<div class="center-box"><div class="big-icon">✓</div><div class="page-kicker">پایان آزمون</div><h1>پاسخ‌های شما ثبت شد</h1><p>۱۰۰ سؤال آزمون ثبت شده است. نتیجه و پاسخنامه تنها برای مسئول استخدام قابل مشاهده است.</p><div class="tag complete">اتمام موفق آزمون</div><div style="margin-top:20px"><button class="btn btn-muted" data-action="candidate-exit">خروج از آزمون</button></div></div>`;}
function candidateQuestionView(d){
 if(d.status==='completed')return candidateCompletedView();
 const q=d.question;
 return `<div class="question-shell"><div class="candidate-head"><div><div class="page-kicker">آزمون اختصاصی • ${esc(d.role_title)}</div><h2>${esc(d.candidate)}</h2><p>هر سؤال چهار گزینه و فقط یک پاسخ صحیح دارد. پاسخ ثبت‌شده قابل تغییر نیست.</p></div><div><div class="progress-flex"><span>${fa(d.answered)} / ۱۰۰</span><div class="progress-rail" style="width:130px"><div class="progress-fill" style="width:${d.answered}%"></div></div></div></div></div>
 <section class="question-card"><div class="question-meta"><span class="tag">سؤال ${fa(q.number)} از ۱۰۰</span><span class="tag medium">${esc(q.category)}</span><span class="tag ${q.difficulty}">${esc(DNAME[q.difficulty])}</span></div>
 <h3>${esc(q.stem)}</h3><div class="choice-list">${q.options.map((o,i)=>`<button class="answer-choice ${state.choice===i?'is-selected':''}" data-action="select-answer" data-choice="${i}"><span class="choice-letter">${['الف','ب','ج','د'][i]}</span><span>${esc(o)}</span></button>`).join('')}</div>
 <div class="question-actions"><button class="btn btn-muted" data-action="skip-answer">بدون پاسخ / رد شدن</button><button class="btn btn-primary" ${state.choice===null?'disabled':''} data-action="submit-answer">${q.number===100?'ثبت پاسخ و پایان آزمون':'ثبت نهایی و سؤال بعدی'} ←</button></div></section>
 <p class="candidate-footnote">پاسخ صحیح، امتیاز و توضیح علمی فقط در پنل مسئول استخدام در دسترس است.</p></div>`;
}
async function showView(view){state.view=view;state.error='';
 try{
 if(!state.admin){show(loginView(!state.meta.initialized));return;}
 if(view==='dashboard'||view==='reports'){state.exams=await api('/api/admin/exams');show(view==='dashboard'?homeView():reportsView());}
 else if(view==='create'){show(createView());}
 else if(view==='bank'){state.bank=await api('/api/admin/bank');state.bankQuestions=await api('/api/admin/questions');show(bankView());}
 else if(view==='report'){
    state.report=await api('/api/admin/reports/'+encodeURIComponent(state.reportId));show(reportView(state.report));
 }
 }catch(e){state.error=e.message;show(`<div class="center-box"><h2>خطا در دریافت اطلاعات</h2><p>${esc(state.error)}</p><button class="btn btn-muted" data-action="refresh">تلاش مجدد</button></div>`);}
}
async function showCandidate(){state.error='';if(!state.candidateCode){show(candidateLoginView());return;}
 try{state.question=await api('/api/candidate/current',{headers:{'X-Exam-Code':state.candidateCode}});show(candidateQuestionView(state.question));}
 catch(e){state.error=e.message;state.candidateCode='';sessionStorage.removeItem('miz_candidate_code');show(candidateLoginView());}
}
function setCode(code){state.candidateCode=String(code||'').trim().toUpperCase();sessionStorage.setItem('miz_candidate_code',state.candidateCode);state.choice=null;}
async function authSubmit(form){state.error='';const password=form.querySelector('#admin-password').value;
 if(!state.meta.initialized){if(password!==form.querySelector('#admin-password2').value){state.error='دو گذرواژه برابر نیستند.';show(loginView(true));return;}
   await api('/api/admin/setup',{method:'POST',body:JSON.stringify({password})});state.meta.initialized=true;toast('حساب مسئول استخدام ساخته شد؛ وارد پنل شوید.');show(loginView(false));return;
 }
 await api('/api/admin/login',{method:'POST',body:JSON.stringify({password})});state.admin=true;await showView('dashboard');toast('ورود به پنل انجام شد.');
}
async function sendAnswer(choice){if(state.busy)return;state.busy=true;
 try{await api('/api/candidate/answer',{method:'POST',headers:{'X-Exam-Code':state.candidateCode},body:JSON.stringify({choice})});state.choice=null;await showCandidate();}
 catch(e){toast('خطا: '+e.message);}finally{state.busy=false;}
}
async function copyText(text){try{await navigator.clipboard.writeText(text);toast('کپی شد.');}catch(e){const el=document.createElement('textarea');el.value=text;document.body.appendChild(el);el.select();document.execCommand('copy');el.remove();toast('متن کپی شد.');}}
async function handleAction(btn){const a=btn.dataset.action;
 if(a==='choose-role'){state.selectedRole=btn.dataset.role;state.created=null;state.candidateDraft='';await showView('create');return;}
 if(a==='select-role'){state.selectedRole=btn.dataset.role;show(createView());return;}
 if(['dashboard','create','reports','bank'].includes(a)){if(a==='create'){state.created=null;state.candidateDraft='';}await showView(a);return;}
 if(a==='open-report'){state.reportId=btn.dataset.id;state.reviewVisible=false;await showView('report');return;}
 if(a==='more-bank'){state.bankLimit+=12;$('#question-preview').innerHTML=questionPreview();return;}
 if(a==='toggle-review'){state.reviewVisible=!state.reviewVisible;show(reportView(state.report));return;}
 if(a==='print'){window.print();return;}
 if(a==='csv'){window.location.href='/api/admin/reports/'+encodeURIComponent(state.reportId)+'.csv';return;}
 if(a==='review-question'){state.reviewTarget=btn.dataset.id;state.reviewEvents=await api('/api/admin/reviews?id='+encodeURIComponent(state.reviewTarget));show(bankView());return;}
 if(a==='cancel-review'){state.reviewTarget=null;show(bankView());return;}
 if(a==='revoke-exam'){
   if(!confirm('کد این آزمون برای همیشه غیرفعال شود؟ پاسخ‌های قبلی برای گزارش باقی می‌مانند.'))return;
   await api('/api/admin/exams/revoke',{method:'POST',body:JSON.stringify({id:btn.dataset.id})});
   await showView(state.view==='reports'?'reports':'dashboard');toast('کد آزمون غیرفعال شد.');return;
 }
 if(a==='copy-code'){await copyText(state.created.code);return;}
 if(a==='copy-link'){await copyText(location.origin+'/candidate#'+state.created.code);return;}
 if(a==='candidate-preview'){window.open('/candidate','_blank','noopener,noreferrer');return;}
 if(a==='select-answer'){state.choice=Number(btn.dataset.choice);show(candidateQuestionView(state.question));return;}
 if(a==='submit-answer'){if(state.choice!==null)await sendAnswer(state.choice);return;}
 if(a==='skip-answer'){if(confirm('این سؤال بی‌پاسخ ثبت می‌شود و قابل بازگشت نیست. ادامه می‌دهید؟'))await sendAnswer(null);return;}
 if(a==='candidate-exit'){state.candidateCode='';sessionStorage.removeItem('miz_candidate_code');show(candidateLoginView());return;}
 if(a==='refresh'){await showView(state.view);return;}
 if(a==='reload'){location.reload();return;}
}
main.addEventListener('click',async ev=>{
 const btn=ev.target.closest('[data-action]');if(!btn)return;
 try{await handleAction(btn);}catch(e){state.error=e.message;toast(e.message);}
});
main.addEventListener('input',ev=>{
 if(ev.target.id==='candidate-name')state.candidateDraft=ev.target.value;
 if(ev.target.id==='bank-search'){
   state.bankSearch=ev.target.value;state.bankLimit=12;
   $('#question-preview').innerHTML=questionPreview();
 }
});
main.addEventListener('change',async ev=>{
 if(ev.target.id==='bank-filter'){
   state.bankFilter=ev.target.value;state.bankLimit=12;
   $('#question-preview').innerHTML=questionPreview();
 }else if(ev.target.id==='import-file' && ev.target.files.length){
   const file=ev.target.files[0];
   if(file.size>1200000){toast('حجم فایل زیاد است؛ هر بار حداکثر ۲۰۰ سؤال وارد کنید.');return;}
   try{
    const raw=JSON.parse(await file.text());
    const result=await api('/api/admin/import',{method:'POST',body:JSON.stringify(raw)});
    toast(`${fa(result.imported)} سؤال به بانک اضافه شد.`);await showView('bank');
   }catch(e){toast('ورود فایل ناموفق بود: '+e.message);}
 }
});
main.addEventListener('submit',async ev=>{
 ev.preventDefault();const form=ev.target;if(!(form instanceof HTMLFormElement))return;
 const submit=form.querySelector('button[type=submit]');if(submit){submit.disabled=true;}
 try{
 if(form.id==='admin-auth-form'){await authSubmit(form);}
 else if(form.id==='new-exam-form'){
   const candidate=form.querySelector('#candidate-name').value.trim();
   state.created=await api('/api/admin/exams',{method:'POST',body:JSON.stringify({candidate,role:state.selectedRole})});
   state.candidateDraft='';show(createView());toast('جلسه استخدامی جدید ساخته شد.');
 }
 else if(form.id==='question-review-form'){
    state.reviewerName=form.querySelector('#reviewer-name').value.trim();
    await api('/api/admin/review',{method:'POST',body:JSON.stringify({question_id:form.querySelector('[name=question_id]').value,
      reviewer:state.reviewerName,status:form.querySelector('#review-status').value,note:form.querySelector('#review-note').value.trim()})});
    state.reviewTarget=null;await showView('bank');toast('بررسی سؤال با سوابق ثبت شد.');
 }
 else if(form.id==='candidate-login-form'){setCode(form.querySelector('#candidate-code').value);await showCandidate();}
 }catch(e){state.error=e.message;
   if(form.id==='admin-auth-form')show(loginView(!state.meta.initialized));
   else if(form.id==='new-exam-form')show(createView());
   else show(candidateLoginView());toast(e.message);
 }finally{if(submit)submit.disabled=false;}
});
document.querySelectorAll('[data-view]').forEach(btn=>btn.addEventListener('click',()=>{if(!state.candidateMode){if(btn.dataset.view==='create'){state.created=null;state.candidateDraft='';}showView(btn.dataset.view);}}));
$('#mobile-menu').addEventListener('click',()=>$('#sidebar').classList.toggle('open'));
$('#logout-btn').addEventListener('click',async()=>{try{await api('/api/admin/logout',{method:'POST',body:'{}'});}catch(e){}state.admin=false;state.created=null;show(loginView(false));});
async function boot(){
 try{state.meta=await api('/api/meta');
 if(state.candidateMode){const hash=decodeURIComponent(location.hash.slice(1));if(hash){setCode(hash);history.replaceState(null,'',location.pathname);}await showCandidate();}
 else{const who=await api('/api/admin/me');state.admin=who.authenticated;await showView('dashboard');}
 }catch(e){show(`<div class="center-box"><h2>ارتباط با سرور برقرار نیست</h2><p>${esc(e.message)}</p><button class="btn btn-muted" data-action="reload">بارگذاری مجدد</button></div>`);}
}
boot();
})();