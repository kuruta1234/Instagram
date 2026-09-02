# ig-toolkit

Instagram投稿の準備作業(画像加工・キャプション作成)を効率化するための、
ローカルで動くツールです。ブラウザで操作する**GUI(`igtool-gui`)**と、ターミナルで使う
**CLI(`igtool`)**の両方を用意しています(内部ロジックは共通)。

- **自動投稿は行いません。** 最終的な投稿はInstagramアプリから手動で行う前提で、
  「投稿に必要な画像とキャプション文をワンステップで用意する」ところまでを自動化します。
- キャプション・ハッシュタグは、**Claude Code CLI(`claude`コマンド)を呼び出して画像を見た上で自動生成**します。
  `claude` コマンドが既にログイン済み(Claude Pro/Max/Team等のサブスクリプション、または`claude`に設定した
  APIキー)であれば動作します。`claude` コマンドはFreeプランでは利用できないため、Freeプランや
  `claude` コマンド未導入の環境では自動生成は使えません(Anthropic APIキーへのフォールバックは行いません
  — 結局追加の有料契約が必要になってしまうためです)。その場合はキャプション・ハッシュタグを
  そのまま手入力できます。生成後のテキストも自由に編集して保存できます。
- 画像トリミングはGUIでは**中央固定ではなく、ドラッグで任意の範囲を選択でき、ズームイン・アウトも可能**です。
- 画像の自動補正・背景除去・透かし合成・**イラスト化(OpenCVによるセルシェーディング風の減色+輪郭線抽出で、明るく鮮やかなポスター/カートゥーン風に変換)**もまとめて扱えます。
- 画像へのテキスト合成は**日本語フォントを同梱**しているため文字化けせず、フォント(ゴシック/明朝)・サイズ・色を選べます。
- GUIのエクスポートは画像+キャプションをZIPファイルとしてその場でダウンロードします。

## セットアップ

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

cp .env.example .env
# 必要に応じてデータ保存先などを .env で変更(未編集でも動作します)
```

キャプション自動生成を使うには [Claude Code](https://claude.com/claude-code) をインストールし、
Pro以上のプランでログインしてください(Freeプランは非対応)。

```bash
npm install -g @anthropic-ai/claude-code
claude login   # Claude Pro/Max/Team等のアカウントでログイン
```

`claude` コマンドが使えない場合(Freeプランなど)は、自動生成の代わりにキャプション・
ハッシュタグをそのまま手入力できます(セットアップ不要)。

イラスト化はOpenCV(`opencv-python-headless`)を使うため、`pip install -e .` で自動的にインストールされます(追加のモデルダウンロードは不要です)。
ただし、色の減色と輪郭線抽出による「セルシェーディング風」変換であり、目を大きくしたり顔立ちそのものを描き直すような
生成AIスタイル変換(例: アニメ風の目が大きいイラスト)ではない点にご注意ください。そこまでの変換は生成AI画像モデルの
領域で、ローカル・無料では実現が難しいため今回のスコープには含めていません。

背景除去(自動補正メニューの「背景を除去する」/ `igtool edit --bg-remove`)を使う場合は追加でインストールします(初回はモデルダウンロードが走るため少し時間がかかります)。

```bash
pip install rembg onnxruntime
```

## GUIで使う(`igtool-gui`)

```bash
igtool-gui
```

ローカルサーバーが起動し、自動的にブラウザで `http://127.0.0.1:5000` が開きます
(開かない場合は手動でアクセスしてください)。ポートを変えたい場合は `IGTOOL_WEB_PORT` 環境変数を設定します。

画面の流れ:

1. **新規作成** — トピックを入力し、画像をアップロード
2. **投稿詳細ページ** — 「Claudeでキャプションを生成」ボタンで、画像を見た上でのキャプション・ハッシュタグ案を自動作成(`claude`コマンドが使えない場合はエラーメッセージが表示されるので、下のテキストボックスに直接手入力する)。内容はそのままテキストボックスで自由に編集して保存できる
3. **画像編集ページ** — 画像上をドラッグして任意の範囲を選択してトリミング(中央固定ではありません)。マウスホイールやズームスライダーで拡大・縮小、アスペクト比ボタン(自由/1:1/4:5/1.91:1/9:16)や出力サイズ指定も可能。自動補正・背景除去・イラスト化・透かし・テキスト合成(フォント/サイズ/色を選択可)もここから実行できる
4. **エクスポート** — 「画像+キャプションをダウンロード(ZIP)」ボタンで、画像とキャプションをZIPファイルとしてダウンロードし、Instagramアプリから手動で投稿

