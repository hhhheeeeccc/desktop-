import os
import platform
import psutil
import cpuinfo
import GPUtil
import wmi
import customtkinter as ctk
import threading
import time
from datetime import datetime

class SystemScanner:
    """
    فئة مسؤولة عن جمع كافة المعلومات الخاصة بالعتاد ونظام التشغيل.
    """
    def __init__(self):
        try:
            self.w = wmi.WMI()
        except Exception:
            self.w = None

    def get_cpu_info(self):
        """جمع معلومات المعالج"""
        info = cpuinfo.get_cpu_info()
        return {
            "الاسم": info.get('brand_raw', "غير معروف"),
            "التردد": info.get('hz_actual_friendly', "غير معروف"),
            "الأنوية الحقيقية": psutil.cpu_count(logical=False),
            "الأنوية المنطقية": psutil.cpu_count(logical=True),
            "المعمارية": info.get('arch', "غير معروف")
        }

    def get_gpu_info(self):
        """جمع معلومات كرت الشاشة (NVIDIA)"""
        gpus_data = []
        try:
            gpus = GPUtil.getGPUs()
            for gpu in gpus:
                gpus_data.append({
                    "الاسم": gpu.name,
                    "الذاكرة الكلية": f"{gpu.memoryTotal} MB",
                    "الذاكرة المستخدمة": f"{gpu.memoryUsed} MB",
                    "درجة الحرارة": f"{gpu.temperature} °C"
                })
        except Exception:
            pass

        # محاولة جلب كروت شاشة أخرى عبر WMI في حال عدم وجود NVIDIA
        if not gpus_data and self.w:
            for video in self.w.Win32_VideoController():
                gpus_data.append({
                    "الاسم": video.Name,
                    "الذاكرة الكلية": f"{int(video.AdapterRAM or 0) / (1024**2):.0f} MB" if video.AdapterRAM else "غير معروف",
                    "الحالة": "متاح"
                })

        return gpus_data if gpus_data else [{"الاسم": "لم يتم العثور على كرت شاشة متوافق"}]

    def get_ram_info(self):
        """جمع معلومات الذاكرة العشوائية"""
        ram = psutil.virtual_memory()
        return {
            "الإجمالي": f"{ram.total / (1024**3):.2f} GB",
            "المستخدم": f"{ram.used / (1024**3):.2f} GB",
            "المتاح": f"{ram.available / (1024**3):.2f} GB",
            "النسبة": f"{ram.percent}%"
        }


    def get_battery_info(self):
        """جمع معلومات البطارية وصحتها"""
        battery_data = {"حالة": "غير متوفرة"}
        if not self.w:
            return battery_data

        try:
            # استخدام namespace root\wmi للحصول على تفاصيل دقيقة
            w_wmi = wmi.WMI(namespace="root\\wmi")
            full_capacity = w_wmi.BatteryFullCapacity()[0].FullChargeCapacity
            design_capacity = w_wmi.BatteryStaticData()[0].DesignedCapacity

            # حساب مستوى التآكل
            wear_level = 100 - (full_capacity / design_capacity * 100)

            # جلب عدد الدورات (قد لا تتوفر في كل الأجهزة)
            try:
                cycle_count = w_wmi.BatteryCycleCount()[0].CycleCount
            except:
                cycle_count = "غير مدعوم"

            battery_data = {
                "السعة التصميمية": f"{design_capacity} mWh",
                "السعة الحالية": f"{full_capacity} mWh",
                "مستوى التآكل": f"{wear_level:.2f}%",
                "عدد دورات الشحن": cycle_count,
                "الحالة": "جيدة" if wear_level < 20 else "متوسطة"
            }
        except Exception:
            # محاولة بسيطة في حال فشل الوصول لـ root\wmi
            batt = psutil.sensors_battery()
            if batt:
                battery_data = {
                    "النسبة المئوية": f"{batt.percent}%",
                    "حالة الشحن": "يشحن" if batt.power_plugged else "تفريغ",
                    "الوقت المتبقي": f"{batt.secsleft // 60} دقيقة" if batt.secsleft != -1 else "غير معروف"
                }
        return battery_data

    def get_storage_info(self):
        """جمع معلومات وحدات التخزين وصحتها (SMART)"""
        disks_info = []
        if not self.w:
            return disks_info

        try:
            for disk in self.w.Win32_DiskDrive():
                # جلب الحالة الأساسية
                status = disk.Status
                size_gb = int(disk.Size) / (1024**3)

                disks_info.append({
                    "الموديل": disk.Model,
                    "الحجم": f"{size_gb:.2f} GB",
                    "النوع": "NVMe/SSD" if "SSD" in disk.Model or "NVMe" in disk.Model else "HDD",
                    "الحالة الصحية": "سليم" if status == "OK" else "تحتاج فحص"
                })

            # محاولة جلب ساعات التشغيل عبر MSStorageDriver (تحتاج صلاحيات مسؤول)
            try:
                w_wmi = wmi.WMI(namespace="root\\wmi")
                # ملاحظة: جلب ساعات التشغيل بشكل دقيق يتطلب تحليل Byte array لـ SMART
                # سنكتفي هنا بإظهار أن النظام يعمل على مراقبة الصحة
            except:
                pass
        except Exception:
            pass

        return disks_info


    def get_temperature_info(self):
        """جلب درجات الحرارة الحالية"""
        temps = {"CPU": "غير مدعوم", "GPU": "غير مدعوم"}
        try:
            # محاولة جلب حرارة المعالج عبر WMI (MSAcpi_ThermalZoneTemperature)
            # النتيجة تكون بالعشر من الكلفن غالباً
            if self.w:
                w_wmi = wmi.WMI(namespace="root\\wmi")
                t = w_wmi.MSAcpi_ThermalZoneTemperature()[0].CurrentTemperature
                temps["CPU"] = f"{(t / 10.0) - 273.15:.1f} °C"
        except:
            pass

        try:
            # حرارة كرت الشاشة من GPUtil
            gpus = GPUtil.getGPUs()
            if gpus:
                temps["GPU"] = f"{gpus[0].temperature} °C"
        except:
            pass

        return temps


class LaptopInspectorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.scanner = SystemScanner()

        # إعدادات النافذة الرئيسية
        self.title("فاحص اللابتوب الاحترافي - Professional Laptop Inspector")
        self.geometry("1000x700")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # إعداد الخطوط
        self.title_font = ctk.CTkFont(family="Arial", size=24, weight="bold")
        self.label_font = ctk.CTkFont(family="Arial", size=14)
        self.data_font = ctk.CTkFont(family="Consolas", size=14, weight="bold")

        # إنشاء الهيكل الرئيسي
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # الشريط العلوي
        self.header_frame = ctk.CTkFrame(self, height=80, corner_radius=0)
        self.header_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        self.title_label = ctk.CTkLabel(self.header_frame, text="أداة فحص الكمبيوتر الشاملة", font=self.title_font)
        self.title_label.pack(pady=20)

        # منطقة التبويبات
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)

        self.tab_hardware = self.tabview.add("المواصفات العتادية")
        self.tab_health = self.tabview.add("الصحة والتخزين")
        self.tab_battery = self.tabview.add("البطارية")
        self.tab_thermal = self.tabview.add("الحرارة والضغط")

        self.setup_hardware_tab()
        self.setup_health_tab()
        self.setup_battery_tab()
        self.setup_thermal_tab()

        # الشريط السفلي (الأزرار العامة)
        self.footer_frame = ctk.CTkFrame(self, height=60, corner_radius=0)
        self.footer_frame.grid(row=2, column=0, sticky="nsew", padx=0, pady=0)

        self.btn_refresh = ctk.CTkButton(self.footer_frame, text="تحديث البيانات", command=self.refresh_all, fg_color="green", hover_color="#006400")
        self.btn_refresh.pack(side="right", padx=20, pady=15)

        self.btn_export = ctk.CTkButton(self.footer_frame, text="تصدير التقرير", command=self.export_report)
        self.btn_export.pack(side="right", padx=10, pady=15)

        self.btn_dead_pixel = ctk.CTkButton(self.footer_frame, text="فحص البكسلات الميتة", command=self.open_dead_pixel_test, fg_color="purple")
        self.btn_dead_pixel.pack(side="left", padx=20, pady=15)

        # تحديث أولي
        self.refresh_all()

    def setup_hardware_tab(self):
        self.tab_hardware.grid_columnconfigure((0,1), weight=1)

        # قسم المعالج
        self.cpu_frame = ctk.CTkLabel(self.tab_hardware, text="[ معلومات المعالج ]", font=self.label_font, text_color="cyan")
        self.cpu_frame.grid(row=0, column=1, sticky="ne", padx=20, pady=10)
        self.cpu_data_label = ctk.CTkLabel(self.tab_hardware, text="جاري التحميل...", justify="right", font=self.data_font)
        self.cpu_data_label.grid(row=1, column=1, sticky="ne", padx=40, pady=5)

        # قسم الرام
        self.ram_frame = ctk.CTkLabel(self.tab_hardware, text="[ الذاكرة العشوائية ]", font=self.label_font, text_color="cyan")
        self.ram_frame.grid(row=2, column=1, sticky="ne", padx=20, pady=10)
        self.ram_data_label = ctk.CTkLabel(self.tab_hardware, text="جاري التحميل...", justify="right", font=self.data_font)
        self.ram_data_label.grid(row=3, column=1, sticky="ne", padx=40, pady=5)

        # قسم كرت الشاشة
        self.gpu_frame = ctk.CTkLabel(self.tab_hardware, text="[ كرت الشاشة ]", font=self.label_font, text_color="cyan")
        self.gpu_frame.grid(row=0, column=0, sticky="ne", padx=20, pady=10)
        self.gpu_data_label = ctk.CTkLabel(self.tab_hardware, text="جاري التحميل...", justify="right", font=self.data_font)
        self.gpu_data_label.grid(row=1, column=0, sticky="ne", padx=40, pady=5)

    def setup_health_tab(self):
        self.tab_health.grid_columnconfigure(0, weight=1)
        self.storage_label = ctk.CTkLabel(self.tab_health, text="[ أقراص التخزين والحالة ]", font=self.label_font, text_color="cyan")
        self.storage_label.pack(pady=10, padx=20, anchor="e")
        self.storage_data_box = ctk.CTkTextbox(self.tab_health, width=600, height=300, font=self.data_font)
        self.storage_data_box.pack(pady=10, padx=20, fill="both", expand=True)

    def setup_battery_tab(self):
        self.tab_battery.grid_columnconfigure(0, weight=1)
        self.battery_data_label = ctk.CTkLabel(self.tab_battery, text="جاري فحص البطارية...", font=self.data_font, justify="right")
        self.battery_data_label.pack(pady=50, padx=20)

    def setup_thermal_tab(self):
        self.tab_thermal.grid_columnconfigure(0, weight=1)

        self.temp_label = ctk.CTkLabel(self.tab_thermal, text="[ درجات الحرارة الحالية ]", font=self.label_font, text_color="orange")
        self.temp_label.pack(pady=10)

        self.temp_data_label = ctk.CTkLabel(self.tab_thermal, text="CPU: -- | GPU: --", font=self.data_font)
        self.temp_data_label.pack(pady=10)

        self.stress_btn = ctk.CTkButton(self.tab_thermal, text="بدء اختبار ضغط (30 ثانية)", command=self.run_stress_test, fg_color="red")
        self.stress_btn.pack(pady=30)

        self.stress_progress = ctk.CTkProgressBar(self.tab_thermal, width=400)
        self.stress_progress.set(0)
        self.stress_progress.pack(pady=10)

    def refresh_all(self):
        """تحديث كافة البيانات في الواجهة"""
        # CPU
        cpu = self.scanner.get_cpu_info()
        cpu_text = f"الاسم: {cpu['الاسم']}\nالتردد: {cpu['التردد']}\nالأنوية: {cpu['الأنوية الحقيقية']} حقيقية / {cpu['الأنوية المنطقية']} منطقية"
        self.cpu_data_label.configure(text=cpu_text)

        # RAM
        ram = self.scanner.get_ram_info()
        ram_text = f"الإجمالي: {ram['الإجمالي']}\nالمستخدم: {ram['المستخدم']}\nالمتاح: {ram['المتاح']}\nالاستهلاك: {ram['النسبة']}"
        self.ram_data_label.configure(text=ram_text)

        # GPU
        gpus = self.scanner.get_gpu_info()
        gpu_text = ""
        for g in gpus:
            gpu_text += f"الاسم: {g.get('الاسم')}\nالذاكرة: {g.get('الذاكرة الكلية')}\n---\n"
        self.gpu_data_label.configure(text=gpu_text)

        # Storage
        disks = self.scanner.get_storage_info()
        self.storage_data_box.delete("1.0", "end")
        for d in disks:
            self.storage_data_box.insert("end", f"الموديل: {d['الموديل']}\nالحجم: {d['الحجم']}\nالنوع: {d['النوع']}\nالحالة: {d['الحالة الصحية']}\n" + "="*30 + "\n")

        # Battery
        batt = self.scanner.get_battery_info()
        batt_text = "بيانات البطارية:\n\n"
        for k, v in batt.items():
            batt_text += f"{k}: {v}\n"
        self.battery_data_label.configure(text=batt_text)

        # Temps
        temps = self.scanner.get_temperature_info()
        self.temp_data_label.configure(text=f"CPU: {temps['CPU']} | GPU: {temps['GPU']}")


    def run_stress_test(self):
        """بدء اختبار الضغط في خيط منفصل"""
        self.stress_btn.configure(state="disabled", text="جاري الاختبار...")
        threading.Thread(target=self._stress_worker, daemon=True).start()

    def _stress_worker(self):
        start_time = time.time()
        duration = 30

        # دالة للضغط على المعالج
        def cpu_heavy_load():
            x = 0
            while time.time() - start_time < duration:
                x += 1

        # تشغيل الضغط في خيوط متعددة حسب عدد الأنوية
        threads = []
        for _ in range(psutil.cpu_count()):
            t = threading.Thread(target=cpu_heavy_load)
            t.start()
            threads.append(t)

        # تحديث شريط التقدم والحرارة أثناء الاختبار
        while time.time() - start_time < duration:
            elapsed = time.time() - start_time
            progress = elapsed / duration
            self.stress_progress.set(progress)

            # تحديث الحرارة اللحظية
            temps = self.scanner.get_temperature_info()
            self.temp_data_label.configure(text=f"CPU: {temps['CPU']} | GPU: {temps['GPU']} (جاري الضغط)")
            time.sleep(1)

        for t in threads:
            t.join()

        self.stress_progress.set(1)
        self.stress_btn.configure(state="normal", text="بدء اختبار ضغط (30 ثانية)")
        self.refresh_all()

    def export_report(self):
        """تصدير تقرير شامل إلى سطح المكتب"""
        try:
            report_path = os.path.join(os.path.expanduser("~"), "Desktop", "Laptop_Report_Arabic.txt")

            cpu = self.scanner.get_cpu_info()
            gpu = self.scanner.get_gpu_info()
            ram = self.scanner.get_ram_info()
            batt = self.scanner.get_battery_info()
            disks = self.scanner.get_storage_info()

            with open(report_path, "w", encoding="utf-8") as f:
                f.write("="*50 + "\n")
                f.write("تقرير فحص جهاز الكمبيوتر الشامل\n")
                f.write(f"تاريخ الفحص: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("="*50 + "\n\n")

                f.write("[ معلومات المعالج ]\n")
                for k, v in cpu.items(): f.write(f"{k}: {v}\n")

                f.write("\n[ كرت الشاشة ]\n")
                for g in gpu: f.write(f"الاسم: {g.get('الاسم')}\nالذاكرة: {g.get('الذاكرة الكلية')}\n---\n")

                f.write("\n[ الذاكرة العشوائية ]\n")
                for k, v in ram.items(): f.write(f"{k}: {v}\n")

                f.write("\n[ حالة البطارية ]\n")
                for k, v in batt.items(): f.write(f"{k}: {v}\n")

                f.write("\n[ وحدات التخزين ]\n")
                for d in disks: f.write(f"الموديل: {d['الموديل']} | الحجم: {d['الحجم']} | الحالة: {d['الحالة الصحية']}\n")

                f.write("\n" + "="*50 + "\n")
                f.write("تم إنشاء هذا التقرير بواسطة أداة فحص اللابتوب الاحترافية\n")

            # عرض رسالة نجاح (مبسطة)
            self.title_label.configure(text="تم تصدير التقرير إلى سطح المكتب بنجاح!", text_color="green")
            self.after(3000, lambda: self.title_label.configure(text="أداة فحص الكمبيوتر الشاملة", text_color="white"))
        except Exception as e:
            print(f"Error exporting report: {e}")


    def open_dead_pixel_test(self):
        """فتح نافذة فحص البكسلات الميتة ملء الشاشة"""
        test_window = ctk.CTkToplevel(self)
        test_window.title("فحص البكسلات الميتة - انقر للتنقل - ESC للخروج")
        test_window.attributes("-fullscreen", True)

        colors = ["black", "white", "red", "green", "blue"]
        self.current_color_idx = 0

        canvas = ctk.CTkCanvas(test_window, bg=colors[self.current_color_idx], highlightthickness=0)
        canvas.pack(fill="both", expand=True)

        def next_color(event):
            self.current_color_idx = (self.current_color_idx + 1) % len(colors)
            canvas.configure(bg=colors[self.current_color_idx])

        def close_test(event):
            test_window.destroy()

        canvas.bind("<Button-1>", next_color)
        test_window.bind("<Escape>", close_test)

        # إضافة نص توضيحي يختفي بعد ثوانٍ
        instruction = ctk.CTkLabel(canvas, text="انقر بالماوس لتغيير اللون\nاضغط ESC للخروج", font=("Arial", 20), text_color="gray")
        instruction.place(relx=0.5, rely=0.5, anchor="center")
        canvas.after(3000, instruction.destroy)

if __name__ == "__main__":
    app = LaptopInspectorApp()
    app.mainloop()
