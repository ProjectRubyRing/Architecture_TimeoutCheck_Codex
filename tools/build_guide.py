"""Build the Japanese Excel/Markdown timeout guide from the checked data."""

import math
from pathlib import Path

import xlsxwriter

from guide_budget import CHECKS, PARAMETERS, evaluate, values
from guide_diagrams import font, render_diagrams
from guide_examples import EXAMPLES, TEST_PLAN
from guide_routes import ROUTES
from guide_settings import SETTINGS, SETTING_MAP
from guide_sources import SOURCES, SOURCE_MAP, source_links
from guide_topics import CHAPTERS, HISTORY, INTRO

ROOT = Path(__file__).resolve().parent.parent
STEM = 'AWS_Timeout_Design_Guide'
DATE = '2026-10-08'
CALC_SHEET = '02_整合性計算'
SOURCE_SHEET = '20_公式出典'


def minimum_value(p):
    return {'p_batch': 1, 'p_gwlb': 60, 'p_nlb': 60, 'p_eni': 60,
            'p_gateway': 0.05, 'p_screen_idle': 1, 'p_api_idle': 1,
            'p_report_idle': 1, 'p_lambda_hard': 1, 'p_stop': 1}.get(p['name'], 0)


def integer_value(p):
    return p['integer'] or p['name'] in ('p_screen_idle', 'p_api_idle', 'p_report_idle', 'p_borrow')


