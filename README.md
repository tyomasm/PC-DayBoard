# PC-DayBoard

Windows 11 ProのサブPCで、日本時間の時計・天気・今日の予定・マーケットニュースをブラウザーの1画面に常時表示します。

## 仕様概要

| 項目 | 表示内容 | 更新間隔 |
| --- | --- | --- |
| 天気 | 現在地または設定地点の気温と、3時間ごとの予報6枠（天気アイコン・気温） | 30分 |
| 今日の予定 | iCloudカレンダーの当日分を3件ずつ表示。前後のページに切り替え可能 | 5分 |
| マーケットニュース | 初期はサンプル3件。RSS設定後は、株式・為替・経済で絞り込める最新見出しを最大4件表示 | RSS設定後は30分 |

## 起動

1. リポジトリをダウンロードして展開します。Windowsターミナルで `winget install --id astral-sh.uv -e` を実行します。
2. 新しいターミナルで展開先を開き、`uv python install 3.12`、続いて `uv sync --frozen` を実行します。
3. `start.cmd` を開くとブラウザーが起動します（http://127.0.0.1:8766/）。自動起動するには、このファイルのショートカットを `shell:startup` に置きます。終了はコンソールで Ctrl+C です。

## ニュースの配信元を選ぶ

初期状態では「サンプル」と明記した架空の見出しを3件表示します。RSSへの通信は行いません。

1. [settings.example.toml](settings.example.toml) を同じフォルダーに `settings.toml` としてコピーします。
2. `rss_url = ""` の引用符の中に、利用するRSSのHTTPS URLを入力します。設定例としてYahoo!ニュース「経済」のURLをコメントに記載しています。実際に利用する配信元の条件を確認してください。[Yahoo!ニュースRSSの個人利用条件](https://news.yahoo.co.jp/rss)
3. Dayboardを再起動すると反映されます。空欄に戻すとサンプル表示に戻ります。

対応形式はRSS 2.0（各記事にtitle、HTTPSのlink、pubDateが必要）です。毎時05分・35分に確認し、直近48時間の見出しを選択中の分類から最大4件表示します。

## 天気と予定

- 天気は「現在地の天気を使う」を押して許可すると表示されます。緯度・経度を小数第2位に丸めてOpen-Meteoに送ります。代替地点は任意で `settings.toml` の `latitude` と `longitude` に設定できます。初期状態では代替地点は未設定です。
- iCloudは任意です。サーバーを終了し、`uv run --frozen dayboard.py --setup` でApple Account・アプリ用パスワードを入力してカレンダーを選択します。再起動後、5分ごとに当日分を更新します。パスワードはWindows資格情報マネージャー、設定とキャッシュは `%LOCALAPPDATA%\PC-DayBoard` に保存します。
- 設定ファイルはUTF-8で保存します。テストは `uv run --frozen python -m unittest discover -s tests -v` で実行できます。
