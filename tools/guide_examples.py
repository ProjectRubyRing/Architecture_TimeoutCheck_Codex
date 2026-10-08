"""Illustrative configuration excerpts; these never change remote resources."""

EXAMPLES = []


def example(title, purpose, language, code, notes, refs=()):
    EXAMPLES.append(dict(title=title, purpose=purpose, language=language,
                         code=code.strip(), notes=notes, refs=refs))


example('01 ALB/TGの現在値を取得', 'まず実設定を保存し、初期案の提案値と比較する。', 'powershell', r'''
# Windows PowerShell。ARNは対象環境の変数として渡す。
aws elbv2 describe-load-balancer-attributes --load-balancer-arn $env:SCREEN_ALB_ARN
aws elbv2 describe-target-group-attributes --target-group-arn $env:SCREEN_TG_ARN
aws elbv2 describe-target-health --target-group-arn $env:SCREEN_TG_ARN
aws ecs describe-task-definition --task-definition $env:TASK_DEFINITION
aws ecs describe-services --cluster $env:ECS_CLUSTER --services $env:ECS_SERVICE
''', '読み取り例。画面ALB/TGだけでなく、API用3ALBと帳票ALB/TGにも個別に実施する。CLI credentials、Region、profileは環境で決める。秘密情報をこの資料へ貼り付けない。', ('S01','S03','S05','S06'))

example('02 SQS/Lambda/Proxyの現在値を取得', '相互依存する設定を同時に読み取る。', 'powershell', r'''
aws sqs get-queue-attributes --queue-url $env:QUEUE_URL --attribute-names All
aws lambda get-function-configuration --function-name $env:FUNCTION_NAME
aws lambda get-event-source-mapping --uuid $env:ESM_UUID
aws rds describe-db-proxies --db-proxy-name $env:PROXY_NAME
aws rds describe-db-proxy-target-groups --db-proxy-name $env:PROXY_NAME
''', '読み取り例。sourceとDLQの保存期間を両方確認し、Lambda Timeout70秒、window0、visibility420秒、BatchSize1の組合せを照合する。', ('S20','S23','S25','S12'))

example('03 API Gateway統合の読み戻し', 'REST methodの値と、stageへ反映したdeploymentを確認する。', 'powershell', r'''
aws apigateway get-integration --rest-api-id $env:REST_API_ID --resource-id $env:RESOURCE_ID --http-method GET
aws apigateway get-stage --rest-api-id $env:REST_API_ID --stage-name $env:STAGE_NAME
aws apigatewayv2 get-vpc-link --vpc-link-id $env:VPC_LINK_ID
''', 'HTTP methodは実際のGET/POST等へ置換する。REST APIでもVPC Link v2の管理はapigatewayv2。stageの既存deploymentが変更済統合を含むか確認し、非本番疎通で実効時間も測定する。', ('S28','S29'))

example('04 共有画面ALBの属性ファイル', 'ALB全体のidleとclient接続寿命を明示する設計例。', 'json', r'''
[
  {"Key": "idle_timeout.timeout_seconds", "Value": "90"},
  {"Key": "client_keep_alive.seconds", "Value": "3600"}
]
''', 'CLI modify-load-balancer-attributesの--attributes file://alb-attributes.jsonへ渡せる配列。変更コマンドは本作業では実行しない。API用ALBはidle60、帳票用ALBは70の別ファイル/値とする。既存接続のkeepaliveは旧値を保持し得る。', ('S01',))

example('05 ECS task definitionの抜粋', '終了猶予と健全性確認の時計を業務deadlineと分離する。', 'json', r'''
{
  "containerDefinitions": [{
    "name": "business-app",
    "essential": true,
    "stopTimeout": 120,
    "healthCheck": {
      "command": ["CMD-SHELL", "curl -fsS http://localhost:8080/live || exit 1"],
      "interval": 15, "timeout": 5, "retries": 3, "startPeriod": 30
    }
  }]
}
''', '完全なtask definitionではなく差分項目の説明用。Fargate Linuxを仮定。curlと/live endpointがimageに存在することが必要。ALBには/readinessを別に設け、サービスhealthCheckGracePeriodSeconds60秒を起動実測で調整する。startTimeoutは依存関係が必要な場合だけ。', ('S05','S06'))

example('06 RDS Proxyのconnection pool設定', 'borrow2秒と容量上限の80%/40%を分けて指定する。', 'json', r'''
{
  "ConnectionBorrowTimeout": 2,
  "MaxConnectionsPercent": 80,
  "MaxIdleConnectionsPercent": 40
}
''', 'modify-db-proxy-target-groupのconnection-pool-config用のobject例。IdleClientTimeout1800秒はProxy本体の別項目。InitQueryは業務専用Proxyでengine/roleを確認してから追加し、パスワードやkeyを入れない。80%/40%は実測前の容量例であり推奨の固定値ではない。', ('S12','S10','S13'))

