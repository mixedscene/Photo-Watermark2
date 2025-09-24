import os
import sys
import tkinter as tk
from tkinter import filedialog, ttk, messagebox, colorchooser
from PIL import Image, ImageDraw, ImageFont, ImageTk
import piexif
from matplotlib.font_manager import findSystemFonts # 用于查找系统字体
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

def add_watermark(img_path, text, font_path, font_size, color, alpha, position, style, outline_color):
    img = Image.open(img_path).convert("RGBA")
    width, height = img.size
    
    # 根据 font_path 和 font_size 创建字体对象
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        font = ImageFont.load_default()

    txt_layer = Image.new("RGBA", img.size, (255,255,255,0))
    draw = ImageDraw.Draw(txt_layer)
    
    # 颜色和透明度
    fill_color = color + (int(alpha * 255 / 100),)

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # 位置计算
    if position == "左上角":
        pos = (10, 10)
    elif position == "中间":
        pos = ((width - text_w)//2, (height - text_h)//2)
    elif position == "右下角":
        pos = (width - text_w - 10, height - text_h - 10)
    else:
        pos = (10, 10)

    # 阴影效果
    if style == "阴影":
        shadow_pos = (pos[0] + 2, pos[1] + 2)
        draw.text(shadow_pos, text, font=font, fill=(0,0,0,128))
    
    # 描边效果
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
        
        self.create_widgets()
        
        # 使用 ttkdnd2 注册拖放功能
        # 拖放绑定已在 create_widgets 的 list_preview_frame 处实现，无需重复绑定

    def create_widgets(self):
        # 顶部框架，包含文件选择按钮
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)
        
        ttk.Button(top_frame, text="选择图片/文件夹", command=self.select_files).pack(side=tk.LEFT, padx=5)

        # 输出文件夹选择
        output_frame = ttk.Frame(self.root, padding="10")
        output_frame.pack(fill=tk.X)
        
        ttk.Label(output_frame, text="输出文件夹:").pack(side=tk.LEFT, padx=(5, 0))
        ttk.Entry(output_frame, textvariable=self.output_dir, state="readonly", width=40).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        ttk.Button(output_frame, text="浏览...", command=self.select_output_dir).pack(side=tk.LEFT, padx=5)

        # 中间框架，用于显示图片列表和预览
        self.list_preview_frame = ttk.Frame(self.root, padding="10")
        self.list_preview_frame.pack(fill=tk.BOTH, expand=True)

        # 图片文件名列表 (Listbox)
        self.file_listbox = tk.Listbox(self.list_preview_frame, height=10, width=50, selectmode=tk.SINGLE)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.file_listbox.bind("<<ListboxSelect>>", self.show_thumbnail)
        
        # 缩略图预览区域 (Label)
        self.preview_label = ttk.Label(self.list_preview_frame)
        self.preview_label.pack(side=tk.RIGHT, padx=10)

        # ... (水印参数设置与之前相同) ...
        options_frame = ttk.Frame(self.root, padding="10")
        options_frame.pack(fill=tk.X)
        
        # ... (所有参数控件与之前相同) ...
        
        # 底部框架，包含执行按钮
        bottom_frame = ttk.Frame(self.root, padding="10")
        bottom_frame.pack(fill=tk.X)
        ttk.Button(bottom_frame, text="应用水印", command=self.apply_watermarks).pack()

    def handle_dnd(self, event):
        dropped_paths = event.paths
        if not dropped_paths:
            return

        temp_paths = []
        for path in dropped_paths:
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
        """获取系统已安装的字体名称列表。"""
        font_paths = findSystemFonts()
        font_names = []
        for path in font_paths:
            try:
                # 获取字体名称，避免重复
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
        else:
            messagebox.showinfo("提示", "所选图片没有拍摄时间信息。")

    def choose_color(self):
        color_code = colorchooser.askcolor(title="选择文本颜色")
        if color_code:
            rgb = color_code[0]
            self.text_color.set(f"{int(rgb[0])},{int(rgb[1])},{int(rgb[2])}")
            
    def choose_outline_color(self):
        color_code = colorchooser.askcolor(title="选择描边颜色")
        if color_code:
            rgb = color_code[0]
            self.outline_color.set(f"{int(rgb[0])},{int(rgb[1])},{int(rgb[2])}")

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

    def handle_dnd(self, event):
        dropped_paths = event.data
        if not dropped_paths:
            return

        temp_paths = []
        for path in dropped_paths:
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
    
    def update_ui_with_files(self):
        self.file_listbox.delete(0, tk.END)
        self.thumbnails.clear()
        self.preview_label.config(image="")
        if self.input_dir:
            self.output_dir.set(os.path.join(self.input_dir, os.path.basename(self.input_dir) + "_watermark"))
        else:
            self.output_dir.set("")

        for i, fpath in enumerate(self.image_paths):
            self.file_listbox.insert(tk.END, os.path.basename(fpath))
            try:
                img = Image.open(fpath)
                img.thumbnail((200, 200))
                self.thumbnails.append(ImageTk.PhotoImage(img))
            except Exception:
                self.thumbnails.append(None)

    def show_thumbnail(self, event):
        selected_index = self.file_listbox.curselection()
        if selected_index:
            index = selected_index[0]
            thumbnail = self.thumbnails[index]
            if thumbnail:
                self.preview_label.config(image=thumbnail)
            else:
                self.preview_label.config(image="")

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
            position = self.position_combo.get()
            style = self.style_combo.get()
            outline_color = tuple(map(int, self.outline_color.get().split(',')))
            
            output_format = self.format_combo.get().lower()
            naming_rule = self.naming_combo.get()
            custom_text = self.prefix_entry.get()
        except ValueError:
            messagebox.showerror("错误", "字体大小、颜色或描边格式不正确。")
            return

        os.makedirs(output_dir, exist_ok=True)
        
        for fpath in self.image_paths:
            fname = os.path.basename(fpath)
            try:
                date = get_exif_date(fpath)
                if watermark_text == "使用拍摄日期" and date:
                    final_text = date
                else:
                    final_text = watermark_text

                if not final_text:
                    print(f"{fname} 水印文本为空，跳过")
                    continue

                watermarked = add_watermark(fpath, final_text, font_path, font_size, text_color, alpha, position, style, outline_color)
                
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
        """根据字体名称查找字体文件路径"""
        from matplotlib.font_manager import FontProperties, findfont
        try:
            prop = FontProperties(fname=font_name)
            font_path = findfont(prop)
            return font_path
        except:
            return "arial.ttf" # 备用字体

if __name__ == "__main__":
    root = tk.Tk()
    app = WatermarkApp(root)
    root.mainloop()