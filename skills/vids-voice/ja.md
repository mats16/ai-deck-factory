# Japanese scripts

The rules for a Japanese voiceover script. Use them with "How to write" and "Audio tags" in [SKILL.md](SKILL.md), and run `speaker_notes.py lint <台本.json> --lang ja`.

- [vids-voice-ja-001] 文体は「です・ます」。1 シーンの目安は 100〜300 字（扉は 50〜100 字）、全体は、スライドのノートをそのまま読んだときの半分ほどにする。
- [vids-voice-ja-002] 英語の語は、製品名や略語も、カタカナで書く。日本語の声は、カタカナのほうが自然に読む（Google Slides は「グーグル スライド」、deck-review は「デッキ レビュー」、AI は「エーアイ」）。ただし、画面の表示（ボタンやメニューの名前）を指して操作を頼むときは、見る人が画面の文字と見比べられるよう、表示のまま英語で書く（「Replace with speaker notes をクリックします。」）。ほかの読み誤りそうな語も、読みで書く（$32 は「32 ドル」）。voiceover は文字をそのまま読むので、記号（/ ~ # $ 括弧 「」 【】）を使わない。言い切れない長い文は 2 つに分ける。
- [vids-voice-ja-003] 前後のシーンは「さきほどの」「このあと」で指し、「〇ページ」と言わない。表や細かいページでは「動画を止めて見てください」と言う。
- [vids-voice-ja-004] 扉は、口で話すように次の話へつなぐ（「次は〇〇についてです。」「続いては〇〇についてお話しします。」など）。言い方は中身と前のシーンに合わせて選び、型にそろえない。
- [vids-voice-ja-005] タグは句点（「。」）のあとに置く。`[short pause]` は、話の切り替わり（「だから」「ただ」「そこで」「2 つ目」の前）に置く。
