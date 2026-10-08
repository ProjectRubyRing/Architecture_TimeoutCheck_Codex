"""Code-drawn monochrome architecture diagrams with Meiryo UI labels."""

import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_DIRECTORY = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Fonts'


def font(size=24, bold=False):
    path = FONT_DIRECTORY / ('meiryob.ttc' if bold else 'meiryo.ttc')
    if not path.is_file():
        raise FileNotFoundError(f'Meiryo UI is required to render diagrams: {path}')
    return ImageFont.truetype(str(path), size, index=2)


class Diagram:
    def __init__(self, title, subtitle):
        self.image = Image.new('RGB', (1800, 1160), '#ffffff')
        self.draw = ImageDraw.Draw(self.image)
        self.nodes = {}
        self.draw.rectangle((0, 0, 1800, 110), fill='#202020')
        self.draw.text((48, 30), title, font=font(38, True), fill='#ffffff')
        self.draw.text((48, 138), subtitle, font=font(24), fill='#333333')

    def node(self, key, x, y, title, detail, width=270, height=134):
        box = (x, y, x + width, y + height)
        self.nodes[key] = box
        self.draw.rounded_rectangle(box, radius=12, fill='#f2f2f2', outline='#303030', width=3)
        title_size = 25
        while font(title_size, True).getlength(title) > width-24:
            title_size -= 1
        self.label((x + width / 2, y + 31), title, title_size, bold=True)
        lines = detail.split('\n')
        for i, line in enumerate(lines):
            detail_size = 22
            while font(detail_size).getlength(line) > width-24:
                detail_size -= 1
            self.label((x + width / 2, y + 69 + i * 29), line, detail_size)

    def point(self, key, side='right', offset=0):
        x0, y0, x1, y1 = self.nodes[key]
        return {'left': (x0, (y0+y1)/2+offset),
                'right': (x1, (y0+y1)/2+offset),
                'top': ((x0+x1)/2+offset, y0),
                'bottom': ((x0+x1)/2+offset, y1)}[side]

    def label(self, point, text, size=22, bold=False, background=False):
        f = font(size, bold)
        bounds = self.draw.textbbox((0, 0), text, font=f)
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        x, y = point[0]-width/2, point[1]-height/2-bounds[1]
        if background:
            self.draw.rectangle((x-7, y+bounds[1]-5, x+width+7, y+bounds[3]+5), fill='white')
        if x < 8 or x + width > 1792 or y + bounds[3] > 1152:
            raise ValueError(f'Diagram label falls outside the canvas: {text}')
        self.draw.text((x, y), text, font=f, fill='#202020')

    def arrow(self, points, dashed=False, label=None, label_at=None):
        points = [(int(x), int(y)) for x, y in points]
        for p0, p1 in zip(points, points[1:]):
            if dashed:
                distance = math.dist(p0, p1)
                if distance:
                    for start in range(0, math.ceil(distance), 22):
                        end = min(start+12, distance)
                        a = tuple(p0[i] + (p1[i]-p0[i]) * start/distance for i in range(2))
                        b = tuple(p0[i] + (p1[i]-p0[i]) * end/distance for i in range(2))
                        self.draw.line((a, b), fill='#555555', width=3)
            else:
                self.draw.line((p0, p1), fill='#333333', width=4)
        p0, tip = points[-2:]
        angle = math.atan2(tip[1]-p0[1], tip[0]-p0[0])
        wings = [(tip[0]-16*math.cos(angle+s), tip[1]-16*math.sin(angle+s)) for s in (-0.45, 0.45)]
        self.draw.polygon([tip, *wings], fill='#333333')
        if label:
            self.label(label_at or ((p0[0]+tip[0])/2, (p0[1]+tip[1])/2-25), label, 21, background=True)

    def edge(self, a, b, side_a='right', side_b='left', via=(), **kwargs):
        self.arrow([self.point(a, side_a), *via, self.point(b, side_b)], **kwargs)

    def footer(self, first, second):
        self.draw.rectangle((30, 1069, 1770, 1140), fill='#e8e8e8')
        self.draw.text((48, 1077), first, font=font(22), fill='#222222')
        self.draw.text((48, 1107), second, font=font(21), fill='#333333')

    def save(self, path):
        self.image.save(path, optimize=True)


