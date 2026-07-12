// Built-in documentation: every feature, metric formula, chart and workflow.
import { useState } from 'react';
import { useLang } from '../i18n';

const H = [
  {
    title: { en: '1 · Getting around', fa: '۱ · آشنایی با بخش‌ها' },
    items: [
      { term: { en: 'Markets', fa: 'بازارها' },
        body: { en: 'The main overview — every asset ranked by 24h volume with price, 1H/24H/7D change, Iran premium, tightest spread, liquidity score, volume, best venue to buy/sell, and a 7-day sparkline. Click any row to open the full Market Detail view.',
                fa: 'نمای اصلی — همه دارایی‌ها بر اساس حجم ۲۴ ساعته رتبه‌بندی شده‌اند: قیمت، تغییرات ۱س/۲۴س/۷روز، پرمیوم ایران، کمترین اسپرد، امتیاز نقدشوندگی، حجم، بهترین صرافی خرید/فروش و نمودار کوچک ۷ روزه. روی هر ردیف کلیک کنید تا جزئیات کامل بازار باز شود.' } },
      { term: { en: 'Market Detail', fa: 'جزئیات بازار' },
        body: { en: 'One asset in depth: candlestick chart (1H–1M ranges, per-exchange or composite), full exchange comparison table, order-book depth chart, and the fee-adjusted arbitrage ladder.',
                fa: 'یک دارایی به‌صورت عمیق: نمودار شمعی (بازه‌های ۱ساعت تا ۱ماه، به تفکیک صرافی یا شاخص ترکیبی)، جدول کامل مقایسه صرافی‌ها، نمودار عمق دفتر سفارشات و جدول آربیتراژ با احتساب کارمزد.' } },
      { term: { en: 'Analytics', fa: 'تحلیل‌ها' },
        body: { en: 'Deep statistics for one asset: spread stats per venue over a chosen window, spread history chart, liquidity distribution with bid/ask imbalance, premium history, and the anomaly log.',
                fa: 'آمار عمیق یک دارایی: آمار اسپرد هر صرافی در بازه انتخابی، نمودار تاریخچه اسپرد، توزیع نقدشوندگی با عدم توازن خرید/فروش، تاریخچه پرمیوم و گزارش ناهنجاری‌ها.' } },
      { term: { en: 'Dealing Desk', fa: 'میز معاملات' },
        body: { en: 'The risk/opportunity cockpit: live arbitrage scanner, largest movers, widest spreads, liquidity warnings, the alert feed, and the alert-rule manager.',
                fa: 'کابین ریسک و فرصت: اسکنر زنده آربیتراژ، بیشترین تحرک‌ها، بازترین اسپردها، هشدارهای نقدشوندگی، جریان هشدارها و مدیریت قوانین هشدار.' } },
      { term: { en: 'Calendar & News', fa: 'تقویم و اخبار' },
        body: { en: 'Macro events (Forex Factory feed) with forecasts, actuals, surprise scoring and history — plus a filtered crypto/macro news feed. All times are Iran time.',
                fa: 'رویدادهای کلان اقتصادی (فید فارکس‌فکتوری) با پیش‌بینی، مقدار واقعی، امتیاز غافلگیری و تاریخچه — به‌علاوه فید اخبار کریپتو/کلان. همه زمان‌ها به وقت ایران است.' } },
      { term: { en: 'Admin', fa: 'مدیریت' },
        body: { en: 'Runtime configuration: poll intervals, adding trading pairs, and adding whole new exchanges with a JSON spec — no restart or rebuild needed.',
                fa: 'پیکربندی در زمان اجرا: بازه‌های دریافت داده، افزودن جفت‌ارز و افزودن صرافی جدید با یک JSON — بدون نیاز به ری‌استارت یا بیلد مجدد.' } },
    ],
  },
  {
    title: { en: '2 · Core metrics — how everything is calculated', fa: '۲ · شاخص‌های اصلی — نحوه محاسبه' },
    items: [
      { term: { en: 'Mid price', fa: 'قیمت میانی' },
        code: 'mid = (best bid + best ask) / 2',
        body: { en: 'The midpoint of the best buy and sell orders on one exchange — the fairest single number for “the price” on that venue.',
                fa: 'میانگین بهترین سفارش خرید و فروش در یک صرافی — منصفانه‌ترین عدد برای «قیمت» در آن صرافی.' } },
      { term: { en: 'Composite index', fa: 'شاخص ترکیبی' },
        code: 'composite = average of mids across live exchanges',
        body: { en: 'The cross-exchange average mid. Used for the main price, changes, sparklines and composite candles. Offline venues are excluded.',
                fa: 'میانگین قیمت میانی بین صرافی‌های فعال. برای قیمت اصلی، تغییرات، نمودارهای کوچک و کندل‌های ترکیبی استفاده می‌شود. صرافی‌های قطع حذف می‌شوند.' } },
      { term: { en: 'Spread & Spread %', fa: 'اسپرد و درصد اسپرد' },
        code: 'spread = ask − bid    spread % = spread / ask × 100',
        body: { en: 'The gap between buying and selling instantly. It is your round-trip cost: e.g. 0.40% spread means buying and immediately selling loses 0.40% before fees. Tighter = cheaper execution.',
                fa: 'فاصله بین خرید و فروش آنی. این هزینه رفت‌وبرگشت شماست: اسپرد ۰.۴٪ یعنی خرید و فروش فوری ۰.۴٪ ضرر قبل از کارمزد. اسپرد کمتر = اجرای ارزان‌تر.' } },
      { term: { en: '1h spread stats (μ, min–max, σ)', fa: 'آمار اسپرد ۱ ساعته (μ، کمینه–بیشینه، σ)' },
        body: { en: 'Rolling statistics of a venue\'s spread over the last hour: μ = average, the range = min to max, σ = volatility. Current spread far above μ = venue is unusually wide right now; high σ = market makers keep pulling quotes (unstable execution).',
                fa: 'آمار متحرک اسپرد صرافی در یک ساعت گذشته: μ میانگین، بازه کمینه تا بیشینه و σ نوسان. اسپرد فعلی بسیار بالاتر از μ یعنی صرافی الان غیرعادی باز است؛ σ بالا یعنی بازارساز مدام سفارش‌ها را برمی‌دارد (اجرای ناپایدار).' } },
      { term: { en: 'Liquidity score (0–100)', fa: 'امتیاز نقدشوندگی (۰–۱۰۰)' },
        code: 'score = 50% depth (log-scaled vs best venue) + 35% spread tightness + 15% freshness',
        body: { en: 'How easily you can trade on each venue right now, relative to the best venue for that asset. ~90 = deep book, tight spread, live feed. ~30 = thin book or wide spread — market orders will slip.',
                fa: 'اینکه همین حالا چقدر راحت می‌توان در هر صرافی معامله کرد، نسبت به بهترین صرافی آن دارایی. حدود ۹۰ = دفتر عمیق، اسپرد تنگ، فید زنده. حدود ۳۰ = دفتر کم‌عمق یا اسپرد باز — سفارش بازار لغزش قیمت خواهد داشت.' } },
      { term: { en: 'Depth & imbalance', fa: 'عمق و عدم توازن' },
        code: 'imbalance = (bid depth − ask depth) / total depth',
        body: { en: 'Depth = total Toman value resting in the top 20 levels of the book. Imbalance ranges −100%…+100%: +40% means far more buy orders than sells (short-term buy pressure); strongly negative = sell-heavy book.',
                fa: 'عمق = مجموع ارزش تومانی سفارشات در ۲۰ سطح اول دفتر. عدم توازن بین ‎−۱۰۰٪ تا +۱۰۰٪: +۴۰٪ یعنی سفارش خرید بسیار بیشتر از فروش (فشار خرید کوتاه‌مدت)؛ منفی شدید = دفتر پر از فروشنده.' } },
      { term: { en: 'Iran premium', fa: 'پرمیوم ایران' },
        code: 'premium % = (asset_TMN ÷ USDT_TMN) ÷ asset_USD_global − 1',
        body: { en: 'How much more crypto costs locally vs the world price. Example: BTC at 12.4B TMN with USDT at 110,000 TMN implies $112,700; if global BTC is $108,000, premium = +4.3%. High premium = local demand/capital-flight pressure; negative = local sell pressure.',
                fa: 'اینکه کریپتو در داخل چقدر گران‌تر از قیمت جهانی است. مثال: بیت‌کوین ۱۲.۴ میلیارد تومان و تتر ۱۱۰,۰۰۰ تومان یعنی قیمت ضمنی ۱۱۲,۷۰۰ دلار؛ اگر قیمت جهانی ۱۰۸,۰۰۰ دلار باشد، پرمیوم = +۴.۳٪. پرمیوم بالا = تقاضای داخلی/خروج سرمایه؛ منفی = فشار فروش داخلی.' } },
      { term: { en: '1H / 24H / 7D change', fa: 'تغییرات ۱ساعت / ۲۴ساعت / ۷روز' },
        body: { en: 'Percent change of the composite index vs 1 hour, 24 hours and 7 days ago. Short windows come from in-memory data; 7D uses stored snapshots — so on a fresh install 7D fills in after a week of collection.',
                fa: 'درصد تغییر شاخص ترکیبی نسبت به ۱ ساعت، ۲۴ ساعت و ۷ روز قبل. بازه‌های کوتاه از حافظه و ۷ روز از اسنپ‌شات‌های ذخیره‌شده — پس در نصب تازه، ستون ۷روز پس از یک هفته پر می‌شود.' } },
      { term: { en: 'Volume (24h)', fa: 'حجم (۲۴ ساعته)' },
        body: { en: 'Toman value traded in the last 24 hours as reported by each exchange; the overview shows the sum across venues. Market ranking is by total volume.',
                fa: 'ارزش تومانی معاملات ۲۴ ساعت اخیر به گزارش هر صرافی؛ صفحه بازارها مجموع همه صرافی‌ها را نشان می‌دهد. رتبه‌بندی بازار بر اساس همین حجم کل است.' } },
    ],
  },
  {
    title: { en: '3 · Arbitrage', fa: '۳ · آربیتراژ' },
    items: [
      { term: { en: 'Gross vs Net', fa: 'ناخالص و خالص' },
        code: 'gross % = (sell bid − buy ask) / buy ask\nnet % = profit after taker fees on BOTH legs',
        body: { en: 'Gross is the raw price gap between the cheapest ask on one venue and the highest bid on another. Net subtracts both taker fees (configured per exchange). Only positive NET rows are real opportunities — a 0.4% gross edge dies under two 0.25% fees.',
                fa: 'ناخالص فاصله خام قیمت بین ارزان‌ترین فروشنده در یک صرافی و بالاترین خریدار در صرافی دیگر است. خالص، کارمزد تیکر هر دو سمت را کم می‌کند. فقط ردیف‌های خالصِ مثبت فرصت واقعی‌اند — لبه ۰.۴٪ ناخالص با دو کارمزد ۰.۲۵٪ از بین می‌رود.' } },
      { term: { en: 'Max size & Est. profit', fa: 'حداکثر حجم و سود تقریبی' },
        body: { en: 'The engine walks both order books level-by-level and accumulates quantity while the fee-adjusted buy price stays below the fee-adjusted sell price. Max Size is the executable amount before the edge closes; Est. Profit is the Toman profit for that size. Note: transfer time between exchanges and withdrawal fees are NOT included.',
                fa: 'موتور، هر دو دفتر سفارش را سطح‌به‌سطح پیمایش می‌کند و تا وقتی قیمت خرید (با کارمزد) زیر قیمت فروش (با کارمزد) بماند حجم جمع می‌زند. حداکثر حجم یعنی مقدار قابل اجرا قبل از بسته شدن لبه؛ سود تقریبی سود تومانی همان حجم است. توجه: زمان انتقال بین صرافی‌ها و کارمزد برداشت لحاظ نشده است.' } },
      { term: { en: 'Example', fa: 'مثال' },
        body: { en: 'Buy BTC on Exir at 12.380B ask, sell on Ramzinex at 12.435B bid → gross 0.44%. With 0.20% + 0.35% taker fees, net ≈ −0.11% → NOT an opportunity. The scanner does this math for every venue pair automatically.',
                fa: 'خرید بیت‌کوین در اکسیر با قیمت ۱۲.۳۸۰ میلیارد و فروش در رمزینکس با ۱۲.۴۳۵ میلیارد → ناخالص ۰.۴۴٪. با کارمزدهای ۰.۲۰٪ و ۰.۳۵٪، خالص ≈ ‎−۰.۱۱٪ → فرصت نیست. اسکنر این محاسبه را برای همه جفت‌صرافی‌ها خودکار انجام می‌دهد.' } },
    ],
  },
  {
    title: { en: '4 · Charts', fa: '۴ · نمودارها' },
    items: [
      { term: { en: 'Candlestick chart', fa: 'نمودار شمعی' },
        body: { en: 'OHLC candles with volume bars. Ranges: 1H (1-min candles), 4H (5-min), 1D (15-min), 1W (1-hour), 1M (4-hour). Source selector switches between the composite index and individual exchanges. Native exchange klines are used where available (Nobitex, Wallex, Exir); other venues use candles built from live mid prices.',
                fa: 'کندل‌های OHLC با حجم. بازه‌ها: ۱ساعت (کندل ۱ دقیقه)، ۴ساعت (۵ دقیقه)، ۱روز (۱۵ دقیقه)، ۱هفته (۱ ساعت)، ۱ماه (۴ ساعت). انتخاب منبع بین شاخص ترکیبی و تک‌تک صرافی‌ها. برای نوبیتکس، والکس و اکسیر کندل رسمی صرافی و برای بقیه کندل ساخته‌شده از قیمت میانی زنده استفاده می‌شود.' } },
      { term: { en: 'Depth chart', fa: 'نمودار عمق' },
        body: { en: 'Cumulative order-book value around the mid price — green wall = resting buys, red wall = resting sells. A tall green wall close to mid means strong support; a lopsided chart matches the imbalance metric.',
                fa: 'ارزش تجمعی دفتر سفارش حول قیمت میانی — دیوار سبز = خریدهای در انتظار، دیوار قرمز = فروش‌ها. دیوار سبز بلند نزدیک قیمت یعنی حمایت قوی؛ نمودار نامتقارن با شاخص عدم توازن هم‌خوانی دارد.' } },
      { term: { en: 'Spread history', fa: 'تاریخچه اسپرد' },
        body: { en: 'Each venue\'s spread % over time (one colored line per exchange, from 5-minute snapshots). Spikes = liquidity events; all venues widening together = market-wide stress.',
                fa: 'درصد اسپرد هر صرافی در طول زمان (هر صرافی یک خط رنگی، از اسنپ‌شات‌های ۵ دقیقه‌ای). جهش = رویداد نقدشوندگی؛ باز شدن هم‌زمان همه صرافی‌ها = تنش کل بازار.' } },
      { term: { en: 'Sparkline', fa: 'نمودار کوچک' },
        body: { en: 'The tiny 7-day line on the Markets page — green if the asset is up over the window, red if down.',
                fa: 'خط کوچک ۷ روزه در صفحه بازارها — سبز اگر دارایی در این بازه رشد کرده و قرمز اگر افت.' } },
    ],
  },
  {
    title: { en: '5 · Alerts & anomaly detection', fa: '۵ · هشدارها و تشخیص ناهنجاری' },
    items: [
      { term: { en: 'Rule types', fa: 'انواع قوانین' },
        body: { en: 'spread_above (venue spread exceeds X%), arb_net_above (net arbitrage exceeds X%), deviation_above (a venue strays X% from the cross-exchange median), liquidity_drop (depth falls X% below its window average), change_above (composite moves X% within the window), premium_above / premium_below (Iran premium thresholds), calendar_high_impact (HIGH-impact event within X minutes). Rules can be scoped to one asset and/or one exchange; empty = all.',
                fa: 'spread_above (اسپرد صرافی از X٪ بیشتر شود)، arb_net_above (آربیتراژ خالص از X٪ بیشتر شود)، deviation_above (انحراف صرافی از میانه بین‌صرافی‌ها بیش از X٪)، liquidity_drop (افت عمق بیش از X٪ نسبت به میانگین بازه)، change_above (حرکت شاخص بیش از X٪ در بازه)، premium_above / premium_below (آستانه پرمیوم)، calendar_high_impact (رویداد پرتاثیر تا X دقیقه دیگر). قوانین را می‌توان به یک دارایی و/یا صرافی محدود کرد؛ خالی = همه.' } },
      { term: { en: 'Window & cooldown', fa: 'بازه و فاصله تکرار' },
        body: { en: 'Window = the lookback used by the rule (e.g. liquidity vs its 1h average). Cooldown = minimum seconds before the same rule can fire again, so one condition doesn\'t spam the feed. Fired alerts appear as toasts, in the Desk feed, and persist to the database.',
                fa: 'بازه = پنجره زمانی محاسبه قانون (مثلاً نقدشوندگی نسبت به میانگین ۱ ساعته). فاصله تکرار = حداقل ثانیه تا فعال شدن دوباره همان قانون تا فید اسپم نشود. هشدارها به‌صورت اعلان، در فید میز معاملات و در پایگاه داده ثبت می‌شوند.' } },
      { term: { en: 'Automatic anomalies', fa: 'ناهنجاری‌های خودکار' },
        body: { en: 'Independent of your rules, the engine always flags: price deviation ≥1.5% (warning) / ≥3% (critical) vs the median, feeds stale >30s, and depth down ≥50% vs its 1-hour average.',
                fa: 'مستقل از قوانین شما، موتور همیشه این‌ها را علامت می‌زند: انحراف قیمت ≥۱.۵٪ (هشدار) / ≥۳٪ (بحرانی) نسبت به میانه، فید قدیمی‌تر از ۳۰ ثانیه، و افت عمق ≥۵۰٪ نسبت به میانگین ۱ ساعته.' } },
    ],
  },
  {
    title: { en: '6 · Economic calendar', fa: '۶ · تقویم اقتصادی' },
    items: [
      { term: { en: 'Status & surprise', fa: 'وضعیت و غافلگیری' },
        body: { en: 'Events are Upcoming (countdown shown), Live (within the first hour after release time, awaiting data) or Released. When the Actual arrives it is compared to the Forecast: ▲ green = better than forecast, ▼ red = worse, ● = in line. For indicators where lower is better (unemployment, jobless claims, inventories) the coloring is flipped automatically. Surprise = Actual − Forecast.',
                fa: 'رویدادها یا «پیش رو» هستند (با شمارش معکوس)، یا «زنده» (تا یک ساعت پس از زمان انتشار، در انتظار داده) یا «منتشر شده». وقتی مقدار واقعی برسد با پیش‌بینی مقایسه می‌شود: ▲ سبز = بهتر از پیش‌بینی، ▼ قرمز = بدتر، ● = مطابق. برای شاخص‌هایی که عدد کمتر بهتر است (بیکاری، مدعیان بیمه بیکاری، ذخایر) رنگ‌بندی خودکار برعکس می‌شود. غافلگیری = واقعی منهای پیش‌بینی.' } },
      { term: { en: 'History & revisions', fa: 'تاریخچه و بازبینی' },
        body: { en: 'Expanding a row shows the event description, past releases stored by the platform, and the average historical surprise — a feel for whether forecasters usually under- or over-shoot this indicator. If the feed revises the previous value, the revision shows under the Previous column in amber.',
                fa: 'با باز کردن هر ردیف، توضیح رویداد، انتشارهای قبلی ذخیره‌شده و میانگین غافلگیری تاریخی نمایش داده می‌شود — تا حس کنید پیش‌بینی‌ها معمولاً کمتر یا بیشتر از واقع بوده‌اند. اگر فید مقدار قبلی را بازبینی کند، زیر ستون «قبلی» با رنگ کهربایی نشان داده می‌شود.' } },
      { term: { en: 'Impact & filters', fa: 'اهمیت و فیلترها' },
        body: { en: 'Red dot = High impact (rate decisions, CPI, NFP…), amber = Medium, gray = Low. Filter by impact, currency, event type (Central Banks, Inflation, Employment…) or search by name. All times are Iran time; the Persian UI uses the Jalali calendar.',
                fa: 'نقطه قرمز = اهمیت زیاد (نرخ بهره، تورم، اشتغال…)، کهربایی = متوسط، خاکستری = کم. فیلتر بر اساس اهمیت، ارز، نوع رویداد (بانک مرکزی، تورم، اشتغال…) یا جستجوی نام. همه زمان‌ها به وقت ایران و در رابط فارسی با تقویم شمسی است.' } },
    ],
  },
  {
    title: { en: '7 · Data management & settings', fa: '۷ · مدیریت داده و تنظیمات' },
    items: [
      { term: { en: 'Add a trading pair', fa: 'افزودن جفت‌ارز' },
        body: { en: 'Admin → Add Trading Pair → type the base symbol (e.g. DOGE). It goes live on the next poll cycle across all exchanges that list it — no restart.',
                fa: 'مدیریت ← افزودن جفت‌ارز ← نماد پایه را بنویسید (مثلاً DOGE). در چرخه بعدی دریافت داده در همه صرافی‌هایی که آن را دارند فعال می‌شود — بدون ری‌استارت.' } },
      { term: { en: 'Add an exchange', fa: 'افزودن صرافی' },
        body: { en: 'Admin → Add Exchange → name + JSON spec pointing at the venue\'s order-book endpoint: orderbook_url (with {symbol}), bids_path/asks_path (dot-paths into the response), symbol_template, price_scale (0.1 converts Rial→Toman), optional stats_url, and taker_fee_pct for arbitrage math. Stored in the database and hot-loaded immediately.',
                fa: 'مدیریت ← افزودن صرافی ← نام + یک JSON که به آدرس دفتر سفارش صرافی اشاره می‌کند: orderbook_url (با {symbol})، bids_path/asks_path (مسیر نقطه‌ای در پاسخ)، symbol_template، price_scale (۰.۱ برای تبدیل ریال به تومان)، stats_url اختیاری و taker_fee_pct برای محاسبه آربیتراژ. در پایگاه داده ذخیره و بلافاصله بارگذاری می‌شود.' } },
      { term: { en: 'Settings & data retention', fa: 'تنظیمات و نگهداری داده' },
        body: { en: 'Poll intervals, snapshot cadence (default: every 5 minutes to the database) and timeouts are tunable live in Admin and persist across restarts. Old data is pruned automatically (snapshots 90d, candles 365d, alerts 30d by default). DEMO badge in the header means synthetic data is on.',
                fa: 'بازه‌های دریافت، تناوب اسنپ‌شات (پیش‌فرض هر ۵ دقیقه در پایگاه داده) و مهلت‌ها به‌صورت زنده در بخش مدیریت قابل تنظیم‌اند و ماندگارند. داده قدیمی خودکار حذف می‌شود (اسنپ‌شات ۹۰ روز، کندل ۳۶۵ روز، هشدار ۳۰ روز). نشان DEMO در سربرگ یعنی داده مصنوعی فعال است.' } },
      { term: { en: 'Status dots', fa: 'نقطه‌های وضعیت' },
        body: { en: 'Green = live feed, amber = delayed (book older than 15s), red = offline (venue unreachable; last known prices shown but excluded from the composite). The dot in the header shows WebSocket connectivity.',
                fa: 'سبز = فید زنده، کهربایی = با تاخیر (دفتر قدیمی‌تر از ۱۵ ثانیه)، قرمز = قطع (صرافی در دسترس نیست؛ آخرین قیمت نمایش داده می‌شود اما از شاخص ترکیبی حذف می‌شود). نقطه سربرگ اتصال وب‌سوکت را نشان می‌دهد.' } },
    ],
  },
  {
    title: { en: '8 · Competitive intelligence', fa: '۸ · هوش رقابتی' },
    items: [
      { term: { en: 'Top-of-book time share', fa: 'سهم زمانی بهترین قیمت' },
        body: { en: 'Every polling cycle the platform records which venue holds the highest bid and lowest ask per pair (quotes within 1 basis point tie). Accumulated time-weighted and stored hourly, it shows the % of time each exchange was the best place to trade — the literal scoreboard for "best exchange". Rankings need a few minutes of uptime to appear and get more meaningful with history.',
                fa: 'در هر چرخه، پلتفرم ثبت می‌کند کدام صرافی بالاترین خرید و پایین‌ترین فروش را دارد (اختلاف تا ۱ بیسیس‌پوینت مساوی حساب می‌شود). این داده وزن‌دار زمانی جمع و ساعتی ذخیره می‌شود و نشان می‌دهد هر صرافی چند درصدِ زمان بهترین قیمت را داشته — جدول امتیاز واقعی «بهترین صرافی». رتبه‌بندی پس از چند دقیقه ظاهر و با گذشت زمان معنادارتر می‌شود.' } },
      { term: { en: 'Market share', fa: 'سهم بازار' },
        body: { en: 'Each venue\'s slice of total reported 24h volume, per pair or across all assets, tracked over time with rank-movement arrows (second half of the window vs the first). Volumes are self-reported by exchanges, so trends and relative changes are more trustworthy than absolute numbers.',
                fa: 'سهم هر صرافی از مجموع حجم ۲۴ ساعته گزارش‌شده، به تفکیک جفت‌ارز یا کل دارایی‌ها، در طول زمان با فلش تغییر رتبه (نیمه دوم بازه نسبت به نیمه اول). حجم‌ها خوداظهاری صرافی‌هاست؛ روند و تغییر نسبی قابل‌اعتمادتر از عدد مطلق است.' } },
      { term: { en: 'Opportunity-cost ledger & inventory', fa: 'دفتر هزینه‌فرصت و موجودی' },
        body: { en: 'Whenever the fee-adjusted, depth-limited edge between two venues exceeds your threshold (Admin → "Ledger min edge"), a window opens in the ledger and tracks peak edge, executable size, peak profit and duration until it dies. The model assumes capital is pre-positioned on both venues (zero-transfer): book-walking prices in the spread, taker fees are deducted on both legs, and no withdrawal fees apply. The inventory table answers "how much must I park where": per venue, the TMN (buy side) and coins (sell side) needed to capture 100% of the period\'s windows — including overlapping ones — plus a 95% variant that drops the heaviest 5%.',
                fa: 'هر زمان لبه خالص (پس از کارمزد و با احتساب عمق) بین دو صرافی از آستانه شما بگذرد (مدیریت ← «حداقل لبه دفتر»)، یک پنجره در دفتر باز می‌شود و اوج لبه، حجم قابل اجرا، اوج سود و مدت آن را تا بسته شدن ثبت می‌کند. مدل فرض می‌کند سرمایه از قبل در هر دو صرافی مستقر است (بدون انتقال): پیمایش دفتر سفارش اسپرد را لحاظ می‌کند، کارمزد تیکر دو سمت کسر می‌شود و کارمزد برداشت نداریم. جدول موجودی پاسخ می‌دهد «کجا چقدر پارک کنم»: برای هر صرافی، تومانِ سمت خرید و کوینِ سمت فروش لازم برای شکار ۱۰۰٪ پنجره‌های دوره — با احتساب همپوشانی — به‌علاوه نسخه ۹۵٪ که سنگین‌ترین ۵٪ را حذف می‌کند.' } },
    ],
  },
];

