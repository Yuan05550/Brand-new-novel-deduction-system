import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog, ttk
import threading
import os
import json
from PIL import Image, ImageTk

# 从 main.py 导入必要的函数和类
from main import (
    GameState,
    generate_initial_state,
    generate_next_state,
    load_json,
    get_api_key,
    list_saves,
    load_save,
    save_game,
    ROLES_FILE,
    HETER_FIRE_FILE,
    COMBAT_SKILLS_FILE,
    DAN_FILE,
    TIME_PERIODS,
    API_CONFIG_FILE,
    SAVE_DIR
)

class DoupoGame:
    def __init__(self, root):
        self.root = root
        self.root.title("斗破苍穹 · 命运推演")
        self.root.geometry("1920x1080")

        # 加载数据
        self.roles_data = load_json(ROLES_FILE)
        self.heter_fire = load_json(HETER_FIRE_FILE)
        self.combat_skills = load_json(COMBAT_SKILLS_FILE)
        self.dan_data = load_json(DAN_FILE)
        self.api_key = get_api_key()

        self.game_state = None

        # 背景图
        self.bg_path = os.path.join(os.path.dirname(__file__), "【哲风壁纸】斗破苍穹-萧炎.png")
        self.bg_image = None
        self.bg_label = None
        self.load_background()
        self.root.bind('<Configure>', self.on_window_resize)

        self.show_start_menu()

    def load_background(self):
        if os.path.exists(self.bg_path):
            try:
                self.original_pil_image = Image.open(self.bg_path)
                self.update_background()
            except Exception as e:
                print(f"背景图加载失败: {e}")
                self.root.configure(bg='black')
        else:
            self.root.configure(bg='black')

    def update_background(self):
        if hasattr(self, 'original_pil_image'):
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            if width <= 1 or height <= 1:
                width, height = 1000, 700
            pil_image = self.original_pil_image.resize((width, height), Image.Resampling.LANCZOS)
            self.bg_image = ImageTk.PhotoImage(pil_image)
            if self.bg_label is None:
                self.bg_label = tk.Label(self.root, image=self.bg_image)
                self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
            else:
                self.bg_label.config(image=self.bg_image)
                self.bg_label.image = self.bg_image

    def on_window_resize(self, event):
        self.update_background()

    def clear_window(self):
        for widget in self.root.winfo_children():
            if widget != self.bg_label:
                widget.destroy()

    def show_start_menu(self):
        self.clear_window()
        frame = tk.Frame(self.root, bg='#2d2d2d', bd=0)
        frame.place(relx=0.5, rely=0.5, anchor='center', width=400, height=300)

        tk.Label(frame, text="斗破苍穹", font=("楷体", 36, "bold"),
                 fg="#ffaa00", bg='#2d2d2d').pack(pady=(40,10))
        tk.Label(frame, text="命运推演", font=("楷体", 24),
                 fg="#ffaa00", bg='#2d2d2d').pack(pady=(0,30))

        tk.Button(frame, text="开始游戏", font=("黑体", 16), bg="#8B4513", fg="white",
                  padx=30, pady=10, command=self.start_new_game).pack(pady=20)
        tk.Button(frame, text="加载存档", font=("黑体", 14), bg="#5a3e2b", fg="white",
                  padx=20, pady=5, command=self.load_game_dialog).pack(pady=5)
        tk.Button(frame, text="设置", font=("黑体", 12), bg="#3d2b1a", fg="white",
                  padx=15, pady=3, command=self.show_settings).pack(pady=5)

    def start_new_game(self):
        # 角色选择窗口（带滚动条）
        role_win = tk.Toplevel(self.root)
        role_win.title("选择角色")
        role_win.geometry("400x300")
        role_win.transient(self.root)
        role_win.grab_set()

        tk.Label(role_win, text="请选择角色（双击或点击确定）:").pack(pady=5)
        frame = tk.Frame(role_win)
        frame.pack(fill='both', expand=True, padx=10, pady=5)

        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side='right', fill='y')
        listbox = tk.Listbox(frame, yscrollcommand=scrollbar.set, font=("宋体", 10))
        listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=listbox.yview)

        for role in self.roles_data:
            listbox.insert(tk.END, f"{role['name']} - {role['identity']}")
        listbox.insert(tk.END, "自定义")

        selected_role = None
        identity = ""  # 新增：存储角色身份

        def on_select():
            nonlocal selected_role, identity
            selection = listbox.curselection()
            if not selection:
                return
            idx = selection[0]
            if idx < len(self.roles_data):
                selected_role = self.roles_data[idx]['name']
                identity = self.roles_data[idx]['identity']  # 获取身份
            else:
                custom = simpledialog.askstring("自定义角色", "输入自定义角色名:", parent=role_win)
                if custom:
                    selected_role = custom.strip()
                    identity = "自定义角色"  # 自定义角色身份
                else:
                    return
            role_win.destroy()

        listbox.bind('<Double-Button-1>', lambda e: on_select())
        tk.Button(role_win, text="确定", command=on_select, bg="#8B4513", fg="white").pack(pady=5)
        self.root.wait_window(role_win)
        if not selected_role:
            return

        # 时间段选择窗口（带滚动条）
        period_win = tk.Toplevel(self.root)
        period_win.title("选择时间段")
        period_win.geometry("500x350")
        period_win.transient(self.root)
        period_win.grab_set()

        tk.Label(period_win, text="请选择时间段（双击或点击确定）:").pack(pady=5)
        frame = tk.Frame(period_win)
        frame.pack(fill='both', expand=True, padx=10, pady=5)

        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side='right', fill='y')
        listbox = tk.Listbox(frame, yscrollcommand=scrollbar.set, font=("宋体", 10))
        listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=listbox.yview)

        period_options = [p[3:] for p in TIME_PERIODS]
        for p in period_options:
            listbox.insert(tk.END, p)

        selected_period = None

        def on_period_select():
            nonlocal selected_period
            selection = listbox.curselection()
            if not selection:
                return
            idx = selection[0]
            if idx == len(period_options) - 1:
                custom = simpledialog.askstring("自定义时间段", "输入时间段描述:", parent=period_win)
                if custom:
                    selected_period = custom.strip()
                else:
                    return
            else:
                selected_period = period_options[idx]
            period_win.destroy()

        listbox.bind('<Double-Button-1>', lambda e: on_period_select())
        tk.Button(period_win, text="确定", command=on_period_select, bg="#8B4513", fg="white").pack(pady=5)
        self.root.wait_window(period_win)
        if not selected_period:
            return

        # 生成初始状态（传入身份参数）
        def task():
            self.root.after(0, lambda: self.show_loading("正在生成初始状态..."))
            initial_state = generate_initial_state(
                selected_role,
                identity,  # 新增：传递身份
                selected_period,
                self.api_key,
                self.heter_fire,
                self.combat_skills,
                self.dan_data
            )
            if initial_state:
                self.game_state = GameState(selected_role, selected_period, initial_state)
                self.root.after(0, self.show_game_interface)
            else:
                self.root.after(0, lambda: messagebox.showerror("错误", "初始状态生成失败，请检查API密钥或网络"))
            self.root.after(0, self.hide_loading)

        threading.Thread(target=task, daemon=True).start()

    def show_game_interface(self):
        """显示游戏主界面（固定输入框在底部）"""
        self.clear_window()

        main_frame = tk.Frame(self.root, bg='#2d2d2d', bd=0)
        main_frame.place(relx=0.5, rely=0.5, anchor='center', relwidth=0.95, relheight=0.95)

        # 标题
        tk.Label(main_frame, text="斗破苍穹 · 命运推演", font=("楷体", 20, "bold"),
                 fg="#ffaa00", bg='#2d2d2d').pack(pady=10)

        # 角色状态区域（保持不变）
        status_frame = tk.LabelFrame(main_frame, text="角色状态", font=("黑体", 12),
                                      fg="#ffaa00", bg='#2d2d2d', bd=2, relief='groove')
        status_frame.pack(fill='x', padx=20, pady=10)

        # 基本信息（角色、境界、地点）放在左侧
        info_frame = tk.Frame(status_frame, bg='#2d2d2d')
        info_frame.pack(side='left', fill='y', padx=10, pady=10)

        self.status_text = tk.StringVar()
        tk.Label(info_frame, textvariable=self.status_text, font=("宋体", 10),
                 bg='#2d2d2d', fg='white', justify='left').pack(anchor='w')

        # ========== 设置进度条样式 ==========
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure("Red.Horizontal.TProgressbar",
                             background='red', troughcolor='gray',
                             bordercolor='gray', lightcolor='red', darkcolor='red')
        self.style.configure("Blue.Horizontal.TProgressbar",
                             background='blue', troughcolor='gray',
                             bordercolor='gray', lightcolor='blue', darkcolor='blue')
        # =================================

        # 生命值进度条（红色）
        tk.Label(info_frame, text="生命：", font=("黑体", 10),
                fg='#ffaa00', bg='#2d2d2d').pack(anchor='w')
        self.hp_bar = ttk.Progressbar(info_frame, length=200, mode='determinate',
                                    style="Red.Horizontal.TProgressbar")
        self.hp_bar.pack(pady=5)

        # [新增] 斗气值进度条（蓝色）
        tk.Label(info_frame, text="斗气：", font=("黑体", 10),
                 fg='#ffaa00', bg='#2d2d2d').pack(anchor='w')
        self.energy_bar = ttk.Progressbar(info_frame, length=200, mode='determinate',
                                          style="Blue.Horizontal.TProgressbar")
        self.energy_bar.pack(pady=5)

        # 描述标签
        tk.Label(info_frame, text="描述：", font=("黑体", 10),
                 fg='#ffaa00', bg='#2d2d2d').pack(anchor='w')
        self.desc_text = tk.StringVar()
        desc_label = tk.Label(info_frame, textvariable=self.desc_text, font=("宋体", 9),
                              bg='#2d2d2d', fg='#cccccc', wraplength=300, justify='left')
        desc_label.pack(anchor='w', pady=(0,5))

        # 物品列表（带滚动条）放在右侧
        items_frame = tk.Frame(status_frame, bg='#2d2d2d')
        items_frame.pack(side='right', fill='both', expand=True, padx=10, pady=10)

        tk.Label(items_frame, text="物品栏", font=("黑体", 10), fg="#ffaa00",
                 bg='#2d2d2d').pack(anchor='w')

        listbox_frame = tk.Frame(items_frame, bg='#2d2d2d')
        listbox_frame.pack(fill='both', expand=True)

        scrollbar = tk.Scrollbar(listbox_frame)
        scrollbar.pack(side='right', fill='y')

        self.items_listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set,
                                         bg='#3d3d3d', fg='white', font=("宋体", 9),
                                         selectbackground='#8B4513', height=5)
        self.items_listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.items_listbox.yview)

        # 绑定双击和右键事件
        self.items_listbox.bind('<Double-Button-1>', self.on_item_double_click)
        self.items_listbox.bind('<Button-3>', self.show_item_context_menu)

        # ===== 使用 grid 布局固定输入框在底部 =====
        # 创建一个容器 frame，用于放置历史剧情、输入区域和按钮栏
        container = tk.Frame(main_frame, bg='#2d2d2d')
        container.pack(fill='both', expand=True, padx=20, pady=(0,10))

        # 配置 grid 行权重，让历史剧情所在行可以扩展
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # 历史剧情文本框（第0行，占据所有额外空间）
        history_frame = tk.LabelFrame(container, text="历史剧情", font=("黑体", 12),
                                       fg="#ffaa00", bg='#2d2d2d', bd=2, relief='groove')
        history_frame.grid(row=0, column=0, sticky='nsew', pady=(0,10))

        self.history_text = scrolledtext.ScrolledText(
            history_frame, wrap=tk.WORD, state='disabled',
            font=("宋体", 10), bg='#1e1e1e', fg='#f0e6d0',
            insertbackground='white'
        )
        self.history_text.pack(fill='both', expand=True, padx=5, pady=5)

        # 输入区域（第1行）
        input_frame = tk.Frame(container, bg='#2d2d2d')
        input_frame.grid(row=1, column=0, sticky='ew', pady=(0,5))

        tk.Label(input_frame, text="你的行动：", font=("黑体", 10),
                 fg='white', bg='#2d2d2d').pack(side='left')
        self.user_input = tk.Entry(input_frame, font=("宋体", 10), bg='#3d3d3d', fg='white',
                                    insertbackground='white')
        self.user_input.pack(side='left', fill='x', expand=True, padx=5)
        self.user_input.bind('<Return>', lambda e: self.send_action())
        self.send_btn = tk.Button(input_frame, text="发送", font=("黑体", 10),
                                  bg="#8B4513", fg="white", command=self.send_action)
        self.send_btn.pack(side='left', padx=5)
        self.free_btn = tk.Button(input_frame, text="自由推演", font=("黑体", 10),
                                   bg="#5a3e2b", fg="white", command=self.free_play)
        self.free_btn.pack(side='left', padx=5)

        # 底部按钮栏（第2行）
        button_frame = tk.Frame(container, bg='#2d2d2d')
        button_frame.grid(row=2, column=0, sticky='ew')

        btns = [
            ("存档", self.save_game),
            ("加载", self.load_game_dialog),
            ("返回主菜单", self.show_start_menu),
            ("设置", self.show_settings),
            ("关于", self.show_about)
        ]
        for text, cmd in btns:
            tk.Button(button_frame, text=text, font=("黑体", 10),
                      bg="#5a3e2b", fg="white", command=cmd).pack(side='left', padx=5)

        self.update_ui()

    def on_item_double_click(self, event):
        selection = self.items_listbox.curselection()
        if not selection:
            return
        display_str = self.items_listbox.get(selection[0])
        if ' x' in display_str:
            item_name = display_str.split(' x')[0]
        else:
            item_name = display_str
        self.use_item(item_name)

    def use_item(self, item_name):
        """双击使用物品，默认行为：斗技/秘法/异火为“使用”，丹药为“服用”"""
        if '[' in item_name and ']' in item_name and not item_name.startswith('['):
            # 斗技、秘法、异火：默认行为为“使用”
            self.use_item_with_action(item_name, "使用")
        else:
            # 丹药：默认行为为“服用”
            self.use_item_with_action(item_name, "服用")

    def show_item_context_menu(self, event):
        """右键点击物品时弹出上下文菜单，根据物品类型显示不同选项"""
        selection = self.items_listbox.curselection()
        if not selection:
            return
        display_str = self.items_listbox.get(selection[0])
        if ' x' in display_str:
            item_name = display_str.split(' x')[0]
        else:
            item_name = display_str

        menu = tk.Menu(self.root, tearoff=0, bg='#3d3d3d', fg='white')

        if item_name.startswith('['):
            # 丹药：只有“服用”选项
            menu.add_command(label="服用", command=lambda: self.use_item_with_action(item_name, "服用"))
        elif '[秘法]' in item_name:
            menu.add_command(label="激活", command=lambda: self.use_item_with_action(item_name, "激活"))
        elif '[异火]' in item_name:
            menu.add_command(label="释放攻击", command=lambda: self.use_item_with_action(item_name, "攻击"))
            menu.add_command(label="防御", command=lambda: self.use_item_with_action(item_name, "防御"))
            menu.add_command(label="使用", command=lambda: self.use_item_with_action(item_name, "使用"))
        else:
            # 普通斗技（格式为“名称[阶别]”）
            menu.add_command(label="释放攻击", command=lambda: self.use_item_with_action(item_name, "攻击"))
            menu.add_command(label="防御", command=lambda: self.use_item_with_action(item_name, "防御"))
            menu.add_command(label="使用", command=lambda: self.use_item_with_action(item_name, "使用"))

        menu.post(event.x_root, event.y_root)

    def use_item_with_action(self, item_name: str, action_type: str):
        """根据选择的行为类型处理物品使用"""
        if not self.game_state:
            messagebox.showwarning("提示", "请先开始新游戏或加载存档")
            return

        if self.user_input['state'] == 'disabled':
            messagebox.showinfo("提示", "正在处理上一个行动，请稍候...")
            return

        # 判断是否为丹药（需要扣除）
        if item_name.startswith('['):
            current_items = self.game_state.state.get('items', [])
            removed = False
            for i, it in enumerate(current_items):
                if it == item_name:
                    del current_items[i]
                    removed = True
                    break
            if not removed:
                for i, it in enumerate(current_items):
                    if it.startswith(item_name):
                        del current_items[i]
                        removed = True
                        break
            if not removed:
                messagebox.showwarning("提示", f"物品栏中没有 {item_name}")
                return
            self.game_state.state['items'] = current_items
            self.update_ui()
            action = f"{action_type}{item_name}"
        else:
            if action_type == "攻击":
                action = f"使用{item_name}发动攻击"
            elif action_type == "防御":
                action = f"使用{item_name}进行防御"
            elif action_type == "使用":
                action = f"使用{item_name}"
            elif action_type == "激活":
                action = f"激活{item_name}"
            else:
                action = f"使用{item_name}"

        self.send_action(action_text=action)

    def send_action(self, action_text=None):
        """发送用户行动，使用 try-finally 确保控件恢复"""
        if not self.game_state:
            messagebox.showwarning("提示", "请先开始新游戏或加载存档")
            return

        if action_text is None:
            action = self.user_input.get().strip()
            if not action:
                return
            self.user_input.delete(0, tk.END)
        else:
            action = action_text

        self.user_input.config(state='disabled')
        self.send_btn.config(state='disabled')
        self.free_btn.config(state='disabled')

        def task():
            try:
                self.game_state.history.append(f"【我】{action}")
                self.root.after(0, self.update_ui)

                result = generate_next_state(
                    self.game_state,
                    self.api_key,
                    self.heter_fire,
                    self.combat_skills,
                    self.dan_data,
                    action
                )
                if result:
                    story = result["story"]
                    new_state = result["new_state"]
                    self.game_state.state = new_state
                    self.game_state.history.append(story)
                    save_game(self.game_state, autosave=True)
                    self.root.after(0, self.update_ui)
                    self.root.after(0, lambda: self.show_temp_message("自动存档成功"))

                    if new_state.get("hp", 100) <= 0:
                        self.root.after(0, lambda: self.ask_save_death())
                else:
                    self.root.after(0, lambda: messagebox.showerror("错误", "剧情生成失败，请重试"))
            finally:
                self.root.after(0, lambda: self.user_input.config(state='normal'))
                self.root.after(0, lambda: self.send_btn.config(state='normal'))
                self.root.after(0, lambda: self.free_btn.config(state='normal'))

        threading.Thread(target=task, daemon=True).start()

    def free_play(self):
        """自由推演：不输入任何行动，直接让AI生成下一步"""
        if not self.game_state:
            messagebox.showwarning("提示", "请先开始新游戏或加载存档")
            return

        self.send_btn.config(state='disabled')
        self.free_btn.config(state='disabled')
        self.user_input.config(state='disabled')

        def task():
            try:
                result = generate_next_state(
                    self.game_state,
                    self.api_key,
                    self.heter_fire,
                    self.combat_skills,
                    self.dan_data,
                    ""
                )
                if result:
                    story = result["story"]
                    new_state = result["new_state"]
                    self.game_state.history.append(story)
                    self.game_state.state = new_state
                    save_game(self.game_state, autosave=True)
                    self.root.after(0, self.update_ui)
                    self.root.after(0, lambda: self.show_temp_message("自动存档成功"))

                    if new_state.get("hp", 100) <= 0:
                        self.root.after(0, lambda: self.ask_save_death())
                else:
                    self.root.after(0, lambda: messagebox.showerror("错误", "剧情生成失败，请重试"))
            finally:
                self.root.after(0, lambda: self.send_btn.config(state='normal'))
                self.root.after(0, lambda: self.free_btn.config(state='normal'))
                self.root.after(0, lambda: self.user_input.config(state='normal'))

        threading.Thread(target=task, daemon=True).start()

    def ask_save_death(self):
        """询问是否保存死亡结局"""
        if messagebox.askyesno("游戏结束", "你的角色已经死亡！是否保存结局？"):
            save_game(self.game_state)
            messagebox.showinfo("已保存", "结局已保存")

    def show_temp_message(self, text, duration=2000):
        msg_label = tk.Label(self.root, text=text, font=("黑体", 10),
                              fg='#ffaa00', bg='black')
        msg_label.place(relx=0.5, rely=0.95, anchor='center')
        self.root.after(duration, msg_label.destroy)

    def save_game(self):
        if not self.game_state:
            messagebox.showwarning("提示", "没有正在进行的游戏")
            return
        path = save_game(self.game_state)
        messagebox.showinfo("存档成功", f"已保存至：{os.path.basename(path)}")

    def load_game_dialog(self):
        saves = list_saves()
        if not saves:
            messagebox.showinfo("提示", "没有找到存档")
            return

        load_win = tk.Toplevel(self.root)
        load_win.title("加载存档")
        load_win.geometry("400x300")
        load_win.transient(self.root)
        load_win.grab_set()
        load_win.configure(bg='#2d2d2d')

        tk.Label(load_win, text="选择存档文件：", font=("黑体", 12),
                 fg='white', bg='#2d2d2d').pack(pady=10)

        frame = tk.Frame(load_win, bg='#2d2d2d')
        frame.pack(fill='both', expand=True, padx=10, pady=5)

        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side='right', fill='y')

        listbox = tk.Listbox(frame, yscrollcommand=scrollbar.set,
                              bg='#3d3d3d', fg='white', selectbackground='#8B4513')
        scrollbar.config(command=listbox.yview)
        listbox.pack(side='left', fill='both', expand=True)

        for s in saves:
            listbox.insert(tk.END, s)

        def load_selected():
            selection = listbox.curselection()
            if not selection:
                return
            filename = saves[selection[0]]
            loaded = load_save(filename)
            if loaded:
                self.game_state = loaded
                self.show_game_interface()
                load_win.destroy()
            else:
                messagebox.showerror("错误", "加载失败")

        listbox.bind('<Double-Button-1>', lambda e: load_selected())
        tk.Button(load_win, text="加载", command=load_selected,
                  bg="#8B4513", fg="white").pack(pady=10)

    def show_settings(self):
        settings_win = tk.Toplevel(self.root)
        settings_win.title("设置")
        settings_win.geometry("400x200")
        settings_win.transient(self.root)
        settings_win.grab_set()
        settings_win.configure(bg='#2d2d2d')

        tk.Label(settings_win, text="API Key:", font=("黑体", 10),
                 fg='white', bg='#2d2d2d').pack(pady=10)

        api_entry = tk.Entry(settings_win, width=50, bg='#3d3d3d', fg='white')
        api_entry.insert(0, self.api_key)
        api_entry.pack(pady=5)

        def save_settings():
            new_key = api_entry.get().strip()
            if new_key:
                with open(API_CONFIG_FILE, 'w', encoding='utf-8') as f:
                    json.dump({"api_key": new_key}, f, ensure_ascii=False, indent=2)
                self.api_key = new_key
                messagebox.showinfo("成功", "API Key已保存，重启程序后生效")
                settings_win.destroy()

        tk.Button(settings_win, text="保存", command=save_settings,
                  bg="#8B4513", fg="white").pack(pady=10)

        tk.Label(settings_win, text=f"存档目录：{SAVE_DIR}\n如需修改，请编辑 main.py 中的 SAVE_DIR",
                 font=("宋体", 9), fg='gray', bg='#2d2d2d').pack(pady=5)

    def show_about(self):
        messagebox.showinfo("关于", "斗破苍穹推演系统 v1.3\n基于 tkinter 构建\n背景图：哲风壁纸")

    def update_ui(self):
        """更新界面显示当前游戏状态（合并显示物品数量）"""
        if self.game_state:
            gs = self.game_state
            status = (
                f"角色：{gs.role}\n"
                f"境界：{gs.state.get('realm', '未知')}\n"
                f"地点：{gs.state.get('location', '未知')}\n"
            )
            self.status_text.set(status)

            hp = gs.state.get('hp', 100)
            self.hp_bar['value'] = hp

            # [新增] 更新能量条
            energy = gs.state.get('energy', 100)
            self.energy_bar['value'] = energy

            desc = gs.state.get('description', '')
            self.desc_text.set(desc)

            raw_items = gs.state.get('items', [])
            display_items = []
            counts = {}
            for item in raw_items:
                if '[' in item and ']' in item:
                    if item.startswith('['):
                        counts[item] = counts.get(item, 0) + 1
                    else:
                        display_items.append(item)
                else:
                    counts[item] = counts.get(item, 0) + 1

            for name, count in counts.items():
                if count == 1:
                    display_items.append(name)
                else:
                    display_items.append(f"{name} x{count}")

            self.items_listbox.delete(0, tk.END)
            if display_items:
                for item in display_items:
                    self.items_listbox.insert(tk.END, item)
            else:
                self.items_listbox.insert(tk.END, "无")

            self.history_text.config(state='normal')
            self.history_text.delete(1.0, tk.END)
            for line in gs.history:
                self.history_text.insert(tk.END, line + "\n\n")
            self.history_text.see(tk.END)
            self.history_text.config(state='disabled')

    def show_loading(self, text):
        self.loading_label = tk.Label(self.root, text=text, font=("黑体", 12),
                                       fg='white', bg='black')
        self.loading_label.place(relx=0.5, rely=0.5, anchor='center')

    def hide_loading(self):
        if hasattr(self, 'loading_label'):
            self.loading_label.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = DoupoGame(root)
    root.mainloop()

#作者：南鸾之巅·零柒柒