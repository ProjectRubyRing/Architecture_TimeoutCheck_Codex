"""Six user-supplied routes, with logical branches made explicit."""

ROUTES = [
dict(id='F1', sheet='03_画面', title='イントラネットの画面',
     original='AWSのクライアント → 画面呼び出し → 画面用ALB → ECS → ElastiCache for Valkey → RDS Proxy → Aurora Serverless v2',
     corrected='クライアント → 画面用ALB → ECS。ECSがValkeyへ照会し、missならECS自身がRDS Proxy経由でAuroraへ照会する。',
     diagram='''flowchart LR
  C["AWS内クライアント\n総30秒"] --> A["画面ALB\nidle 90秒"] --> E["ECSアプリ\n総20秒"]
  E --> V["Valkey\ncache段階0.5秒"]
  V -->|hit| E
  E -->|miss・許可したfallback| P["RDS Proxy\nborrow 2秒"] --> D["Aurora\nSQL 5秒"]
  D --> P --> E
  E --> A --> C''',
     stages=[
       ('1','client → 画面ALB','HTTPS。呼出し側が総30秒を管理。','C01 C03 C04 C05','最初の30秒時計は、DB照会を始めてもゼロに戻さない。'),
       ('2','画面ALB → ECS','ALB idle90秒、ECS request20秒。','A01 A06 A07 E01 E04','ECSが先に意味のあるエラー応答を返す。idle90秒を処理90秒と読まない。'),
       ('3','ECS ↔ Valkey','cache connect0.2秒＋command0.3秒以内。','V01 V02 V03 V04 V05 V06 V07','hitならDBへの線は使わない。cache障害時のfallback可否をデータ用途で決める。'),
       ('4','ECS → RDS Proxy','DB段階総12秒の内側でpool・接続・borrow。','D01 D02 D03 D04 D06 D07 D08','ValkeyがSQLを中継する構成ではない。Proxy borrow既定120秒は短い同期要求と衝突する。'),
       ('5','RDS Proxy ↔ Aurora','SQL5秒、lock1秒、transaction8秒。','D05 D09 D10 D11 D12 D13 D14 D15 D16 D17 D18 D19 D20','DB engine別の設定を選ぶ。PG用のstatement_timeoutをMySQLへ入れない。'),
       ('6','ECS → ALB → clientの応答','JSON作成・HTML生成・送信・取消も予算に含める。','E01 X01 X02','DBが終わった時点で成功ではない。応答が届くまでの余裕を残す。'),
     ],
     explanations=[
       ('図書館のたとえ','画面は「本を見せて」というお願いです。ALBは空いている係を選ぶ案内係、ECSはお願いを聞く係、Valkeyは机の上のよく使うメモ、Auroraは大きな本棚です。メモに答えがあれば本棚まで歩きません。なければECSの係が、接続を貸すRDS Proxyを通して本棚を調べます。',()),
       ('通常の動作イメージ','例としてt=0で画面要求、0.1秒でECS受付、0.15秒でcache miss、0.3秒でDB照会、0.7秒で結果、0.9秒で画面応答、と考えます。これは理解のための例で、AWSが保証する速度ではありません。各上限は普段からその長さだけ待つ設定ではなく、異常時に止める柵です。',()),
       ('cacheが止まった時','cache段階を0.5秒で切り上げてからDBへ進む設計なら、DB時間を残せます。ただしcache障害で全要求がDBへ集中するとDBも止まります。fallbackには同時実行上限、短期circuit breaker、同じkeyへの照会集約を付け、DBへ何でも無制限に流さないようにします。これはアプリ側の設計です。',()),
       ('SQLが長い時','PGならSQLがDBへ届いてから5秒程度でstatement_timeoutが働き、アプリがrollbackし、20秒より前にエラーを整えます。MySQLの更新は同じSQL変数だけで止まらないため、driver取消が実効的か別試験が必要です。HTTP timeout後にcommitが済むこともあり、更新結果不明は再送前に照会します。',('S15','S16')),
       ('時間を積み上げる','cache0.5＋DB段階12＋その他3＋応答余裕2=17.5秒をECS20秒へ収めます。DB段階の12秒はSQL5秒を内包し、lock1秒もSQLの内側です。20＋12＋5とすべてを足す計算ではありません。予算の最長経路と包含関係を見て足します。',()),
       ('同じ画面ALBを帳票と共有','帳票には長い無通信があるため画面ALBのidleは90秒とします。それでも通常画面ECS20秒・client30秒は独立して有効です。idleはALB全体の属性なので、URLルールごとに20秒と90秒を直接設定することはできません。',('S01',)),
     ]),
dict(id='F2', sheet='04_画面非同期', title='イントラネットの画面非同期',
     original='AWSのクライアント → 画面呼び出し → 画面用ALB → ECS → SQS → Lambda → 画面用ALB → ECS（バックコンテナ）',
     corrected='前半の受付HTTPはjobIdと202等を返して終了。その後LambdaのESMがSQSを受信し、別HTTPで画面ALBのバック用ルールへアクセスする。',
     diagram='''flowchart LR
  C["client\n受付総10秒"] --> A["画面ALB\nidle90秒"] --> E["ECS受付\n総5秒"] --> Q["SQS\nvisibility420秒"]
  E -->|202・jobId| C
  Q -->|Lambda ESMがpoll| L["Lambda\nhard70秒・soft60秒"]
  L -->|別HTTP総55秒| A2["同じ画面ALB\nバック用rule"] --> B["ECSバック\n総50秒"]
  B -->|結果・jobId| L
  L -->|成功後ESMが削除| Q
  C -. 状態照会2～5秒間隔 .-> E''',
     stages=[
       ('1','client → 画面ALB → 受付ECS','受付client10秒、受付アプリ5秒。','Q02 A01 C03 C05','画面をバック処理終了まで開きっぱなしにしない。'),
       ('2','受付ECS → SQS','SendMessage総4秒、最大2attempts。','Q01 Q05 Q06 X01 X03','受理済か不明な時も同じjobIdで再確認。業務状態保存と送信の整合が必要。'),
       ('3','SQS → Lambda ESM','visibility420秒、window0秒、batch1件。','Q03 Q04 Q07 L02 L03','Lambda pollerが受信する。SQSが最初のclient TCP接続を保持する機能ではない。'),
       ('4','Lambda handler','Timeout70秒、soft60秒、最後10秒を確保。','L01 L05 L06','標準Lambdaを想定。処理能力に合わせてESM同時実行を抑える。'),
       ('5','Lambda → 画面ALB','新しいHTTP総55秒、接続3秒以内。','L04 A01 A06 A07','画面ALBのバック用Host/path ruleへ送る。同じALBの同じ先へ戻る必要はない。'),
       ('6','画面ALB → バックECS','バックrequest50秒、server keepalive120秒。','E03 E04 A09 E05 X02','deadline内で結果を永続化し、同じjobIdの二重実行を防ぐ。'),
       ('7','バックECS → Lambda → SQS削除','HTTP成功を受け、handlerが成功終了。','L03 Q07 X03','ESMによる削除前にLambdaが止まると再配信され得る。重複の実試験を行う。'),
       ('8','clientの完了確認・取消','poll2～5秒、初回完了SLO120秒、job期限1時間。','L07 X03','SLO・visibility・message retentionはそれぞれ別の時計。'),
     ],
     explanations=[
       ('整理券のたとえ','食堂で時間のかかる料理を頼んだら、受付は整理券を渡します。お客さんは受付の前でずっと電話をつなぐ必要がありません。SQSは注文箱、Lambdaは箱から注文を取る係、バックECSは調理係です。「受付できた」と「料理ができた」を別の状態として知らせます。',()),
       ('一本の長い線ではない','t=0で受付、t=1秒でjobIdを返し前半HTTP終了、t=3秒でLambda受信、t=4秒でバック要求、t=12秒で処理成功、t=13秒で画面のpollingが完了を確認する例です。キューが混雑したらt=3はもっと遅れます。ALB90秒を増やしてもキュー待ちの完了時間は短くなりません。',('S26',)),
       ('420秒の意味','注文を取った係が仕事をしている間、ほかの係からその注文を見えにくくします。その時間がvisibilityです。70秒でLambdaを止める本案ではAWS推奨6倍で420秒にします。70秒で失敗しても直ちに再受信されるとは限らず、再び見えるまで待つ場合があります。',('S21','S23')),
       ('失敗と重複','バックECSがDBへ保存した直後、応答を返す前に回線が切れると、Lambdaは成功を知りません。SQSへ戻った注文が再実行されても二重登録しないよう、jobIdと業務unique制約を使います。FIFOでも、外部のDB更新とSQS削除を一つのtransactionにはできないため、冪等化を省略しません。',('S26',)),
       ('202応答の責任','202は結果の成功を約束する番号ではなく、受付済を知らせる例です。SQS受理前に成功応答して注文を失わないことが大切です。DBに受付だけ保存できてSQS送信が失敗した場合などは、outboxや送信状態の再確認を採用すると整合を取りやすくなります。これは必要時の実装方針で、既存構成に新サービスを勝手に追加する前提ではありません。',()),
       ('バック用ルーティング','画面ALBへ戻る要求は/_internal/jobs等の専用ruleからバックtarget groupへ送る設計例です。通常画面へ戻って再びSQSへ送るループを防ぎます。Lambda→ALB→バックの認証・SG・Host/SNIも確認します。バックコンテナが同じtask内か別serviceかによって登録するportと容量が変わります。',()),
       ('job期限と運用','120秒SLOを超えたら「遅延中」と表示し、同じ注文を追加しません。1時間の業務期限を過ぎた未実行jobはexpiredとして記録します。DLQ再投入は受付期限、同じjobId、すでに済んだ処理を確認してから行います。保存14日と再実行してよい14日は別です。',('S56',)),
     ]),
dict(id='F3', sheet='05_帳票', title='イントラネットの帳票出力',
     original='AWSのクライアント → 画面呼び出し → 画面用ALB → ECS → 帳票用ALB → EC2（帳票用サーバ） → JSONデータ → ECS',
     corrected='基本案はECSがEC2へ帳票要求を送り、EC2のJSON応答を同じHTTPで受け取る。EC2がECSへJSON取得要求を出す別通信の場合は追加15秒/12秒を明示する。',
     diagram='''flowchart LR
  C["client\n帳票総90秒"] --> A["画面ALB\nidle90秒"] --> E["画面ECS\n帳票総75秒"]
  E -->|HTTP総65秒| R["帳票ALB\nidle70秒"] --> B["EC2帳票server\n業務総60秒"]
  B -->|同じHTTPのJSON応答| R --> E --> A --> C
  B -. 別HTTPのJSON取得なら総15秒 .-> D["専用ECS data endpoint\n総12秒・条件付き"]''',
     stages=[
       ('1','client → 画面ALB','帳票client90秒、画面ALB idle90秒。','C02 C03 A01','clientの90秒は総時間、ALBの90秒は無通信時間。値が同じでも時計が違う。'),
       ('2','画面ALB → 画面ECS','帳票endpoint75秒。','E02 E04 A09 E05','通常画面E01の20秒を帳票に流用しない。header deadlineを受けて残り時間で短縮。'),
       ('3','画面ECS → 帳票ALB','HTTP呼出し総65秒、connect3秒。','R01 C05 X02','readだけを65秒にして総時間無制限にならないよう外側deadlineを付ける。'),
       ('4','帳票ALB → EC2','ALB idle70秒、接続はAWS管理10秒。','A03 A06 A07 R03','EC2側keepalive100秒。接続待ちを引いた残りでEC2の60秒上限を短縮。'),
       ('5','EC2帳票処理','render request総60秒。','R02 A09 X01','帳票生成・JSON加工・応答準備を含む。無条件な再生成は重い仕事を二重化する。'),
       ('6','EC2 → ECSのJSON応答（基本案）','同じHTTP response body。新しいTCP接続なし。','R01 E02 X02','別のJSONサービス用timeoutという設定を作らない。受信サイズとJSON parse時間も総予算内。'),
       ('7','EC2 → ECSのJSON取得（条件付き）','別HTTPなら取得15秒、data endpoint12秒。','R04 R05 A01 X02','専用endpointへの追加線を描き、同じ待機中の画面処理へ再入して詰まらないようにする。'),
       ('8','ECS → clientの最終応答','前処理2秒＋呼出し65秒＋後処理3秒。','E02 C02','計70秒 < ECS75秒 < client90秒。大きいファイルの送信時間も別途実測。'),
     ],
     explanations=[
       ('工作室のたとえ','ECSの係が工作室のEC2へ「このデータをきれいな紙にして」と頼みます。紙の作成に60秒の上限があるなら、ECSの電話はそれより長い65秒、画面係全体は75秒、利用者は90秒にします。内側の係が先に「間に合いません」と答える時間を用意する設計です。',()),
       ('JSONという言葉の読み分け','JSONはデータの書き方です。「EC2 → JSON → ECS」がEC2の応答なら、往きのHTTPと同じやり取りに含まれます。一方、EC2がデータを取りにECSへ電話する意味なら新しい要求であり、接続・read・総時間・受けるECSの上限が必要です。記述だけでは決められないため、基本案と条件付き案を両方示します。',()),
       ('通常の帳票動作','t=0で画面要求、t=2でECSが帳票要求、t=3でEC2受付、t=38で生成完了、t=40でECSへJSONが戻り、t=43で画面に結果を返す例です。35秒間byteが戻らない場合でも帳票ALB70秒・画面ALB90秒なら無通信による切断を避けられます。これは動作例で性能保証ではありません。',()),
       ('別JSON取得がある場合','EC2の60秒の箱の中に、JSON取得15秒、帳票生成35秒、前後5秒を入れ、合計55秒とします。15＋60=75秒を許す形ではありません。ECS data endpoint12秒よりHTTP15秒を長くする一方、ALB共有idle90秒はこの15秒の停止条件にはなりません。',()),
       ('接続不良も考える','帳票ALBがEC2へ新規接続を作る時は最大10秒の接続待ちが別に存在します。10秒の後にEC2が60秒全部を使うとECS呼出し65秒を超えます。ECSが65秒のdeadlineを伝え、EC2が受信時点の残り時間から終了余裕を引いて60秒を短縮する必要があります。成功時の大小関係だけで保証しない理由です。',('S02',)),
       ('長い帳票をどうするか','60秒で生成できない仕様があるなら、無理にこの例へ合わせず時間予算を作り直します。画面用ALBも影響するため、帳票だけのALB変更では足りません。生成時間が大きく変動する帳票では非同期受付と保存済ファイルの取得が選択肢ですが、今回の同期経路の前提とは分けて判断します。',()),
       ('サイズと取消','JSONのサイズに上限を設け、parseが長引く場合も75秒以内へ収めます。PDF等の本体を返すなら回線速度によるdownload時間を含めて再計算します。利用者が閉じた時はrender子processを中止し、既に生成済ならjobIdで再利用することで、同じ重い生成を繰り返さずに済みます。',()),
     ]),
dict(id='F4', sheet='06_社内API', title='イントラネットのAPI',
     original='AWSのクライアント → API呼び出し → イントラネットAPI用ALB → ECS → Valkey → RDS Proxy → Aurora Serverless v2',
     corrected='API用ALBは画面用ALBと別。ECS→Valkey照会とECS→RDS Proxy→Aurora照会はhit/missによる分岐として扱う。',
     diagram='''flowchart LR
  C["社内API client\n総30秒"] --> A["社内API ALB\nidle60秒"] --> E["ECS API\n総20秒"]
  E --> V["Valkey\n総0.5秒"] -->|hit| E
  E -->|miss| P["RDS Proxy\nborrow2秒"] --> D["Aurora\nSQL5秒"]
  D --> P --> E --> A --> C''',
     stages=[
       ('1','AWS client → 社内API用ALB','総30秒、接続3秒、pool待ち1秒。','C01 C03 C04 C05 X01','社内SDKもbrowserも、明示した契約のdeadlineを持つ。'),
       ('2','社内API用ALB → ECS','ALB idle60秒、ECS20秒。','A02 A06 A07 A08 E01 E04','画面ALB90秒と異なるLBなので60秒を独立設定できる。'),
       ('3','ECS ↔ Valkey','段階総0.5秒、missでDBへ。','V01 V02 V03 V04 V05 V06 V07','read cacheを経由しない更新処理もある。ユーザー記述の線を中継と誤解しない。'),
       ('4','ECS → RDS Proxy','DB段階総12秒、borrow2秒。','D01 D02 D03 D04 D06 D07 D08','task数×pool上限×service数を把握し、DB接続を無限に増やさない。'),
       ('5','Proxy ↔ Aurora','SQL5秒、engine別のlock/transaction上限。','D05 D09 D10 D11 D12 D13 D14 D15 D16 D17 D18 D19 D20','短い同期待ちと長いbatchはrole・接続設計を分ける。'),
       ('6','clientへの結果・エラー返却','JSON全体の応答と結果不明の処理。','E01 X01 X02 X03','更新APIのtimeout後は結果照会または同じ冪等keyで再試行。'),
     ],
     explanations=[
       ('画面とAPIの違い','画面は人が見やすい形を返し、APIは別のプログラムが読めるJSONなどを返します。答えを作るECSとDBの仕組みは似ていますが、APIでは呼び出すプログラムのtimeout、retry、結果不明の扱いが大切になります。人がボタンを押し直す場合と同じように、プログラムも同じ処理を二度頼むことがあります。',()),
       ('API用ALBの独立性','社内API用ALBは画面用ALBと別のため、帳票の75秒を守る必要がなければidle60秒で十分な設計例です。API業務上限20秒とclient30秒が先に働きます。画面・APIのコードが同じserver設定を共有するなら、server keepaliveは最大ALB90秒を見た120秒でも矛盾しません。',('S01',)),
       ('社内だから無限待ちにしない','社内networkでもDBのlock、接続枯渇、deploy中の切断、DNSの更新、task停止は起こります。短い接続timeoutと総deadlineを決めるのは、悪い通信を疑うためだけでなく、待ち続けるthreadやconnectionをほかの要求へ返すためです。失敗の理由をrequestIdと一緒に返します。',()),
       ('cache更新の注意','APIがAuroraへ更新したあとcacheを消せなかった場合、古い答えを返す可能性があります。SQLのtimeoutだけではcacheの鮮度は守れません。更新と失効の順序、TTL、version番号などを既存方式に合わせ、timeoutによりどこまで済んだかを把握します。',()),
       ('計算と再試行','通常画面と同じ17.5秒の処理予算を20秒へ入れます。client30秒でもECSを20秒ずつ2回呼ぶことはできません。safe readを再試行したい時は1回目が何秒かかったかを引き、残り時間と同時処理容量がある時だけ行います。',()),
     ]),
dict(id='F5', sheet='07_公開API', title='インターネットのAPI',
     original='外部API request → Cognito M2M（CloudFront）でtoken取得 → Regional REST API Gateway → VPC Link v2 → GWLBE → GWLB → Palo Alto → 公開API用ALB → ECS → RDS Proxy → Aurora Serverless v2',
     corrected='①token取得HTTPSと②Bearer token付きAPI要求は別。VPC Link ENI↔ALBのroutingでGWLBE検査を挿入し、Palo Altoで検査後GWLB/GWLBEへ戻ってALBへ届く。',
     diagram='''flowchart LR
  C["外部client\n業務一件45秒"] -. token取得総10秒 .-> T["Cognito M2M\nAWS管理CloudFront"]
  T -. access token .-> C
  C -->|Bearer API総30秒| G["Regional REST\nBUFFERED統合25秒"] --> L["VPC Link v2 ENI"]
  L --> EP["GWLBE"] --> W["GWLB\nTCP idle350秒"] --> F["Palo Alto\nApp-ID実効idle確認"]
  F -->|検査後の戻り| W --> EP
  EP --> A["公開API ALB\nidle60秒"] --> E["ECS\n総20秒・残りで短縮"] --> P["RDS Proxy\nborrow2秒"] --> D["Aurora\nSQL5秒"]''',
     stages=[
       ('0a','外部client → Cognito/CloudFront','別HTTPS POST、token取得総10秒。','T01 T02 T03 T04','tokenを返す通信はALB/DBへ直列に通る業務requestではない。'),
       ('0b','tokenを添えた業務API request','API要求総30秒、業務一件45秒。','C03 C04 C05 C06 T05','Authorization: BearerでAPI入口へ。tokenのexp1時間とHTTP30秒は別。'),
       ('1','Regional REST API Gateway','BUFFERED integration25秒。','G01 G02 G03 G06','認証とintegrationを区別し、Gateway入口時刻でECSに残り時間を伝える。'),
       ('2','API Gateway → VPC Link v2 ENI','同一account/利用Region/AZ確認。','G04 G05','VPC Link自身へ設定する独立HTTP timeoutはない。'),
       ('3','VPC Link ENI → GWLBE','subnet routeで検査へ誘導。','N01 X02','単にGWLBEを作っただけではALB宛trafficが検査へ行く保証がない。'),
       ('4','GWLBE → GWLB → Palo Alto → GWLB → GWLBE','元packetをGENEVEで運び、検査後戻す。','N02 N03 N06 N07 N08 N09 N10','TCP flow350秒と外側GENEVE UDPを区別。App-IDごとの実効timeoutと対称routeを確認。'),
       ('5','GWLBE検査後 → 公開API用ALB','ALB idle60秒。','A04 A06 A07','Palo Altoから直接ALBへTCP proxyする前提とは限らない。packet検査の挿入構成。'),
       ('6','ALB → ECS','最大20秒。ただしGatewayの残り時間で短縮。','E01 E04 A08 E05 G06 X02','ALB接続10秒＋ECS20秒は30秒なので、固定値だけでは25秒に収まらない。'),
       ('7','ECS → RDS Proxy → Aurora','cacheなし。DB段階総12秒。','D01 D02 D03 D04 D05 D06 D07 D08 D09 D10 D11 D12 D13 D14 D15 D16 D17 D18 D19 D20','他経路と同じProxyならborrow・InitQuery等も共有。network検査の対象は実routeで判定。'),
       ('8','戻りtraffic → client','検査pathも往復で対応。','N07 X01 X02 X03','504後に更新が続く事故を試験し、取消・結果確認・冪等化を組み合わせる。'),
     ],
     explanations=[
       ('入場券と門のたとえ','最初にCognitoで機械用の入場券をもらいます。券を取る電話が終わってから、その券を見せてAPIの門へ別の電話をします。API Gatewayは券と権限を確認する門、VPC Linkは内部への通路、GWLBとPalo Altoは通路の検査係です。入場券を取る電話の待ち時間は、門の中で本を調べる時間と別です。',('S40','S44')),
       ('CognitoのCloudFront','Cognito custom domainのCloudFrontはAWSが管理します。利用者が自由にorigin timeoutを変えられる自分のdistributionと区別します。token取得clientの総10秒、token cache、再取得時期を設定します。tokenが有効なら毎回Cognitoへ取りに行く必要はありません。',('S41','S42')),
       ('検査経路を正しく読む','GWLBE→GWLB→Palo Altoは、元のIP packetを検査装置へ運ぶ部分です。検査したpacketはGWLB/GWLBE側へ戻り、その先のrouteでALBへ届きます。応答も同じ検査状態が見えるように戻します。VPC Link ENIとALBを適切なsubnetへ置くなど、実際のroute制約を満たす必要があります。図の矢印は設定完了を意味しません。',('S34','S36')),
       ('25秒と20秒の整合','健全時はbackendアプリ20秒＋network/応答余裕5秒でGateway25秒へ入れます。新規ALB target接続が10秒かかる異常時には、20秒全部は残りません。Gateway入口時刻を信頼できるheaderへ写し、入口22秒を内部予算、ECSの実行上限はmin(20, 残り−2)とする例で、取消と応答余裕を確保します。',('S02','S58','S59')),
       ('350秒を長くすれば速くなるか','GWLB350秒・Palo Alto3600秒は、黙った接続の状態をどれだけ覚えるかの時間です。SQLを速くする値ではありません。処理20秒のJSON APIなら本案でnetwork idleを長く変更する必要はありません。長時間streamやpoolを採用する時は、最短idleとprobe・接続寿命・ENIのconntrackを別に整合させます。',('S33','S35','S38')),
       ('TLS検査の前提','Palo AltoがTLSを復号しない構成では、暗号化された中身のJSON全文を検査できるとは限りません。復号する構成は証明書信頼・handshake・App-IDの待機を追加で確認します。証明書確認を無効化してtimeoutのように見えるTLSエラーを回避する方式は採用しません。',()),
       ('既定29秒を超えたい時','BUFFEREDのRegional/Private RESTでは延長申請が可能ですが、承認と統合値変更とstage deployは別作業です。request rate quotaの調整もあり得ます。本案は申請を必要としない25秒です。長い処理は非同期化かSTREAMの別設計を比較し、全機器を単純に90秒へ変更しません。',('S27','H08','S31')),
     ]),
dict(id='F6', sheet='08_SalesforceAPI', title='SalesforceのAPI',
     original='Salesforce → API request → Cognito M2M（CloudFront）でtoken取得 → Private Connect（PrivateLink） → VPC endpoint service → NLB → VPC endpoint → Private REST API Gateway → VPC Link v2 → Salesforce API用ALB → ECS → RDS Proxy → Aurora Serverless v2',
     corrected='token取得を別通信に分離。Salesforce transit VPCのconsumer endpoint → 顧客endpoint service/NLB → 顧客VPCのexecute-api endpoint ENI → Private REST → VPC Link v2 → ALBという二つのPrivateLink入口を区別する。',
     diagram='''flowchart LR
  C["Salesforce\nApex例callout30秒"] -. token取得総10秒 .-> T["Cognito M2M\nCloudFrontの公開endpoint"]
  T -. access token .-> C
  C --> SC["Private Connect\nSF側consumer endpoint"] --> ES["顧客VPC endpoint service"] --> N["NLB TCP443\nidle350秒"]
  N --> VE["顧客execute-api\ninterface endpoint ENI"] --> G["Private REST\n統合25秒"] --> L["VPC Link v2"]
  L --> A["SF API ALB\nidle60秒"] --> E["ECS\n総20秒・残りで短縮"] --> P["RDS Proxy\nborrow2秒"] --> D["Aurora\nSQL5秒"]''',
     stages=[
       ('0','Salesforce → Cognito token取得','基本案は公開HTTPSの別認証通信。','T01 T02 T03 T04 C06','Private Connectの業務経路を用意してもCognito domainへの認証通信が自動でprivateになるわけではない。'),
       ('1','Salesforce callout → Private Connect','ApexならsetTimeout30000ms。','C07 C08 C06 X01','実際の実装がApex/Flow/MuleSoftのどれか未提供なので、Apex数値は条件付き。'),
       ('2','SF transit VPC consumer endpoint → 顧客endpoint service','PrivateLinkの利用側と提供側。','N01','Salesforce側に作るendpointと、後段のexecute-api endpointは別のENI入口。Named Credentialへ接続を関連付ける。'),
       ('3','顧客endpoint service → NLB','提供serviceがNLBを公開。TCP443例。','N04 N05 N09','TLS passthroughと終端を区別。endpoint serviceにHTTP処理時間の属性はない。'),
       ('4','NLB → execute-api endpoint ENI','NLBのIP targetにinterface endpointのprivate IPを指定する構成例。','N01 N04','DNS名・Host・SNI・API ID、ENI交換時のtarget更新、health checkを確認する。'),
       ('5','execute-api endpoint → Private REST API Gateway','endpoint policyとAPI resource policy、token scope。','G01 G02 G03 G06 T05','Private APIの入口とVPC Linkで内部ALBへ出る出口を区別。'),
       ('6','Private REST → VPC Link v2','ENI経由のprivate integration。','G04 G05','Link作成APIはapigatewayv2でも業務API種別はRESTのまま。'),
       ('7','VPC Link → SF API用ALB → ECS','ALB idle60秒、ECS最大20秒。','A05 A06 A07 E01 E04 A08 E05 X02','Gateway25秒の残りを受けてECS処理を短縮。'),
       ('8','ECS → RDS Proxy → Aurora','cacheなし。DB段階12秒、SQL5秒。','D01 D02 D03 D04 D05 D06 D07 D08 D09 D10 D11 D12 D13 D14 D15 D16 D17 D18 D19 D20','共有DB/Proxyの設定は他のrouteと矛盾しない値を使う。'),
       ('9','結果 → Salesforce','token10＋API30＋余裕5=45秒例。','C06 C08 X03','同一Apex transactionのほかのcalloutを含め累積120秒制約を確認。'),
     ],
     explanations=[
       ('専用通路のたとえ','Salesforceの建物から、一般の道へ出ない専用の通路でAWSの建物へ来るのがPrivate Connectです。入口のNLBの先に、Private API Gatewayへ入るためのexecute-api入口もあります。利用側の入口と、顧客AWS側の入口を同じ「VPC endpoint」という名前だけでまとめると、設定する場所を間違えます。',('S36','S48','S51')),
       ('成立するための前提','このNLB→execute-api endpoint構成は、endpoint ENIのIPをtargetにした到達、適切なHost/API ID/SNI、TLS証明書名、API resource policy等がそろうことが前提です。NLB DNS名へHTTPSを向けるだけでPrivate APIが呼べると保証するものではありません。実環境設定が未提供なので、到達可能性は検証項目として明示します。',('S51',)),
       ('HTTPを理解しないNLB','TCP passthroughのNLBはHTTPのHost headerを書き替える案内係ではありません。Salesforceの呼出しURLと証明書名が整合する必要があります。対応するPrivate API custom domainを使う設計、正しいHost/x-apigw-api-idを渡す設計、必要ならL7 proxyを置く設計を比較します。本案の数値は追加proxyを置かない場合です。',('S35','S51')),
       ('Private Connectの状態','Salesforce側の接続をprovisionし、必要なら顧客側でendpoint接続をacceptしてReady状態を確認します。接続確立にかかる数分は管理操作の時間で、毎回の業務callout30秒と別です。Named Credentialが正しいOutbound Network Connectionを使っていることも確認します。',('S48',)),
       ('Apexの既定10秒の落とし穴','APIが20秒以内の仕様でもApexを既定10秒のままにすると、10秒でSalesforceが諦めることがあります。本案のApex例は30000msです。ただし同じtransactionでtoken取得・ほかのAPI・retryが増えると累積120秒に達し得ます。setTimeoutを120000へ上げるだけでは、Private REST統合25秒を延長できません。',('S49','S50')),
       ('認証もprivateにしたい場合','元のCognito domain/CloudFront経路は公開HTTPSとして扱います。2026年のGetClientTokenはdomain不要でPrivateLink対応の追加選択肢ですが、Salesforce Named CredentialがそのAPIをそのまま実行できるとは確認していません。別の認証実装・専用endpoint service等の要否を検証してから選ぶ条件付きの別案です。',('H12','S45')),
       ('想定する失敗','誤ったHostなら403等、SGやNLB targetの誤りなら接続失敗、長いbackendならGateway504など、同じ「呼べない」に複数の原因があります。timeoutを広げる前にSF requestId、NLB target状態、Private REST access log、ECS requestIdを突き合わせ、到達していない段階と処理が遅い段階を分けます。',()),
     ]),
]