class GuideWorkbook:
    def __init__(self, path):
        self.book = xlsxwriter.Workbook(path, {'strings_to_formulas': False,
                                              'strings_to_urls': False})
        self.book.formats[0].set_font_name('Meiryo UI')
        self.book.formats[0].set_font_size(11)
        self.book.set_properties(dict(title='AWS 6経路 タイムアウト設計詳解',
                                      subject='時間予算、正式設定項目、原理、検証計画',
                                      author='Architecture Timeout Design',
                                      comments='提案値は設計例。実環境での試験は未実施。'))
        self.book.set_calc_mode('auto')
        base = dict(font_name='Meiryo UI', font_size=11, font_color='#202020',
                    text_wrap=True, valign='top')
        self.formats = {}
        for name, extras in {
            'title': dict(bold=True, font_size=19, font_color='#FFFFFF', bg_color='#242424', valign='vcenter'),
            'subtitle': dict(font_size=10, font_color='#555555'),
            'nav': dict(font_size=10, underline=True, font_color='#333333', valign='vcenter'),
            'header': dict(bold=True, font_color='#FFFFFF', bg_color='#3D3D3D', valign='vcenter', border=1, border_color='#3D3D3D'),
            'section': dict(bold=True, font_size=12, bg_color='#DADADA', valign='vcenter'),
            'body': dict(bottom=1, bottom_color='#DDDDDD'),
            'stripe': dict(bg_color='#F2F2F2', bottom=1, bottom_color='#DDDDDD'),
            'link': dict(underline=True, bottom=1, bottom_color='#DDDDDD'),
            'link_stripe': dict(bg_color='#F2F2F2', underline=True, bottom=1, bottom_color='#DDDDDD'),
            'code': dict(font_size=9, bg_color='#F2F2F2', border=1, border_color='#DDDDDD'),
            'input': dict(bg_color='#FFFFFF', border=2, border_color='#666666',
                          num_format='#,##0.###', align='right', valign='vcenter'),
            'number': dict(num_format='#,##0.###', align='right', valign='vcenter', bottom=1, bottom_color='#DDDDDD'),
            'ok': dict(bg_color='#E8E8E8', bold=True, align='center', valign='vcenter', border=1, border_color='#BBBBBB'),
            'fail': dict(bg_color='#3D3D3D', font_color='#FFFFFF', bold=True, align='center', valign='vcenter', border=2),
        }.items():
            self.formats[name] = self.book.add_format({**base, **extras})
        self.widths = {}
        self.last_rows = {}
        self.source_rows = {s[0]: i + 5 for i, s in enumerate(SOURCES)}
        self.setting_rows = {s['id']: i + 5 for i, s in enumerate(SETTINGS)}

    def sheet(self, name, title, widths):
        ws = self.book.add_worksheet(name)
        self.widths[name] = widths
        ws.hide_gridlines(2)
        ws.set_zoom(80)
        ws.set_default_row(22)
        for i, width in enumerate(widths):
            ws.set_column(i, i, width, self.formats['body'])
        ws.merge_range(0, 0, 0, len(widths)-1, title, self.formats['title'])
        ws.set_row(0, 44)
        ws.merge_range(1, 0, 1, len(widths)-1,
                       f'基準日 {DATE}  |  提案値＝設計例  |  実際の環境値・負荷試験結果とは区別', self.formats['subtitle'])
        ws.set_row(1, 24)
        targets = [('00_読み方', '目次へ'), ('01_設定一覧', '設定一覧へ'),
                   (CALC_SHEET, '時間計算へ'), (SOURCE_SHEET, '公式出典へ')]
        for i, (target, text) in enumerate(targets[:len(widths)]):
            ws.write_url(2, i, f"internal:'{target}'!A1", self.formats['nav'], text)
        ws.set_row(2, 25)
        ws.set_landscape()
        ws.set_paper(8)  # A3: wide technical tables stay on one page horizontally.
        ws.fit_to_pages(1, 0)
        ws.set_margins(0.25, 0.25, 0.4, 0.4)
        ws.repeat_rows(0, 2)
        ws.set_header('&L&"Meiryo UI"&9AWS タイムアウト設計&C&"Meiryo UI"&9'+name)
        ws.set_footer('&L&"Meiryo UI"&8'+DATE+'&R&"Meiryo UI"&8&P / &N')
        self.last_rows[name] = 3
        return ws

    def row_height(self, texts, widths, size=11):
        f = font(round(size * 96 / 72))
        lines = 1
        for text, width in zip(texts, widths):
            available = max(22, (width * 7 + 5 - 12) * 0.84)
            count = 0
            for paragraph in str(text).split('\n'):
                current = ''
                count += 1
                for ch in paragraph:
                    if current and f.getlength(current+ch) > available:
                        count += 1
                        current = ch
                    else:
                        current += ch
            lines = max(lines, count)
        height = max(28, math.ceil(lines * size * 1.65 + 10))
        if height > 409:
            raise ValueError(f'Row exceeds Excel height limit: {texts!r}')
        return height

    def row(self, ws, row, texts, stripe=False, code=False):
        fmt = self.formats['code' if code else 'stripe' if stripe else 'body']
        for i, text in enumerate(texts):
            ws.write(row, i, text, fmt)
        ws.set_row(row, self.row_height(texts, self.widths[ws.name][:len(texts)], size=9 if code else 11))
        self.last_rows[ws.name] = max(self.last_rows[ws.name], row)

    def merged(self, ws, row, text, section=False):
        widths = self.widths[ws.name]
        ws.merge_range(row, 0, row, len(widths)-1, text, self.formats['section' if section else 'body'])
        ws.set_row(row, self.row_height([text], [sum(widths)]))
        self.last_rows[ws.name] = max(self.last_rows[ws.name], row)

    def headers(self, ws, row, labels):
        for i, label in enumerate(labels):
            ws.write(row, i, label, self.formats['header'])
        ws.set_row(row, 35)

    def source_cell(self, ws, row, col, ids, stripe=False):
        if not ids:
            ws.write(row, col, '設計例', self.formats['stripe' if stripe else 'body'])
            return
        first = ids[0]
        ws.write_url(row, col, f"internal:'{SOURCE_SHEET}'!A{self.source_rows[first]+1}",
                     self.formats['link_stripe' if stripe else 'link'], ' / '.join(ids))
        ws.write_comment(row, col, '\n'.join(f'{sid}: {SOURCE_MAP[sid][1]}\n{SOURCE_MAP[sid][3]}' for sid in ids),
                         {'font_name': 'Meiryo UI', 'font_size': 10, 'width': 570, 'height': min(450, 90*len(ids))})

    def topics(self, ws, row, rows):
        self.headers(ws, row, ['項目', '詳しい説明・動作イメージ', '出典'])
        for i, (title, body, refs) in enumerate(rows, start=row+1):
            self.row(ws, i, [title, body, ' / '.join(refs) or '設計例'], stripe=i % 2 == 0)
            self.source_cell(ws, i, 2, refs, stripe=i % 2 == 0)
        return row+len(rows)+1

    def finish(self):
        for ws in self.book.worksheets():
            ws.print_area(0, 0, self.last_rows[ws.name], len(self.widths[ws.name])-1)
        self.book.close()


