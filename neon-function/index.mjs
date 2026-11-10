
import net from 'node:net';
import tls from 'node:tls';
import {randomBytes,randomUUID,pbkdf2Sync,createHash,createHmac,timingSafeEqual} from 'node:crypto';

const SPEC=__SPEC_JSON__;
const ASSETS=__ASSETS_JSON__;
const ROLES={intern:'کارآموز حسابداری',assistant:'کمک‌حسابدار',accountant:'حسابدار'};
const LEVELS=['easy','easy','medium','medium','hard','hard','medium','hard'];
const BANK=[];
for (const c of SPEC.categories) {
  for(let ordinal=1;ordinal<=8;ordinal++){
    const n=Number(c.id.slice(-2)),base=n*17+ordinal*11,level=LEVELS[ordinal-1];
    let left,right,extra=0,result,stem,rationale;
    if(level==='easy'){left=base;right=ordinal+4;result=left+right;stem='جمع دو مبلغ فرضی '+left+' و '+right+' ریال چند ریال است؟';rationale='جمع مبالغ '+left+' و '+right+' برابر '+result+' است.';}
    else if(level==='medium'){left=base+120;right=ordinal*7;result=left-right;stem='مبلغ '+left+' ریال پس از کسر '+right+' ریال چقدر است؟';rationale='مانده مبلغ برابر '+result+' ریال است.';}
    else{left=base+150;right=ordinal*3;extra=ordinal+2;result=left+right-extra;stem='مانده فرضی '+left+' ریال با افزودن '+right+' و کسر '+extra+' ریال چند می‌شود؟';rationale='مانده حاصل '+result+' ریال است.';}
    const correct=String(result),vals=[String(result+7),String(result-5),String(result+13),correct],shift=(n+ordinal)%4,options=vals.slice(shift).concat(vals.slice(0,shift));
    BANK.push({id:c.id+'-'+String(ordinal).padStart(2,'0'),category_id:c.id,category:c.name,subtopic:c.subtopics[(ordinal-1)%c.subtopics.length],difficulty:level,stem:'سؤال نمونه شماره '+ordinal+' از '+c.name+': '+stem,options,correct_index:options.indexOf(correct),rationale,review_status:'draft',source_reference:'پیش‌نویس فنی آزمایشی؛ نه ابزار معتبر استخدامی'});
  }
}
const BYID=new Map(BANK.map(q=>[q.id,q]));
const b=(s)=>Buffer.from(s,'utf8'), int=(n)=>{const x=Buffer.alloc(4);x.writeInt32BE(n);return x}, z=(s)=>b(s+'\0');
const pack=(type,payload)=>Buffer.concat([b(type),int(payload.length+4),payload]);
function makeReader(socket){
 let cache=Buffer.alloc(0),messages=[],waiter=null,failed=null;
 socket.on('data',chunk=>{cache=Buffer.concat([cache,chunk]);while(cache.length>=5){const n=cache.readInt32BE(1);if(n<4||n>10000000){failed=Error('Invalid PG packet');socket.destroy();break;}if(cache.length<n+1)break;const msg={type:String.fromCharCode(cache[0]),payload:cache.subarray(5,n+1)};cache=cache.subarray(n+1);if(waiter){const w=waiter;waiter=null;w.resolve(msg)}else messages.push(msg)}});
 socket.on('error',err=>{failed=err;if(waiter){waiter.reject(err);waiter=null}});
 socket.on('close',()=>{failed=failed||Error('Connection closed');if(waiter){waiter.reject(failed);waiter=null}});
 return ()=>{if(messages.length)return Promise.resolve(messages.shift());if(failed)return Promise.reject(failed);return new Promise((resolve,reject)=>waiter={resolve,reject})};
}
async function connectPG(){
 const u=new URL(process.env.DATABASE_URL||'');
 if(!u.hostname)throw Error('Database environment not configured');
 const socket=net.connect({host:u.hostname,port:Number(u.port||5432)});
 await new Promise((resolve,reject)=>{socket.once('connect',resolve);socket.once('error',reject)});
 socket.write(Buffer.from([0,0,0,8,4,210,22,47]));
 const ssl=await new Promise((resolve,reject)=>{socket.once('data',resolve);socket.once('error',reject)});
 if(ssl[0]!==83)throw Error('Postgres TLS required');
 const secure=tls.connect({socket,servername:u.hostname,rejectUnauthorized:true});
 await new Promise((resolve,reject)=>{secure.once('secureConnect',resolve);secure.once('error',reject)});
 secure.setTimeout(15000,()=>secure.destroy(Error('Database timeout')));
 const next=makeReader(secure);
 const user=decodeURIComponent(u.username),password=decodeURIComponent(u.password),database=u.pathname.slice(1);
 secure.write(Buffer.concat([int(4+4+z('user').length+z(user).length+z('database').length+z(database).length+z('client_encoding').length+z('UTF8').length+1),int(196608),z('user'),z(user),z('database'),z(database),z('client_encoding'),z('UTF8'),Buffer.from([0])]));
 const nonce=randomBytes(18).toString('base64url'),firstBare='n=,r='+nonce,first='n,,'+firstBare;
 let expectedServerSignature=null;
 while(true){
  const m=await next();
  if(m.type==='E')throw Error('Postgres authentication rejected');
  if(m.type==='Z')break;
  if(m.type!=='R')continue;
  const code=m.payload.readInt32BE(0);
  if(code===0)continue;
  if(code===10){
    if(!m.payload.subarray(4).toString().includes('SCRAM-SHA-256'))throw Error('Unsupported authentication');
    secure.write(pack('p',Buffer.concat([z('SCRAM-SHA-256'),int(b(first).length),b(first)])));
  }else if(code===11){
    const serverFirst=m.payload.subarray(4).toString();
    const kv=Object.fromEntries(serverFirst.split(',').map(x=>[x[0],x.slice(2)]));
    if(!kv.r?.startsWith(nonce))throw Error('Invalid SCRAM nonce');
    const iterations=Number(kv.i);
    if(!(iterations>=4096&&iterations<=1000000))throw Error('Invalid SCRAM iterations');
    const salted=pbkdf2Sync(password,Buffer.from(kv.s,'base64'),iterations,32,'sha256');
    const clientKey=createHmac('sha256',salted).update('Client Key').digest();
    const storedKey=createHash('sha256').update(clientKey).digest();
    const finalWithout='c=biws,r='+kv.r,authMessage=firstBare+','+serverFirst+','+finalWithout;
    const clientSignature=createHmac('sha256',storedKey).update(authMessage).digest();
    const proof=Buffer.alloc(32);for(let i=0;i<32;i++)proof[i]=clientKey[i]^clientSignature[i];
    expectedServerSignature=createHmac('sha256',createHmac('sha256',salted).update('Server Key').digest()).update(authMessage).digest();
    secure.write(pack('p',b(finalWithout+',p='+proof.toString('base64'))));
  }else if(code===12){
    const verify=m.payload.subarray(4).toString();
    if(!verify.startsWith('v=')||!expectedServerSignature||!timingSafeEqual(Buffer.from(verify.slice(2),'base64'),expectedServerSignature))throw Error('Invalid server signature');
  }else throw Error('Unsupported PG auth '+code);
 }
 return {secure,next};
}
async function sql(query){
 const {secure,next}=await connectPG();
 try{
  secure.write(pack('Q',z(query)));
  const rows=[];let columns=[];
  while(true){
   const m=await next();
   if(m.type==='T'){
    let p=2;const count=m.payload.readInt16BE(0);columns=[];
    for(let i=0;i<count;i++){let q=m.payload.indexOf(0,p);columns.push(m.payload.subarray(p,q).toString());p=q+1+18;}
   }else if(m.type==='D'){
    let p=2;const count=m.payload.readInt16BE(0),row={};
    for(let i=0;i<count;i++){const n=m.payload.readInt32BE(p);p+=4;row[columns[i]]=n===-1?null:m.payload.subarray(p,p+n).toString();if(n!==-1)p+=n;}
    rows.push(row);
   }else if(m.type==='E'){
    let p=0,msg='Database query failed';while(p<m.payload.length&&m.payload[p]!==0){const code=String.fromCharCode(m.payload[p++]);const q=m.payload.indexOf(0,p);if(code==='M')msg=m.payload.subarray(p,q).toString();p=q+1;}
    throw Error(msg);
   }else if(m.type==='Z')return rows;
  }
 }finally{secure.end()}
}
const q=(v)=>"'"+String(v).replaceAll("'","''")+"'";
const sha=(x)=>createHash('sha256').update(x).digest('hex');
const deny=(message='دسترسی مجاز نیست.')=>{const e=Error(message);e.status=403;throw e};
const invalid=(message='اطلاعات ارسالی نامعتبر است.')=>{const e=Error(message);e.status=400;throw e};
function authToken(){
 const exp=Date.now()+12*60*60*1000,raw=randomBytes(16).toString('hex')+':'+exp;
 const sig=createHmac('sha256',process.env.ADMIN_SECRET).update(raw).digest('hex');
 return raw+':'+sig;
}
function isAdmin(request){
 const cookie=(request.headers.get('cookie')||'').match(/(?:^|;\s*)miz_admin=([^;]+)/);
 if(!cookie)return false;
 const token=decodeURIComponent(cookie[1]),fields=token.split(':');
 if(fields.length!==3||!/^\d{13}$/.test(fields[1])||Number(fields[1])<Date.now())return false;
 const raw=fields[0]+':'+fields[1],want=createHmac('sha256',process.env.ADMIN_SECRET).update(raw).digest('hex');
 const got=Buffer.from(fields[2]||''),exp=Buffer.from(want);
 return got.length===exp.length&&timingSafeEqual(got,exp);
}
function json(data,status=200,headers={}){return new Response(JSON.stringify(data),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store','x-content-type-options':'nosniff','referrer-policy':'no-referrer',...headers}})}
function requireAdmin(req){if(!isAdmin(req))deny('لطفاً وارد پنل مسئول استخدام شوید.')}
function requireOrigin(req){
 const o=req.headers.get('origin');if(o&&o!==new URL(req.url).origin)deny('درخواست از مبدأ نامعتبر');
}
async function candidateByCode(req){
 const code=(req.headers.get('x-exam-code')||'').trim().toUpperCase();
 if(!/^[0-9A-F]{16}$/.test(code))deny('کد آزمون نامعتبر است.');
 const rows=await sql("SELECT e.id::text,e.status,e.started_at,e.deadline_at,c.full_name AS candidate,c.role FROM asan.exams e JOIN asan.candidates c ON c.id=e.candidate_id WHERE e.code_hash="+q(sha(code))+" LIMIT 1");
 if(!rows.length)deny('کد آزمون پیدا نشد.');
 return rows[0];
}
async function activate(exam){
 if(exam.status!=='active')return exam;
 if(!exam.started_at){
  await sql("UPDATE asan.exams SET started_at=now(),deadline_at=now()+interval '20 minutes' WHERE id="+q(exam.id)+" AND started_at IS NULL");
  const a=await sql("SELECT started_at,deadline_at FROM asan.exams WHERE id="+q(exam.id));Object.assign(exam,a[0]);
 }
 if(new Date(exam.deadline_at).getTime()<=Date.now()){
  await sql("UPDATE asan.exams SET status='completed',completed_at=now() WHERE id="+q(exam.id)+" AND status='active'");
  exam.status='completed';
 }
 return exam;
}
async function current(exam){
 exam=await activate(exam);
 const replies=await sql("SELECT a.position,a.question_id,a.selected_index,a.is_correct FROM asan.answers a WHERE exam_id="+q(exam.id)+" ORDER BY position");
 const ans=replies.length;
 const base={candidate:exam.candidate,role:exam.role,role_title:ROLES[exam.role],answered:ans,total:100,status:exam.status};
 if(exam.status!=='active')return base;
 const pos=ans+1,existing=await sql("SELECT question_id FROM asan.assignments WHERE exam_id="+q(exam.id)+" AND position="+pos);
 let quest;
 if(existing.length)quest=BYID.get(existing[0].question_id);
 else {
  const category=SPEC.categories[(pos-1)%25].id;
  const used=await sql("SELECT question_id FROM asan.assignments WHERE exam_id="+q(exam.id));
  const previous=new Set(used.map(x=>x.question_id));
  const recent=replies.slice(-8);
  const rating=recent.length>=4?recent.filter(x=>x.is_correct==='t').length/recent.length:.5;
  let ideal=exam.role==='intern'?'easy':exam.role==='assistant'?'medium':'hard';
  if(pos>50){ideal=rating>.75?'hard':rating<.35?'easy':ideal;}
  const levels={easy:0,medium:1,hard:2};
  const pool=BANK.filter(x=>x.category_id===category&&!previous.has(x.id)).sort((a,b)=>Math.abs(levels[a.difficulty]-levels[ideal])-Math.abs(levels[b.difficulty]-levels[ideal]));
  quest=pool[0];
  if(!quest)throw Error('Question bank exhausted');
  await sql("INSERT INTO asan.assignments(exam_id,position,question_id,correct_index) VALUES ("+[q(exam.id),pos,q(quest.id),quest.correct_index].join(',')+") ON CONFLICT DO NOTHING");
 }
 base.question={id:quest.id,category:quest.category,category_id:quest.category_id,difficulty:quest.difficulty,stem:quest.stem,options:quest.options,phase:pos<=50?'anchor':'adaptive',number:pos};
 return base;
}
async function api(req,path){
 const method=req.method,post=method==='POST';
 let data={};if(post){requireOrigin(req);const raw=await req.text();if(raw.length>25000)invalid('درخواست بزرگ است');try{data=JSON.parse(raw||'{}')}catch{invalid('JSON معتبر نیست')}}
 if(path==='/api/meta')return json({initialized:true,total_questions:BANK.length,target_questions:3000,categories:25,exam_length:100,version:'2.2.0-neon-pilot',require_approved:false});
 if(path==='/api/health'){const rows=await sql('SELECT 1 AS ok');return json({online:true,database:rows[0]?.ok==='1',version:'2.2.0-neon-pilot'})}
 if(path==='/api/admin/me')return json({authenticated:isAdmin(req)});
 if(path==='/api/admin/setup')deny('مدیریت حساب تنها در تنظیمات امن سرور ممکن است.');
 if(path==='/api/admin/login'&&post){
  const a=sha(String(data.password||'')),b=sha(process.env.ADMIN_PASSWORD||'');
  if(!timingSafeEqual(Buffer.from(a),Buffer.from(b)))deny('گذرواژه صحیح نیست.');
  return json({authenticated:true},200,{'set-cookie':'miz_admin='+authToken()+'; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=43200'});
 }
 if(path==='/api/admin/logout'&&post)return json({ok:true},200,{'set-cookie':'miz_admin=; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=0'});
 if(path==='/api/candidate/current'&&!post)return json(await current(await candidateByCode(req)));
 if(path==='/api/candidate/answer'&&post){
  const exam=await candidateByCode(req);
  const state=await current(exam);
  if(state.status!=='active')invalid('مهلت آزمون پایان یافته است.');
  const index=data.choice;
  if(index!==null && !(Number.isInteger(index)&&index>=0&&index<=3))invalid('پاسخ نامعتبر است.');
  const pos=state.answered+1,selected=index===null?'NULL':String(index),question=state.question;
  const inserted=await sql("INSERT INTO asan.answers(exam_id,position,question_id,selected_index,correct_index) VALUES ("+[q(exam.id),pos,q(question.id),selected,questCorrect(question.id)].join(',')+") ON CONFLICT DO NOTHING RETURNING position");
  if(!inserted.length)invalid('پاسخ قبلاً ثبت شده است.');
  if(pos===100)await sql("UPDATE asan.exams SET status='completed',completed_at=now() WHERE id="+q(exam.id)+" AND status='active'");
  return json({accepted:true,answered:pos,total:100,finished:pos===100});
 }
 if(path==='/api/candidate/finish'&&post){
  const exam=await candidateByCode(req);
  await sql("UPDATE asan.exams SET status='completed',completed_at=now() WHERE id="+q(exam.id)+" AND status='active'");
  return json({finished:true});
 }
 if(!path.startsWith('/api/admin/'))return json({error:'مسیر پیدا نشد.'},404);
 requireAdmin(req);
 if(path==='/api/admin/exams'&&!post){
  const rows=await sql("SELECT e.id::text,c.full_name AS candidate,c.role,e.created_at,e.completed_at,e.status,count(a.position)::text AS answered FROM asan.exams e JOIN asan.candidates c ON c.id=e.candidate_id LEFT JOIN asan.answers a ON a.exam_id=e.id GROUP BY e.id,c.full_name,c.role ORDER BY e.created_at DESC");
  return json(rows.map(r=>({...r,role_title:ROLES[r.role],answered:Number(r.answered)})));
 }
 if(path==='/api/admin/exams'&&post){
  const candidate=String(data.candidate||'').trim(),role=data.role;
  if(candidate.length<2||candidate.length>100||!ROLES[role])invalid('نام داوطلب یا نقش نامعتبر است.');
  const cid=randomUUID(),eid=randomUUID(),code=randomBytes(8).toString('hex').toUpperCase();
  await sql("INSERT INTO asan.candidates(id,full_name,role) VALUES ("+[q(cid),q(candidate),q(role)].join(',')+")");
  await sql("INSERT INTO asan.exams(id,candidate_id,code_hash) VALUES ("+[q(eid),q(cid),q(sha(code))].join(',')+")");
  return json({id:eid,code,candidate,role,role_title:ROLES[role]},201);
 }
 if(path==='/api/admin/exams/revoke'&&post){
  const id=String(data.id||'');if(!/^[0-9a-f-]{36}$/i.test(id))invalid();
  await sql("UPDATE asan.exams SET status='revoked' WHERE id="+q(id)+" AND status='active'");
  return json({id,status:'revoked'});
 }
 if(path==='/api/admin/bank'&&!post)return json({target:3000,actual:200,reviewed:0,draft:200,rejected:0,categories:SPEC.categories.map(c=>({id:c.id,name:c.name,actual:{easy:2,medium:3,hard:3},target:c.quota})),status:'pilot_draft',require_approved:false});
 if(path==='/api/admin/questions'&&!post)return json(BANK);
 if(path==='/api/admin/reviews'&&!post)return json([]);
 if(path==='/api/admin/import'&&post)invalid('ورود بانک سؤالات در نسخه پایلوت ابری غیرفعال است.');
 if(path==='/api/admin/review'&&post)invalid('ثبت تأیید علمی در نسخه پایلوت ابری غیرفعال است.');
 if(path.startsWith('/api/admin/reports/')&&!post){
  const csv=path.endsWith('.csv');
  const id=path.split('/').at(-1).replace(/\.csv$/,'');
  if(!/^[0-9a-f-]{36}$/i.test(id))invalid();
  const rows=await sql("SELECT e.id::text,c.full_name AS candidate,c.role,e.created_at,e.completed_at,e.status FROM asan.exams e JOIN asan.candidates c ON c.id=e.candidate_id WHERE e.id="+q(id));
  if(!rows.length)invalid('آزمون پیدا نشد.');
  const e=rows[0],responses=await sql("SELECT position,question_id,selected_index,correct_index,is_correct FROM asan.answers WHERE exam_id="+q(id)+" ORDER BY position");
  const details=responses.map(r=>{const a=BYID.get(r.question_id);return {...a,position:Number(r.position),choice_index:r.selected_index===null?null:Number(r.selected_index),is_correct:r.is_correct==='t',phase:Number(r.position)<=50?'anchor':'adaptive'}});
  if(csv){
   const escapeCSV=x=>{let v=String(x??'');if(/^[\s]*[=+\-@]/.test(v))v="'"+v;return '"'+v.replaceAll('"','""')+'"'};
   const lines=[['ردیف','حوزه','سطح','سؤال','پاسخ داوطلب','پاسخ صحیح','درست؟','توضیح']];
   for(const d of details)lines.push([d.position,d.category,d.difficulty,d.stem,d.choice_index===null?'بی‌پاسخ':d.options[d.choice_index],d.options[d.correct_index],d.is_correct?'بله':'خیر',d.rationale]);
   return new Response('\ufeff'+lines.map(row=>row.map(escapeCSV).join(',')).join('\r\n'),{headers:{'content-type':'text/csv; charset=utf-8','content-disposition':'attachment; filename="asan-report.csv"','cache-control':'no-store'}});
  }
  const byCat=SPEC.categories.map(c=>{const d=details.filter(x=>x.category_id===c.id);return {category:c.name,answered:d.length,correct:d.filter(x=>x.is_correct).length,weight_total:d.length,weight_correct:d.filter(x=>x.is_correct).length}});
  const correct=details.filter(x=>x.is_correct).length,skipped=details.filter(x=>x.choice_index===null).length;
  return json({...e,role_title:ROLES[e.role],answered:details.length,correct,wrong:details.length-correct-skipped,skipped,raw_percent:details.length?Math.round(correct/details.length*1000)/10:0,weighted_percent:details.length?Math.round(correct/details.length*1000)/10:0,areas:byCat,details,calibrated:false,comparable_between_candidates:false,warning:'بانک عمومی نمایشی و غیرقابل استفاده برای تصمیم استخدامی قطعی است.'});
 }
 return json({error:'مسیر پیدا نشد.'},404);
}
function questCorrect(id){const x=BYID.get(id);if(!x)throw Error('Missing question');return x.correct_index}
export default {
 async fetch(req){
  try{
   const p=new URL(req.url).pathname;
   if(p.startsWith('/api/'))return await api(req,p);
   if(req.method!=='GET')return json({error:'Method not allowed'},405);
   if(p==='/'||p==='/admin'||p==='/candidate'){
    return new Response(ASSETS['index.html'],{headers:{'content-type':'text/html; charset=utf-8','cache-control':'no-store','content-security-policy':"default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"}});
   }
   if(p.startsWith('/static/')){
    const name=p.slice(8),asset=ASSETS[name];if(asset===undefined)return json({error:'Not found'},404);
    const types={'app.js':'application/javascript','styles.css':'text/css','theme-green.css':'text/css','logo.svg':'image/svg+xml','manifest.webmanifest':'application/manifest+json','import-template.json':'application/json'};
    return new Response(asset,{headers:{'content-type':(types[name]||'text/plain')+'; charset=utf-8','cache-control':'public,max-age=1800'}});
   }
   return json({error:'Not found'},404);
  }catch(e){console.error('asan api error',e.message);return json({error:e.status?e.message:'خطای سرویس؛ اتصال را بررسی کنید.'},e.status||500);}
 }
};