def draw_cache(d, api=False):
    d.node('client', 65, 330, '社内API client' if api else 'AWS内client', '総deadline 30秒')
    d.node('alb', 435, 330, '社内API用ALB' if api else '共有画面用ALB', 'idle 60秒' if api else 'idle 90秒')
    d.node('ecs', 810, 330, 'ECS アプリ', 'endpoint総20秒')
    d.node('cache', 1230, 230, 'ElastiCache / Valkey', 'cache段階総0.5秒\n接続0.2＋command0.3', width=415)
    d.node('proxy', 1085, 675, 'RDS Proxy', 'borrow 2秒')
    d.node('db', 1455, 675, 'Aurora Serverless v2', 'SQL 5秒', width=300)
    d.edge('client', 'alb')
    d.edge('alb', 'ecs')
    d.edge('ecs', 'cache', via=((1150, 397), (1150, 297)), label='照会', label_at=(1168, 266))
    d.arrow([d.point('cache', 'bottom'), (1437, 535), (1005, 535), d.point('ecs', 'bottom', 60)], dashed=True,
            label='hit → 答えをECSへ返す', label_at=(1437, 475))
    d.arrow([d.point('ecs', 'bottom', -75), (870, 742), d.point('proxy', 'left')],
            label='miss / 許可したfallback', label_at=(850, 600))
    d.edge('proxy', 'db')
    d.label((1250, 870), 'DB段階12秒の中に、取得・borrow・SQL・rollbackを含める', 26, bold=True)
    d.footer('実線：要求の経路。cacheとDBはECSが選ぶ分岐。応答は各HTTPの逆の経路を戻る。',
             '総時間は開始からの上限、idleは最後の送受信からの無通信時間。図の値は設計例。')


