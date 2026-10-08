# AWSの6経路におけるタイムアウト設計資料

成果物は [Excel](AWS_Timeout_Design_Guide.xlsx) と [Markdown](AWS_Timeout_Design_Guide.md) です。
情報の基準日は2026年10月8日。Excelは21シート、全セルMeiryo UI、モノトーンの書式です。
Markdownの経路図は `diagrams` フォルダーと一緒に保管してください。

`02_整合性計算` のC列には70の入力があり、変更すると43の整合条件が再計算されます。
説明本文・図・設定一覧は初期案の固定記述です。採用した変更値は本文と実設定にも反映してください。
設定値は提案であり、AWS/Salesforceの実環境への変更や32項目の受入試験は行っていません。

WindowsのPython 3.12で、既存の `xlsxwriter`、`openpyxl`、`Pillow` を使用します。
図の描画にはWindowsのMeiryo UIフォントが必要です。

```powershell
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONDONTWRITEBYTECODE = '1'
python tools\build_guide.py
python tools\verify_guide.py
```

生成処理は既存の同名成果物を更新します。データは `tools\guide_*.py` に分かれており、
設定・各経路・本文・一次資料・計算・実装例を編集してから再生成できます。
数式には初期値の計算結果を埋め込み、Excelを開く前でも表示できるようにしています。

生成物の検査結果は `validation\guide_checks.json` に保存します。Excel本体を自動起動する
追加確認は `tools\verify_excel_native.py` で行えます（`pywin32` が必要）。今回の実行では
COMサーバーの起動に失敗したため、Excel本体での表示・再計算は未確認です。
Excelでは `02_整合性計算` の値を変更し、たとえばSQL上限を10秒にしたときに
B06/B07/B08が「要見直し」になることを確認できます。
