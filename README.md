完成した自動化パイプライン
Copy毎朝 7:00 JST（GitHub Actions）
        ↓
collect_data.py
市場データ取得（日経・ドル円・金・原油）
        ↓
collect_overseas_intel.py
FRB・AlphaVantage・RSS・Reddit・決算収集
+ 古い記事フィルタリング
+ top_story自動選定
        ↓
generate_note_jp.py
Gemmaでtop_storyを軸に記事生成
タイトル・ハッシュタグ・本文をパース
        ↓
post_to_note.py
Cookie認証 → 下書き作成 → 本文保存 → 公開


⚠️ 今後の運用で注意すること
Cookieの期限切れ対策が唯一の定期メンテナンス項目です。_note_session_v5 は数週間〜数ヶ月で失効するので、Actions が失敗したらローカルで以下を実行してSecretを更新してください。

Cookieを再取得してSecretの更新値を表示
python src/post_to_note.py
ログに「NOTE_SESSION_COOKIEを更新してください: xxxxx」と表示される
