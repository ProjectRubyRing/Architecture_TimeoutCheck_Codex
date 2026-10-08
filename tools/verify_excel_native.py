"""Recalculate a private workbook copy in hidden Excel and export review pages."""

import json
import shutil
from pathlib import Path

import pythoncom
import pywintypes
import win32com.client

from guide_budget import CHECKS, PARAMETERS

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT/'AWS_Timeout_Design_Guide.xlsx'
VALIDATION = ROOT/'validation'

SCENARIOS = [
    ('SQL時間超過', {'p_sql':10}, {'B06','B07','B08'}),
    ('帳票ALB idle不足', {'p_report_idle':40}, {'B17'}),
    ('visibility不足', {'p_visibility':60}, {'B27'}),
    ('Lambda延長後のvisibility未更新', {'p_lambda_hard':80}, {'B27'}),
    ('window追加後のvisibility未更新', {'p_window':5}, {'B27'}),
    ('batch10件の逐次処理', {'p_batch':10}, {'B25'}),
    ('短いL4 idleと長いpool', {'p_gwlb':120,'p_nlb':120}, {'B36'}),
    ('token期限と同時に再取得', {'p_token_refresh':3600}, {'B32'}),
    ('到着時点でdeadline超過', {'p_gateway_elapsed':25}, {'B38','B39'}),
    ('短いstopTimeout', {'p_stop':30}, {'B43'}),
    ('不正な負数入力', {'p_client':-1}, set()),
    ('不正な文字入力', {'p_client':'invalid'}, set()),
    ('必須入力の空欄', {'p_client':None}, set()),
    ('整数項目への小数入力', {'p_lambda_hard':70.5}, set()),
    ('承認を前提にしないREST入力範囲超過', {'p_gateway':30}, set()),
]


def main():
    VALIDATION.mkdir(exist_ok=True)
    copy_path = VALIDATION/'native_check_copy.xlsx'
    shutil.copy2(ARTIFACT, copy_path)
    pythoncom.CoInitialize()
    app = None
    workbook = None
    report = dict(artifact=ARTIFACT.name, validation_date='2026-10-08',
                  environment_tests_executed=False, native_excel_scenarios=[])
    try:
        print('Starting a hidden Excel instance for native checks...', flush=True)
        app = win32com.client.DispatchEx('Excel.Application')
        app.Visible = False
        app.DisplayAlerts = False
        app.EnableEvents = False
        app.AutomationSecurity = 3
        app.AskToUpdateLinks = False
        workbook = app.Workbooks.Open(str(copy_path), UpdateLinks=0, ReadOnly=False)
        report['excel_version'] = str(app.Version)
        calc = workbook.Worksheets('02_整合性計算')
        app.CalculateFull()
        assert calc.Range('F7').Value == 'OK', 'Initial summary does not recalculate to OK'
        check_ids = {c['id'] for c in CHECKS}
        check_rows = {}
        for row_index, cells in enumerate(calc.Range('A1:F200').Value, start=1):
            cid = str(cells[0]).split('\n')[-1]
            if cid in check_ids:
                check_rows[cid] = row_index
        assert set(check_rows) == check_ids, 'Condition IDs are missing in Excel'
        for cid, row in check_rows.items():
            assert calc.Cells(row, 6).Value == 'OK', f'Initial check fails: {cid}'
        assert calc.Cells(check_rows['B38'],3).Value == 9, 'Propagated deadline must shrink work to nine seconds'
        report['initial_checks'] = dict(count=len(CHECKS), all_ok=True, shortened_ecs_seconds=9)
        defaults = {p['name']:p['value'] for p in PARAMETERS}
        for name, overrides, expected_failed in SCENARIOS:
            for key,value in overrides.items():
                workbook.Names(key).RefersToRange.Value = value
            app.CalculateFull()
            failures = {cid for cid,row in check_rows.items() if calc.Cells(row,6).Value != 'OK'}
            assert expected_failed <= failures, (name, expected_failed, failures)
            assert calc.Range('F7').Value == '要見直し', f'Invalid scenario accepted: {name}'
            report['native_excel_scenarios'].append(dict(name=name, overrides=overrides,
                                                         detected_failed_checks=sorted(failures),
                                                         overall='要見直し', passed=True))
            for key in overrides:
                workbook.Names(key).RefersToRange.Value = defaults[key]
            app.CalculateFull()
            assert calc.Range('F7').Value == 'OK', f'Defaults did not recover after {name}'
        # Export every sheet using its actual print area, font and row/column sizes.
        # This is review evidence, not a replacement for the requested XLSX.
        pdf_path = VALIDATION/'Excel_render_preview.pdf'
        workbook.Worksheets('00_読み方').Activate()
        workbook.ExportAsFixedFormat(0, str(pdf_path), Quality=0, IncludeDocProperties=True,
                                    IgnorePrintAreas=False, OpenAfterPublish=False)
        report['native_excel_pdf'] = pdf_path.name
        report['native_excel_pdf_bytes'] = pdf_path.stat().st_size
        report['result'] = 'passed'
        (VALIDATION/'native_checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n',
                                                  encoding='utf-8')
        print(f'Excel {app.Version}: initial {len(CHECKS)} checks OK; {len(SCENARIOS)} edit scenarios passed')
        print(f'Native render: {pdf_path.name} ({pdf_path.stat().st_size:,} bytes)')
    except (pywintypes.com_error, AssertionError) as exc:
        report['result'] = 'failed'
        report['error'] = dict(type=type(exc).__name__, message=str(exc))
        (VALIDATION/'native_checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n',
                                                   encoding='utf-8')
        raise
    finally:
        if workbook is not None:
            workbook.Close(SaveChanges=False)
        if app is not None:
            app.Quit()
        workbook = None
        app = None
        pythoncom.CoUninitialize()
        if copy_path.is_file():
            copy_path.unlink()


if __name__ == '__main__':
    main()
