
const icon = name => '<svg class="icon '+name+'" aria-hidden="true"><use href="#ico-'+name+'"/></svg>';
document.querySelectorAll('[data-i]').forEach(el => el.outerHTML=icon(el.dataset.i));
const dayFormat=new Intl.DateTimeFormat('ja-JP',{timeZone:'Asia/Tokyo',year:'numeric',month:'long',day:'numeric',weekday:'long'});
const clockFormat=new Intl.DateTimeFormat('ja-JP',{timeZone:'Asia/Tokyo',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
function tick(){const t=new Date();document.querySelector('#today').textContent=dayFormat.format(t);document.querySelector('#now').textContent=clockFormat.format(t)}
tick();setInterval(tick,1000);
const full=document.querySelector('#full');
full.onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen()}catch{const msg=document.querySelector('#message');msg.textContent='ブラウザーの全画面機能（PCでは通常 F11）を利用してください。';msg.hidden=false;setTimeout(()=>msg.hidden=true,6500)}};
document.addEventListener('fullscreenchange',()=>{const label=document.fullscreenElement?'全画面を終了':'全画面表示';full.querySelector('span').textContent=label;full.setAttribute('aria-label',label)});
