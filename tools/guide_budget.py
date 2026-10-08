"""Editable time budgets and their Excel/Python arithmetic contracts."""

PARAMETERS = []


def param(name, group, label, value, note, refs=(), maximum=100000, integer=False):
    PARAMETERS.append(dict(name=f'p_{name}', group=group, label=label, value=value,
                           unit='件' if name == 'batch' else '秒', note=note,
                           refs=refs, maximum=maximum, integer=integer))


param('client', '同期API', '通常画面・社内/公開/SF APIのclient総時間', 30, '公開/SFではtoken取得10秒と別のAPI呼出し。C01/C06。')
param('ecs', '同期API', '通常ECS endpoint処理上限', 20, 'E01。受信時の残り時間でさらに短縮する。')
param('gateway', '同期API', 'REST BUFFERED統合時間', 25, 'G01。入力秒×1000をtimeoutInMillisへ。29秒超は承認を確認。', ('S27',), maximum=29)
param('screen_idle', 'HTTP接続', '共有画面ALB idle', 90, 'A01。画面・帳票・バック用ruleが共有するALB全体の属性。', ('S01',), maximum=4000)
param('api_idle', 'HTTP接続', '社内/公開/SF API用ALB idle', 60, 'A02/A04/A05。各ALBへ同じ設計値を別々に設定。', ('S01',), maximum=4000)
param('server_idle', 'HTTP接続', 'ECS HTTP serverのkeepalive idle', 120, 'E04。共有ALB90秒より長くする。業務20秒とは別。')
param('http_pool_idle', 'HTTP接続', 'HTTP client poolの未使用接続破棄', 45, 'C05。次段のALB/API Gatewayより先に未使用接続を捨てる。')
param('cache_connect', '通常処理', 'Valkey新規接続の上限', 0.2, 'V01。DNS/TLSを含む総cache段階も別途制限する。')
param('cache_command', '通常処理', 'Valkey command待機上限', 0.3, 'V02。小さいGETの設計例。')
param('cache', '通常処理', 'cache段階総時間', 0.5, 'V03。接続とGETを含む。miss時のDB12秒は別の逐次段階。')
param('db_phase', '通常処理', 'DB段階全体の総時間', 12, 'D08。pool取得・Proxy borrow・SQL・取消/rollbackを内包する。')
param('app_misc', '通常処理', '認証・業務・JSON等の合計予算', 3, '並列/逐次の実態を計測する。DB/cacheを再び含めない。')
param('response', '通常処理', '通常APIの応答・終了余裕', 2, 'エラー整形、応答準備などに予約する。巨大downloadは別計算。')
param('db_pool', 'DB内部', 'DB connection取得全体', 3, 'D01/D02。HikariCP例。driver新規接続3秒を二重計上しない。')
param('borrow', 'DB内部', 'RDS Proxy ConnectionBorrowTimeout', 2, 'D03。SQL待ちとは別。共有Proxy TGへ設定。', ('S12',), maximum=300)
param('sql', 'DB内部', '1 SQLの処理上限', 5, 'PG statement_timeout。MySQL更新は取消の実効性が前提。')
param('db_cleanup', 'DB内部', 'DB取消・rollback・応答の余裕', 1, '計測で確保する。cancelが届かない時は結果照合が必要。')
param('db_command', 'DB内部', 'DB commandの外側総上限', 8, 'D07。socket/read8秒だけでは総8秒を保証しない場合がある。')
param('transaction', 'DB内部', 'transaction総上限', 8, 'D08。本計算は1 SQL例。複数SQLでは残り時間で短縮する。')
param('db_pool_idle', 'DB接続', 'DB pool idle eviction', 240, 'D06。minIdleと掃除の遅れを確認。')
param('proxy_idle', 'DB接続', 'RDS Proxy IdleClientTimeout', 1800, 'D04。SQL実行時間ではない。')
param('db_life', 'DB接続', 'DB pool maxLifetime', 1800, 'D06。RDS Proxyの固定client寿命86400秒より短くする。')
param('report_client', '帳票', '帳票client総上限', 90, 'C02。通常client30秒とはendpoint別に設定する。')
param('report_ecs', '帳票', '画面ECSの帳票endpoint総上限', 75, 'E02。帳票HTTPと前後処理を内包する。')
param('report_http', '帳票', 'ECS→EC2帳票HTTP総上限', 65, 'R01。接続・render・JSON応答をすべて含む。')
param('render', '帳票', 'EC2 render request総上限', 60, 'R02。受信時点の残り時間で短縮する。')
param('report_idle', '帳票', '帳票ALB idle', 70, 'A03。無通信のrender60秒を覆う。', ('S01',), maximum=4000)
param('report_server_idle', '帳票', 'EC2 HTTP server keepalive idle', 100, 'R03。帳票ALB70秒より長くする。')
param('report_pre', '帳票', '画面ECS前処理', 2, '帳票HTTP65秒より前に使う逐次予算。')
param('report_post', '帳票', '画面ECS後処理', 3, 'JSON加工・応答準備。')
param('json_http', '帳票・別JSON', 'EC2→ECSの別JSON取得HTTP', 15, 'R04。EC2から新しいHTTP要求を出す場合だけ。')
param('json_ecs', '帳票・別JSON', 'ECS data endpoint処理', 12, 'R05。通常画面処理へ再入しない専用endpointの例。')
param('json_render', '帳票・別JSON', 'JSON取得後の生成予算', 35, 'EC260秒の中で15＋35＋5秒。')
param('json_misc', '帳票・別JSON', 'EC2前後処理予算', 5, '取得と生成以外の合計。')
param('accept_client', '非同期受付', 'job受付client総上限', 10, '受付HTTPだけの時計。完了SLO120秒とは別。')
param('accept_ecs', '非同期受付', 'job受付ECS総上限', 5, 'Q02。SQS送信・状態保存・202応答を含む。')
param('sqs_send', '非同期受付', 'SendMessage総上限', 4, 'Q01。最大2attemptsをこの4秒の内側で管理する。')
param('accept_misc', '非同期受付', '送信以外の受付予算', 0.5, '状態保存とjobId応答の例。')
param('worker', '非同期実行', 'バックECSのrequest総上限', 50, 'E03。jobIdの業務結果保存を含む。')
param('worker_http', '非同期実行', 'Lambda→バックECS HTTP総上限', 55, 'L04。再試行なしを起点とする。')
param('lambda_misc', '非同期実行', 'Lambda内HTTP以外の予算', 5, '前後処理の合計。hard終了用10秒を重複加算しない。')
param('lambda_soft', '非同期実行', 'Lambda soft deadline', 60, 'L05。新しい仕事を止めてfailure応答を作る境界。')
param('lambda_end', '非同期実行', 'Lambda終了余裕', 10, 'hard70−soft60。')
param('lambda_hard', '非同期実行', '標準Lambda Timeout', 70, 'L01。標準Lambdaの最大900秒。LMIの5400秒と区別。', ('S25',), maximum=900, integer=True)
param('visibility', '非同期実行', 'SQS VisibilityTimeout', 420, 'Q03。推奨6×Lambda hard＋batch window。', ('S23',), maximum=43200, integer=True)
param('window', '非同期実行', 'MaximumBatchingWindowInSeconds', 0, 'L02。Standard queue。FIFOのwindow設定へ転用しない。', ('S23',), maximum=300, integer=True)
param('batch', '非同期実行', 'BatchSize（逐次処理の計算）', 1, '1件あたりHTTP55秒の例。並列処理時は別に容量も評価。', ('S23',), maximum=10000, integer=True)
param('queue_wait', '初回SLO', '通常時のqueue待ち予算', 30, '実測の目標。visibility420秒とは別。')
param('result', '初回SLO', '状態反映・pollでの完了検知予算', 10, 'poll2～5秒を含む合計予算例。')
param('job_slo', '初回SLO', '初回完了SLO', 120, '故障・再配信を含む厳密な最大完了時間ではない。')
param('sqs_poll', '自前poller', 'ReceiveMessage long poll', 20, '自前consumerの場合だけ。Lambda ESM pollerはAWS管理。', ('S22',), maximum=20, integer=True)
param('sqs_read', '自前poller', 'ReceiveMessage client read', 25, 'poll20秒より長い。ESMへこの値を直接指定しない。')
param('token_http', '認証', 'token取得HTTP総上限', 10, 'T01。通常はcacheに有効tokenがあれば省略。')
param('token_ttl', '認証', 'access token有効期限', 3600, 'T02。HTTP待機時間と別。')
param('token_refresh', '認証', '再取得目安（jitter前）', 2700, 'T03。有効期間約75%。この少し前へ0～60秒jitter。')
param('business_misc', '認証', 'token＋API以外の業務余裕', 5, '全体契約を決める時に予約。')
param('business', '認証', '外部/SFの業務一件の総上限', 45, 'token10＋API30＋余裕5。Apex累積制約は別途確認。')
param('gwlb', 'L4状態', 'GWLB TCP flow idle', 350, 'N02。5-tuple stickinessの条件。', ('S33',), maximum=6000, integer=True)
param('nlb', 'L4状態', 'NLB TCP listener idle', 350, 'N04。TLS listenerは350秒固定で、この入力を変更しない。', ('S35',), maximum=6000, integer=True)
param('pan', 'L4状態', 'Palo Alto該当App-IDの実効TCP idle', 3600, 'N07。global既定ではなく該当sessionの値を入力。', ('S39',), integer=True)
param('eni', 'L4状態', '対象ENIの実効TcpEstablishedTimeout', 350, 'N09。AWS管理ENIは変更できると仮定しない。', ('S38',), maximum=432000, integer=True)
param('network_pool_idle', 'L4状態', '長期接続の未使用pool破棄', 240, '経路内の最短L4 idleより早く、余裕を含めて破棄する。')
param('gateway_internal', 'deadline伝播', 'Gateway入口起点の内部総予算', 22, 'G06。統合25秒に対して先に終了するための保守的な予算。')
param('gateway_elapsed', 'deadline伝播', 'Gateway入口→ECS到着までの経過例', 10, '異常時の新規接続等を含む例。入力を変えて短縮量を確認。')
param('clock_skew', 'deadline伝播', '時計差として差し引く余裕', 1, 'epoch伝播からlocal monotonicへ変換する時に確保。')
param('ecs_end', 'deadline伝播', '短縮ECSの応答終了余裕', 2, '残り時間から引いて、業務を止めて応答を準備する。')
param('drain_normal', '終了猶予', '通常API専用TGのderegistration delay', 30, 'A08。帳票と共有する画面TGにはこの30秒を使わない。', ('S03',), maximum=3600, integer=True)
param('drain_long', '終了猶予', '帳票・画面共用・バックTGのdrain', 90, 'A09。最も長い画面帳票75秒に余裕を取る。', ('S03',), maximum=3600, integer=True)
param('stop', '終了猶予', 'Fargate Linux container stopTimeout', 120, 'E05。SIGTERMで新規受付を止めることが前提。', ('S05',), maximum=120, integer=True)
param('stop_cleanup', '終了猶予', 'container終了処理の予算', 10, '残処理の取消・log flush等を実測する。')

