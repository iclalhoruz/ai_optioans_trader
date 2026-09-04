# chaos-sandbox (:8003)

Tek bacaklı long opsiyonları ve net-debit çok bacaklı opsiyon spread'lerini üç sabit senaryoyla yeniden fiyatlayan
deterministik FastAPI servisi. LLM, E2B, dinamik kod üretimi, kod çalıştırma,
piyasa verisi indirme veya harici finans kütüphanesi kullanmaz. Çalışırken Redis,
broker, internet veya başka bir servise ihtiyaç duymaz. HTTP/validasyon altyapısı
FastAPI, Pydantic, pydantic-settings ve Uvicorn'dan oluşur.

Bu **tam bir piyasa risk modeli değildir**. `is_safe`, yalnızca yapılandırılmış
bu üç senaryoda kaybın eşiği aşmadığını belirtir; işlem veya kâr garantisi değildir.

## API ve işlem tipleri

- `GET /health` → `200 {"status":"ok","service":"chaos-sandbox"}`.
- `POST /stress-test`: doğrudan `contracts.schemas.TradeProposal` alır;
  `contracts.schemas.ChaosTestResult` döndürür. Envelope kullanılmaz.
- `BUY`: tek long call/put veya `order_details.legs` içeren net-debit spread için hesaplama yapar.
- `HOLD`: `order_details` içeriğini doğrulamadan güvenli ve `0.0` skorla döner.
  Tek log tam olarak `HOLD: no position will be opened; stress testing skipped` olur.
- `SELL`: kapanış/satış ayrımı veya short margin modeli olmadığı için tüm SELL
  teklifleri hesaplama ve `order_details` doğrulaması yapılmadan `200`,
  `is_safe=false`, `stress_score=1.0` ve açıklayıcı `VETO` loguyla döner.
- `generated_code` ortak kontrat gereği zorunludur; `""` gönderin. Değeri hiçbir
  zaman çalıştırılmaz, diğer teklif alanlarıyla birlikte aynen geri verilir.
- `refined_proposal` miktar, fiyat, metadata ve içerik bakımından değiştirilmez;
  yerel doğrulamanın varsayılanları bile bu alana eklenmez.
- `net_delta`, spread bacaklarından hesaplanan güncel portföy delta'sını hisse
  eşdeğeri olarak taşır. Örneğin `85.0`, dayanak varlıktan 85 hisse long
  taşımaya yakın fiyat duyarlılığı demektir. Tek bacak, HOLD ve üst seviye SELL
  sonuçlarında bu alan `null` kalır.

`legs` bulunmayan BUY teklifi mevcut tek-bacak modeline, `legs` bulunan teklif
spread modeline yönlendirilir. Net-credit spread'ler ile closing/rolling
bacakları geçerli bir risk sonucu olarak fail-closed veto edilir.

Geçersiz BUY verisi alan bazlı `422` döndürür; örneğin eksik strike:

```json
{"detail":[{"type":"missing","loc":["body","order_details","strike"],"msg":"Field required"}]}
```

Beklenmeyen hesaplama hataları (örneğin temsil edilemeyecek kadar büyük parasal
değerler) sunucu loguna yazılır ve `500 {"detail":"Stress calculation failed"}`
döner. Böyle bir hata güvenli sonuç üretmez; stack trace yanıta eklenmez.

## AI Strategy için kesin order_details sözleşmesi

Alanlar JSON sayısı olarak gönderilmeli; sayısal string ve boolean kabul edilmez.
Tamsayı alanlarına kesirli sayı gönderilmez. Tüm sayılar sonlu olmalıdır.
Tanımlanmayan ekstra alanlar da reddedilir.

| Alan | Kural | Zorunlu / varsayılan |
|---|---|---|
| `option_type` | `"call"` veya `"put"` | Zorunlu |
| `quantity` | Pozitif tamsayı | Zorunlu |
| `limit_price` | Pozitif; bir underlying birimi başına prim | Zorunlu |
| `spot_price` | Pozitif | Zorunlu |
| `strike` | Pozitif | Zorunlu |
| `implied_volatility` | `0 < IV <= 5`; yıllık ondalık oran (`0.27 = %27`) | Zorunlu |
| `days_to_expiry` | Negatif olmayan tamsayı; takvim günü | Zorunlu |
| `bid` | Negatif olmayan, primle aynı birimde | Zorunlu |
| `ask` | Pozitif ve `ask >= bid` | Zorunlu |
| `risk_free_rate` | Sonlu; yıllık sürekli bileşik ondalık oran | `0.04` |
| `contract_multiplier` | Pozitif tamsayı | `100` |
| `option_symbol` | String veya null; metadata | `null` |
| `delta` | Sonlu sayı veya null; hesaplamada kullanılmaz | `null` |