def build_excel(path):
    g = GuideWorkbook(path)
    topic_widths = [30, 126, 20]
    cover = g.sheet('00_読み方', 'AWS 6経路 タイムアウト設計詳解', topic_widths)
    end = g.topics(cover, 4, INTRO)
    g.merged(cover, end+1, '21シートの案内  /  下線付きのセルを選ぶと対象のシートへ移動', section=True)
    entries = [('01_設定一覧', '104設定項目：正式名、時計の起点、既定/範囲、提案値、注意点', '辞書'),
               (CALC_SHEET, f'{len(PARAMETERS)}入力・{len(CHECKS)}整合条件。入力値を変更して余裕を再計算', '編集可')]
    entries += [(r['sheet'], r['title']+'：経路図・各接続点・正常/異常動作・例', r['id']) for r in ROUTES]
    entries += [(c['sheet'], c['title'], '詳解') for c in CHAPTERS if not c['sheet'].startswith('19_')]
    entries += [('17_設定と実装例', f'{len(EXAMPLES)}の読み取り/設定/疑似code例。実環境へは未反映', '参考'),
                ('18_検証計画', f'{len(TEST_PLAN)}の実環境受入試験。すべて未実施として記載', '計画'),
                ('19_用語集', '専門語を小学生にも伝わる言葉で読む', '用語'),
                (SOURCE_SHEET, f'{len(SOURCES)}件の一次資料とURL。資料本文の出典IDと対応', '公式')]
    for i, entry in enumerate(entries, start=end+2):
        g.row(cover, i, entry, stripe=i % 2 == 0)
        cover.write_url(i, 0, f"internal:'{entry[0]}'!A1", g.formats['link'], entry[0])
    cover.freeze_panes(5, 0)

    ws = g.sheet('01_設定一覧', '設定辞書：AWSの仕様と本資料の提案値', [7, 20, 36, 47, 32, 49, 39, 73, 18])
    g.headers(ws, 4, ['ID', '分類', '接続点・対象', '正式な設定名', '時計の対象 / 起点', '既定値・範囲 / 条件', '本資料の提案値', '設定のポイント・異常時・適用範囲', '出典'])
    for i, setting in enumerate(SETTINGS, start=5):
        fields = [setting[k] for k in ('id','group','point','key','kind','limits','proposal','notes')]
        fields.append(' / '.join(setting['refs']) or '設計例')
        g.row(ws, i, fields, stripe=i % 2 == 0)
        g.source_cell(ws, i, 8, setting['refs'], stripe=i % 2 == 0)
    ws.autofilter(4, 0, 4+len(SETTINGS), 8)
    ws.freeze_panes(5, 3)

    calc = g.sheet(CALC_SHEET, '時間予算：入力値を変えて整合性を確認する', [20, 48, 16, 10, 98, 17])
    g.merged(calc, 4, '枠の太いC列が入力。F列は入力確認/整合判定。計算OKは性能保証や実環境検証の成功を意味しない。')
    g.merged(calc, 5, '本文・図・設定一覧は初期案の固定記述。入力変更後に採用する値は、本文と実設定にも反映する。')
    g.headers(calc, 7, ['分類', '入力する時計・予算', '入力値', '単位', '意味と適用範囲 / 値は初期案', '入力確認'])
    input_start = 8
    inputs = values()
    for i, p in enumerate(PARAMETERS, start=input_start):
        g.row(calc, i, [p['group'],p['label'],p['value'],p['unit'],p['note'],'OK'], stripe=i % 2 == 0)
        calc.write_number(i, 2, p['value'], g.formats['input'])
        cell = f'C{i+1}'
        integer = integer_value(p)
        floor = minimum_value(p)
        calc.data_validation(i, 2, i, 2, {'validate': 'integer' if integer else 'decimal',
                             'criteria': 'between', 'minimum': floor, 'maximum': p['maximum'],
                             'ignore_blank': False, 'input_title': '計算用の入力値',
                             'input_message': f"{p['name']} / {floor}～{p['maximum']} {p['unit']}",
                             'error_title': '入力値を確認してください', 'error_message': '数値と入力範囲を確認してください。',
                             'error_type': 'stop'})
        conditions = f'ISNUMBER({cell}),{cell}>={floor},{cell}<={p["maximum"]}'
        if integer:
            conditions += f',MOD({cell},1)=0'
        calc.write_formula(i, 5, f'=IFERROR(IF(AND({conditions}),"OK","要見直し"),"要見直し")', g.formats['ok'], 'OK')
        self_comment = p['name']+'\n'+p['note']
        if p['refs']:
            self_comment += '\n'+'\n'.join(SOURCE_MAP[sid][3] for sid in p['refs'])
        calc.write_comment(i, 2, self_comment, {'font_name':'Meiryo UI','font_size':10,'width':540,'height':170})
        g.book.define_name(p['name'], f"='{CALC_SHEET}'!$C${i+1}")
    input_end = input_start+len(PARAMETERS)-1
    check_header = input_end+3
    g.merged(calc, check_header-1, '整合条件  /  C列は条件を満たす余裕（B38は短縮後の実行可能秒数、B40は件数）', section=True)
    g.headers(calc, check_header, ['分類・ID', '整合条件', '余裕 / 実行可能', '単位', '判定の前提・包含関係・読み方', '判定'])
    for i, c in enumerate(CHECKS, start=check_header+1):
        result = evaluate(c['expression'], inputs)
        ok = result > 0 if c['strict'] else result >= 0
        g.row(calc, i, [c['group']+'\n'+c['id'],c['label'],result,c['unit'],c['note'],'OK' if ok else '要見直し'], stripe=i % 2 == 0)
        calc.write_formula(i, 2, f'=IFERROR(ROUND({c["expression"]},6),"入力不正")', g.formats['number'], result)
        operator = '>' if c['strict'] else '>='
        calc.write_formula(i, 5, f'=IFERROR(IF(AND(ISNUMBER(C{i+1}),C{i+1}{operator}0),"OK","要見直し"),"要見直し")',
                           g.formats['ok'], 'OK' if ok else '要見直し')
    check_end = check_header+len(CHECKS)
    summary = f'=IF(COUNTIF(F{input_start+1}:F{input_end+1},"<>OK")+COUNTIF(F{check_header+2}:F{check_end+1},"<>OK")=0,"OK","要見直し")'
    calc.write_formula(6, 5, summary, g.formats['ok'], 'OK')
    calc.merge_range(6, 0, 6, 4, '全入力・整合条件の判定 →  「要見直し」が出た場合はF列の該当行を確認', g.formats['section'])
    calc.conditional_format(input_start, 5, check_end, 5, {'type':'text','criteria':'containing','value':'要見直し','format':g.formats['fail']})
    calc.freeze_panes(8, 2)
    calc.set_h_pagebreaks([check_header-1])

    for route in ROUTES:
        ws = g.sheet(route['sheet'], f"{route['id']}  {route['title']}", [7, 33, 60, 29, 72, 18])
        g.merged(ws, 4, '指定された線：'+route['original'])
        g.merged(ws, 5, '論理構成の読み方：'+route['corrected'])
        image_width, image_height = 1800, 1160
        display_width = sum(g.widths[ws.name])*7-25
        scale = min(display_width/image_width, 0.85)
        image_rows = math.ceil(image_height*scale / (22*96/72)) + 1
        ws.insert_image(7, 0, str(ROOT/'diagrams'/f"{route['id']}_route.png"),
                        {'x_scale':scale,'y_scale':scale,'object_position':1,'description':route['corrected']})
        row = 7+image_rows+1
        ws.set_h_pagebreaks([row])
        g.merged(ws, row, '各接続点の設定  /  設定IDセルから01_設定一覧の最初の該当項目へ移動', section=True)
        g.headers(ws, row+1, ['段階','接続線・処理点','この段階の設定と内容','設定ID','整合性・動作のポイント','参照'])
        for i, stage in enumerate(route['stages'], start=row+2):
            n, edge, settings, ids, note = stage
            g.row(ws, i, [n,edge,settings,ids,note,'設定一覧へ'], stripe=i % 2 == 0)
            first = ids.split()[0]
            target = f"internal:'01_設定一覧'!A{g.setting_rows[first]+1}"
            ws.write_url(i, 3, target, g.formats['link'], ids)
            ws.write_url(i, 5, target, g.formats['link'], '設定一覧へ')
        row += len(route['stages'])+3
        g.merged(ws, row, '動作イメージ・失敗時の動作・この経路の注意点', section=True)
        row += 1
        # Keep explanation text in a wide merged body cell without a narrow table.
        for title, body, refs in route['explanations']:
            g.merged(ws, row, title, section=True)
            g.merged(ws, row+1, body)
            g.row(ws, row+2, ['出典',' / '.join(refs) or '設計例','','','',''])
            g.source_cell(ws, row+2, 1, refs)
            row += 4
        ws.freeze_panes(3, 0)

    for chapter in CHAPTERS:
        if chapter['sheet'].startswith('19_'):
            continue
        ws = g.sheet(chapter['sheet'], chapter['title'], topic_widths)
        end = g.topics(ws, 4, chapter['rows'])
        if chapter['sheet'].startswith('14_'):
            g.merged(ws, end+1, '登場・仕様変更の年表  /  発表・preview・一般提供を区別する', section=True)
            g.headers(ws, end+2, ['時期 / 技術','背景 → 現在のtimeout設計への影響','出典'])
            for i, h in enumerate(HISTORY, start=end+3):
                date, name, background, impact, refs = h
                g.row(ws, i, [date+'\n'+name, background+'\n\n設計への影響：'+impact, ' / '.join(refs)], stripe=i % 2 == 0)
                g.source_cell(ws, i, 2, refs, stripe=i % 2 == 0)
        ws.freeze_panes(5, 1)

    ws = g.sheet('17_設定と実装例', '設定・読み取り・deadline実装の例', topic_widths)
    g.merged(ws, 4, '読み取りcommandと設定抜粋の説明。ここにあるcommandは実環境へ実行していない。部分JSON・疑似codeは完成した実装ではない。')
    row = 6
    for e in EXAMPLES:
        g.merged(ws, row, e['title'], section=True)
        g.row(ws, row+1, ['目的',e['purpose'],'設計例'])
        g.row(ws, row+2, [e['language'],e['code'],'例'], code=True)
        g.row(ws, row+3, ['適用条件・注意',e['notes'],' / '.join(e['refs']) or '設計例'])
        g.source_cell(ws, row+3, 2, e['refs'])
        row += 5
    ws.freeze_panes(3, 0)

    ws = g.sheet('18_検証計画', '実環境の受入試験計画：この資料作成では未実施', [7, 23, 36, 58, 76, 60, 14])
    g.headers(ws, 4, ['ID','対象','試験条件','操作 / 観測','受入条件','確認のポイント','実施状態'])
    for i, test in enumerate(TEST_PLAN, start=5):
        g.row(ws, i, [*test,'未実施'], stripe=i % 2 == 0)
    ws.autofilter(4, 0, 4+len(TEST_PLAN), 6)
    ws.freeze_panes(5, 3)

    glossary = next(c for c in CHAPTERS if c['sheet'].startswith('19_'))
    ws = g.sheet(glossary['sheet'], glossary['title'], topic_widths)
    g.topics(ws, 4, glossary['rows'])
    ws.autofilter(4, 0, 4+len(glossary['rows']), 2)
    ws.freeze_panes(5, 1)

    ws = g.sheet(SOURCE_SHEET, '一次資料：設定一覧と本文の出典IDに対応', [8, 57, 25, 91, 19, 24])
    g.headers(ws, 4, ['出典ID','資料名','公開元','確認する内容・使い方','閲覧基準日','公式URL'])
    for i, (sid,title,publisher,url,note) in enumerate(SOURCES, start=5):
        g.row(ws, i, [sid,title,publisher,note,DATE,'公式資料を開く'], stripe=i % 2 == 0)
        ws.write_url(i, 5, url, g.formats['link'], '公式資料を開く')
        ws.write_comment(i, 5, url, {'font_name':'Meiryo UI','font_size':10,'width':660,'height':100})
    ws.autofilter(4, 0, 4+len(SOURCES), 5)
    ws.freeze_panes(5, 2)
    g.finish()