画像トリミングを動かすCropper.jsはリポジトリに同梱済み(`ig_toolkit/webapp/static/vendor/`)のため、この部分はオフラインでも動作します。

## CLIで使う(`igtool`)

GUIの代わりにターミナルからスクリプト的に操作したい場合は、`igtool` コマンドが使えます。

| 機能 | コマンド | 説明 |
|---|---|---|
| 下書き作成 | `igtool new` | トピック・画像から投稿ドラフトを作成 |
| 一覧・詳細確認 | `igtool list` / `igtool show` | 下書きの状態を確認 |
| キャプション生成 | `igtool caption` | 画像を見てClaudeがキャプション/ハッシュタグを自動生成(`claude`コマンドが使えない場合は自動的に手入力に切り替わる。`--manual`で最初から手入力も可) |
| 画像編集 | `igtool edit` | Instagram向けリサイズ(中央クロップ)・自動補正・イラスト化・背景除去・透かし・テキスト合成(フォント/サイズ/色指定可) |
| エクスポート | `igtool export` | 投稿用の画像とキャプションテキストをまとめて書き出す(手動投稿用。CLIではdata/exports/にファイルとして保存) |
| 投稿済みマーク | `igtool mark-posted` | 手動投稿が終わった投稿を記録 |
| 削除 | `igtool delete` | 投稿ドラフトを削除 |

CLIの `igtool edit --preset` は中央固定のクロップです。任意の範囲を選んでトリミングしたい場合はGUI(`igtool-gui`)の画像編集ページを使ってください。

## CLIの基本的な使い方

```bash
# 1. 下書きを作成(画像は複数指定可)
igtool new --topic "秋の新作紅茶" --image ./photos/tea1.jpg --image ./photos/tea2.jpg

# 2. 画像を編集(正方形にトリミング+自動補正、必要ならロゴ透かしも)
igtool edit <post_id> --preset square --enhance
igtool edit <post_id> --watermark ./assets/logo.png --watermark-position bottom-right

# イラスト風に変換したり、日本語テキストを合成することもできる
igtool edit <post_id> --illustrate
igtool edit <post_id> --text "秋の新作紅茶" --text-font mincho --text-size 72 --text-color "#ffcc00"

# 3. Claudeが画像を見てキャプション・ハッシュタグを自動生成
# (`claude`コマンドが使えない場合は自動的に手入力プロンプトに切り替わります)
igtool caption <post_id>
igtool caption <post_id> --notes "季節限定であることを強調して"

# 最初から手入力したい場合は --manual を付ける
igtool caption <post_id> --manual
igtool caption <post_id> --caption-text "秋限定の新作紅茶が入荷しました。" --hashtags "紅茶,秋限定"

# 4. 内容を確認
igtool show <post_id>

# 5. 画像+キャプションテキストをエクスポートして、Instagramアプリから手動投稿
igtool export <post_id>

# 6. 投稿が終わったらマーク
igtool mark-posted <post_id>
```

投稿ドラフトの状態は `draft → posted` の2段階です。

## データの保存場所

すべてのデータは `data/` 配下にローカル保存されます(Git管理対象外)。

```
data/
  posts/<post_id>/
    meta.yaml            投稿メタデータ(トピック・キャプション・ハッシュタグなど)
    images/original/     取り込んだ元画像
    images/edited/        編集後の画像
  exports/<post_id>/     手動投稿用にエクスポートした画像+caption.txt
```

保存先の場所は `.env` の `IGTOOL_DATA_DIR` で変更できます(`.env.example` 参照)。
使用する `claude` コマンド名やタイムアウトも `IGTOOL_CLAUDE_CLI_COMMAND` / `IGTOOL_CLAUDE_CLI_TIMEOUT` で変更可能です。

## 同梱フォント

テキスト合成機能では [IPAフォント](https://moji.or.jp/ipafont/)(IPAゴシック/IPA明朝)を
`ig_toolkit/assets/fonts/` に同梱しています。IPAフォントライセンスv1.0の下で再配布しており、
ライセンス全文は同ディレクトリの `LICENSE_IPAFONT.txt` を参照してください。

## テスト

```bash
pip install -e ".[dev]"
pytest
```