### Multi-leg spread order_details

Spread teklifi üst seviyede `direction` (`bullish`/`bearish`), pozitif tamsayı
`quantity`, sıfır olmayan net `limit_price`, pozitif `spot_price`, 2–4 elemanlı
`legs` listesi ve isteğe bağlı `strategy_type`, `risk_free_rate` (`0.04`),
`contract_multiplier` (`100`), `time_in_force` (`day`) taşır. Pozitif
`limit_price` net debit, negatif değer net credit anlamındadır; bu sürüm yalnızca
pozitif net debit'i hesaplar.

Her leg aşağıdaki alanları taşır:

| Alan | Kural |
|---|---|
| `symbol` veya `option_symbol` | Opsiyon kontrat sembolü |
| `option_type` | `call` veya `put` |
| `strike` | Pozitif |
| `implied_volatility` | `0 < IV <= 5` |
| `days_to_expiry` | Negatif olmayan tamsayı |
| `bid`, `ask` | `bid >= 0`, `ask > 0`, `ask >= bid` |
| `ratio_qty` | Pozitif tamsayı; varsayılan `1` |
| `side` | `buy` veya `sell` |
| `position_intent` | `buy_to_open`, `sell_to_open`, `buy_to_close`, `sell_to_close` |

`side`, `position_intent` ile aynı yönde olmalıdır. Kontrat sembolü OCC biçiminde
olmalı; semboldeki underlying/type/strike, teklif alanlarıyla eşleşmelidir.
Chaos fiyatlaması için IV/vade/bid/ask değerleri kontrat sembolünden varsayılmaz.
Hesaplanacak net-debit opening spread'lerin bacakları aynı vadeyi taşımalı ve
vade sonu payoff'u negatif veya yukarı yönde sınırsız zararlı olmamalıdır.

Üst seviye `TradeProposal` ayrıca `strategy_id`, `action`, `symbol`,
`generated_code`, `conviction_score` alanlarını gerektirir. Eksik piyasa verisi
üst seviye alanlardan veya başka servislerden türetilmez.

## Senaryolar ve skor

Vade `T = days_to_expiry / 365` olarak hesaplanır. Call ve put fiyatları
`math.erf` ile normal dağılım CDF'si kullanan Black–Scholes formülünden gelir.
Vade sıfırsa intrinsic value, `volatility * sqrt(T) <= 1e-12` ise iskonto edilmiş
deterministik payoff kullanılır. Negatif opsiyon/çıkış değeri üretilmez.

Her senaryo aynı orijinal girdiden başlar; şoklar birleştirilmez, zaman ilerlemez:

1. **SPREAD_SHOCK:** `spread = ask - bid`, `stressed_spread = spread * 6`.
   `%500 artış` mevcut spread'in altı katıdır.
   `exit_price = max(0, baseline_theoretical_price - stressed_spread / 2)`.
   Sıfır spread kabul edilir.
2. **IV_CRUSH:** `IV_stressed = IV * 0.20`; diğer fiyatlama girdileri aynı kalır.
   `exit_price = BlackScholes(IV_stressed)`.
3. **ADVERSE_MOVE:** long call için `spot_stressed = spot * 0.90`, long put için
   `spot_stressed = spot * 1.10`; diğer fiyatlama girdileri aynı kalır.
   `exit_price = BlackScholes(spot_stressed)`.

Spread tekliflerinde aynı şok her bacağın kendi strike, IV, vade ve kotasyonuna
ayrı uygulanır. Bir buy leg pozisyon değerine pozitif, sell leg negatif katkı
yapar. Spread şokunda buy leg teorik fiyat eksi yarım stresli spread'den
satılıyor; sell leg teorik fiyat artı yarım stresli spread maliyetiyle geri
alınıyor. IV ve adverse-move senaryolarında her bacağın stresli teorik değeri
işareti ve `ratio_qty` ile netleştirilir.

Spread'in güncel net delta'sı senaryo şoklarından önce, aynı Black–Scholes
girdileriyle her bacak için ayrı hesaplanır. Buy bacak deltası pozitif, sell
bacak deltası negatif işaretle ve `ratio_qty` ile toplanır; ardından üst seviye
`quantity` ve `contract_multiplier` ile çarpılır:

```text
net_delta = sum(side_sign * ratio_qty * leg_delta)
            * quantity * contract_multiplier
```

Bu değer, stres skoru SAFE veya VETO üretse de geçerli spread sonuçlarında
`ChaosTestResult.net_delta` alanına yazılır. Net-credit, closing/rolling veya
underlying eşleşmezliği nedeniyle fail-closed VETO edilen, ancak şema açısından
geçerli spread'lerde de delta hesaplanır. Spread girdisinden hazır delta kabul
edilmez; her bacak strike, IV ve vadesinden yeniden hesaplanır.

IV ve fiyat şoklarında çıkış fiyatı teorik değerdir; ilave spread kesintisi
uygulanmaz. Bu tercih her şokun etkisini ayrı ölçer. Spread senaryosunda merkez,
kotasyon midpoint'i yerine istenen formüldeki teorik fiyattır.

```text
entry_total = limit_price * quantity * contract_multiplier
exit_total  = exit_price * quantity * contract_multiplier
pnl         = exit_total - entry_total
loss_pct    = max(0, (entry_total - exit_total) / entry_total)
stress_score = min(1, max(scenario.loss_pct for scenario in scenarios))
is_safe      = stress_score <= max_stress_loss_pct
```

Net-debit spread için de aynı karar formülü kullanılır:

```text
entry_total = positive_net_debit * quantity * contract_multiplier
net_exit_price = sum(position_sign * leg_exit_price * ratio_qty)
exit_total = net_exit_price * quantity * contract_multiplier
pnl = exit_total - entry_total
loss_pct = max(0, (entry_total - exit_total) / entry_total)
```

Skor ortalama kayıp değil, en kötü kayıptır. Eşiğe eşit kayıp güvenlidir.
Hesaplarda erken yuvarlama yapılmaz; yalnızca frontend logları yuvarlanır.
Her senaryonun girdileri, teorik/çıkış fiyatı, giriş/çıkış tutarı, PnL ve kaybı
`logs` alanındadır. Son log `SAFE` veya `VETO` kararını açıklar (HOLD özel durumu hariç).

## Konfigürasyon

| Environment variable | Varsayılan | Geçerli aralık |
|---|---|---|
| `CHAOS_MAX_STRESS_LOSS_PCT` | `0.35` | `[0, 1]` |
| `CHAOS_ADVERSE_PRICE_MOVE_PCT` | `0.10` | `[0, 1]` |
| `CHAOS_SPREAD_WIDENING_MULTIPLIER` | `6.0` | Sonlu, `>= 1` |

IV azalma katsayısı sabit `0.20`'dir. Ayarlar pydantic-settings ile uygulama
oluşturulurken okunur ve değiştirilemez. Geçersiz ortam değeri servisin
başlamasını engeller; değişiklikler restart gerektirir. Yerelde ortam
değişkenlerini `export` edin. Servis kendi başına `.env` dosyası okumaz;
mevcut Compose yapılandırması kök `.env` dosyasını container ortamına aktarır.

## Lokal çalıştırma ve test

Komutlar repo kökünden, Python 3.11+ ile:

```bash
python -m venv services/chaos-sandbox/.venv
source services/chaos-sandbox/.venv/bin/activate
python -m pip install -r services/chaos-sandbox/requirements-dev.txt
export PYTHONPATH="$PWD:$PWD/services/chaos-sandbox"
uvicorn chaos_sandbox.main:app --host 0.0.0.0 --port 8003
```

Aktif sanal ortamda test:

```bash
python -m pytest services/chaos-sandbox/tests -q
```

Testler fiyat referanslarını, bağımsız şokları, PnL/score hesaplarını, eşik
sınırlarını, tek ve çok bacaklı input doğrulamasını, HOLD/SELL davranışını, deterministik
cevapları, hata yalıtımını ve ortak kontratı gerçek harici servise bağlanmadan test eder.
Test paketleri `requirements-dev.txt` içindedir; production image'a kurulmaz.

## Docker

Repo köklü build context, mevcut Compose ile uyumludur:

```bash
docker compose build chaos-sandbox
docker compose up -d --no-deps chaos-sandbox
curl --fail-with-body http://localhost:8003/health
```

Image Python slim kullanır, root olmayan `chaos` kullanıcısıyla çalışır;
`contracts` ve `chaos_sandbox` paketleri `/app` altındadır. Image yalnızca gerekli
Python dosyalarını ve runtime bağımlılıklarını içerir. Dockerfile'a özel ignore
dosyası `.env`, frontend ve sanal ortamın build context'e alınmasını engeller.
Healthcheck container'ın kendi `/health` endpoint'ini denetler.