def md_cell(value):
    return str(value).replace('|', '\\|').replace('\n', '<br>')


def md_table(headers, rows):
    return '\n'.join(['| '+' | '.join(headers)+' |',
                      '| '+' | '.join('---' for _ in headers)+' |',
                      *('| '+' | '.join(md_cell(cell) for cell in row)+' |' for row in rows)])+'\n'


def build_markdown(path):
    chunks = ['# AWS 6経路 タイムアウト設計詳解\n',
              f'情報の基準日：**{DATE}（日本時間）**。Excel：[同じ資料を開く]({STEM}.xlsx)。\n',
              'この資料の秒数は、整合する設計例です。実環境の設定値や測定結果ではありません。\n']
    sections = [('00','読み方'),('01','設定一覧'),('02','整合性計算')]
    sections += [(r['sheet'][:2],r['title']) for r in ROUTES]
    sections += [(c['sheet'][:2],c['title']) for c in CHAPTERS if not c['sheet'].startswith('19_')]
    sections += [('17','設定と実装例'),('18','検証計画'),('19','用語集'),('20','公式出典')]
    chunks += ['## 目次\n', '\n'.join(f'- [{sid} {title}](#s{sid})' for sid,title in sections)+'\n']

    def heading(sid, title):
        chunks.append(f'<a id="s{sid}"></a>\n\n## {sid} {title}\n')

    def paragraphs(rows):
        for title, body, refs in rows:
            chunks.append(f'### {title}\n\n{body} {source_links(refs)}\n')

    heading('00','読み方・前提')
    paragraphs(INTRO)
    chunks.append('### 最初に押さえる六つの時間予算\n')
    chunks.append(md_table(['経路','処理上限の設計例','共有/接続の時計'], [
        ['画面','cache0.5＋DB12＋その他3＋応答2＝17.5 ≤ ECS20 < client30','画面ALB idle90 / ECS keepalive120'],
        ['画面非同期','受付ECS5 < client10。バック50 < HTTP55 < soft60 < hard70','SQS visibility420 ≥ 6×70＋window0'],
        ['帳票','EC260 < HTTP65。前2＋65＋後3＝70 ≤ ECS75 < client90','帳票ALB idle70 / 画面ALB idle90'],
        ['社内API','ECS20 < client30。cache/DBは画面と同じ分岐','API用ALB idle60'],
        ['公開API','ECS20 < REST統合25 < API client30。token取得10は別HTTP','GWLB TCP idle350 / API ALB idle60'],
        ['Salesforce API','Apex例callout30。token10＋API30＋余裕5＝業務45','NLB TCP idle350 / Private REST統合25'],
    ]))

    heading('01','設定一覧：正式名称・仕様・提案値')
    chunks.append('「既定値・範囲」は公式仕様、「設計例」は本資料の提案です。clockの起点と適用範囲を確認してから設定します。\n')
    for group in dict.fromkeys(s['group'] for s in SETTINGS):
        chunks.append(f'### {group}\n')
        records = []
        for s in SETTINGS:
            if s['group'] == group:
                records.append([f'<a id="setting-{s["id"]}"></a>{s["id"]}',s['point'],s['key'],s['kind'],
                                s['limits'],s['proposal'],s['notes'],source_links(s['refs']) or '設計例'])
        chunks.append(md_table(['ID','接続点','正式設定名','時計 / 起点','既定・範囲・条件','設計例','設定のポイント','出典'],records))

    heading('02','整合性計算：足す時間と内包する時間')
    chunks.append(f'Excelの**{CALC_SHEET}**では、枠の太いC列の{len(PARAMETERS)}入力を変更すると、{len(CHECKS)}条件の余裕と判定が再計算されます。'
                  '本文・図・設定一覧は初期案の固定記述なので、採用した値は本文と実環境へ別途反映します。\n')
    chunks.append('入力は秒単位（BatchSizeだけ件数）。たとえばSQL5秒はDB段階12秒に含まれ、lock1秒はSQLの内側です。'
                  'SQL5＋DB12＋ECS20を全部足しません。逐次段階だけを足し、並列段階は必要な最長経路を確認します。\n')
    chunks.append(md_table(['入力名','分類 / 設定','初期値','意味'],
        [[p['name'],p['group']+' / '+p['label'],f"{p['value']:g} {p['unit']}",p['note']] for p in PARAMETERS]))
    inputs = values()
    chunks.append(md_table(['ID','整合条件','初期案の余裕 / 実行可能時間','判定','前提'],
        [[c['id'],c['label'],f"{evaluate(c['expression'],inputs):g} {c['unit']}",
          'OK' if (evaluate(c['expression'],inputs)>0 if c['strict'] else evaluate(c['expression'],inputs)>=0) else '要見直し',c['note']] for c in CHECKS]))
    chunks.append('B38は短縮後の実行可能時間です。経過10秒・時計差1秒・終了余裕2秒なら、'
                  '**min(20, 22−10−1−2)=9秒**にECSを短縮します。残りが0なら新しい業務を始めません。'
                  'Gateway入口起点22秒の予算は統合開始起点25秒より保守的で、認証等に時間を使った場合も早く切り上げます。\n')

    for r in ROUTES:
        heading(r['sheet'][:2],r['title'])
        chunks.append('**指定された接続線**\n\n'+r['original']+'\n')
        chunks.append('**論理構成の読み方**\n\n'+r['corrected']+'\n')
        chunks.append(f'![{r["title"]}の経路図](diagrams/{r["id"]}_route.png)\n')
        chunks.append('Mermaid対応の閲覧環境では、次の図も利用できます。\n')
        chunks.append('```mermaid\n%%{init: {"theme":"neutral","themeVariables":{"fontFamily":"Meiryo UI"}}}%%\n'+r['diagram']+'\n```\n')
        chunks.append('### 各接続点で設定する内容\n')
        stage_rows = []
        for n, edge, settings, ids, note in r['stages']:
            links = ' '.join(f'[{sid}](#setting-{sid})' for sid in ids.split())
            stage_rows.append([n,edge,settings,links,note])
        chunks.append(md_table(['段階','接続点','設定内容','設定ID','整合性・動作のポイント'],stage_rows))
        paragraphs(r['explanations'])

    for chapter in CHAPTERS:
        if chapter['sheet'].startswith('19_'):
            continue
        heading(chapter['sheet'][:2],chapter['title'])
        paragraphs(chapter['rows'])
        if chapter['sheet'].startswith('14_'):
            chunks.append('### 登場・仕様変更の年表\n')
            chunks.append(md_table(['時期','技術','必要になった背景','現在のtimeout設計へ与える意味','公式出典'],
                                   [[date,name,background,impact,source_links(refs)] for date,name,background,impact,refs in HISTORY]))

    heading('17','設定と実装例')
    chunks.append('以下は説明用の設定抜粋・読み取りcommand・疑似codeです。本作業ではAWS、DB、Salesforceへ反映・実行していません。'
                  '部分JSONは完全なresource定義ではなく、示した適用条件に従って実際の構成へ組み込みます。\n')
    for e in EXAMPLES:
        chunks.append(f'### {e["title"]}\n\n{e["purpose"]}\n\n```{e["language"]}\n{e["code"]}\n```\n\n{e["notes"]} {source_links(e["refs"])}\n')

    heading('18','実環境の検証計画')
    chunks.append('次の32件は**今後、非本番で実施する受入試験計画**です。この資料作成では未実施です。'
                  '資料生成時のExcel構造・数式・日本語・リンク・図の検査とは分けて扱います。\n')
    chunks.append(md_table(['ID','対象','条件','操作/観測','受入条件','確認ポイント','実施状態'],[[*test,'未実施'] for test in TEST_PLAN]))
    heading('19','小学生にも伝わる用語集')
    glossary = next(c for c in CHAPTERS if c['sheet'].startswith('19_'))
    chunks.append(md_table(['用語','意味'],[[term,meaning] for term,meaning,_ in glossary['rows']]))
    heading('20','公式出典')
    chunks.append(f'閲覧基準日：{DATE}。設定/API仕様は現行guide・API reference、歴史と背景は当時の発表や公式回顧を根拠にします。'
                  '公開資料の更新日がない場合、閲覧基準日から公開日を推測しません。DB/PAN-OS/driverの版は各sourceの対象を確認します。\n')
    chunks.append(md_table(['ID','資料名','公開元','使う内容','公式URL'],
        [[sid,title,publisher,note,f'[{sid} 公式資料]({url})'] for sid,title,publisher,url,note in SOURCES]))
    output = '\n'.join(chunks)
    path.write_text('\n'.join(line.rstrip() for line in output.splitlines())+'\n', encoding='utf-8', newline='\n')


