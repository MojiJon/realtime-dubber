# ریل‌تایم دوبلر (Realtime Dubber)

📖 [English](README.md)

> **⚠️ وضعیت: نسخه‌ی اولیه، تقریباً کاملاً با کمک هوش مصنوعی (Claude) ساخته
> شده.** پایپ‌لاین اصلی کار می‌کنه، ولی فقط روی یک سیستم و یک کانفیگ صوتی
> تست شده. نیاز به تست روی سخت‌افزار/بازی‌های مختلف، بازبینی کد توسط کسی که
> صدای ویندوز و asyncio رو بهتر از یه AI بلده، و تکمیل بخش‌های ناتمام داره.
> **مشارکت (کد، گزارش باگ، حتی بازنویسی بخش‌های ضعیف) کاملاً خوش‌آمده** —
> به [CONTRIBUTING.md](CONTRIBUTING.md) نگاه کن.

یک برنامه‌ی دسکتاپ ویندوزی که صدای خروجی سیستم رو لحظه‌ای می‌گیره و با
**Gemini Live Translate** (مدل `gemini-3.5-live-translate-preview`) ترجمه
می‌کنه — این مدل خودش صدای ترجمه‌شده تولید می‌کنه (audio-to-audio)، پس
نیازی به STT و TTS جدا نیست.

**هدف اصلی پروژه:** فهمیدن صدای یه بازی یا برنامه‌ای که به زبونی غیر از
زبون خودت صحبت می‌کنه، بدون نیاز به alt-tab کردن به یه مترجم. صدای خروجی
اسپیکرت رو می‌گیره، ترجمه می‌کنه، و ترجمه رو پخش می‌کنه (همزمان ولوم صدای
اصلی رو موقتاً کم می‌کنه).

## نحوه‌ی کار

```
صدای سیستم (loopback capture، 16kHz مونو)
    -> به‌صورت پیوسته روی WebSocket به Gemini Live فرستاده میشه
    -> صدای ترجمه‌شده برمی‌گرده (24kHz مونو)
    -> با یک jitter buffer + مکانیزم catch-up پخش میشه
    -> ولوم صدای اصلی حین پخش ترجمه موقتاً کم میشه
```

نکات مهم معماری:

- **گرفتن صدا (capture) و ارسال شبکه از هم جدا هستن.** capture توی یه
  thread جدا (با callback خودِ PortAudio) کار می‌کنه و فقط یه صف رو پر
  می‌کنه؛ ارسال به شبکه مستقل از اون انجام میشه. این از drop شدن بی‌صدای
  صدا در صورت کند شدن لحظه‌ای شبکه جلوگیری می‌کنه (`audio_io.py`).
- **پخش صدا هم مستقل شده**، با یک بافر سایز-محدود و مکانیزم «رسیدن به سر»:
  اگه صدای ترجمه‌شده سریع‌تر از سرعت پخش برسه (که معموله — مدل می‌تونه چند
  تیکه رو یهو بفرسته)، پخش کمی سریع‌تر میشه (تا ۳۰٪) تا نرم‌نرمک به
  real-time برسه، به‌جای اینکه هی عقب‌تر بیفته یا با پرش ناگهانی جبران بشه.
- **اتصال WebSocket خودکار reconnect میشه.** session های Gemini Live حدود
  ۱۰-۱۵ دقیقه عمر دارن؛ با `session_resumption` و
  `context_window_compression`، برنامه می‌تونه بی‌نهایت اجرا بمونه و هر بار
  که سرور قطع کرد، بی‌صدا دوباره وصل بشه.
- **جلوگیری از loop صوتی.** چون این برنامه کل صدای سیستم رو capture
  می‌کنه، اگه صدای ترجمه از همون دستگاهی که capture میشه پخش بشه، دوباره
  capture و دوباره ترجمه میشه (بی‌نهایت). بخش نصب پایین، مسیر صدا رو به یه
  دستگاه مجازی جدا (VoiceMeeter یا VB-Cable) هدایت می‌کنه تا این اتفاق
  نیفته.

## نصب

