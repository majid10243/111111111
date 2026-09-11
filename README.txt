نسخه v7 اصلاح‌شده

این بسته Build واقعی v6 را از GitHub می‌گیرد و v7 را می‌سازد.

اصلاحات:
- Password داشبورد اختیاری است.
- Login بدون Password متوقف نمی‌شود.
- Register Provider ابتدا OpenAI Compatible Node را پیدا/ایجاد می‌کند.
- سپس Provider Connection را با Node ID ثبت می‌کند.
- enabledModels به Connection اضافه می‌شود.
- خطای 404 OpenAI Compatible node not found برای مسیر قبلی برطرف می‌شود.

روش اجرا:
RUN_BUILD_V7.bat

پس از ساخته شدن v7:
1. Password داشبورد را خالی بگذارید.
2. Login / Test را بزنید.
3. Scan Models.
4. مدل‌ها را انتخاب کنید.
5. Register Provider.
