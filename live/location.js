// Keep only the current forecast in this tab. Store the user's preference without coordinates.
const locateButton = $('#locate');
const note = $('#geo-note');
let permission;
let pending = false;
let generation = 0;
let nextCheck = 0;
const interval = 30 * 60 * 1000;

function fallback(reason) {
    localForecast = null;
    note.textContent = reason;
    drawForecast();
}

async function locate(manual = false) {
    if (pending || (!manual && (Date.now() < nextCheck || permission?.state !== 'granted' ||
        localStorage.getItem('dayboard-location') !== 'on'))) return;
    pending = true;
    const version = ++generation;
    locateButton.disabled = true;
    nextCheck = (Math.floor(Date.now()/interval)+1)*interval;
    try {
        if (!navigator.geolocation) throw new Error('このブラウザーでは測位できません');
        if (manual) localStorage.setItem('dayboard-location','on');
        note.textContent = '現在地を確認中';
        const position = await new Promise((resolve, reject) =>
            navigator.geolocation.getCurrentPosition(resolve, reject,
                {enableHighAccuracy:false, timeout:10000, maximumAge:300000}));
        if (version !== generation) return;
        localStorage.setItem('dayboard-location','on');
        fallback('現在地の予報を取得中');
        const response = await fetch('/api/weather/location', {
            method:'POST', headers:{'Content-Type':'application/json'},
            body:JSON.stringify({latitude:Number(position.coords.latitude.toFixed(2)),
                                 longitude:Number(position.coords.longitude.toFixed(2))}),
            signal:AbortSignal.timeout(15000)
        });
        if (!response.ok) throw new Error('予報取得失敗');
        const forecast = await response.json();
        if (version !== generation) return;
        localForecast = forecast;
        drawForecast();
        note.textContent = '';
        locateButton.textContent = '現在地を再取得';
    } catch (err) {
        if (version !== generation) return;
        if (err.code === 1) localStorage.removeItem('dayboard-location');
        fallback(err.code === 1 ? '位置情報の許可が必要です' :
            err.code === 3 ? '測位がタイムアウトしました' : '現在地の予報を取得できません');
    } finally {
        pending = false;
        locateButton.disabled = false;
    }
}

locateButton.onclick = () => locate(true);
async function watchPermission() {
    if (!navigator.permissions) return;
    try { permission = await navigator.permissions.query({name:'geolocation'}); }
    catch { return; }
    permission.onchange = () => {
        if (permission.state !== 'granted') {
            generation++;
            localStorage.removeItem('dayboard-location');
            fallback('位置情報の許可が必要です');
        }
    };
    locate();
}
watchPermission();
setInterval(() => locate(),15000);
document.addEventListener('visibilitychange',() => {if (!document.hidden) locate()});
