import os
import sys
import tkinter as tk
from tkinter import filedialog, ttk, messagebox, colorchooser
from PIL import Image, ImageDraw, ImageFont, ImageTk
import piexif
from matplotlib.font_manager import findSystemFonts, FontProperties, findfont
from tkinterdnd2 import DND_FILES, TkinterDnD

# 核心函数
def get_exif_date(img_path):
    try:
        exif_dict = piexif.load(img_path)
        date_str = exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal].decode()
        date = date_str.split(' ')[0].replace(':', '.')
        return date
    except Exception:
        return None

def add_watermark(img_path, text, font_path, font_size, color, alpha, pos_x, pos_y, style, outline_color):
    """
    为图片添加水印的核心函数。
    - 修复了文件句柄未释放导致多次保存失败的Bug。
    """
    exif_data = None
    is_jpg = img_path.lower().endswith((".jpg", ".jpeg"))
    is_png = img_path.lower().endswith(".png")
    # 仅对jpeg/jpg文件尝试加载EXIF信息
    if is_jpg:
        try:
            exif_data = piexif.load(img_path)
        except Exception as e:
            print(f"警告：无法加载 {os.path.basename(img_path)} 的EXIF信息: {e}")

    # --- 核心修复：使用 with 语句确保文件句柄被正确关闭 ---
    with Image.open(img_path) as img_file:
        img = img_file.convert("RGBA")

    width, height = img.size

    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        font = ImageFont.load_default()

    txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(txt_layer)

    fill_color = color + (int(alpha * 255 / 100),)

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    if pos_x == -1: # 居中
        x = (width - text_w) // 2
    elif pos_x == -2: # 靠右
        x = width - text_w - 10
    else: # 左对齐或手动拖拽的绝对坐标
        x = pos_x

    if pos_y == -1: # 居中
        y = (height - text_h) // 2
    elif pos_y == -2: # 靠下
        y = height - text_h - 10
    else: # 靠上或手动拖拽的绝对坐标
        y = pos_y

    pos = (x, y)

    if style == "阴影":
        shadow_pos = (pos[0] + 2, pos[1] + 2)
        draw.text(shadow_pos, text, font=font, fill=(0, 0, 0, 128))

    elif style == "描边":
        outline_fill = outline_color + (int(alpha * 255 / 100),)
        for x_offset in [-1, 0, 1]:
            for y_offset in [-1, 0, 1]:
                if x_offset == 0 and y_offset == 0:
                    continue
                outline_pos = (pos[0] + x_offset, pos[1] + y_offset)
                draw.text(outline_pos, text, font=font, fill=outline_fill)

    draw.text(pos, text, font=font, fill=fill_color)
    watermarked_img = Image.alpha_composite(img, txt_layer)

    # PNG 保留透明通道，JPG转为RGB
    if is_png:
        final_img = watermarked_img  # 保持RGBA
        final_exif_bytes = None      # PNG不支持EXIF
    else:
        final_img = watermarked_img.convert("RGB")
        final_exif_bytes = b''
        if exif_data:
            try:
                final_exif_bytes = piexif.dump(exif_data)
            except Exception as e:
                print(f"警告：无法打包 {os.path.basename(img_path)} 的EXIF信息: {e}")

    # 返回处理后的图片和EXIF数据
    return final_img, final_exif_bytes

import json
from tkinter import simpledialog

