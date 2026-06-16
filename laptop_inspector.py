import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import os
import platform
import psutil
import cpuinfo
import GPUtil
import customtkinter as ctk
import threading
import time
import subprocess
from datetime import datetime

# Guard Windows-specific imports
if platform.system() == "Windows":
    try:
        import wmi
    except ImportError:
        wmi = None
else:
    wmi = None

class SystemScanner:
    """
    فئة مسؤولة عن جمع كافة المعلومات الخاصة بالعتاد ونظام التشغيل.
    """
    def __init__(self):
        self.system = platform.system()
        try:
            if self.system == "Windows" and wmi:
                self.w = wmi.WMI()
            else:
                self.w = None
        except Exception:
            self.w = None

    def get_cpu_info(self):
        """جمع معلومات المعالج"""
        try:
            info = cpuinfo.get_cpu_info()
            return {
                "الاسم": info.get('brand_raw', "غير معروف"),
                "التردد": info.get('hz_actual_friendly', "غير معروف"),
                "الأنوية الحقيقية": psutil.cpu_count(logical=False),
                "الأنوية المنطقية": psutil.cpu_count(logical=True),
                "المعمارية": info.get('arch', "غير معروف")
            }
        except Exception:
            return {
                "الاسم": "غير معروف",
                "التردد": "غير معروف",
                "الأنوية الحقيقية": psutil.cpu_count(logical=False),
                "الأنوية المنطقية": psutil.cpu_count(logical=True),
                "المعمارية": "غير معروف"
            }

    def get_gpu_info(self):
        """جمع معلومات كرت الشاشة"""
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

        # محاولة جلب كروت شاشة أخرى في حال عدم وجود NVIDIA
        if not gpus_data:
            if self.system == "Windows" and self.w:
                for video in self.w.Win32_VideoController():
                    gpus_data.append({
                        "الاسم": video.Name,
                        "الذاكرة الكلية": f"{int(video.AdapterRAM or 0) / (1024**2):.0f} MB" if video.AdapterRAM else "غير معروف",
                        "الحالة": "متاح"
                    })
            elif self.system == "Linux":
                # Fallback for Linux - simplified
                gpus_data.append({"الاسم": "جاري البحث في Linux...", "الحالة": "متاح"})

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

        if self.system == "Windows" and self.w:
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
                except Exception:
                    cycle_count = "غير مدعوم"

                battery_data = {
                    "السعة التصميمية": f"{design_capacity} mWh",
                    "السعة الحالية": f"{full_capacity} mWh",
                    "مستوى التآكل": f"{wear_level:.2f}%",
                    "عدد دورات الشحن": cycle_count,
                    "الحالة": "ممتازة 🟢" if wear_level < 15 else "جيدة 🟡" if wear_level < 30 else "متوسطة 🟠" if wear_level < 50 else "سيئة - يُنصح بالاستبدال 🔴"
                }
                return battery_data
            except Exception:
                pass

        # Fallback for Linux or Windows failure
        batt = psutil.sensors_battery()
        if batt:
            battery_data = {
                "النسبة المئوية": f"{batt.percent}%",
                "حالة الشحن": "يشحن" if batt.power_plugged else "تفريغ",
                "الوقت المتبقي": f"{batt.secsleft // 60} دقيقة" if batt.secsleft != -1 and batt.secsleft is not None else "غير معروف"
            }
        return battery_data

    def get_storage_info(self):
        """جمع معلومات وحدات التخزين وصحتها"""
        disks_info = []

        if self.system == "Windows" and self.w:
            try:
                for disk in self.w.Win32_DiskDrive():
                    status = disk.Status
                    size_gb = int(disk.Size) / (1024**3)
                    disks_info.append({
                        "الموديل": disk.Model,
                        "الحجم": f"{size_gb:.2f} GB",
                        "النوع": "NVMe/SSD" if "SSD" in disk.Model or "NVMe" in disk.Model else "HDD",
                        "الحالة الصحية": "سليم" if status == "OK" else "تحتاج فحص"
                    })
                return disks_info
            except Exception:
                pass

        # Fallback / Linux
        try:
            partitions = psutil.disk_partitions()
            for partition in partitions:
                if 'cdrom' in partition.opts or partition.fstype == '':
                    continue
                usage = psutil.disk_usage(partition.mountpoint)
                disks_info.append({
                    "الموديل": partition.device,
                    "الحجم": f"{usage.total / (1024**3):.2f} GB",
                    "النوع": "مجهول",
                    "الحالة الصحية": "سليم (برمجياً)"
                })
        except Exception:
            pass

        return disks_info

    def get_temperature_info(self):
        """جلب درجات الحرارة الحالية"""
        temps = {"CPU": "غير مدعوم", "GPU": "غير مدعوم"}

        if self.system == "Windows" and self.w:
            try:
                w_wmi = wmi.WMI(namespace="root\\wmi")
                t = w_wmi.MSAcpi_ThermalZoneTemperature()[0].CurrentTemperature
                temps["CPU"] = f"{(t / 10.0) - 273.15:.1f} °C"
            except Exception:
                pass

        # Linux thermal or PSUtil fallback
        if temps["CPU"] == "غير مدعوم":
            try:
                ps_temps = psutil.sensors_temperatures()
                if ps_temps:
                    # Try to find common CPU thermal zones
                    for name, entries in ps_temps.items():
                        if name in ['coretemp', 'cpu_thermal', 'k10temp']:
                            temps["CPU"] = f"{entries[0].current} °C"
                            break
                    if temps["CPU"] == "غير مدعوم":
                        first_key = list(ps_temps.keys())[0]
                        temps["CPU"] = f"{ps_temps[first_key][0].current} °C"
            except Exception:
                pass

        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                temps["GPU"] = f"{gpus[0].temperature} °C"
        except Exception:
            pass

        return temps



