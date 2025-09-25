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
    img = Image.open(img_path).convert("RGBA")
    width, height = img.size
    
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        font = ImageFont.load_default()

    txt_layer = Image.new("RGBA", img.size, (255,255,255,0))
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
        draw.text(shadow_pos, text, font=font, fill=(0,0,0,128))
    
    elif style == "描边":
        outline_fill = outline_color + (int(alpha * 255 / 100),)
        for x_offset in [-1, 0, 1]:
            for y_offset in [-1, 0, 1]:
                if x_offset == 0 and y_offset == 0:
                    continue
                outline_pos = (pos[0] + x_offset, pos[1] + y_offset)
                draw.text(outline_pos, text, font=font, fill=outline_fill)
                
    draw.text(pos, text, font=font, fill=fill_color)
    watermarked = Image.alpha_composite(img, txt_layer)
    return watermarked.convert("RGB")

class WatermarkApp:
    def __init__(self, root):
        self.root = root
        self.root.title("图片水印工具")
        
        self.image_paths = []
        self.thumbnails = []
        self.output_dir = tk.StringVar(value="")
        self.input_dir = "" 
        self.font_path = tk.StringVar()
        self.text_color = tk.StringVar(value="255,255,255")
        self.outline_color = tk.StringVar(value="0,0,0")
        self.current_preview_image = None
        self.position_x = 10
        self.position_y = 10
        self.drag_start_x = 0
        self.drag_start_y = 0

        self.create_widgets()
        
        # 注册拖放功能
        self.list_preview_frame.drop_target_register(DND_FILES)
        self.list_preview_frame.dnd_bind('<<Drop>>', self.handle_dnd)

    def create_widgets(self):
        # 顶部框架
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)
        ttk.Button(top_frame, text="选择图片/文件夹", command=self.select_files).pack(side=tk.LEFT, padx=5)

        # 输出文件夹
        output_frame = ttk.Frame(self.root, padding="10")
        output_frame.pack(fill=tk.X)
        ttk.Label(output_frame, text="输出文件夹:").pack(side=tk.LEFT, padx=(5, 0))
        ttk.Entry(output_frame, textvariable=self.output_dir, state="readonly", width=40).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        ttk.Button(output_frame, text="浏览...", command=self.select_output_dir).pack(side=tk.LEFT, padx=5)

        # 中间框架
        self.list_preview_frame = ttk.Frame(self.root, padding="10")
        self.list_preview_frame.pack(fill=tk.BOTH, expand=True)

        # 文件列表
        self.file_listbox = tk.Listbox(self.list_preview_frame, height=10, width=50, selectmode=tk.SINGLE)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 预览区域
        self.preview_label = ttk.Label(self.list_preview_frame)
        self.preview_label.pack(side=tk.RIGHT, padx=10, expand=True)
        self.preview_label.bind("<Button-1>", self.on_drag_start)
        self.preview_label.bind("<B1-Motion>", self.on_drag)

        # --- 水印参数设置 ---
        options_frame = ttk.Frame(self.root, padding="10")
        options_frame.pack(fill=tk.X)

        # 水印文本
        ttk.Label(options_frame, text="水印文本:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.text_entry = ttk.Entry(options_frame, width=30)
        self.text_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Button(options_frame, text="使用拍摄日期", command=self.use_exif_date).grid(row=0, column=2, padx=5, pady=5)
        
        # 字体和大小
        ttk.Label(options_frame, text="字体:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.font_combo = ttk.Combobox(options_frame, values=self.get_font_names(), width=28)
        self.font_combo.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        self.font_combo.set("Arial") # Default font
        ttk.Label(options_frame, text="大小:").grid(row=1, column=2, padx=5, pady=5, sticky=tk.W)
        self.font_size_entry = ttk.Entry(options_frame, width=5)
        self.font_size_entry.grid(row=1, column=3, padx=5, pady=5, sticky=tk.W)
        self.font_size_entry.insert(0, "36")

        # 颜色和透明度
        ttk.Label(options_frame, text="颜色:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        color_frame = ttk.Frame(options_frame)
        color_frame.grid(row=2, column=1, columnspan=3, padx=5, pady=5, sticky=tk.W)
        ttk.Button(color_frame, text="文本颜色", command=self.choose_color).pack(side=tk.LEFT)
        ttk.Button(color_frame, text="描边颜色", command=self.choose_outline_color).pack(side=tk.LEFT, padx=5)
        ttk.Label(color_frame, text="透明度:").pack(side=tk.LEFT, padx=(10, 5))
        self.alpha_scale = ttk.Scale(color_frame, from_=0, to=100, orient=tk.HORIZONTAL)
        self.alpha_scale.set(80)
        self.alpha_scale.pack(side=tk.LEFT)

        # 位置和样式
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
        
        # --- 输出设置 ---
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

        # 底部执行按钮
        bottom_frame = ttk.Frame(self.root, padding="10")
        bottom_frame.pack(fill=tk.X)
        ttk.Button(bottom_frame, text="应用水印", command=self.apply_watermarks).pack()

        # --- !! CORRECTED: BIND EVENTS AFTER WIDGETS ARE CREATED !! ---
        self.text_entry.bind("<KeyRelease>", self.update_preview)
        self.font_combo.bind("<<ComboboxSelected>>", self.update_preview)
        self.font_size_entry.bind("<KeyRelease>", self.update_preview)
        self.style_combo.bind("<<ComboboxSelected>>", self.update_preview)
        self.alpha_scale.config(command=self.update_preview)
        self.file_listbox.bind("<<ListboxSelect>>", self.show_thumbnail)


    def set_position(self, pos_key):
        if pos_key == "左上角":
            self.position_x, self.position_y = 10, 10
        elif pos_key == "中上":
            self.position_x, self.position_y = -1, 10
        elif pos_key == "右上":
            self.position_x, self.position_y = -2, 10
        elif pos_key == "左中":
            self.position_x, self.position_y = 10, -1
        elif pos_key == "中间":
            self.position_x, self.position_y = -1, -1
        elif pos_key == "右中":
            self.position_x, self.position_y = -2, -1
        elif pos_key == "左下":
            self.position_x, self.position_y = 10, -2
        elif pos_key == "中下":
            self.position_x, self.position_y = -1, -2
        elif pos_key == "右下":
            self.position_x, self.position_y = -2, -2
        self.update_preview()

    def handle_dnd(self, event):
        # tkinterdnd2 returns a string of file paths
        dropped_paths_str = event.data
        # Remove curly braces and split if multiple files
        if dropped_paths_str.startswith('{') and dropped_paths_str.endswith('}'):
            dropped_paths = dropped_paths_str[1:-1].split('} {')
        else:
            dropped_paths = [dropped_paths_str]

        if not dropped_paths:
            return

        temp_paths = []
        for path in dropped_paths:
            path = path.strip()
            if os.path.isdir(path):
                self.input_dir = path
                for fname in os.listdir(path):
                    fpath = os.path.join(path, fname)
                    if os.path.isfile(fpath) and fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                        temp_paths.append(fpath)
            elif os.path.isfile(path) and path.lower().endswith(('.jpg', '.jpeg', '.png')):
                temp_paths.append(path)
                if len(set(os.path.dirname(p) for p in dropped_paths)) == 1:
                    self.input_dir = os.path.dirname(dropped_paths[0])
                else:
                    self.input_dir = None

        if temp_paths:
            self.image_paths = temp_paths
            self.update_ui_with_files()

    def get_font_names(self):
        font_paths = findSystemFonts()
        font_names = []
        for path in font_paths:
            try:
                font_name = os.path.basename(path).split(".")[0]
                if font_name not in font_names:
                    font_names.append(font_name)
            except:
                continue
        font_names.sort()
        return font_names

    def use_exif_date(self):
        selected_index = self.file_listbox.curselection()
        if not selected_index:
            messagebox.showwarning("警告", "请先在列表中选择一张图片。")
            return
        
        fpath = self.image_paths[selected_index[0]]
        date = get_exif_date(fpath)
        if date:
            self.text_entry.delete(0, tk.END)
            self.text_entry.insert(0, date)
            self.update_preview()
        else:
            messagebox.showinfo("提示", "所选图片没有拍摄时间信息。")

    def choose_color(self):
        color_code = colorchooser.askcolor(title="选择文本颜色")
        if color_code and color_code[0]:
            rgb = color_code[0]
            self.text_color.set(f"{int(rgb[0])},{int(rgb[1])},{int(rgb[2])}")
            self.update_preview()

    def choose_outline_color(self):
        color_code = colorchooser.askcolor(title="选择描边颜色")
        if color_code and color_code[0]:
            rgb = color_code[0]
            self.outline_color.set(f"{int(rgb[0])},{int(rgb[1])},{int(rgb[2])}")
            self.update_preview()

    def select_files(self):
        self.image_paths.clear()
        self.thumbnails.clear()
        self.file_listbox.delete(0, tk.END)
        self.preview_label.config(image="")
        self.input_dir = ""

        mode = messagebox.askyesno("选择", "是否选择一个文件夹？\n\n'是' - 选择文件夹\n'否' - 选择多个图片文件")
        
        if mode:
            dir_path = filedialog.askdirectory()
            if dir_path:
                self.input_dir = dir_path
                for fname in os.listdir(dir_path):
                    fpath = os.path.join(dir_path, fname)
                    if os.path.isfile(fpath) and fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                        self.image_paths.append(fpath)
        else:
            file_paths = filedialog.askopenfilenames(filetypes=[("Image files", "*.jpg *.jpeg *.png")])
            if file_paths:
                self.image_paths.extend(file_paths)
                if len(set(os.path.dirname(p) for p in file_paths)) == 1:
                    self.input_dir = os.path.dirname(file_paths[0])
                else:
                    self.input_dir = None
        
        if self.image_paths:
            self.update_ui_with_files()

    def select_output_dir(self):
        dir_path = filedialog.askdirectory()
        if dir_path:
            self.output_dir.set(dir_path)

    def toggle_prefix_entry(self, event=None):
        if self.naming_combo.get() in ["添加前缀", "添加后缀"]:
            self.prefix_entry.config(state="normal")
        else:
            self.prefix_entry.config(state="disabled")
    
    def update_ui_with_files(self):
        self.file_listbox.delete(0, tk.END)
        self.thumbnails.clear()
        self.preview_label.config(image="")
        if self.input_dir:
            self.output_dir.set(os.path.join(self.input_dir, os.path.basename(self.input_dir) + "_watermarked"))
        else:
            self.output_dir.set("")

        for i, fpath in enumerate(self.image_paths):
            self.file_listbox.insert(tk.END, os.path.basename(fpath))
            try:
                img = Image.open(fpath)
                img.thumbnail((400, 400)) # Create a slightly larger base thumbnail
                self.thumbnails.append(img) # Store PIL image, not PhotoImage
            except Exception:
                self.thumbnails.append(None)
        
        if self.thumbnails:
            self.file_listbox.select_set(0)
            self.show_thumbnail()

    def show_thumbnail(self, event=None):
        selected_index = self.file_listbox.curselection()
        if selected_index:
            self.update_preview()
        else:
            self.preview_label.config(image="")
            self.current_preview_image = None
    
    def update_preview(self, event=None):
        selected_index = self.file_listbox.curselection()
        if not selected_index:
            return

        index = selected_index[0]
        original_image_path = self.image_paths[index]
        
        try:
            watermark_text = self.text_entry.get()
            font_path = self.get_font_path(self.font_combo.get())
            font_size = int(self.font_size_entry.get())
            text_color = tuple(map(int, self.text_color.get().split(',')))
            alpha = self.alpha_scale.get()
            style = self.style_combo.get()
            outline_color = tuple(map(int, self.outline_color.get().split(',')))
            
            # If watermark text is empty, just show the original thumbnail
            if not watermark_text:
                thumb = self.thumbnails[index]
                if thumb:
                    self.current_preview_image = ImageTk.PhotoImage(thumb)
                    self.preview_label.config(image=self.current_preview_image)
                return
            
            # Use the correct position variables
            pos_x = self.position_x
            pos_y = self.position_y
            
            watermarked_image = add_watermark(
                original_image_path, 
                watermark_text, 
                font_path, 
                font_size, 
                text_color, 
                alpha, 
                pos_x,
                pos_y, 
                style, 
                outline_color
            )
            
            watermarked_image.thumbnail((400, 400))
            
            self.current_preview_image = ImageTk.PhotoImage(watermarked_image)
            self.preview_label.config(image=self.current_preview_image)

        except (ValueError, FileNotFoundError, IndexError) as e:
            # If parameters are invalid, show original thumbnail
            thumb = self.thumbnails[index]
            if thumb:
                self.current_preview_image = ImageTk.PhotoImage(thumb)
                self.preview_label.config(image=self.current_preview_image)
    
    def on_drag_start(self, event):
        self.drag_start_x = event.x
        self.drag_start_y = event.y

    def on_drag(self, event):
        # We need to scale the drag movement from preview size to original image size
        selected_index = self.file_listbox.curselection()
        if not selected_index: return
        
        original_img = Image.open(self.image_paths[selected_index[0]])
        original_w, original_h = original_img.size
        
        preview_w = self.current_preview_image.width()
        preview_h = self.current_preview_image.height()

        scale_x = original_w / preview_w
        scale_y = original_h / preview_h

        dx = (event.x - self.drag_start_x) * scale_x
        dy = (event.y - self.drag_start_y) * scale_y
        
        self.position_x += dx
        self.position_y += dy
        
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        
        self.update_preview()

    def apply_watermarks(self):
        if not self.image_paths:
            messagebox.showwarning("警告", "请先选择图片。")
            return
            
        output_dir = self.output_dir.get()
        if not output_dir:
            messagebox.showerror("错误", "请指定一个输出文件夹。")
            return
            
        if self.input_dir and os.path.abspath(output_dir) == os.path.abspath(self.input_dir):
            messagebox.showerror("错误", "输出文件夹不能和原文件夹相同，以防覆盖原图。")
            return
            
        try:
            watermark_text = self.text_entry.get()
            font_path = self.get_font_path(self.font_combo.get())
            font_size = int(self.font_size_entry.get())
            text_color = tuple(map(int, self.text_color.get().split(',')))
            alpha = self.alpha_scale.get()
            style = self.style_combo.get()
            outline_color = tuple(map(int, self.outline_color.get().split(',')))
            
            output_format = self.format_combo.get().lower()
            naming_rule = self.naming_combo.get()
            custom_text = self.prefix_entry.get()
        except ValueError:
            messagebox.showerror("错误", "字体大小、颜色或描边格式不正确。")
            return

        os.makedirs(output_dir, exist_ok=True)
        
        pos_x = self.position_x
        pos_y = self.position_y

        for fpath in self.image_paths:
            fname = os.path.basename(fpath)
            try:
                final_text = watermark_text
                if watermark_text == "使用拍摄日期":
                    date = get_exif_date(fpath)
                    final_text = date if date else ""

                if not final_text:
                    print(f"{fname} 水印文本为空，跳过")
                    continue

                watermarked = add_watermark(fpath, final_text, font_path, font_size, text_color, alpha, pos_x, pos_y, style, outline_color)
                
                base_name, _ = os.path.splitext(fname)
                if naming_rule == "添加前缀":
                    new_fname = f"{custom_text}{base_name}.{output_format}"
                elif naming_rule == "添加后缀":
                    new_fname = f"{base_name}{custom_text}.{output_format}"
                else:
                    new_fname = f"{base_name}.{output_format}"
                
                out_path = os.path.join(output_dir, new_fname)
                
                watermarked.save(out_path, format=output_format)
                print(f"已保存: {out_path}")
            except Exception as e:
                print(f"{fname} 处理失败: {e}")
        
        messagebox.showinfo("完成", f"所有图片处理完毕！\n文件已保存至：{output_dir}")
        
    def get_font_path(self, font_name):
        try:
            prop = FontProperties(family=font_name)
            font_path = findfont(prop)
            return font_path
        except Exception:
            return "arial.ttf" # Fallback font

if __name__ == "__main__":
    # Use TkinterDnD.Tk() for the main window
    root = TkinterDnD.Tk()
    app = WatermarkApp(root)
    root.mainloop()