example('07 PostgreSQLの確認とtransaction局所設定', '現在のengineで使える項目を確認し、SQLとlockの上限を分ける。', 'sql', r'''
SELECT name, setting, unit
FROM pg_settings
WHERE name IN ('statement_timeout', 'lock_timeout',
              'idle_in_transaction_session_timeout', 'transaction_timeout');

BEGIN;
SET LOCAL statement_timeout = '5s';
SET LOCAL lock_timeout = '1s';
-- 対象の業務SQLを実行。失敗時は必ずROLLBACKする。
COMMIT;
''', 'SQL実行例であり本作業ではDBへ接続しない。transaction_timeoutは存在確認後に候補8秒を検討。SET LOCALでもRDS Proxyのpinningへの影響を評価し、戻した設定が次のrequestへ漏れないことを試験する。残り時間が3秒ならSQL5秒を3秒未満へ縮める。', ('S15','S13'))

example('08 MySQLの確認とSELECT用上限', 'SELECTの実行上限とInnoDB行lock待ちを分離する。', 'sql', r'''
SHOW VARIABLES WHERE Variable_name IN
  ('max_execution_time','innodb_lock_wait_timeout',
   'wait_timeout','net_read_timeout','net_write_timeout');

SET SESSION max_execution_time = 5000;
SET SESSION innodb_lock_wait_timeout = 1;
-- 更新SQLはdriver取消とtransaction総deadlineを別途実装。
''', 'max_execution_timeは主にread-only SELECT用で、更新SQLの停止保証ではない。lock timeout後もtransaction全体が自動rollbackされたと考えず、アプリが明示rollbackする。上のSESSION変更はconnection再利用・pinningを評価した上で適用する。', ('S16','S57','S18','S13'))

example('09 REST integration設定objectの抜粋', 'BUFFERED25秒と、信頼できる入口時刻headerを示す。', 'json', r'''
{
  "type": "HTTP_PROXY",
  "httpMethod": "POST",
  "connectionType": "VPC_LINK",
  "connectionId": "REPLACE_WITH_VPC_LINK_V2_ID",
  "integrationTarget": "REPLACE_WITH_ALB_ARN",
  "uri": "https://api.example.com:443/jobs",
  "timeoutInMillis": 25000,
  "responseTransferMode": "BUFFERED",
  "requestParameters": {
    "integration.request.header.X-Gateway-Start-Ms": "context.requestTimeEpoch"
  }
}
''', 'REST PutIntegration APIの部分object。OpenAPI拡張ではintegration-targetという別表記なので混同しない。api.example.comは予約された例示用domain。ALB側証明書・Host/SNIと整合させ、headerはGatewayで上書きし、外部からALBへ直接入る要求を制限する。統合変更後はstage deployが必要。', ('S29','S58','S59','S31'))

example('10 アプリdeadlineの疑似code', 'epochで渡した入口時刻を受け、local monotonicで残り時間を管理する。', 'text', r'''
trusted_start_ms = 検証済みGateway header
elapsed = max(0, wall_clock_ms - trusted_start_ms) / 1000
remaining = 22 - elapsed - 1   # 内部22秒、時計差余裕1秒
work_budget = min(20, remaining - 2)  # 応答用2秒を予約
if work_budget <= 0:
    新しい仕事を始めずtimeout応答を返す
local_deadline = monotonic_now + work_budget
child_budget = min(child_cap, local_deadline - monotonic_now - child_cleanup)
if child_budget <= 0:
    依存先を呼ばず、取消と結果照合へ進む
''', '疑似code。入口headerが欠ける/不正/未来すぎる場合の拒否または厳しいlocal上限を決め、未来時刻で20秒を延ばさない。同期HTTPの待機終了、SQL取消、rollback、子process終了はそれぞれ実装し、取消失敗なら結果不明として照合する。別machineのmonotonic値をそのまま比較しない。')

example('11 SQS属性とESMの抜粋', 'source queueとESMの時間・batch設定をまとめて確認する。', 'json', r'''
{
  "sourceQueueAttributes": {
    "VisibilityTimeout": "420", "DelaySeconds": "0",
    "MessageRetentionPeriod": "345600"
  },
  "eventSourceMapping": {
    "BatchSize": 1, "MaximumBatchingWindowInSeconds": 0,
    "FunctionResponseTypes": ["ReportBatchItemFailures"],
    "ScalingConfig": {"MaximumConcurrency": 10}
  },
  "functionConfiguration": {"Timeout": 70}
}
''', '説明用に異なるAPIの項目を一つへまとめたobjectで、これをそのままAWSへ送るものではない。sourceのRedrivePolicyでmaxReceiveCount5とDLQ ARNを指定し、DLQのMessageRetentionPeriodは1209600秒。10並列はバックECS/DB容量に合わせる。', ('S20','S23','S24','S56'))

