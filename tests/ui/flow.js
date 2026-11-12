const {JSDOM}=require('jsdom');
const base='http://127.0.0.1:8765';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const html=await (await fetch(base+'/')).text();
 const errs=[];
 const dom=new JSDOM(html,{runScripts:'dangerously',url:base+'/',pretendToBeVisual:true,beforeParse(w){
   w.fetch=(u,o)=>fetch(new URL(u,base),o);w.FormData=FormData;w.File=File;w.AbortController=AbortController;
   w.addEventListener('error',e=>errs.push('window error: '+e.message));w.alert=m=>errs.push('alert: '+m)}});
 const w=dom.window,d=w.document,$=s=>d.querySelector(s);
 await sleep(800);
 const log=(...a)=>console.log(...a);
 log('samples in dropdown:',[...$('#sample').options].map(o=>o.textContent).join(' | '));
 // Flow 1: sample 1 -> review -> try submit while locked -> dismiss all -> submit
 $('#sample').value='0';$('#sample').dispatchEvent(new w.Event('change'));
 log('title auto-filled:',$('#title').value);
 $('#useai').checked=false;$('#run').click();await sleep(800);
 log('findings cards:',d.querySelectorAll('#res .card').length,'| submit disabled:',d.querySelector('#res button.p[onclick="submitIt()"]').disabled);
 log('lock message:',($('#res .err')||{}).textContent);
 let n=0;for(let k=0;k<30;k++){const b=[...d.querySelectorAll('#res button')].find(x=>x.textContent==='Dismiss');if(!b)break;b.click();n++}
 log('dismiss clicks:',n);
 const sb=d.querySelector('#res button.p[onclick="submitIt()"]');log('submit disabled after dismissals:',sb.disabled);
 sb.click();await sleep(900);
 log('on queue tab:',$('#queue').classList.contains('on'),'| queue has title:',$('#queue').textContent.includes('Launch'));
 // Flow 2: empty title message
 $('nav button[data-t="new"]').click();$('#title').value='';$('#sample').value='2';$('#sample').dispatchEvent(new w.Event('change'));$('#title').value='';
 $('#run').click();await sleep(700);d.querySelector('#res button.p[onclick="submitIt()"]').click();await sleep(300);
 log('empty-title message:',($('#msg')||{}).textContent);
 // Flow 3: sample file upload (off-brand image)
 $('#title').value='';$('#sample').value='';clearFile=w.clearFile;
 d.querySelector('.sf[data-f="bad_post.png"]').click();await sleep(1500);
 log('file info:',$('#fileinfo').textContent.slice(0,140));
 log('file findings:',[...d.querySelectorAll('#res .card .src')].map(e=>e.textContent.slice(0,6)).join(','));
 // Flow 4: docx sample
 d.querySelector('.sf[data-f="launch_brief.docx"]').click();await sleep(1500);
 log('docx text filled:',$('#text').value.slice(0,60).replace(/\n/g,' / '),'| img checked:',$('#img').checked);
 log('docx cards:',d.querySelectorAll('#res .card').length);
 // Flow 5: benchmark + kb + insights tabs
 for(const t of ['bench','kb','insights','queue']){$('nav button[data-t="'+t+'"]').click();await sleep(700);log(t,'tab text length:',$('#'+t).textContent.length)}
 log('bench head:',$('#bench').textContent.slice(0,90));
 log('errors:',errs.length?errs:'none');
 process.exit(0)})().catch(e=>{console.log('TEST CRASH',e);process.exit(1)});