1. ویندوز ۱۰/۱۱، Python 3.10+.
2. virtual environment بساز:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```
3. وابستگی‌ها رو نصب کن:
   ```
   pip install -r requirements.txt
   ```
4. `.env.example` رو کپی کن و اسمش رو بذار `.env`، کلید API جمینی رو داخلش
   بذار:
   ```
   GEMINI_API_KEY=کلید-تو-اینجا
   ```
   اگه به مشکل شبکه/فیلترینگ برخوردی، خط `HTTPS_PROXY` رو فعال کن.

## ⚠️ مرحله‌ی ضروری: جلوگیری از loop صوتی

### گزینه‌ی الف: اگه از VoiceMeeter استفاده می‌کنی

1. مطمئن شو صدای گیم/اپ داره میره به `VoiceMeeter Input`.
2. `python list_devices.py` رو اجرا کن، اسم دقیق `VoiceMeeter Input`
   (بخش LOOPBACK-CAPTURABLE) و `VoiceMeeter AUX Input` (بخش OUTPUT) رو پیدا
   کن.
3. توی `.env`:
   ```
   INPUT_DEVICE_NAME=VoiceMeeter Input
   OUTPUT_DEVICE_NAME=VoiceMeeter Aux Input
   ```
4. توی خودِ VoiceMeeter، روی strip مربوط به `AUX Input`، فقط `A1` رو فعال
   کن (نه `B1`).

### گزینه‌ی ب: بدون VoiceMeeter

1. [VB-Audio Virtual Cable](https://vb-audio.com/Cable/) رو نصب کن (رایگان).
2. `python list_devices.py`، اسم `CABLE Input` رو پیدا کن.
3. `.env`: `OUTPUT_DEVICE_NAME=CABLE Input`
4. برای شنیدنش: **Sound Control Panel > تب Recording > دوبار کلیک روی
   `CABLE Output` > تب Listen > تیک "Listen to this device" > هدفون واقعیت
   رو انتخاب کن.**

## اجرا

```
python main.py
```

## تنظیمات (`config.py`)

| تنظیم | کاربرد |
|---|---|
| `TARGET_LANGUAGE_CODE` | کد زبان مقصد (فارسی = `"fa"`) |
| `ECHO_TARGET_LANGUAGE` | آیا صدایی که از قبل به زبون مقصده هم تکرار بشه یا نه |
| `INPUT_DEVICE_NAME` | نام دستگاه loopback برای capture (خالی = دستگاه پیش‌فرض) |
| `OUTPUT_DEVICE_NAME` | نام دستگاه پخش ترجمه (باید با دستگاه capture فرق داشته باشه) |
| `DUCK_VOLUME_FACTOR` | میزان کم شدن ولوم حین پخش ترجمه |
| `CATCHUP_START_MS` / `CATCHUP_MAX_SPEED` / `HARD_DROP_MS` | تنظیمات مکانیزم «رسیدن به سر» صدا |

## محدودیت‌های شناخته‌شده / کارهای باقی‌مونده

جاهایی که مشارکت بیشترین کمک رو می‌کنه:

- **capture کل سیستم، نه فقط یک اپ.** الان همه‌چیزی که از دستگاه هدف رد
  میشه گرفته میشه. Windows Process Loopback Capture API می‌تونه فقط صدای
  یک پروسس رو بگیره — هنوز پیاده نشده.
- **ducking کل سیستم، نه یک اپ خاص.** `volume_control.py` ولوم master
  ویندوز رو کم می‌کنه، نه ولوم یک اپ مشخص — با میکسرهایی مثل VoiceMeeter
  هماهنگ نیست.
- **مدل preview.** `gemini-3.5-live-translate-preview` ممکنه محدودیت
  quota یا تغییرات رفتاری داشته باشه.
- **کیفیت resample.** الان از interpolation ساده‌ی numpy استفاده میشه، نه
  یک کتابخونه‌ی resample حرفه‌ای.
- **بدون رابط گرافیکی (GUI).** فعلاً فقط یه اسکریپت کنسولیه.
- **بدون تست خودکار.**
- **فقط ویندوز/WASAPI.**

جزئیات کامل‌تر توی [README.md](README.md) (انگلیسی) و
[CONTRIBUTING.md](CONTRIBUTING.md) هست.

## لایسنس

MIT — فایل [LICENSE](LICENSE) رو ببین.