example('12 SQS部分失敗応答の形', 'soft deadlineで失敗IDを返し、成功済jobの再配信を抑える。', 'json', r'''
{
  "batchItemFailures": [
    {"itemIdentifier": "REPLACE_WITH_FAILED_SQS_MESSAGE_ID"}
  ]
}
''', 'itemIdentifierはSQS messageIdで、業務jobIdと区別する。全件成功ならbatchItemFailuresは空配列。FIFOでは順序を守るため最初の失敗後の未処理分も返す。hard timeoutでは応答できないため業務冪等化が必要。', ('S24',))

example('13 Cognito token取得とApex callout', 'OAuth取得は別HTTP、業務calloutは30秒という二つの時計。', 'text', r'''
token: POST https://AUTH_DOMAIN/oauth2/token
Content-Type: application/x-www-form-urlencoded
grant_type=client_credentials&scope=RESOURCE_SERVER/SCOPE
Authorization: client ID/secretを安全な認証設定から適用
取得総deadline10秒。access token本文やsecretをlogへ出さない。

Apex例:
HttpRequest req = new HttpRequest();
req.setEndpoint('callout:BUSINESS_NAMED_CREDENTIAL/jobs');
req.setMethod('POST');
req.setTimeout(30000);
''', 'Apexは抜粋。Named Credentialに認証とOutbound Network Connectionを正しく関連付ける。認証実装が内部でtokenを取得する場合、その時間がcallout全体へどう含まれるか測定する。120秒累積制約には同transactionのほかのcalloutも含む。M2Mのrefreshはrefresh tokenではなく新規取得。', ('S40','S48','S49','S50'))