export default function Help() {
  const { t, lang } = useLang();
  const [open, setOpen] = useState({ 0: true, 1: true });
  return (
    <div style={{ maxWidth: 900 }}>
      <h2 style={{ fontSize: 18, marginBottom: 4 }}>{t('help')}</h2>
      <p style={{ color: 'var(--text-2)', fontSize: 13, marginBottom: 16 }}>
        {lang === 'fa'
          ? 'راهنمای کامل پلتفرم — هر بخش، هر شاخص و نحوه محاسبه آن.'
          : 'Complete guide to the platform — every section, every metric, and how it\'s calculated.'}
      </p>
      {H.map((sec, i) => (
        <div key={i} className="card" style={{ marginBottom: 10, padding: 0 }}>
          <button className="cal-day-head" onClick={() => setOpen((p) => ({ ...p, [i]: !p[i] }))}>
            <span className="chev">{open[i] ? '▾' : '▸'}</span>
            <b>{sec.title[lang]}</b>
          </button>
          {open[i] && (
            <div style={{ padding: '4px 16px 14px' }}>
              {sec.items.map((item, j) => (
                <div key={j} style={{ padding: '10px 0',
                                      borderBottom: j < sec.items.length - 1 ? '1px solid var(--border)' : 'none' }}>
                  <div style={{ fontWeight: 700, fontSize: 13.5, marginBottom: 4 }}>
                    {item.term[lang]}
                  </div>
                  {item.code && (
                    <pre className="help-code">{item.code}</pre>
                  )}
                  <div style={{ fontSize: 12.5, color: 'var(--text-2)', lineHeight: 1.65 }}>
                    {item.body[lang]}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