class WatermarkApp:
    def __init__(self, root):
        self.root = root
        self.root.title("图片水印工具")

        self.settings_file = "watermark_templates.json"
        self.templates = {}

        self.image_paths = []
        self.image_settings = {}
        self.thumbnails = []
        self.output_dir = tk.StringVar(value="")
        self.input_dir = ""
        self.current_preview_image = None
        self.active_index = None
        self.text_color = tk.StringVar(value="255,255,255")
        self.outline_color = tk.StringVar(value="0,0,0")
        self.position_x = 10
        self.position_y = 10
        self.drag_start_x = 0
        self.drag_start_y = 0
        self._loading_settings = False

        self.create_widgets()

        # --- 修改后的启动加载顺序 ---
        self._load_templates_from_file()
        self._ensure_default_template_exists()  # 确保默认模板存在
        self._populate_template_combo()
        self._load_startup_settings()           # 加载启动设置（上次会话或默认）

        self.list_preview_frame.drop_target_register(DND_FILES)
        self.list_preview_frame.dnd_bind('<<Drop>>', self.handle_dnd)
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def create_widgets(self):
        # 此方法无需改动，请保留您原来的代码
        # (为了简洁，这里省略)
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)
        ttk.Button(top_frame, text="选择图片/文件夹", command=self.select_files).pack(side=tk.LEFT, padx=5)
        output_frame = ttk.Frame(self.root, padding="10")
        output_frame.pack(fill=tk.X)
        ttk.Label(output_frame, text="输出文件夹:").pack(side=tk.LEFT, padx=(5, 0))
        ttk.Entry(output_frame, textvariable=self.output_dir, state="readonly", width=40).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        ttk.Button(output_frame, text="浏览...", command=self.select_output_dir).pack(side=tk.LEFT, padx=5)
        self.list_preview_frame = ttk.Frame(self.root, padding="10")
        self.list_preview_frame.pack(fill=tk.BOTH, expand=True)
        self.file_listbox = tk.Listbox(self.list_preview_frame, height=10, width=50, selectmode=tk.SINGLE)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.preview_label = ttk.Label(self.list_preview_frame)
        self.preview_label.pack(side=tk.RIGHT, padx=10, expand=True)
        self.preview_label.bind("<Button-1>", self.on_drag_start)
        self.preview_label.bind("<B1-Motion>", self.on_drag)
        options_frame = ttk.Frame(self.root, padding="10")
        options_frame.pack(fill=tk.X)
        ttk.Label(options_frame, text="水印文本:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.text_entry = ttk.Entry(options_frame, width=30)
        self.text_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Button(options_frame, text="使用拍摄日期", command=self.use_exif_date).grid(row=0, column=2, padx=5, pady=5)
        ttk.Label(options_frame, text="字体:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.font_names = self.get_font_names()
        self.font_combo = ttk.Combobox(options_frame, values=self.font_names, width=28)
        self.font_combo.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        self.font_combo.set("Arial")
        ttk.Label(options_frame, text="大小:").grid(row=1, column=2, padx=5, pady=5, sticky=tk.W)
        self.font_size_entry = ttk.Entry(options_frame, width=5)
        self.font_size_entry.grid(row=1, column=3, padx=5, pady=5, sticky=tk.W)
        self.font_size_entry.insert(0, "36")
        ttk.Label(options_frame, text="颜色:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        color_frame = ttk.Frame(options_frame)
        color_frame.grid(row=2, column=1, columnspan=3, padx=5, pady=5, sticky=tk.W)
        ttk.Button(color_frame, text="文本颜色", command=self.choose_color).pack(side=tk.LEFT)
        ttk.Button(color_frame, text="描边颜色", command=self.choose_outline_color).pack(side=tk.LEFT, padx=5)
        ttk.Label(color_frame, text="透明度:").pack(side=tk.LEFT, padx=(10, 5))
        self.alpha_scale = ttk.Scale(color_frame, from_=0, to=100, orient=tk.HORIZONTAL)
        self.alpha_scale.set(80)
        self.alpha_scale.pack(side=tk.LEFT)
        ttk.Label(options_frame, text="位置:").grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
        position_grid_frame = ttk.Frame(options_frame)
        position_grid_frame.grid(row=3, column=1, padx=5, pady=5, columnspan=2, sticky=tk.W)
        ttk.Button(position_grid_frame, text="↖", width=3, command=lambda: self.set_position("左上角")).grid(row=0, column=0)
        ttk.Button(position_grid_frame, text="↑", width=3, command=lambda: self.set_position("中上")).grid(row=0, column=1)
        ttk.Button(position_grid_frame, text="↗", width=3, command=lambda: self.set_position("右上")).grid(row=0, column=2)
        ttk.Button(position_grid_frame, text="←", width=3, command=lambda: self.set_position("左中")).grid(row=1, column=0)
        ttk.Button(position_grid_frame, text="●", width=3, command=lambda: self.set_position("中间")).grid(row=1, column=1)
        ttk.Button(position_grid_frame, text="→", width=3, command=lambda: self.set_position("右中")).grid(row=1, column=2)
        ttk.Button(position_grid_frame, text="↙", width=3, command=lambda: self.set_position("左下")).grid(row=2, column=0)
        ttk.Button(position_grid_frame, text="↓", width=3, command=lambda: self.set_position("中下")).grid(row=2, column=1)
        ttk.Button(position_grid_frame, text="↘", width=3, command=lambda: self.set_position("右下")).grid(row=2, column=2)
        ttk.Label(options_frame, text="样式:").grid(row=4, column=0, padx=5, pady=5, sticky=tk.W)
        self.style_combo = ttk.Combobox(options_frame, values=["无", "阴影", "描边"], width=10)
        self.style_combo.grid(row=4, column=1, padx=5, pady=5, sticky=tk.W)
        self.style_combo.set("无")
        output_settings_frame = ttk.Frame(self.root, padding="10")
        output_settings_frame.pack(fill=tk.X)
        ttk.Label(output_settings_frame, text="输出格式:").pack(side=tk.LEFT, padx=5)
        self.format_combo = ttk.Combobox(output_settings_frame, values=["JPG", "PNG"], width=8)
        self.format_combo.set("JPG")
        self.format_combo.pack(side=tk.LEFT, padx=5)
        ttk.Label(output_settings_frame, text="命名规则:").pack(side=tk.LEFT, padx=5)
        self.naming_combo = ttk.Combobox(output_settings_frame, values=["保持原名", "添加前缀", "添加后缀"], width=12)
        self.naming_combo.set("保持原名")
        self.naming_combo.pack(side=tk.LEFT, padx=5)
        self.naming_combo.bind("<<ComboboxSelected>>", self.toggle_prefix_entry)
        self.prefix_entry = ttk.Entry(output_settings_frame, width=15, state="disabled")
        self.prefix_entry.pack(side=tk.LEFT, padx=5)
        template_frame = ttk.LabelFrame(self.root, text="模板管理", padding="10")
        template_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(template_frame, text="选择模板:").pack(side=tk.LEFT, padx=5)
        self.template_combo = ttk.Combobox(template_frame, width=25)
        self.template_combo.pack(side=tk.LEFT, padx=5)
        self.template_combo.bind("<<ComboboxSelected>>", self._load_template)
        ttk.Button(template_frame, text="保存当前模板", command=self._save_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(template_frame, text="删除选中模板", command=self._delete_template).pack(side=tk.LEFT, padx=5)
        bottom_frame = ttk.Frame(self.root, padding="10")
        bottom_frame.pack(fill=tk.X)
        ttk.Button(bottom_frame, text="应用水印", command=self.apply_watermarks).pack()
        self.text_entry.bind("<KeyRelease>", self.update_preview)
        self.font_combo.bind("<<ComboboxSelected>>", self.update_preview)
        self.font_size_entry.bind("<KeyRelease>", self.update_preview)
        self.style_combo.bind("<<ComboboxSelected>>", self.update_preview)
        self.alpha_scale.config(command=self.update_preview)
        self.file_listbox.bind("<<ListboxSelect>>", self.show_thumbnail)


    # --- 新增和修改的核心方法 ---

    def _ensure_default_template_exists(self):
        """新增：检查并创建默认模板。"""
        template_name = "默认模板 (右下角阴影)"
        if template_name not in self.templates:
            print(f"未找到默认模板，正在创建 '{template_name}'...")
            default_settings = {
                "text": "© Your Name",
                "font_name": "Arial",
                "font_size": 24,
                "text_color": "255,255,255",
                "outline_color": "0,0,0",
                "alpha": 80.0,
                "style": "阴影",
                "pos_x": -2,  # 右对齐
                "pos_y": -2   # 底对齐
            }
            self.templates[template_name] = default_settings
            # 创建后立即保存一次，确保它持久化
            self._save_templates_to_file()

    def _load_startup_settings(self):
        """修改：加载启动设置，优先加载上次会话，否则加载默认模板。"""
        last_session_settings = self.templates.get("__last_session__")
        if last_session_settings:
            print("加载上次会话的设置...")
            self._apply_settings_to_ui(last_session_settings)
        else:
            print("未找到上次会话的设置，加载默认模板...")
            default_template_settings = self.templates.get("默认模板 (右下角阴影)")
            if default_template_settings:
                self._apply_settings_to_ui(default_template_settings)

    # _load_last_session_settings 方法已被上面的 _load_startup_settings 替代

    # --- 以下是您原有的模板管理和辅助方法，保持不变 ---
    def _on_close(self):
        print("正在保存上次会话的设置..."); last_settings = self._get_current_ui_settings(); self.templates["__last_session__"] = last_settings; self._save_templates_to_file(); self.root.destroy()
    def _get_current_ui_settings(self):
        try: font_size = int(self.font_size_entry.get())
        except (ValueError, TypeError): font_size = 36
        return {"text": self.text_entry.get(), "font_name": self.font_combo.get(), "font_size": font_size, "text_color": self.text_color.get(), "outline_color": self.outline_color.get(), "alpha": self.alpha_scale.get(), "style": self.style_combo.get(), "pos_x": self.position_x, "pos_y": self.position_y}
    def _apply_settings_to_ui(self, settings):
        self._loading_settings = True
        self.text_entry.delete(0, tk.END); self.text_entry.insert(0, settings.get("text", ""))
        self.font_combo.set(settings.get("font_name", "Arial")); self.font_size_entry.delete(0, tk.END); self.font_size_entry.insert(0, str(settings.get("font_size", 36)))
        self.text_color.set(settings.get("text_color", "255,255,255")); self.outline_color.set(settings.get("outline_color", "0,0,0")); self.alpha_scale.set(settings.get("alpha", 80.0)); self.style_combo.set(settings.get("style", "无"))
        self.position_x = settings.get("pos_x", 10); self.position_y = settings.get("pos_y", 10)
        self._loading_settings = False
        if self.active_index is not None: self.save_current_settings(); self.update_preview()
    def _load_templates_from_file(self):
        try:
            with open(self.settings_file, 'r', encoding='utf-8') as f: self.templates = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError): self.templates = {}
    def _save_templates_to_file(self):
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f: json.dump(self.templates, f, indent=4, ensure_ascii=False)
        except Exception as e: print(f"保存模板失败: {e}")
    def _populate_template_combo(self):
        template_names = [name for name in self.templates.keys() if name != "__last_session__"]; self.template_combo['values'] = sorted(template_names); self.template_combo.set("")
    def _save_template(self):
        template_name = simpledialog.askstring("保存模板", "请输入模板名称:", parent=self.root)
        if template_name:
            if template_name == "__last_session__": messagebox.showerror("错误", "该名称为内部保留，请使用其他名称。"); return
            if template_name in self.templates and not messagebox.askyesno("确认", f"模板 '{template_name}' 已存在，要覆盖吗？"): return
            current_settings = self._get_current_ui_settings(); self.templates[template_name] = current_settings; self._save_templates_to_file(); self._populate_template_combo(); self.template_combo.set(template_name); messagebox.showinfo("成功", f"模板 '{template_name}' 已保存。")
    def _load_template(self, event=None):
        template_name = self.template_combo.get()
        if template_name and template_name in self.templates:
            settings_to_load = self.templates[template_name]; self._apply_settings_to_ui(settings_to_load); messagebox.showinfo("加载成功", f"已加载模板 '{template_name}'。", parent=self.root)
    def _delete_template(self):
        template_name = self.template_combo.get()
        if not template_name: messagebox.showwarning("提示", "请先在下拉菜单中选择一个要删除的模板。"); return
        if template_name in self.templates:
            if messagebox.askyesno("确认删除", f"确定要删除模板 '{template_name}' 吗？此操作无法撤销。"):
                del self.templates[template_name]; self._save_templates_to_file(); self._populate_template_combo(); messagebox.showinfo("成功", f"模板 '{template_name}' 已删除。")
    def get_default_settings(self): return { "text": "", "font_name": "Arial", "font_size": 36, "text_color": "255,255,255", "outline_color": "0,0,0", "alpha": 80.0, "style": "无", "pos_x": 10, "pos_y": 10 }
    def update_ui_with_files(self):
        self.file_listbox.delete(0, tk.END); self.thumbnails.clear(); self.active_index = None; self.preview_label.config(image=""); self.current_preview_image = None
        if self.input_dir: self.output_dir.set(os.path.join(self.input_dir, os.path.basename(self.input_dir) + "_watermarked"))
        else: self.output_dir.set("")
        current_paths = set(self.image_paths)
        self.image_settings = {path: settings for path, settings in self.image_settings.items() if path in current_paths}
        for i, fpath in enumerate(self.image_paths):
            self.file_listbox.insert(tk.END, os.path.basename(fpath))
            if fpath not in self.image_settings: self.image_settings[fpath] = self.get_default_settings()
            try: img = Image.open(fpath); img.thumbnail((400, 400)); self.thumbnails.append(img)
            except Exception: self.thumbnails.append(None)
        if self.thumbnails: self.file_listbox.selection_set(0); self.show_thumbnail()
    def load_settings_for_image(self, path):
        if path not in self.image_settings: return
        self._loading_settings = True
        settings = self.image_settings[path]
        self.text_entry.delete(0, tk.END); self.text_entry.insert(0, settings["text"])
        self.font_combo.set(settings["font_name"]); self.font_size_entry.delete(0, tk.END); self.font_size_entry.insert(0, str(settings["font_size"]))
        self.text_color.set(settings["text_color"]); self.outline_color.set(settings["outline_color"]); self.alpha_scale.set(settings["alpha"]); self.style_combo.set(settings["style"])
        self.position_x = settings["pos_x"]; self.position_y = settings["pos_y"]
        self._loading_settings = False
    def save_current_settings(self):
        if self._loading_settings or self.active_index is None: return
        path = self.image_paths[self.active_index]
        if path not in self.image_settings: self.image_settings[path] = self.get_default_settings()
        settings = self.image_settings[path]
        settings["text"] = self.text_entry.get(); settings["font_name"] = self.font_combo.get()
        try: settings["font_size"] = int(self.font_size_entry.get())
        except ValueError: pass
        settings["text_color"] = self.text_color.get(); settings["outline_color"] = self.outline_color.get(); settings["alpha"] = self.alpha_scale.get(); settings["style"] = self.style_combo.get()
        settings["pos_x"] = self.position_x; settings["pos_y"] = self.position_y
    def show_thumbnail(self, event=None):
        selected_indices = self.file_listbox.curselection()
        if selected_indices:
            self.active_index = selected_indices[0]; path = self.image_paths[self.active_index]
            self.load_settings_for_image(path); self.update_preview()
    def update_preview(self, event=None):
        if self.active_index is None:
            self.preview_label.config(image="")
            self.current_preview_image = None
            return

        self.save_current_settings()

        original_image_path = self.image_paths[self.active_index]
        settings = self.image_settings.get(original_image_path)
        if not settings: return

        try:
            font_path = self.get_font_path(settings["font_name"])
            text_color = tuple(map(int, settings["text_color"].split(',')))
            outline_color = tuple(map(int, settings["outline_color"].split(',')))
            
            # 如果没有水印文字，直接显示原始缩略图
            if not settings["text"]:
                thumb = self.thumbnails[self.active_index]
                if thumb:
                    self.current_preview_image = ImageTk.PhotoImage(thumb)
                    self.preview_label.config(image=self.current_preview_image)
                return

            # --- 核心修复：正确处理 add_watermark 返回的两个值 ---
            # 我们只需要第一个返回值（图片对象），用 _ 来忽略第二个返回值（EXIF数据）
            watermarked_image, _ = add_watermark(
                original_image_path, 
                settings["text"], 
                font_path, 
                settings["font_size"], 
                text_color, 
                settings["alpha"], 
                settings["pos_x"],
                settings["pos_y"], 
                settings["style"], 
                outline_color
            )
            # --- 修复结束 ---
            
            watermarked_image.thumbnail((400, 400))
            self.current_preview_image = ImageTk.PhotoImage(watermarked_image)
            self.preview_label.config(image=self.current_preview_image)

        except Exception as e:
            # 打印错误有助于调试
            print(f"预览更新失败: {e}")
            # Fallback: 显示原始缩略图
            thumb = self.thumbnails[self.active_index]
            if thumb:
                self.current_preview_image = ImageTk.PhotoImage(thumb)
                self.preview_label.config(image=self.current_preview_image)

    def use_exif_date(self):
        if self.active_index is None: messagebox.showwarning("警告", "请先在列表中选择一张图片。"); return
        fpath = self.image_paths[self.active_index]
        date = get_exif_date(fpath)
        if date: self.text_entry.delete(0, tk.END); self.text_entry.insert(0, date); self.update_preview()
        else: messagebox.showinfo("提示", "所选图片没有拍摄时间信息。")
    def on_drag_start(self, event): self.drag_start_x = event.x; self.drag_start_y = event.y
    def on_drag(self, event):
        if self.active_index is None: return
        try:
            original_img = Image.open(self.image_paths[self.active_index]); original_w, original_h = original_img.size
            preview_w = self.current_preview_image.width(); preview_h = self.current_preview_image.height()
            scale_x = original_w / preview_w; scale_y = original_h / preview_h
            watermark_text = self.text_entry.get(); font_path = self.get_font_path(self.font_combo.get()); font_size = int(self.font_size_entry.get())
            font = ImageFont.truetype(font_path, font_size)
            bbox = ImageDraw.Draw(Image.new("RGBA", (0,0))).textbbox((0,0), watermark_text, font=font)
            text_w = bbox[2] - bbox[0]; text_h = bbox[3] - bbox[1]
        except Exception: return
        dx = (event.x - self.drag_start_x) * scale_x; dy = (event.y - self.drag_start_y) * scale_y
        new_x = self.position_x + dx; new_y = self.position_y + dy
        self.position_x = max(0, min(new_x, original_w - text_w)); self.position_y = max(0, min(new_y, original_h - text_h))
        self.drag_start_x = event.x; self.drag_start_y = event.y
        self.update_preview()
    def get_font_names(self):
        font_paths = findSystemFonts(); font_names = []
        for path in font_paths:
            try: font_name = os.path.basename(path).split(".")[0]; \
                (font_name not in font_names) and font_names.append(font_name)
            except: continue
        font_names.sort(); return font_names
    def get_font_path(self, font_name):
        try: prop = FontProperties(family=font_name); return findfont(prop)
        except Exception: return "arial.ttf"
    def choose_color(self):
        color_code = colorchooser.askcolor(title="选择文本颜色")
        if color_code and color_code[0]: rgb = color_code[0]; self.text_color.set(f"{int(rgb[0])},{int(rgb[1])},{int(rgb[2])}"); self.update_preview()
    def choose_outline_color(self):
        color_code = colorchooser.askcolor(title="选择描边颜色")
        if color_code and color_code[0]: rgb = color_code[0]; self.outline_color.set(f"{int(rgb[0])},{int(rgb[1])},{int(rgb[2])}"); self.update_preview()
    def select_files(self):
        new_paths = []
        mode = messagebox.askyesno("选择", "是否选择一个文件夹？\n\n'是' - 选择文件夹\n'否' - 选择多个图片文件")
        if mode:
            dir_path = filedialog.askdirectory()
            if dir_path:
                self.input_dir = dir_path
                for fname in os.listdir(dir_path):
                    fpath = os.path.join(dir_path, fname)
                    if os.path.isfile(fpath) and fname.lower().endswith(('.jpg', '.jpeg', '.png')): new_paths.append(fpath)
        else:
            file_paths = filedialog.askopenfilenames(filetypes=[("Image files", "*.jpg *.jpeg *.png")])
            if file_paths:
                new_paths.extend(file_paths)
                if len(set(os.path.dirname(p) for p in file_paths)) == 1: self.input_dir = os.path.dirname(file_paths[0])
                else: self.input_dir = None
        if new_paths: self.image_paths = new_paths; self.update_ui_with_files()
    def select_output_dir(self):
        dir_path = filedialog.askdirectory(); dir_path and self.output_dir.set(dir_path)
    def toggle_prefix_entry(self, event=None):
        if self.naming_combo.get() in ["添加前缀", "添加后缀"]: self.prefix_entry.config(state="normal")
        else: self.prefix_entry.config(state="disabled")
    def set_position(self, pos_key):
        if pos_key == "左上角": self.position_x, self.position_y = 10, 10
        elif pos_key == "中上": self.position_x, self.position_y = -1, 10
        elif pos_key == "右上": self.position_x, self.position_y = -2, 10
        elif pos_key == "左中": self.position_x, self.position_y = 10, -1
        elif pos_key == "中间": self.position_x, self.position_y = -1, -1
        elif pos_key == "右中": self.position_x, self.position_y = -2, -1
        elif pos_key == "左下": self.position_x, self.position_y = 10, -2
        elif pos_key == "中下": self.position_x, self.position_y = -1, -2
        elif pos_key == "右下": self.position_x, self.position_y = -2, -2
        self.update_preview()
    def handle_dnd(self, event):
        dropped_paths_str = event.data
        if dropped_paths_str.startswith('{') and dropped_paths_str.endswith('}'): dropped_paths = dropped_paths_str[1:-1].split('} {')
        else: dropped_paths = [dropped_paths_str]
        if not dropped_paths: return
        temp_paths = []
        for path in dropped_paths:
            path = path.strip()
            if os.path.isdir(path):
                self.input_dir = path
                for fname in os.listdir(path):
                    fpath = os.path.join(path, fname)
                    if os.path.isfile(fpath) and fname.lower().endswith(('.jpg', '.jpeg', '.png')): temp_paths.append(fpath)
            elif os.path.isfile(path) and path.lower().endswith(('.jpg', '.jpeg', '.png')):
                temp_paths.append(path)
                if len(set(os.path.dirname(p) for p in dropped_paths)) == 1: self.input_dir = os.path.dirname(dropped_paths[0])
                else: self.input_dir = None
        if temp_paths: self.image_paths = temp_paths; self.update_ui_with_files()
    def apply_watermarks(self):
        if not self.image_paths: messagebox.showwarning("警告", "请先选择图片。"); return
        output_dir = self.output_dir.get()
        if not output_dir: messagebox.showerror("错误", "请指定一个输出文件夹。"); return
        if self.input_dir and os.path.abspath(output_dir) == os.path.abspath(self.input_dir): messagebox.showerror("错误", "输出文件夹不能和原文件夹相同，以防覆盖原图。"); return
        try: output_format = self.format_combo.get().lower(); naming_rule = self.naming_combo.get(); custom_text = self.prefix_entry.get()
        except ValueError: messagebox.showerror("错误", "参数格式不正确。"); return
        os.makedirs(output_dir, exist_ok=True)
        for fpath in self.image_paths:
            fname = os.path.basename(fpath); settings = self.image_settings.get(fpath)
            if not settings or not settings["text"]: print(f"{fname} 水印文本为空或无设置，跳过"); continue
            try:
                final_text = settings["text"]
                if final_text == "使用拍摄日期": date = get_exif_date(fpath); final_text = date if date else ""
                if not final_text: print(f"{fname} 水印文本为空，跳过"); continue
                font_path = self.get_font_path(settings["font_name"]); text_color = tuple(map(int, settings["text_color"].split(','))); outline_color = tuple(map(int, settings["outline_color"].split(',')))
                # add_watermark 现在返回图片和EXIF
                watermarked_img, exif_bytes = add_watermark(fpath, final_text, font_path, settings["font_size"], 
                    text_color, settings["alpha"], settings["pos_x"], 
                    settings["pos_y"], settings["style"], outline_color
                )
                
                base_name, _ = os.path.splitext(fname)
                if naming_rule == "添加前缀":
                    new_fname = f"{custom_text}{base_name}.{output_format}"
                elif naming_rule == "添加后缀":
                    new_fname = f"{base_name}{custom_text}.{output_format}"
                else:
                    new_fname = f"{base_name}.{output_format}"
                
                out_path = os.path.join(output_dir, new_fname)

                # --- 核心修复：根据格式和EXIF数据进行保存 ---
                if output_format.lower() in ['jpg', 'jpeg']:
                    if exif_bytes:
                        watermarked_img.save(out_path, format='jpeg', exif=exif_bytes)
                    else:
                        watermarked_img.save(out_path, format='jpeg')
                elif output_format.lower() == 'png':
                    # PNG 保持RGBA，不能带exif
                    watermarked_img.save(out_path, format='png')
                else:
                    watermarked_img.save(out_path, format=output_format)

                print(f"已保存: {out_path}")
            except Exception as e: print(f"{fname} 处理失败: {e}")
        messagebox.showinfo("完成", f"所有图片处理完毕！\n文件已保存至：{output_dir}")

if __name__ == "__main__":
    # Use TkinterDnD.Tk() for the main window
    root = TkinterDnD.Tk()
    app = WatermarkApp(root)
    root.mainloop()