## Örnek istekler ve cevaplar

Bu örnekler sentetiktir, canlı piyasa verisi değildir. Varsayılan ayarlarla:

```bash
curl --fail-with-body http://localhost:8003/stress-test \
  -H 'Content-Type: application/json' \
  --data-binary @services/chaos-sandbox/examples/buy.json

curl --fail-with-body http://localhost:8003/stress-test \
  -H 'Content-Type: application/json' \
  --data-binary @services/chaos-sandbox/examples/buy-safe.json

curl --fail-with-body http://localhost:8003/stress-test \
  -H 'Content-Type: application/json' \
  --data-binary @services/chaos-sandbox/examples/spread-buy.json
```

- [BUY isteği](examples/buy.json) → HTTP `200`, `is_safe=false`;
  [tam veto cevabı](examples/veto-response.json).
- [Güvenli BUY isteği](examples/buy-safe.json) → HTTP `200`, `is_safe=true`;
  [tam başarılı cevap](examples/safe-response.json).
- [İki bacaklı call debit spread isteği](examples/spread-buy.json) → her leg
  ayrı fiyatlanır, net spread kaybı üzerinden `SAFE` veya `VETO` kararı verilir.

Her cevapta orijinal teklif tamamen `refined_proposal` içine alınır. Yanıtı
ortak kontratla kontrol etmek için çıktıyı bir dosyaya kaydedip
`ChaosTestResult.model_validate_json(...)` kullanabilirsiniz; API testleri aynı
doğrulamayı `ChaosTestResult.model_validate(response.json())` ile yapar.

## Sınırlamalar ve entegrasyon

- Model Avrupa tipi, temettüsüz opsiyon fiyatlaması varsayar. Amerikan tipi erken
  kullanım/assignment, temettü, IV smile/skew, likidite derinliği, slippage,
  komisyon, kur, jump risk ve portföy korelasyonları modellenmez.
- Sayılar aynı para biriminde varsayılır; loglarda `$` gösterilir. Pozitif
  tamsayı multiplier ve miktar tek bacaklı long pozisyonu ölçekler.
- Tek bacaklı eski `OptionStressInputs.delta` alanı yalnızca metadata olarak
  korunur ve sonuç üretiminde kullanılmaz. Spread girdisinde delta alanı yoktur;
  `net_delta` servis tarafından fiyatlama girdilerinden hesaplanır. `option_symbol`
  da metadata olarak korunur. Sembolün strike,
  tür veya tarih alanlarıyla tutarlılığı ve kotasyon güncelliği doğrulanmaz.
  Verilen `days_to_expiry` kullanılır; sistem saati hesaplamaya katılmaz.
- Net-debit BUY spread içinde `sell_to_open` leg desteklenir. Net-credit,
  closing/rolling spread ve üst seviye SELL işlemleri, gerekli margin veya mevcut
  pozisyon maliyet modeli bulunmadığı için fail-closed veto edilir.
- `direction`, adverse spot şokunun yönünü belirler; yönsüz stratejiler bu
  sürümde desteklenmez. Vade sonu payoff'unun sınırlı olduğu doğrulanır; güvenlik
  skoru ise tüm olası piyasa yolları yerine yapılandırılmış üç sabit senaryoyu ölçer.
- Çok uç ama sonlu girdiler kayan nokta kapasitesini aşarsa HTTP `500` döner;
  risk/execution katmanı hata veya `is_safe=false` sonucunda ilerlememelidir.
- Kök `test_pipeline.py` şu anda mock transport kullanır ve örnek teklifi bu
  servisin zorunlu alanlarını eksik bırakır. Gerçek entegrasyonda AI Strategy
  yukarıdaki dokuz zorunlu `order_details` alanını sağlamalıdır.
- Mevcut workflow yürütmeyi risk servisinin `is_approved` alanına göre durdurur;
  risk servisi chaos veto kararını korumalıdır. HOLD da emir açmamalıdır.
- Frontend'in survival yüzdesi `(1 - stress_score) * 100` olmalıdır.
  Ortak kontratlar, diğer servisler, workflow ve frontend değiştirilmemiştir.

Validasyon davranışı için kullanılan resmi kaynaklar:
[Pydantic strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/) ve
[FastAPI validation errors](https://fastapi.tiangolo.com/tutorial/handling-errors/).