TEST_PLAN = [
 ('T01','全同期経路','正常な小さい要求','client/ALB/ECS/DBの時刻を同一IDで照合','client総30秒以内、ECS20秒以内。P95/P99とerror率を記録','設定の上限だけで性能保証しない'),
 ('T02','画面・社内API','cache hit / miss','同じkeyのhitと初回missを作る','hitではDB照会なし、missはECSからProxyへ照会','ValkeyがSQL中継していないことを確認'),
 ('T03','cache障害','Valkey GETの遅延・切断','非本番でclient接続/応答を遅らせる','cache段階0.5秒で打切り、許可されたfallbackだけ実行','同時fallbackを抑えDB容量とcircuit breakerも見る'),
 ('T04','DB取得','アプリpool枯渇','pool全connectionを占有する','取得3秒以内で失敗、DB phase12秒へ収まる','新規driver接続3秒を二重加算しない'),
 ('T05','Proxy借用','DB pool枯渇・failover','借用不能状態を安全な非本番で作る','borrow2秒で失敗、意味あるerror応答','DatabaseConnectionsBorrowLatency/pinningを記録'),
 ('T06','PostgreSQL','遅いSELECT','非本番でpg_sleep等の遅延SQL','statement5秒付近で停止、rollbackしclean connectionへ','発火/取消/応答までの実時間を別計測'),
 ('T07','PostgreSQL','lock待ち','別transactionで対象行lockを保持','lock1秒で失敗、statement5秒を超えない','失敗後のtransaction/connection状態を確認'),
 ('T08','MySQL SELECT','遅いread-only SELECT','対象engineで遅延読取を作る','max_execution_time適用範囲と実停止を確認','stored procedure/更新へ同じ保証を転用しない'),
 ('T09','MySQL更新','更新SQLの遅延・取消','更新を遅らせdriver query timeoutを発火','DB側で実停止/rollback、取消失敗なら結果不明を照合','socket切断だけをcancel成功と判定しない'),
 ('T10','transaction','複数SQLの逐次実行','各SQLが数秒かかる処理を用意','transaction8秒・DB12秒内へ残り予算で短縮','単独SQL5秒を毎回満額使わない'),
 ('T11','公開/SF API','Gateway25秒超相当のbackend遅延','非本番で応答を遅らせる','統合25秒とECS早期終了のlogを照合','Gateway504とtarget504を分ける'),
 ('T12','公開/SF API','ALB→target新規接続の遅延','許可された検証環境で接続段階を遅らせる','ECS到着時に残りを縮め、Gateway後の業務継続を防ぐ','固定10＋20=30秒の反例を再現して比較'),
 ('T13','deadline header','未来・欠落・外部偽装header','clientから入口時刻headerを送信する','Gateway上書き・入口制限が働き、処理20秒を延ばせない','時計差1秒の前提もNTP/計測で確認'),
 ('T14','slow response','少量byteを連続送信','I/O idle未到達だが総時間を超える応答','client総deadlineで終了する','HTTP/2 PINGをALB idleリセットと扱わない'),
 ('T15','帳票基本','60秒以内のrenderと大きめJSON','サイズ別・生成時間別に計測','EC260、HTTP65、ECS75、client90の箱へ収まる','parseと最終送信も含める'),
 ('T16','帳票別JSON','EC2からECSへ別のJSON要求','data endpoint12秒・取得15秒の遅延試験','15＋生成35＋前後5≤render60で取消も伝播','画面requestのthread pool再入を避ける'),
 ('T17','帳票取消','利用者切断・子processが長時間動作','clientをdeadline前後に終了','render子process/依存HTTPを停止、生成済結果を照合','中断直後のcommit/生成済みの扱いを確認'),
 ('T18','接続再利用','ALB/server/client idleの競合','各idle付近で再利用を繰り返す','client45秒破棄、server120/100秒で不要な502を抑える','旧値のconnectionと新規connectionを両方試す'),
 ('T19','deploy終了','通常/帳票/バック処理中にrolling更新','SIGTERM、drain、強制kill時刻を記録','TG30/90秒とstop120秒で残要求を処理または明確に取消','SIGTERMの発生順序を実測する'),
 ('T20','起動/健康','遅い起動と依存障害','起動時間、readiness、livenessを別測定','grace/check設定が起動実測へ合い、過剰再起動しない','ALB全target不健康時のfail openも試験'),
 ('T21','SQS受付','送信成功後に202応答を消失','送信とclient結果の間で接続を切る','同じjobId再照会で二重受付/業務更新なし','outbox等が必要なら業務整合性で判断'),
 ('T22','SQS再配信','バックcommit後のHTTP応答消失','Lambdaが結果を受け取れない状態を作る','再配信でも同一jobIdは同じ結果、DB効果一回','FIFOでも外部DBとのexactly-onceを仮定しない'),
 ('T23','Lambda soft/hard','HTTP55秒・handler60/70秒境界','時間境界に遅延を設定','softでfailure応答、hard停止でも重複安全','強制終了時はpartial responseが出ないことを確認'),
 ('T24','visibility/window','Lambda timeoutやwindowを変更','70→80秒、window0→5秒の候補を比較','6×hard＋windowを満たしESM実効値を読み戻す','再受信までの待ちと初回SLOを分けて記録'),
 ('T25','batch/concurrency','batch件数/並列数を増加','1件50秒を10件逐次等で比較','70秒へ収まらない設定を拒否し、DB容量を超えない','FIFO partial failureの未処理順序も確認'),
 ('T26','DLQ/期限','5回失敗・1時間超・再投入','expired jobと処理済jobをDLQから検証再投入','expiredは新規実行なし、済jobは二重更新なし','保存4/14日と業務1時間を区別'),
 ('T27','token','期限・再取得・大量同時miss','期限近辺、2700秒、認証endpoint障害を試す','取得10秒以内、single-flight/jitter、正しいscope','token/secretをlogに残さない'),
 ('T28','認証拒否','invalid token・scope不足・policy拒否','401/403を意図的に作る','接続timeoutと区別し未認証要求をbackendへ通さない','Gateway/Cognito/SalesforceログのIDで照合'),
 ('T29','Salesforce private','Host/SNI/API ID・ENI IP変更','private URL、NLB target、endpoint policyを確認','TLS検証有効でPrivate RESTまで到達する','consumer endpointとexecute-api endpointを別々に確認'),
 ('T30','GWLB/Palo Alto','往復route・App-ID・idle','同じflowの両方向と350秒付近のidleを観測','GENEVE検査戻り、実効App-ID timer、ENI stateが整合','global3600秒だけで合格としない'),
 ('T31','VPC Link','AVAILABLE/INACTIVEの復帰','利用の少ない検証linkの状態と疎通を観察','再作成中の数分失敗を運用手順で扱う','25秒統合の延長で休眠復帰を解決しない'),
 ('T32','容量/運用','負荷・DB最大/最小ACU・alarm','目標throughputでP95/P99/並列/queue ageを測定','時間を守る容量を決め、borrow/timeout/DLQを監視','計算シートOKはこの試験の成功ではない'),
]