TRANSLATIONS = {
    'ar': {
        'title': 'فاحص اللابتوب الاحترافي',
        'header': 'أداة فحص الكمبيوتر الشاملة',
        'tab_hardware': 'المواصفات العتادية',
        'tab_health': 'الصحة والتخزين',
        'tab_battery': 'البطارية',
        'tab_thermal': 'الحرارة والضغط',
        'tab_network': 'الشبكة',
        'speed_test': 'بدء اختبار السرعة',
        'testing_speed': 'جاري الفحص...',
        'download': 'تحميل',
        'upload': 'رفع',
        'cpu_info': '[ معلومات المعالج ]',
        'ram_info': '[ الذاكرة العشوائية ]',
        'gpu_info': '[ كرت الشاشة ]',
        'storage_info': '[ أقراص التخزين والحالة ]',
        'refresh': 'تحديث البيانات',
        'export': 'تصدير التقرير',
        'export_pdf': 'تصدير PDF',
        'dead_pixel': 'فحص البكسلات الميتة',
'speaker_test': 'فحص السماعات',
        'keyboard_test': 'فحص لوحة المفاتيح',
        'camera_test': 'فحص الكاميرا',
        'loading': 'جاري التحميل...',
        'cpu_name': 'الاسم',
        'cpu_freq': 'التردد',
        'cpu_cores': 'الأنوية',
        'real': 'حقيقية',
        'logical': 'منطقية',
        'ram_total': 'الإجمالي',
        'ram_used': 'المستخدم',
        'ram_avail': 'المتاح',
        'ram_percent': 'الاستهلاك',
        'gpu_name': 'الاسم',
        'gpu_mem': 'الذاكرة',
        'batt_checking': 'جاري فحص البطارية...',
        'thermal_current': '[ درجات الحرارة الحالية ]',
        'stress_test': 'بدء اختبار ضغط (30 ثانية)',
        'stressing': 'جاري الاختبار...',
        'stress_done': 'بدء اختبار ضغط (30 ثانية)',
        'report_success': 'تم تصدير التقرير بنجاح!',
        'lang_toggle': 'English'
    },
    'en': {
        'title': 'Professional Laptop Inspector',
        'header': 'Comprehensive Computer Inspection Tool',
        'tab_hardware': 'Hardware Specs',
        'tab_health': 'Health & Storage',
        'tab_battery': 'Battery',
        'tab_thermal': 'Thermal & Stress',
        'tab_network': 'Network',
        'speed_test': 'Start Speed Test',
        'testing_speed': 'Testing...',
        'download': 'Download',
        'upload': 'Upload',
        'cpu_info': '[ CPU Information ]',
        'ram_info': '[ RAM Information ]',
        'gpu_info': '[ GPU Information ]',
        'storage_info': '[ Storage Drives & Status ]',
        'refresh': 'Refresh Data',
        'export': 'Export Report',
        'export_pdf': 'Export PDF',
        'dead_pixel': 'Dead Pixel Test',
'speaker_test': 'Speaker Test',
        'keyboard_test': 'Keyboard Test',
        'camera_test': 'Camera Test',
        'loading': 'Loading...',
        'cpu_name': 'Name',
        'cpu_freq': 'Frequency',
        'cpu_cores': 'Cores',
        'real': 'Real',
        'logical': 'Logical',
        'ram_total': 'Total',
        'ram_used': 'Used',
        'ram_avail': 'Available',
        'ram_percent': 'Usage',
        'gpu_name': 'Name',
        'gpu_mem': 'Memory',
        'batt_checking': 'Checking battery...',
        'thermal_current': '[ Current Temperatures ]',
        'stress_test': 'Start Stress Test (30s)',
        'stressing': 'Testing...',
        'stress_done': 'Start Stress Test (30s)',
        'report_success': 'Report exported successfully!',
        'lang_toggle': 'العربية'
    }
}


class LaptopInspectorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.scanner = SystemScanner()
        self.lang = "ar"

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
        self.tab_network = self.tabview.add("الشبكة")

        self.setup_hardware_tab()
        self.setup_health_tab()
        self.setup_battery_tab()
        self.setup_thermal_tab()
        self.setup_network_tab()

        # الشريط السفلي (الأزرار العامة)
        self.footer_frame = ctk.CTkFrame(self, height=60, corner_radius=0)
        self.footer_frame.grid(row=2, column=0, sticky="nsew", padx=0, pady=0)

        self.btn_refresh = ctk.CTkButton(self.footer_frame, text="تحديث البيانات", command=self.refresh_all, fg_color="green", hover_color="#006400")
        self.btn_refresh.pack(side="right", padx=20, pady=15)

        self.btn_export = ctk.CTkButton(self.footer_frame, text="تصدير التقرير", command=self.export_report)
        self.btn_pdf = ctk.CTkButton(self.footer_frame, text="Export PDF", command=self.export_pdf, fg_color="#C0392B")
        self.btn_pdf.pack(side="right", padx=10, pady=15)
        self.btn_theme = ctk.CTkButton(self.footer_frame, text="🌙", width=50, command=self.toggle_theme, fg_color="#34495E")
        self.btn_theme.pack(side="left", padx=10, pady=15)
        self.btn_export.pack(side="right", padx=10, pady=15)

        self.btn_dead_pixel = ctk.CTkButton(self.footer_frame, text="فحص البكسلات الميتة", command=self.open_dead_pixel_test, fg_color="purple")
        self.btn_dead_pixel.pack(side="left", padx=20, pady=15)

        self.btn_lang = ctk.CTkButton(self.footer_frame, text="English", command=self.toggle_language, fg_color="gray")
        self.btn_lang.pack(side="left", padx=10, pady=15)
        self.btn_speaker = ctk.CTkButton(self.footer_frame, text="Speaker Test", command=self.open_speaker_test, fg_color="#E67E22")
        self.btn_speaker.pack(side="left", padx=10, pady=15)

        self.btn_keyboard = ctk.CTkButton(self.footer_frame, text="Keyboard Test", command=self.open_keyboard_test, fg_color="#27AE60")
        self.btn_keyboard.pack(side="left", padx=10, pady=15)

        self.btn_camera = ctk.CTkButton(self.footer_frame, text="Camera Test", command=self.open_camera_test, fg_color="#2980B9")
        self.btn_camera.pack(side="left", padx=10, pady=15)


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


    def setup_network_tab(self):
        self.tab_network.grid_columnconfigure(0, weight=1)
        self.speed_btn = ctk.CTkButton(self.tab_network, text="Start Speed Test", command=self.run_speed_test)
        self.speed_btn.pack(pady=20)

        self.speed_label = ctk.CTkLabel(self.tab_network, text="-- Mbps", font=self.data_font)
        self.speed_label.pack(pady=10)

    def run_speed_test(self):
        t = TRANSLATIONS[self.lang]
        self.speed_btn.configure(state="disabled", text=t['testing_speed'])
        threading.Thread(target=self._speed_worker, daemon=True).start()

    def _speed_worker(self):
        try:
            import speedtest
            st = speedtest.Speedtest()
            st.get_best_server()
            download = st.download() / 1_000_000
            upload = st.upload() / 1_000_000
            t = TRANSLATIONS[self.lang]
            self.after(0, lambda: self.speed_label.configure(text=f"{t['download']}: {download:.2f} Mbps | {t['upload']}: {upload:.2f} Mbps"))
        except Exception as e:
            self.after(0, lambda: self.speed_label.configure(text=f"Error: {e}"))
        finally:
            t = TRANSLATIONS[self.lang]
            self.after(0, lambda: self.speed_btn.configure(state="normal", text=t['speed_test']))

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

        self.temp_history = {'CPU': [], 'GPU': []}
        self.fig, self.ax = plt.subplots(figsize=(5, 3), dpi=100)
        self.ax.set_title("Temperature History")
        self.canvas_graph = FigureCanvasTkAgg(self.fig, master=self.tab_thermal)
        self.canvas_graph.get_tk_widget().pack(pady=10, fill='both', expand=True)




    def toggle_theme(self):
        current_mode = ctk.get_appearance_mode()
        new_mode = "Light" if current_mode == "Dark" else "Dark"
        ctk.set_appearance_mode(new_mode)
        self.btn_theme.configure(text="☀️" if new_mode == "Light" else "🌙")

    def toggle_language(self):
        self.lang = 'en' if self.lang == 'ar' else 'ar'
        self.update_ui_text()
        self.refresh_all()

    def update_ui_text(self):
        t = TRANSLATIONS[self.lang]
        self.title(t['title'])
        self.title_label.configure(text=t['header'])

        # Tabview tab names update is tricky in ctk, might need to re-add them or just update internal labels
        # For now, let's update the buttons and labels we can easily access
        self.btn_refresh.configure(text=t['refresh'])
        self.btn_export.configure(text=t['export'])
        self.btn_pdf.configure(text=t['export_pdf'])
        self.btn_dead_pixel.configure(text=t['dead_pixel'])
        self.btn_lang.configure(text=t['lang_toggle'])

        self.cpu_frame.configure(text=t['cpu_info'])
        self.ram_frame.configure(text=t['ram_info'])
        self.gpu_frame.configure(text=t['gpu_info'])
        self.storage_label.configure(text=t['storage_info'])
        self.temp_label.configure(text=t['thermal_current'])
        self.stress_btn.configure(text=t['stress_test'])

        self.btn_speaker.configure(text=t['speaker_test'])
        self.btn_keyboard.configure(text=t['keyboard_test'])
        self.btn_camera.configure(text=t['camera_test'])


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
            gpu_text += f"الاسم: {g.get('الاسم')}\nالذاكرة: {g.get('الذاكرة الكلية', 'N/A')}\n---\n"
        self.gpu_data_label.configure(text=gpu_text)

        # Storage
        disks = self.scanner.get_storage_info()
        self.storage_data_box.delete("1.0", "end")
        for d in disks:
            self.storage_data_box.insert("end", f"الموديل: {d['الموديل']}\nالحجم: {d['الحجم']}\nالنوع: {d.get('النوع', 'N/A')}\nالحالة: {d.get('الحالة الصحية', 'N/A')}\n" + "="*30 + "\n")

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


    def _update_graph(self):
        self.ax.clear()
        self.ax.plot(self.temp_history['CPU'], label='CPU', color='red')
        self.ax.plot(self.temp_history['GPU'], label='GPU', color='blue')
        self.ax.legend()
        self.ax.set_ylabel('Temp °C')
        self.canvas_graph.draw()

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
            self.after(0, lambda t=temps: self.temp_data_label.configure(text=f"CPU: {t['CPU']} | GPU: {t['GPU']} (جاري الضغط)"))

            # Update Graph
            cpu_temp = float(temps['CPU'].replace(' °C', '')) if '°C' in temps['CPU'] else 0
            gpu_temp = float(temps['GPU'].replace(' °C', '')) if '°C' in temps['GPU'] else 0
            self.temp_history['CPU'].append(cpu_temp)
            self.temp_history['GPU'].append(gpu_temp)

            self.after(0, self._update_graph)

            time.sleep(1)

        for t in threads:
            t.join()

        self.stress_progress.set(1)
        self.stress_btn.configure(state="normal", text="بدء اختبار ضغط (30 ثانية)")
        self.refresh_all()


    def export_pdf(self):
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter

            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            if not os.path.exists(desktop):
                desktop = os.path.expanduser("~")

            report_path = os.path.join(desktop, "Laptop_Report.pdf")
            c = canvas.Canvas(report_path, pagesize=letter)
            width, height = letter

            c.setFont("Helvetica-Bold", 16)
            c.drawString(50, height - 50, "Professional Laptop Inspection Report")

            c.setFont("Helvetica", 12)
            c.drawString(50, height - 80, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            y = height - 120

            sections = [
                ("CPU", self.scanner.get_cpu_info()),
                ("RAM", self.scanner.get_ram_info()),
                ("Battery", self.scanner.get_battery_info()),
            ]

            for section_name, data in sections:
                c.setFont("Helvetica-Bold", 14)
                c.drawString(50, y, f"[{section_name}]")
                y -= 20
                c.setFont("Helvetica", 10)
                for k, v in data.items():
                    c.drawString(70, y, f"{k}: {v}")
                    y -= 15
                y -= 10

            c.save()
            t = TRANSLATIONS[self.lang]
            self.title_label.configure(text=t['report_success'], text_color="green")
            self.after(3000, lambda: self.title_label.configure(text=t['header'], text_color="white"))
        except Exception as e:
            print(f"Error exporting PDF: {e}")

    def export_report(self):
        """تصدير تقرير شامل إلى سطح المكتب"""
        try:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            if not os.path.exists(desktop):
                desktop = os.path.expanduser("~")

            report_path = os.path.join(desktop, "Laptop_Report_Arabic.txt")

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
                for g in gpu: f.write(f"الاسم: {g.get('الاسم')}\nالذاكرة: {g.get('الذاكرة الكلية', 'N/A')}\n---\n")

                f.write("\n[ الذاكرة العشوائية ]\n")
                for k, v in ram.items(): f.write(f"{k}: {v}\n")

                f.write("\n[ حالة البطارية ]\n")
                for k, v in batt.items(): f.write(f"{k}: {v}\n")

                f.write("\n[ وحدات التخزين ]\n")
                for d in disks: f.write(f"الموديل: {d['الموديل']} | الحجم: {d['الحجم']} | الحالة: {d.get('الحالة الصحية', 'N/A')}\n")

                f.write("\n" + "="*50 + "\n")
                f.write("تم إنشاء هذا التقرير بواسطة أداة فحص اللابتوب الاحترافية\n")

            # عرض رسالة نجاح (مبسطة)
            self.title_label.configure(text=f"تم تصدير التقرير بنجاح!", text_color="green")
            self.after(3000, lambda: self.title_label.configure(text="أداة فحص الكمبيوتر الشاملة", text_color="white"))
        except Exception as e:
            print(f"Error exporting report: {e}")



    def open_speaker_test(self):
        # Implementation for speaker test
        import math
        if self.lang == 'ar':
            title = "فحص السماعات - اضغط على الأزرار لتشغيل صوت"
        else:
            title = "Speaker Test - Press buttons to play sound"

        test_window = ctk.CTkToplevel(self)
        test_window.title(title)
        test_window.geometry("400x300")

        def play_freq(freq):
            if platform.system() == "Windows":
                try:
                    import winsound
                    winsound.Beep(freq, 500)
                except Exception: pass
            else:
                # Linux fallback: a bit harder without extra libs, just print for now
                print(f"Playing frequency {freq}Hz")

        ctk.CTkButton(test_window, text="440Hz (A4)", command=lambda: play_freq(440)).pack(pady=10)
        ctk.CTkButton(test_window, text="880Hz (A5)", command=lambda: play_freq(880)).pack(pady=10)
        ctk.CTkButton(test_window, text="1760Hz (A6)", command=lambda: play_freq(1760)).pack(pady=10)

    def open_keyboard_test(self):
        if self.lang == 'ar':
            title = "فحص لوحة المفاتيح - اضغط على أي مفتاح"
        else:
            title = "Keyboard Test - Press any key"

        test_window = ctk.CTkToplevel(self)
        test_window.title(title)
        test_window.geometry("600x400")

        key_label = ctk.CTkLabel(test_window, text="Press a key...", font=("Arial", 30))
        key_label.pack(expand=True)

        def on_key(event):
            key_label.configure(text=f"Key Pressed: {event.keysym}")

        test_window.bind("<Key>", on_key)

    def open_camera_test(self):
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                raise Exception("Could not open camera")

            def show_frame():
                ret, frame = cap.read()
                if ret:
                    cv2.imshow('Camera Test (Press Q to exit)', frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        cap.release()
                        cv2.destroyAllWindows()
                        return
                    self.after(10, show_frame)
                else:
                    cap.release()
                    cv2.destroyAllWindows()

            show_frame()
        except Exception as e:
            if self.lang == 'ar':
                err = f"خطأ في فتح الكاميرا: {e}"
            else:
                err = f"Error opening camera: {e}"
            print(err)

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
