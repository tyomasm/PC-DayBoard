const $ = selector => document.querySelector(selector);
function element(tag, text, className) {
    const node = document.createElement(tag);
    node.textContent = text;
    if (className) node.className = className;
    return node;
}
const timeOf = stamp => clockFormat.format(new Date(stamp * 1000));
const dateOf = new Intl.DateTimeFormat('ja-JP', {timeZone:'Asia/Tokyo', month:'numeric', day:'numeric'});
const displayTime = stamp => dateOf.format(new Date(stamp * 1000)) + ' ' + timeOf(stamp);
const conditions = new Map();
for (const [codes, name, symbol] of [
    [[0], '快晴', 'sun'], [[1], '晴れ', 'sun'], [[2], '晴れ時々曇り', 'part'],
    [[3], '曇り', 'cloud'], [[45,48], '霧', 'fog'],
    [[51,53,55,56,57,61,63,65,66,67,80,81,82], '雨', 'rain'],
    [[71,73,75,77,85,86], '雪', 'snow'], [[95,96,99], '雷雨', 'thunder']
]) {
    for (const code of codes) conditions.set(code, {name, symbol});
}
function condition(code) {
    return conditions.get(code) || {name:'予報不明', symbol:'info'};
}
function forecastIcon(code) {
    const {name, symbol} = condition(code);
    const pictogram = element('span', '', 'weather-icon');
    pictogram.title = name;
    pictogram.setAttribute('role', 'img');
    pictogram.setAttribute('aria-label', name);
    pictogram.innerHTML = icon(symbol);
    return pictogram;
}
function renderWeather(data) {
    if (!data) {
        $('.temp').textContent = '—';
        $('.condition').textContent = '—';
        $('.limits').textContent = '';
        $('.weatherinfo').replaceChildren();
        $('#forecasts').replaceChildren();
        return;
    }
    const c = data.current;
    $('.temp').replaceChildren(String(Math.round(c.temperature_2m)), element('sup','°C'));
    $('.condition').textContent = condition(c.weather_code).name;
    $('.limits').textContent = '↑ ' + Math.round(data.high) + '°　↓ ' + Math.round(data.low) + '°';
    const direction = ['北','北東','東','南東','南','南西','西','北西'][Math.round(c.wind_direction_10m / 45) % 8];
    $('.weatherinfo').replaceChildren(element('span','湿度 ' + c.relative_humidity_2m + '%'),element('span',direction + '風 ' + c.wind_speed_10m + ' m/s'));
    const day = dateOf.format(new Date());
    $('#forecasts').replaceChildren(...data.forecast.map(([stamp,temp,code]) => {
        const when = new Date(stamp);
        const label = (day === dateOf.format(when) ? '' : '翌') + clockFormat.format(when).slice(0,2) + '時';
        const cell = element('div','','forecast');
        cell.append(element('small',label),forecastIcon(code),element('b',temp+'°'));
        return cell;
    }));
}

let localForecast = null;
function drawForecast() {
    const source = localForecast || snapshot.weather;
    $('#place').textContent = localForecast ? '現在地付近' : (source?.data ? '設定地点' : '地点未設定');
    $('#weather-status').textContent = (source?.status || '取得中') +
        (source?.stamp ? ' · 最終取得 '+displayTime(source.stamp) : '');
    renderWeather(source?.data);
}

let page = 0;
let restore;
let snapshot = {};
function position(event, now) {
    if (event.allDay) return 2;
    if (event.start > now) return 1;
    return event.end > now ? 0 : 3;
}
function renderAgenda() {
    const source = snapshot.agenda;
    if (!source) return;
    const now = Date.now()/1000;
    const events = (source.data || []).slice().sort((a,b) => position(a,now)-position(b,now)
        || (position(a,now) === 3 ? b.end-a.end : a.start-b.start));
    page = Math.min(page, Math.max(0, Math.ceil(events.length/3)-1));
    $('#eventcount').textContent = source.data ? events.length+'件' : '';
    $('#pager').hidden = events.length <= 3;
    $('#prev').disabled = page === 0;
    $('#next').disabled = (page+1)*3 >= events.length;
    $('#range').textContent = (page*3+1)+'–'+Math.min(page*3+3,events.length)+' / '+events.length;
    const list = $('#agenda');
    list.replaceChildren();
    if (!events.length) list.textContent = source.data ? '今日の予定はありません' : source.status;
    for (const event of events.slice(page*3,page*3+3)) {
        const row = document.createElement('li');
        const times = element('div',event.allDay ? '終日' : timeOf(event.start),'times');
        if (!event.allDay) times.append(element('small',timeOf(event.end)));
        const stripe = element('span','','stripe');
        stripe.style.setProperty('--accent', ['#accba5','#9dbbd2','#d4b580','#89928a'][position(event,now)]);
        const title = element('button',event.title,'event');
        title.onclick = () => {
            $('#details p').textContent = [event.title,event.place].filter(Boolean).join('　');
            $('#details').showModal();
        };
        const content = document.createElement('div');
        content.append(title,element('div',event.place,'eventmeta'));
        row.append(times,stripe,content);
        list.append(row);
    }
}
function movePage(delta) {
    page += delta;
    renderAgenda();
    clearTimeout(restore);
    restore = setTimeout(() => {page=0;renderAgenda()},60000);
}
$('#prev').onclick = () => movePage(-1);
$('#next').onclick = () => movePage(1);
function renderNews() {
    const source = snapshot.news;
    if (!source) return;
    const category = $('#market').value;
    const articles = (source.data || []).filter(a => a.stamp === null || Date.now()/1000-a.stamp < 172800);
    const list = $('#news');
    list.replaceChildren();
    for (const item of articles.filter(a => category === 'すべて' || a.tag === category).slice(0,4)) {
        const row = element('article','','newsrow');
        const link = element(item.url ? 'a' : 'span',item.title);
        if (item.url) link.href = item.url;
        link.title = item.title;
        link.target = '_blank';
        link.rel = 'noreferrer';
        const heading = element('h3','');
        heading.append(link);
        row.append(element('time',item.stamp === null ? 'サンプル' : displayTime(item.stamp)),element('span',item.tag,'tag '+({'為替':'fx','株式':'stock','経済':'macro'}[item.tag])),heading);
        list.append(row);
    }
    if (!list.childElementCount) list.textContent = !source.data ? source.status : articles.length ? 'この分類の配信はありません' : '直近48時間の配信なし';
}
$('#market').onchange = renderNews;
let busy = false;
let previousMinute = -1;
async function refresh() {
    if (busy) return;
    busy = true;
    try {
        const res = await fetch('/api/dashboard',{signal:AbortSignal.timeout(8000)});
        if (!res.ok) throw Error();
        const next = await res.json();
        const minute = Math.floor(Date.now()/60000);
        const old = snapshot;
        snapshot = next;
        for (const [key, draw] of Object.entries({weather:renderWeather,agenda:renderAgenda,news:renderNews})) {
            if (key === 'weather') {
                if (!localForecast) drawForecast();
                continue;
            }
            const source = next[key];
            $('#'+key+'-status').textContent = source.status + (source.stamp ? ' · 最終取得 '+displayTime(source.stamp) : '');
            if (JSON.stringify(old[key]) !== JSON.stringify(source) || minute !== previousMinute) draw(source.data);
        }
        previousMinute = minute;
        $('.sample').textContent = 'ローカル表示';
    } catch {
        $('.sample').textContent = 'サーバー接続失敗';
    } finally {busy = false}
}
refresh();
setInterval(refresh,15000);
document.addEventListener('visibilitychange',() => {if (!document.hidden) refresh()});