def validate_data():
    assert len(SETTINGS) == len(SETTING_MAP), 'Duplicate setting IDs'
    assert len(SOURCES) == len(SOURCE_MAP), 'Duplicate source IDs'
    assert len({p['name'] for p in PARAMETERS}) == len(PARAMETERS), 'Duplicate parameter names'
    refs = [s['refs'] for s in SETTINGS] + [p['refs'] for p in PARAMETERS]
    refs += [e['refs'] for e in EXAMPLES]
    refs += [r[2] for c in CHAPTERS for r in c['rows']]
    refs += [r[4] for r in HISTORY]
    refs += [r[2] for route in ROUTES for r in route['explanations']]
    for ids in refs:
        for sid in ids:
            if sid not in SOURCE_MAP:
                raise ValueError(f'Undefined source ID: {sid}')
    for route in ROUTES:
        for stage in route['stages']:
            for sid in stage[3].split():
                if sid not in SETTING_MAP:
                    raise ValueError(f'Undefined setting ID in {route["id"]}: {sid}')
    for c in CHECKS:
        result = evaluate(c['expression'], values())
        if not (result > 0 if c['strict'] else result >= 0):
            raise ValueError(f'Initial budget fails: {c["id"]} {result}')


def main():
    validate_data()
    render_diagrams(ROOT/'diagrams', ROUTES)
    build_excel(ROOT/f'{STEM}.xlsx')
    build_markdown(ROOT/f'{STEM}.md')
    print(f'Created {STEM}.xlsx and {STEM}.md')
    print(f'21 sheets; {len(SETTINGS)} settings; {len(PARAMETERS)} inputs; {len(CHECKS)} checks; {len(SOURCES)} sources')


if __name__ == '__main__':
    main()
