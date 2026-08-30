# ig-toolkit

Instagram投稿の準備作業(画像加工・キャプション作成・スケジュール管理)を効率化するための、
ローカルで動くCLIツールです。

- **自動投稿は行いません。** 最終的な投稿はInstagramアプリから手動で行う前提で、
  「投稿に必要な画像とキャプション文をワンステップで用意し、投稿前チェックを通す」ところまでを自動化します。
- キャプション(文面・ハッシュタグ)は画像を確認しながらの手入力方式です(外部APIキー不要)。
  画像の自動補正・背景除去・透かし合成、下書き管理・承認チェックリスト・投稿カレンダーをまとめて扱えます。

## できること

| 機能 | コマンド | 説明 |
|---|---|---|
| 下書き作成 | `igtool new` | トピック・キーワード・画像から投稿ドラフトを作成 |
| 一覧・詳細確認 | `igtool list` / `igtool show` | 下書きの状態を確認 |
| キャプション入力 | `igtool caption` | 画像を確認しながらキャプション文・ハッシュタグを手入力 |
| 画像編集 | `igtool edit` | Instagram向けリサイズ・自動補正・背景除去・透かし・テキスト合成 |
| 投稿前チェック | `igtool review` | NGワード・画像サイズ・権利関係などのチェックリストを対話形式で実施 |
| 承認 | `igtool approve` | チェック済みの投稿を承認状態にする |
| スケジュール | `igtool schedule` | 投稿予定日を設定 |
| カレンダー表示 | `igtool calendar` | 月間の投稿予定を一覧表示 |
| エクスポート | `igtool export` | 投稿用の画像とキャプションテキストをまとめて書き出す(手動投稿用) |
| 投稿済みマーク | `igtool mark-posted` | 手動投稿が終わった投稿を記録 |

## セットアップ

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

cp .env.example .env
# 必要に応じてデータ保存先などを .env で変更(未編集でも動作します)
```

背景除去(`igtool edit --bg-remove`)を使う場合は追加でインストールします(初回はモデルダウンロードが走るため少し時間がかかります)。

```bash
pip install rembg onnxruntime
```

## 基本的な使い方

```bash
# 1. 下書きを作成(画像は複数指定可)
igtool new --topic "秋の新作紅茶" --keyword 紅茶 --keyword 秋限定 --tone casual \
  --image ./photos/tea1.jpg --image ./photos/tea2.jpg

# 2. 画像を編集(正方形にトリミング+自動補正、必要ならロゴ透かしも)
igtool edit <post_id> --preset square --enhance
igtool edit <post_id> --watermark ./assets/logo.png --watermark-position bottom-right

# 3. キャプション・ハッシュタグを入力(画像のパス・サイズを見ながら対話入力)
igtool caption <post_id>
# コマンド一発で決め打ちしたい場合は直接指定もできる
igtool caption <post_id> --caption-text "秋限定の新作紅茶が入荷しました。" --hashtags "紅茶,秋限定"

# 4. 内容を確認して手直ししたい場合は meta.yaml を直接編集してもOK
igtool show <post_id>

# 5. 投稿前チェック(NGワード・画像サイズ・権利関係などを確認しながら承認)
igtool review <post_id>

# 6. 投稿予定日を設定してカレンダーで確認
igtool schedule <post_id> --date 2026-09-05
igtool calendar --year 2026 --month 9

# 7. 画像+キャプションテキストをエクスポートして、Instagramアプリから手動投稿
igtool export <post_id>

# 8. 投稿が終わったらマーク
igtool mark-posted <post_id>
```

投稿ドラフトの状態は `draft → in_review → approved → scheduled → posted` の順に遷移します。

## データの保存場所

すべてのデータは `data/` 配下にローカル保存されます(Git管理対象外)。

```
data/
  posts/<post_id>/
    meta.yaml            投稿メタデータ(トピック・キャプション・チェックリストなど)
    images/original/     取り込んだ元画像
    images/edited/        編集後の画像
  exports/<post_id>/     手動投稿用にエクスポートした画像+caption.txt
```

保存先や設定ファイルの場所は `.env` の `IGTOOL_DATA_DIR` などで変更できます(`.env.example` 参照)。

## NGワードリストのカスタマイズ

`config/ng_words.txt` に1行1ワードで登録すると、`igtool review` 実行時に
キャプション・ハッシュタグに含まれていないかを自動チェックします。
薬機法・景品表示法まわりの表現や、自社のNGワードを自由に追加してください。

## テスト

```bash
pip install -e ".[dev]"
pytest
```