CHECKS = []


def check(cid, group, label, expression, strict, note):
    CHECKS.append(dict(id=cid, group=group, label=label, expression=expression,
                       strict=strict, note=note, unit='件' if cid == 'B40' else '秒'))


check('B01', '通常処理', 'cache接続＋command ≤ cache総時間', 'p_cache-p_cache_connect-p_cache_command', False, '逐次合計。0秒余裕でも外側deadlineを実装する。')
check('B02', '通常処理', 'cache＋DB段階＋その他＋応答 ≤ ECS', 'p_ecs-(p_cache+p_db_phase+p_app_misc+p_response)', False, '初期案17.5秒、ECS20秒との差2.5秒。SQL5秒はDB12秒に内包。')
check('B03', '通常処理', 'ECS < client', 'p_client-p_ecs', True, '正常な経路の外側余裕。接続待ちは残りdeadlineで制限する。')
check('B04', '通常処理', 'ECS < REST integration', 'p_gateway-p_ecs', True, '固定値だけでは接続待ちを含めた25秒保証にならない。B38～B40も読む。')
check('B05', '通常処理', 'REST integration < client', 'p_client-p_gateway', True, 'token取得を統合25秒へ足さない。')
check('B06', 'DB内部', '取得＋borrow＋SQL＋掃除 ≤ DB段階', 'p_db_phase-(p_db_pool+p_borrow+p_sql+p_db_cleanup)', False, '初期案11秒≤12秒。Hikari新規接続は取得3秒へ内包。')
check('B07', 'DB内部', 'borrow＋SQL＋掃除 ≤ command総時間', 'p_db_command-(p_borrow+p_sql+p_db_cleanup)', False, 'socket/readだけで総時間を保証できないdriverには別deadlineが必要。')
check('B08', 'DB内部', '1 SQL例＋borrow＋掃除 ≤ transaction', 'p_transaction-(p_borrow+p_sql+p_db_cleanup)', False, '複数SQLを行う時は再配分する。各5秒を何回でも使わない。')
check('B09', 'HTTP接続', 'API処理 < API用ALB idle', 'p_api_idle-p_ecs', True, '最大無通信がECS処理時間程度である小さいBUFFERED応答の前提。')
check('B10', 'HTTP接続', 'ECS keepalive > 共有ALB最大idle', 'p_server_idle-MAX(p_screen_idle,p_api_idle)', True, 'target serverの未使用接続をALBより先に閉じる競合を避ける。')
check('B11', 'HTTP接続', 'client pool idle < 次段最短idle', 'MIN(p_screen_idle,p_api_idle,p_report_idle,310)-p_http_pool_idle', True, '310秒はREST frontend公開値。借用時の健全性確認も必要。')
check('B12', 'DB接続', 'DB pool idle < Proxy client idle', 'p_proxy_idle-p_db_pool_idle', True, 'Hikariの掃除遅延・minIdle条件に余裕を持つ。')
check('B13', 'DB接続', 'DB pool寿命 < Proxy固定24時間', '86400-p_db_life', True, '接続生成からの寿命。SQLや未使用時間のtimerと別。')
check('B14', '帳票', 'EC2 render < ECS→EC2 HTTP', 'p_report_http-p_render', True, '受信時の残り予算でrender60秒を縮める。')
check('B15', '帳票', '帳票HTTP＋前後処理 ≤ 画面ECS', 'p_report_ecs-(p_report_pre+p_report_http+p_report_post)', False, '初期案2＋65＋3=70秒、ECS75秒との差5秒。')
check('B16', '帳票', '画面ECS帳票処理 < client', 'p_report_client-p_report_ecs', True, 'HTTP接続待ちや大きいdownloadは残り予算で短縮する。')
check('B17', '帳票', 'render無通信 < 帳票ALB idle', 'p_report_idle-p_render', True, '60秒byteが返らないrenderに70秒idle。')
check('B18', '帳票', '画面帳票無通信 < 共有画面ALB idle', 'p_screen_idle-p_report_ecs', True, '通常画面・非同期バックと同じALBの共有値。')
check('B19', '帳票', 'EC2 keepalive > 帳票ALB idle', 'p_report_server_idle-p_report_idle', True, 'EC2 HTTP server側の未使用時間。')
check('B20', '帳票・別JSON', 'data endpoint < 別JSON HTTP', 'p_json_http-p_json_ecs', True, '別要求の場合だけ。JSONが元HTTPの応答ならこの経路は不要。')
check('B21', '帳票・別JSON', 'JSON取得＋生成＋前後 ≤ EC2 render', 'p_render-(p_json_http+p_json_render+p_json_misc)', False, '初期案15＋35＋5=55秒≤60秒。取得15秒を60秒の外に足さない。')
check('B22', '非同期受付', 'SendMessage＋前後 ≤ 受付ECS', 'p_accept_ecs-(p_sqs_send+p_accept_misc)', False, '受理済か不明な状態へjobIdを用意する。')
check('B23', '非同期受付', '受付ECS < 受付client', 'p_accept_client-p_accept_ecs', True, '202/jobIdを返して前半のHTTPを閉じる。')
check('B24', '非同期実行', 'バックECS < LambdaのHTTP', 'p_worker_http-p_worker', True, '別HTTPの総時間。画面ALBの90秒はこの55秒を延ばさない。')
check('B25', '非同期実行', '逐次batch HTTP＋前後 ≤ soft', 'p_lambda_soft-(p_batch*p_worker_http+p_lambda_misc)', False, '初期案1×55＋5=60秒。batch10件を直列では収まらない。')
check('B26', '非同期実行', 'soft＋終了余裕 ≤ hard', 'p_lambda_hard-(p_lambda_soft+p_lambda_end)', False, 'soft60＋failure応答余裕10=hard70秒。')
check('B27', '非同期実行', 'visibility ≥ 6×hard＋window', 'p_visibility-(6*p_lambda_hard+p_window)', False, 'AWS推奨。Lambdaの設定検証はhard≤visibility、推奨はそれより長い。')
check('B28', '非同期実行', 'バック無通信 < 共有画面ALB idle', 'p_screen_idle-p_worker', True, 'shared ALBは帳票75秒も通るため90秒案。')
check('B29', '初回SLO', 'queue待ち＋soft＋完了検知 ≤ SLO', 'p_job_slo-(p_queue_wait+p_lambda_soft+p_result)', False, '初期案100秒≤120秒。再配信で420秒待つ場合まで保証しない。')
check('B30', '自前poller', 'ReceiveMessage read > long poll', 'p_sqs_read-p_sqs_poll', True, '自前consumerの場合だけ。Lambda ESMへSDK readを指定しない。')
check('B31', '認証', 'token取得＋API＋余裕 ≤ 業務総時間', 'p_business-(p_token_http+p_client+p_business_misc)', False, '初期案10＋30＋5=45秒。token cache hit時は取得を省略。')
check('B32', '認証', '再取得 < token期限', 'p_token_ttl-p_token_refresh', True, '2700秒を基準に早めjitter。遅らせて期限後に取得しない。')
check('B33', '認証', '業務一件 < Apex累積callout上限', '120-p_business', True, 'Apexの場合だけ。別calloutの実際の待機も合算する。')
check('B34', 'L4状態', 'Palo Alto実効idle ≥ GWLB idle', 'p_pan-p_gwlb', False, '同じflowの検査区間を想定。App-ID実効値を入力する。')
check('B35', 'L4状態', '対象ENI conntrack ≥ NLB/GWLB idle', 'p_eni-MAX(p_nlb,p_gwlb)', False, '対象instanceのENIを延長する場合の関係。経路ごとの管理範囲を確認。')
check('B36', 'L4状態', '長期pool idle < 最短L4 idle', 'MIN(p_nlb,p_gwlb,p_pan,p_eni)-p_network_pool_idle', True, '240秒で掃除して350秒の閉じたflow再利用を避ける設計例。')
check('B37', 'deadline伝播', '入口内部予算＋時計差 < integration', 'p_gateway-(p_gateway_internal+p_clock_skew)', True, '統合開始より早い入口起点を使う保守的な設計。')
check('B38', 'deadline伝播', '短縮後に業務を開始できる残り', 'MIN(p_ecs,MAX(0,p_gateway_internal-p_gateway_elapsed-p_clock_skew-p_ecs_end))', True, '初期例ではmin(20,22−10−1−2)=9秒。0なら新しい業務を始めず終了する。')
check('B39', 'deadline伝播', '経過＋短縮ECS＋時計差＋終了 ≤ 内部', 'p_gateway_internal-(p_gateway_elapsed+MIN(p_ecs,MAX(0,p_gateway_internal-p_gateway_elapsed-p_clock_skew-p_ecs_end))+p_clock_skew+p_ecs_end)', False, '初期例10＋9＋1＋2=22秒。固定20秒なら30秒でGateway25秒を超える。')
check('B40', '適用範囲', 'batchが少なくとも1件', 'p_batch-1', False, '0件・負数ではworker予算が意味を持たない。')
check('B41', '終了猶予', '通常TG drain > 通常ECS処理', 'p_drain_normal-p_ecs', True, '新規受付停止からの残処理を実測し、deploy時に途中切断しない。')
check('B42', '終了猶予', '長時間TG drain > 最長endpoint処理', 'p_drain_long-MAX(p_report_ecs,p_worker,p_render)', True, '画面帳票75秒・バック50秒・EC2帳票60秒の最大値。')
check('B43', '終了猶予', '最長残処理＋終了処理 ≤ stop', 'p_stop-(MAX(p_report_ecs,p_worker,p_render)+p_stop_cleanup)', False, 'drain90秒とstop120秒を足して210秒の保証と考えない。SIGTERM時刻と実際の順序も確認。')


def values(overrides=None):
    result = {p['name']: p['value'] for p in PARAMETERS}
    result.update(overrides or {})
    return result


def evaluate(expression, inputs):
    # Expressions are maintained in this file; no external strings are accepted.
    import ast
    import operator

    operations = {ast.Add: operator.add, ast.Sub: operator.sub,
                  ast.Mult: operator.mul, ast.Div: operator.truediv}

    def visit(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name):
            return inputs[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in operations:
            return operations[type(node.op)](visit(node.left), visit(node.right))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in ('MIN', 'MAX') and not node.keywords:
                fn = min if node.func.id == 'MIN' else max
                return fn(visit(arg) for arg in node.args)
        raise ValueError(f'Unsupported budget expression: {ast.dump(node)}')

    return round(visit(ast.parse(expression, mode='eval').body), 9)


def statuses(overrides=None):
    inputs = values(overrides)
    return {c['id']: evaluate(c['expression'], inputs) > 0 if c['strict']
            else evaluate(c['expression'], inputs) >= 0 for c in CHECKS}
