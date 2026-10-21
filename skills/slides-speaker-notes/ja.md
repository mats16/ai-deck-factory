# Japanese scripts

The rules for a Japanese voiceover script. Use them with "How to write" and "Audio tags" in [SKILL.md](SKILL.md), and run `speaker_notes.py lint <台本.json> --lang ja`.

- [slides-speaker-notes-004] 文体は「です・ます」。1 シーンの目安は 100〜300 字（扉は 50〜100 字）、全体は、スライドのノートをそのまま読んだときの半分ほどにする。
- [slides-speaker-notes-005] 読み誤りそうな語は、読みで書く（pi は「パイ」、$32 は「32 ドル」、ハイフンでつないだ名前は空白で区切る〔deck-review は「deck review」〕）。voiceover は文字をそのまま読むので、記号（/ ~ # $ 括弧 「」 【】）を使わない。言い切れない長い文は 2 つに分ける。
- [slides-speaker-notes-008] 前後のシーンは「さきほどの」「このあと」で指し、「〇ページ」と言わない。表や細かいページでは「動画を止めて見てください」と言う。
- [slides-speaker-notes-014] 扉は、口で話すように次の話へつなぐ（「次は〇〇についてです。」「続いては〇〇についてお話しします。」など）。言い方は中身と前のシーンに合わせて選び、型にそろえない。
- [slides-speaker-notes-009] タグは句点（「。」）のあとに置く。`[short pause]` は、話の切り替わり（「だから」「ただ」「そこで」「2 つ目」の前）に置く。
