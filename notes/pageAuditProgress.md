# pageAuditProgress ─ pageAuditFixPlan20260911 の進捗

- T1 見どころ：完了（2026-09-11 15:28 JST）。P3・P4・N1・J1・J2・J3・J8・J9・D3・N18 を scripts/build_highlights.py と docs/highlights/index.html で修正。未変更：「(カドの一撃)」「(インの格が軽い)」は scripts/build_arare.py の文字列で、T1 の触ってよいファイル外のため触らず。highlights_prev.json・highlights_prev2.json は過去日の複製で再生成できないため、旧文面は日替わりで順次消える
- T2 出走表：完了（2026-09-11 15:33 JST）。N3・J10・D2・D3・N18 を scripts/template_racers.html で修正。T1 の見立て文は出走表の「展開の見どころ」に highlights.json 経由で出ることを確認し、出走表側の定型「過去1年、該当#つのレースの①着外率」を T1 と同じ規則で直した。J10 の docs/highlights/index.html 側（逃げ時2着の4文字切り）は T2 の触ってよいファイル外のため未変更
- T3 万舟：完了（2026-09-11 15:44 JST）。N2 は集計元 docs/payouts/*Payouts.csv に同じ (開催日, R) の行が重複（蒲郡・丸亀440・大村404・常滑1）。CSV は触らず、R別万舟率24本・trifectaTop・boat1Second の集計時に重複を除いて再生成。N12・N17・N19・D1 を25ページに同じ変更で反映。summary.json はネットワーク集計のため再生成せず（境界の変更は次回の定時集計で反映）