def render_diagrams(directory, routes):
    directory.mkdir(parents=True, exist_ok=True)
    for route in routes:
        rid = route['id']
        d = Diagram(f"{rid}  {route['title']}", 'タイムアウトの対象と通信の分岐を示した論理図  /  基準日 2026-10-08')
        if rid in ('F1', 'F4'):
            draw_cache(d, api=rid == 'F4')
        elif rid == 'F2':
            d.node('client', 60, 310, 'client', '受付総10秒')
            d.node('alb', 440, 310, '共有画面ALB', 'idle 90秒')
            d.node('front', 820, 310, '受付ECS', '受付総5秒')
            d.node('queue', 1280, 310, 'SQS', 'visibility 420秒\njob期限とは別', width=345)
            d.node('lambda', 1250, 695, 'Lambda handler', 'hard70 / soft60秒', width=385)
            d.node('back_alb', 790, 695, '同じ画面ALB', 'バック用Host/path rule', width=355)
            d.node('back', 325, 695, 'バックECS', '業務総50秒', width=355)
            d.edge('client', 'alb')
            d.edge('alb', 'front')
            d.edge('front', 'queue', label='送信総4秒', label_at=(1180, 350))
            d.edge('front', 'client', side_a='bottom', side_b='bottom', via=((955, 555), (195, 555)), dashed=True,
                   label='202 / jobId を返して受付HTTP終了', label_at=(580, 540))
            d.edge('queue', 'lambda', side_a='bottom', side_b='top', label='ESMがpoll', label_at=(1570, 573))
            d.edge('lambda', 'back_alb', side_a='left', side_b='right', label='別HTTP 総55秒', label_at=(1198, 666))
            d.edge('back_alb', 'back', side_a='left', side_b='right')
            d.label((985, 908), 'バック成功 → handler成功 → ESMがSQS messageを削除', 26, bold=True)
            d.footer('同じjobIdが複数回届いても、DBの業務効果は重複させない。画面は2～5秒間隔で状態を照会。',
                     '初回完了SLO120秒とvisibility420秒は別の時計。再配信ではSLOを超える場合がある。')
        elif rid == 'F3':
            for key, x, title, detail in [
                ('client', 40, 'client', '帳票総90秒'), ('screen_alb', 390, '共有画面ALB', 'idle90秒'),
                ('ecs', 740, '画面ECS', '帳票endpoint総75秒'), ('report_alb', 1090, '帳票ALB', 'idle70秒'),
                ('render', 1440, 'EC2 帳票アプリ', 'render総60秒')]:
                d.node(key, x, 385, title, detail)
            for a, b in [('client','screen_alb'),('screen_alb','ecs'),('ecs','report_alb'),('report_alb','render')]:
                d.edge(a, b)
            d.label((1290, 334), 'ECS → EC2 の帳票HTTP全体：総65秒', 25, bold=True)
            d.edge('render', 'ecs', side_a='bottom', side_b='bottom', via=((1575, 626), (875, 626)), dashed=True,
                   label='基本案：同じHTTPのJSON応答', label_at=(1230, 650))
            d.node('data', 950, 815, '専用ECS data endpoint', '受信から総12秒', width=390)
            d.edge('render', 'data', side_a='bottom', side_b='right', via=((1680, 595), (1680, 882)), dashed=True,
                   label='条件付き：別HTTP JSON取得 総15秒', label_at=(1330, 748))
            d.label((550, 881), 'ECS前2 ＋ HTTP65 ＋ 後3 = 70 ≤ 75秒', 24, bold=True)
            d.footer('JSONはデータ形式。同じHTTPの応答なら新しい要求ではなく、追加のJSON用接続timerは不要。',
                     '別取得なら15秒はEC2 render60秒の内側。受信時の残りdeadlineで各上限を縮める。')
        elif rid == 'F5':
            d.node('token', 550, 215, 'Cognito M2M / CloudFront', '別HTTPS 総10秒 / token TTL3600秒', width=680)
            d.node('client', 45, 420, '外部client', 'API総30秒 / 業務45秒', width=285)
            d.node('gateway', 430, 420, 'Regional REST', 'BUFFERED統合25秒', width=300)
            d.node('link', 850, 420, 'VPC Link v2 ENI', '独立した業務timerなし', width=320)
            d.node('endpoint', 1300, 420, 'GWLBE', 'routingで検査を挿入', width=320)
            d.edge('client', 'token', side_a='top', side_b='left', via=((187, 282),), dashed=True)
            d.edge('client', 'gateway')
            d.edge('gateway', 'link')
            d.edge('link', 'endpoint')
            d.node('gwlb', 1260, 650, 'GWLB', 'TCP idle350秒')
            d.node('pan', 1550, 650, 'Palo Alto', 'App-ID実効idle確認', width=225)
            d.edge('endpoint','gwlb',side_a='bottom',side_b='top', label='検査へ', label_at=(1230, 600))
            d.edge('gwlb','pan')
            d.arrow([d.point('pan', 'bottom'), (1662, 813), (1395, 813), d.point('gwlb', 'bottom')], dashed=True,
                    label='検査結果をGWLBへ', label_at=(1530, 825))
            d.arrow([d.point('gwlb', 'top', 50), (1445, 608), (1560, 608), d.point('endpoint', 'bottom', 100)], dashed=True,
                    label='GWLBEへ戻る', label_at=(1660, 605))
            d.node('alb', 1160, 875, '公開API ALB', 'idle60秒')
            d.node('ecs', 790, 875, 'ECS', '総20秒・残りで短縮')
            d.node('proxy', 420, 875, 'RDS Proxy', 'borrow2秒')
            d.node('db', 50, 875, 'Aurora Serverless v2', 'SQL5秒', width=300)
            d.edge('endpoint','alb',side_a='bottom',side_b='right',via=((1460, 605), (1225, 605), (1225, 842), (1500, 842), (1500, 942)),
                   label='検査後のpacketをALBへ',label_at=(980, 737))
            for a,b in [('alb','ecs'),('ecs','proxy'),('proxy','db')]:
                d.edge(a,b,side_a='left',side_b='right')
            d.footer('GWLBE → GWLB → Palo Alto → GWLB → GWLBE の検査往復を含む。route/AZ/GENEVEを別途確認。',
                     'token取得は別通信。HTTP 20/25/30秒と、L4 flow idle350秒を同じ業務deadlineとして並べない。')
        elif rid == 'F6':
            d.node('token', 465, 210, 'Cognito M2M / CloudFront', '基本案は公開HTTPSの別認証 / 総10秒', width=890)
            upper = [
                ('sf',40,'Salesforce','Apex例 API callout30秒',285),
                ('consumer',395,'SF側consumer endpoint','Private Connect transit VPC',305),
                ('service',760,'顧客endpoint service','PrivateLink提供定義',310),
                ('nlb',1130,'NLB TCP443','flow idle350秒',250),
                ('execute',1450,'顧客execute-api endpoint','interface endpoint ENI',310)]
            for key,x,title,detail,w in upper:
                d.node(key,x,435,title,detail,width=w)
            for a,b in zip([n[0] for n in upper],[n[0] for n in upper][1:]):
                d.edge(a,b)
            d.edge('sf','token',side_a='top',side_b='left',via=((182,277),),dashed=True)
            lower = [
                ('gateway',1450,'Private REST','統合25秒',310),
                ('link',1100,'VPC Link v2','API Gatewayの出口',275),
                ('alb',750,'SF API ALB','idle60秒',275),
                ('ecs',400,'ECS','総20秒・残りで短縮',275),
                ('proxy',50,'RDS Proxy','borrow2秒',275)]
            for key,x,title,detail,w in lower:
                d.node(key,x,725,title,detail,width=w)
            d.edge('execute','gateway',side_a='bottom',side_b='top')
            for a,b in zip([n[0] for n in lower],[n[0] for n in lower][1:]):
                d.edge(a,b,side_a='left',side_b='right')
            d.node('db',50,940,'Aurora Serverless v2','SQL5秒',width=325,height=112)
            d.edge('proxy','db',side_a='bottom',side_b='top')
            d.label((960,980),'TLS証明書・Host/SNI・API ID・policy・NLB target IP を照合',26,bold=True)
            d.footer('SF側consumer endpointと、顧客AWSのexecute-api endpointは別の入口。Private APIとVPC Linkも別。',
                     'NLB TCP passthroughはHostを書き替えない。token取得がprivateになることは自動では保証されない。')
        path = directory / f'{rid}_route.png'
        d.save(path)
