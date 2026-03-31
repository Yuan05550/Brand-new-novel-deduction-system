import json
import os
import requests
import datetime
import sys
import re  # [新增] 用于正则提取境界
from typing import List, Dict, Any, Optional

# ================== 配置 ==================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SAVE_DIR = r"C:\Users\Administrator\Desktop\斗破deepseek推演"
API_CONFIG_FILE = os.path.join(BASE_DIR, "api_config.json")
ROLES_FILE = os.path.join(BASE_DIR, "[整理好]人物角色清单.json")
HETER_FIRE_FILE = os.path.join(BASE_DIR, "[整理好]斗破原著所有异火.json")
COMBAT_SKILLS_FILE = os.path.join(BASE_DIR, "[整理好]斗破原著所有斗技 - 副本.json")
DAN_FILE = os.path.join(BASE_DIR, "[整理好]斗破苍穹所有丹药.json")   # 新增丹药文件

# 自动存档文件名
AUTOSAVE_FILE = os.path.join(SAVE_DIR, "autosave.json")

TIME_PERIODS = [
    "1. 萧炎斗之气三段（退婚前夕）",
    "2. 萧炎突破斗者（魔兽山脉历练）",
    "3. 萧炎斗师（塔戈尔大沙漠）",
    "4. 萧炎大斗师（迦南学院）",
    "5. 萧炎斗灵（黑角域）",
    "6. 萧炎斗王（出云帝国等）",
    "7. 萧炎斗皇（中州闯荡）",
    "8. 萧炎斗宗（丹塔大会）",
    "9. 萧炎斗尊（古族之行）",
    "10.萧炎斗圣（天墓修炼）",
    "11.萧炎斗帝（最终决战）",
    "12.自定义时间段（请手动输入描述）"
]

# ================== 工具函数 ==================
def load_json(file_path: str) -> Any:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"读取文件 {file_path} 失败: {e}")
        sys.exit(1)

def save_json(data: Any, file_path: str):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def ensure_dir(path: str):
    if not os.path.exists(path):
        os.makedirs(path)

def get_api_key() -> str:
    config = load_json(API_CONFIG_FILE)
    return config.get("api_key", "")

# ================== API调用 ==================
def call_deepseek(prompt: str, system_msg: str, api_key: str) -> Optional[str]:
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.8,
        "max_tokens": 2000,
        "stream": True   # 开启流式
    }
    try:
        # 注意：这里设置较长的超时，因为流式会持续接收数据
        response = requests.post(url, headers=headers, json=data, stream=True, timeout=120)
        response.raise_for_status()
        
        full_content = ""
        # 逐行读取服务器返回的数据块
        for line in response.iter_lines(decode_unicode=True):
            if line and line.startswith("data: "):
                data_str = line[6:]  # 去掉 "data: " 前缀
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    # 提取内容
                    delta = chunk["choices"][0]["delta"]
                    if "content" in delta:
                        full_content += delta["content"]
                except json.JSONDecodeError:
                    continue
        return full_content
    except Exception as e:
        print(f"API调用失败: {e}")
        return None

# ================== 状态管理 ==================
class GameState:
    def __init__(self, role: str, time_period: str, initial_state: dict, history: List[str] = None):
        self.role = role
        self.time_period = time_period
        self.state = initial_state
        self.history = history or []

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "time_period": self.time_period,
            "state": self.state,
            "history": self.history
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GameState":
        return cls(
            role=data["role"],
            time_period=data["time_period"],
            initial_state=data["state"],
            history=data["history"]
        )

# ================== 辅助函数：统计斗技和丹药数量 ==================
def count_skills_and_dans(items: List[str]) -> tuple:
    """返回 (斗技数量, 丹药数量)"""
    skill_count = 0
    dan_count = 0
    for item in items:
        if '[' in item and ']' in item:
            if item.startswith('['):
                dan_count += 1      # 丹药
            else:
                skill_count += 1     # 斗技
        # 其他物品不计
    return skill_count, dan_count

# ================== 境界等级提取与斗技阶别验证 ==================
def extract_realm_level(realm: str) -> Optional[str]:
    """从境界字符串中提取基础境界名称，如'斗宗'、'斗尊'等"""
    match = re.search(r'斗[之气者师灵王皇宗尊圣帝]', realm)
    if match:
        return match.group()
    return None

def validate_skills_by_realm(items: List[str], realm: str) -> bool:
    """
    验证斗技阶别是否与境界匹配：
    - 斗宗及以上必须至少有一门地阶或以上斗技。
    - 若无法识别境界或境界低于斗宗，则自动通过。
    """
    level = extract_realm_level(realm)
    if not level:
        return True  # 无法判断则通过
    # 定义境界顺序（从低到高）
    realm_order = ['斗者', '斗师', '大斗师', '斗灵', '斗王', '斗皇', '斗宗', '斗尊', '斗圣', '斗帝']
    try:
        idx = realm_order.index(level)
    except ValueError:
        return True  # 非标准境界（如自定义）也通过
    # 如果境界低于斗宗（索引<6），不强制要求
    if idx < 6:
        return True
    # 境界 >= 斗宗，必须至少有一个斗技包含“地阶”或“天阶”
    for item in items:
        if '[' in item and ']' in item:
            if '地阶' in item or '天阶' in item:
                return True
    return False

def validate_no_ultra_skills(items: List[str], realm: str) -> bool:
    """
    验证非斗帝角色是否拥有超天阶斗技：
    - 如果角色境界不是斗帝，且物品中包含任何带有“超天阶”的斗技，返回 False。
    - 否则返回 True。
    """
    level = extract_realm_level(realm)
    if level == '斗帝':
        return True  # 斗帝可以拥有超天阶
    # 检查 items 中是否有超天阶斗技
    for item in items:
        if '[' in item and ']' in item:
            if '超天阶' in item:
                return False
    return True

# ================== 新增过滤函数 ==================
def remove_ultra_skills(items: List[str], realm: str) -> List[str]:
    """如果角色不是斗帝，移除所有超天阶斗技；否则原样返回"""
    level = extract_realm_level(realm)
    if level == '斗帝':
        return items
    new_items = []
    for item in items:
        # 只过滤掉包含“超天阶”的斗技（丹药和其他物品保留）
        if '[' in item and ']' in item and '超天阶' in item:
            continue
        new_items.append(item)
    return new_items

# ================== 初始状态生成（带重试机制）==================
def generate_initial_state(role: str, identity: str, time_period: str, api_key: str,
                           heter_fire_data: dict, combat_skills_data: dict, dan_data: dict,
                           retry_count: int = 0) -> Optional[dict]:
    """生成初始状态，确保至少3个斗技和3个丹药，且斗宗以上至少有一门地阶及以上斗技，最多重试5次"""
    system_msg = f"""你是一个斗破苍穹世界的推演引擎。你需要根据用户选择的角色、该角色的身份以及时间段，生成该角色的初始状态。

**角色身份**：{identity}

请参考以下异火、斗技和丹药知识：
异火信息：{json.dumps(heter_fire_data, ensure_ascii=False)}
斗技信息：{json.dumps(combat_skills_data, ensure_ascii=False)}
丹药信息：{json.dumps(dan_data, ensure_ascii=False)}

**重要约束（请严格遵守）**：
1. 必须严格按照原著设定，为角色生成符合其身份和实力阶段的初始状态。角色身份已在上面给出，请基于此身份决定其归属势力、拥有的异火、斗技和丹药。
2. 对于以下角色，初始化时必须固定特定境界（即使时间段较晚，也要以该境界为基础，但可因时间线调整描述，例如“已修炼至”或“当前处于封印中”等）：
   - 鹰凰：一星斗圣中期
   - 萧晨 (血斧萧晨)：五星斗圣中期
   - 林老怪：二星斗圣初期
   - 古烈：八星斗圣初期
   - 古道 (古族三仙)：七星斗圣后期
   - 古南海：四星斗圣初期
   - 魂天帝：九星后期至斗帝
   - 虚无吞炎：九星斗圣初期
   - 魂元天：八星斗圣后期
   - 魂天生：八星斗圣后期
   - 魂尧：八星斗圣后期
   - 魂焱：七星斗圣后期
   - 魂屠：七星斗圣后期
   - 魂煞：七星斗圣后期
   - 魂镜：七星斗圣后期
   - 魂千陌：六星斗圣初期
   - 魂魔老人：五星斗圣后期
   - 魂殿副殿主：三星斗圣后期
   - 大天尊：二星斗圣中期
   - 魂清圣者：一星斗圣
   - 雷赢：八星斗圣后期
   - 雷族大长老：四星斗圣初期
   - 炎烬：八星斗圣后期
   - 火耀：四星斗圣初期
   - 火玄：四星斗圣初期
   - 药丹：七星斗圣中期
   - 石族族长：六星斗圣
   - 石族长老：四星斗圣初期
   - 烛坤：九星后期至斗帝
   - 西龙王：三星斗圣后期
   - 南龙王：三星斗圣后期
   - 东龙岛青山大长老：二星斗圣中期
   - 东龙岛二长老：一星斗圣
   - 烛火：斗圣
   - 玄魔：二星斗圣
   - 诛木：一星斗圣
   - 烈山：一星斗圣
   - 凰天：五星斗圣后期
   - 妖啸天：一星斗圣中期
   - 幽冥子：半圣
   - 焚炎老祖：九星斗圣后期
   - 丹塔始祖：九星斗圣后期
   - 神农老人：六星斗圣
3. **斗技分配规则**：
   - 超天阶斗技只能分配给斗帝，是斗帝专属的。如果角色是超天阶斗技的所有者但是并未达到斗帝境界也不行！
   - 每个斗技在斗技信息中都有 `owner` 字段，表示其专属者或所属势力。请根据你对原著的理解，为角色分配他/她应该拥有的斗技，严禁分配其他角色的专属斗技。
   - 如果原著中该角色拥有的斗技太少，你可以根据角色的斗气属性和时间段合理创造新的斗技，但斗技阶别必须符合角色当前实力，且不能与其他角色的专属斗技冲突。
   - 斗技名称后必须附上阶别，格式为“斗技名称[阶别]”，例如“吸掌[玄阶低级]”。
   - **天阶及以上斗技只能分配给斗尊及以上境界的角色**，请根据你生成的境界(realm)来判断。
   - **斗技的阶别必须与角色当前境界相匹配**：例如斗宗及以上境界的角色至少应拥有一门地阶或以上斗技；斗尊及以上可拥有天阶斗技；黄阶、玄阶适合低境界角色。
   - 初始状态中，**至少要有3个斗技**。
4. **丹药分配规则**：
   - 根据角色的境界、底蕴和能力，分配合适品阶和数量的丹药。可以参考丹药信息中的品阶、功效和适用对象。
   - 每枚丹药的名称前必须附上品级，格式为“[品级]丹药名称”，例如“[二品]冰清丹”。
   - 初始状态中，**至少要有3枚丹药**。
5. 请以JSON格式返回角色的初始状态，必须包含以下字段：
   - "realm": 角色当前的境界（如斗者一星）
   - "location": 当前所在地点
   - "hp": 生命值（0-100整数）
   - "energy": 斗气值，范围0-100，初始为100。   # [新增]
   - "items": 持有的物品列表（数组），每个物品是一个字符串，必须按上述格式标注斗技阶别或丹药品级。
   - "description": 对角色当前状态的简要描述
6. **异火分配规则**：
   - 如果角色在选择的时间线拥有异火，必须将异火加入物品列表，格式为“异火名称[异火]”，例如“青莲地心火[异火]”。

返回格式示例：
{{"realm": "斗者三星", "location": "乌坦城", "hp": 100, "energy": 100, "items": ["吸掌[玄阶低级]", "[二品]冰清丹", "疗伤药"], "description": "刚刚突破斗者，意气风发。"}}
注意：只返回JSON，不要有其他文字。"""

    # 根据重试次数调整用户提示
    if retry_count == 0:
        user_prompt = f"角色：{role}（身份：{identity}）\n时间段：{time_period}\n请生成该角色在此时间段的初始状态。"
    else:
        user_prompt = f"角色：{role}（身份：{identity}）\n时间段：{time_period}\n你上次生成的斗技数量不足3个或格式不正确（应为“名称[阶别]”），或丹药数量不足3个（格式为“[品级]名称”），或斗宗以上角色缺少地阶及以上斗技。请重新生成，确保满足所有要求。"

    reply = call_deepseek(user_prompt, system_msg, api_key)
    if not reply:
        return None
    try:
        if "```json" in reply:
            reply = reply.split("```json")[1].split("```")[0].strip()
        elif "```" in reply:
            reply = reply.split("```")[1].split("```")[0].strip()
        state = json.loads(reply)
        required = ["realm", "location", "hp", "energy", "items", "description"]  # [新增] energy
        for field in required:
            if field not in state:
                # 默认值：energy 设为 100，其余保持原有处理
                if field == "energy":
                    state[field] = 100
                elif field == "hp":
                    state[field] = 100
                else:
                    state[field] = "" if field != "hp" else 100

        # ========== 关键修改：先过滤超天阶斗技 ==========
        items = state.get("items", [])
        realm = state.get("realm", "")
        filtered_items = remove_ultra_skills(items, realm)
        if len(filtered_items) != len(items):
            print(f"自动移除非斗帝角色的超天阶斗技，移除 {len(items)-len(filtered_items)} 个")
            state["items"] = filtered_items

        # 检查斗技和丹药数量及阶别合理性
        skill_count, dan_count = count_skills_and_dans(state.get("items", []))
        realm_ok = validate_skills_by_realm(state.get("items", []), state.get("realm", ""))

        if skill_count < 3 or dan_count < 3 or not realm_ok:
            if retry_count < 5:  # 最多重试5次
                print(f"验证不通过: skill_count={skill_count}, dan_count={dan_count}, realm_ok={realm_ok}，第{retry_count+2}次重试...")
                return generate_initial_state(role, identity, time_period, api_key, heter_fire_data, combat_skills_data, dan_data, retry_count+1)
            else:
                print("重试次数已达上限，生成失败。")
                return None  # 失败返回None
        return state
    except Exception as e:
        print(f"解析初始状态失败: {e}\nAI回复: {reply}")
        return None

# ================== 下一步剧情生成（支持用户输入行动，传入完整历史）==================
def generate_next_state(state: GameState, api_key: str,
                        heter_fire_data: dict, combat_skills_data: dict, dan_data: dict,
                        user_action: str = "", retry_count=0) -> Optional[dict]:
    # 使用全部历史
    history_text = "\n".join([f"{i+1}. {h}" for i, h in enumerate(state.history)])

    system_msg = f"""你是一个斗破苍穹世界的推演引擎。当前用户正在以第一人称扮演角色 {state.role}。
用户可能会输入他想采取的行动或说的话（已标记为“用户行动”）。你需要基于当前状态、全部历史剧情和用户行动，生成合理的后续剧情。

**重要规则**：
1. 剧情必须始终以用户扮演的角色（即“我”）的第一人称视角进行叙述。例如：“我走向前，问道……”
2. 用户输入的行动（如果有）代表“我”已经做了或说了这些事。你只需描述这件事发生后的世界反应（其他人物的回应、环境变化等），**不要重复用户输入的内容**，也不要再让“我”说同样的话。
3. 如果用户没有输入行动，则自由发挥，推动剧情发展。
4. 剧情必须符合斗破苍穹世界观，角色可以受伤、死亡、获得奇遇、逆袭等。
5. **JSON格式要求**：你返回的必须是严格有效的JSON。特别注意：
   - 字符串中的双引号必须转义为 \\" ，换行符必须用 \\n 表示，不能出现实际的换行符。
   - 属性名和字符串值必须用双引号包围。
   - 不能有多余的逗号，也不能缺少逗号。
6. 你可以参考以下异火、斗技和丹药知识：
异火信息：{json.dumps(heter_fire_data, ensure_ascii=False)}
斗技信息：{json.dumps(combat_skills_data, ensure_ascii=False)}
丹药信息：{json.dumps(dan_data, ensure_ascii=False)}

7. **使用秘法提升规则**(重要)：
   - 当用户输入包含“激活[秘法]xxx”时，代表角色激活了该秘法，并更新状态栏，你必须根据秘法的效果，**立即在 new_state 中暂时提升角色的境界（realm）**，幅度和持续时间可参考秘法描述或原著设定，并且在境界后面标注处于XXX状态下。

8. **斗技和丹药格式要求**：
   - 当角色获得新斗技时，必须标注阶别，格式为“斗技名称[阶别]”。
   - 当角色获得新丹药时，必须标注品级，格式为“[品级]丹药名称”。

9. **斗气消耗**：当角色使用斗技时，必须在 `new_state` 中根据斗技阶别和角色自身的境界强度适当减少 `energy` 值。若 `energy` 不足，则无法使用该斗技，或威力大幅下降，AI 需在剧情中体现这一点。丹药中的回气类（如回气丹）可以恢复 energy。  # [新增]

请以JSON格式返回，包含以下字段：
- "story": 下一步剧情的文本描述（第一人称视角）
- "new_state": 更新后的状态字典，必须包含与初始状态相同的字段（realm, location, hp, energy, items, description），只列出有变化的字段也可以，但建议全量更新。

返回格式示例：
{{"story": "我提出想看看他的实力，他冷哼一声，周身斗气涌动，竟是斗皇强者！我心中一凛，连忙后退。", "new_state": {{"location": "魔兽山脉深处", "hp": 90, "description": "遇到神秘强者，警惕万分。"}}}}

注意：只返回JSON，不要有其他文字。"""

    action_text = f"用户行动：{user_action}" if user_action else "用户未输入行动，请自由推演。"
    user_prompt = f"当前状态：\n{json.dumps(state.state, ensure_ascii=False)}\n全部历史剧情：\n{history_text}\n{action_text}\n请生成下一步。"
    
    if retry_count > 0:
        user_prompt += f"\n\n你上次返回的JSON格式有误，请仔细检查并确保输出的JSON是严格有效的。特别注意字符串内的双引号需要转义，不要有实际换行符。"

    reply = call_deepseek(user_prompt, system_msg, api_key)
    if not reply:
        return None

    # 提取JSON代码块
    if "```json" in reply:
        reply = reply.split("```json")[1].split("```")[0].strip()
    elif "```" in reply:
        reply = reply.split("```")[1].split("```")[0].strip()

    # 尝试解析JSON
    try:
        result = json.loads(reply)
    except json.JSONDecodeError as e:
        print(f"JSON解析失败，尝试清理换行符: {e}")
        cleaned_reply = reply.replace('\n', ' ').replace('\r', ' ')
        try:
            result = json.loads(cleaned_reply)
            print("清理换行符后解析成功。")
        except json.JSONDecodeError as e2:
            print(f"清理后仍然解析失败: {e2}\nAI回复原文:\n{reply}")
            if retry_count < 3:
                print(f"尝试第{retry_count+2}次重试...")
                return generate_next_state(state, api_key, heter_fire_data, combat_skills_data, dan_data, user_action, retry_count+1)
            else:
                print("重试次数已达上限，放弃。")
                return None

    if "story" not in result or "new_state" not in result:
        print("AI返回缺少必要字段")
        return None

    new_state = state.state.copy()
    new_state.update(result["new_state"])
    return {
        "story": result["story"],
        "new_state": new_state
    }

# ================== 存档管理 ==================
def save_game(state: GameState, autosave: bool = False) -> str:
    """保存游戏状态，autosave=True 时保存为自动存档文件，否则保存为时间戳文件"""
    ensure_dir(SAVE_DIR)
    if autosave:
        filepath = AUTOSAVE_FILE
    else:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{state.role}_{timestamp}.json"
        filepath = os.path.join(SAVE_DIR, filename)
    save_json(state.to_dict(), filepath)
    return filepath

def list_saves() -> List[str]:
    """列出所有存档文件（包括自动存档）"""
    ensure_dir(SAVE_DIR)
    files = [f for f in os.listdir(SAVE_DIR) if f.endswith('.json')]
    # 将自动存档放在最前面（如果存在）
    if "autosave.json" in files:
        files.remove("autosave.json")
        files.insert(0, "autosave.json")
    return files

def load_save(filename: str) -> Optional[GameState]:
    """加载指定存档文件"""
    filepath = os.path.join(SAVE_DIR, filename)
    try:
        data = load_json(filepath)
        return GameState.from_dict(data)
    except Exception as e:
        print(f"加载存档失败: {e}")
        return None

# ================== 主菜单 ==================
def main_menu():
    print("=" * 50)
    print("     斗破苍穹 角色推演系统")
    print("=" * 50)
    print("1. 开始新推演")
    print("2. 设置")
    print("3. 加载存档")
    print("4. 退出")
    return input("请选择操作 (1-4): ").strip()

def settings_menu():
    global SAVE_DIR, AUTOSAVE_FILE
    print("\n--- 设置 ---")
    print("当前API Key: " + (api_key[:5] + "****" if api_key else "未设置"))
    print("存储目录: " + SAVE_DIR)
    print("1. 修改API Key")
    print("2. 修改存储目录")
    print("3. 返回主菜单")
    choice = input("请选择: ").strip()
    if choice == "1":
        new_key = input("请输入新的API Key: ").strip()
        if new_key:
            save_json({"api_key": new_key}, API_CONFIG_FILE)
            print("API Key已更新，请重启程序生效。")
    elif choice == "2":
        new_dir = input("请输入新的存储目录路径: ").strip()
        if new_dir:
            SAVE_DIR = new_dir
            AUTOSAVE_FILE = os.path.join(SAVE_DIR, "autosave.json")
            print("存储目录已更新。")
    input("按回车返回...")

# ================== 主推演循环 ==================
def play_game(state: GameState, api_key: str, heter_fire: dict, combat_skills: dict, dan_data: dict):
    while True:
        print("\n" + "=" * 50)
        print(f"角色：{state.role}")
        print(f"时间段：{state.time_period}")
        print(f"当前状态：")
        print(f"  境界：{state.state.get('realm', '未知')}")
        print(f"  地点：{state.state.get('location', '未知')}")
        print(f"  生命值：{state.state.get('hp', 100)}")
        print(f"  斗气值：{state.state.get('energy', 100)}")  # [新增] 显示斗气
        print(f"  物品：{', '.join(state.state.get('items', []))}")
        print(f"  描述：{state.state.get('description', '')}")
        print("-" * 50)
        print("1. 继续推演")
        print("2. 手动存档")
        print("3. 查看历史剧情")
        print("4. 返回主菜单")
        choice = input("请选择操作: ").strip()

        if choice == "1":
            user_action = input("\n请输入你想采取的行动或说的话（直接回车则自由推演）: ").strip()
            print("\n正在生成剧情...")
            result = generate_next_state(state, api_key, heter_fire, combat_skills, dan_data, user_action)
            if result:
                story = result["story"]
                new_state = result["new_state"]
                print("\n【新剧情】")
                print(story)
                state.state = new_state
                state.history.append(story)

                # 自动存档（覆盖上一次自动存档）
                autosave_path = save_game(state, autosave=True)
                print(f"已自动存档至：{autosave_path}")

                if state.state.get("hp", 100) <= 0:
                    print("\n⚠️ 你的角色已经死亡！游戏结束。")
                    save_choice = input("是否保存死亡结局？(y/n): ").lower()
                    if save_choice == 'y':
                        save_game(state)  # 手动保存死亡结局
                    break
            else:
                print("生成失败，请重试。")
        elif choice == "2":
            filepath = save_game(state)  # 手动存档（时间戳命名）
            print(f"游戏已手动存档至：{filepath}")
        elif choice == "3":
            print("\n--- 全部历史剧情 ---")
            for i, h in enumerate(state.history):
                print(f"{i+1}. {h}")
            input("按回车继续...")
        elif choice == "4":
            break
        else:
            print("无效选择，请重新输入。")

# ================== 入口 ==================
if __name__ == "__main__":
    roles_data = load_json(ROLES_FILE)
    heter_fire = load_json(HETER_FIRE_FILE)
    combat_skills = load_json(COMBAT_SKILLS_FILE)
    dan_data = load_json(DAN_FILE)       # 新增：加载丹药数据
    api_key = get_api_key()

    if not api_key:
        print("错误：未找到API Key，请在api_config.json中设置。")
        sys.exit(1)

    while True:
        choice = main_menu()
        if choice == "1":
            print("\n--- 角色列表 ---")
            for idx, role in enumerate(roles_data, 1):
                print(f"{idx}. {role['name']} - {role['identity']}")
            print("0. 输入自定义角色名")
            role_choice = input("请选择角色编号或输入名称: ").strip()
            selected_role = None
            identity = ""
            if role_choice.isdigit() and 1 <= int(role_choice) <= len(roles_data):
                idx = int(role_choice) - 1
                selected_role = roles_data[idx]['name']
                identity = roles_data[idx]['identity']
            elif role_choice == "0":
                selected_role = input("请输入自定义角色名: ").strip()
                identity = "自定义角色"
            else:
                for role in roles_data:
                    if role['name'] == role_choice:
                        selected_role = role_choice
                        identity = role['identity']
                        break
                if not selected_role:
                    print("无效选择，返回主菜单。")
                    continue

            print("\n--- 选择时间段 ---")
            for p in TIME_PERIODS:
                print(p)
            period_choice = input("请选择时间段编号 (1-12): ").strip()
            if period_choice.isdigit() and 1 <= int(period_choice) <= 12:
                idx = int(period_choice) - 1
                if idx == 11:
                    time_period = input("请输入自定义时间段描述: ").strip()
                else:
                    time_period = TIME_PERIODS[idx][3:]
            else:
                print("无效选择，返回主菜单。")
                continue

            print("\n正在生成初始状态...")
            initial_state = generate_initial_state(selected_role, identity, time_period, api_key, heter_fire, combat_skills, dan_data)
            if not initial_state:
                print("初始状态生成失败，请重试。")
                continue
            print("\n【初始状态】")
            print(f"境界：{initial_state['realm']}")
            print(f"地点：{initial_state['location']}")
            print(f"生命值：{initial_state['hp']}")
            print(f"斗气值：{initial_state.get('energy', 100)}")  # [新增]
            print(f"物品：{', '.join(initial_state['items'])}")
            print(f"描述：{initial_state['description']}")
            confirm = input("\n是否确认开始推演？(y/n): ").lower()
            if confirm == 'y':
                state = GameState(selected_role, time_period, initial_state)
                play_game(state, api_key, heter_fire, combat_skills, dan_data)   # 传入丹药数据
            else:
                print("取消推演。")

        elif choice == "2":
            settings_menu()
        elif choice == "3":
            saves = list_saves()
            if not saves:
                print("没有找到存档。")
                input("按回车返回...")
                continue
            print("\n--- 存档列表 ---")
            for i, f in enumerate(saves, 1):
                print(f"{i}. {f}")
            save_choice = input("请输入要加载的存档编号 (0返回): ").strip()
            if save_choice.isdigit():
                idx = int(save_choice) - 1
                if 0 <= idx < len(saves):
                    state = load_save(saves[idx])
                    if state:
                        print(f"加载存档 {saves[idx]} 成功。")
                        play_game(state, api_key, heter_fire, combat_skills, dan_data)   # 传入丹药数据
                elif idx == -1:
                    continue
                else:
                    print("无效编号。")
            else:
                print("无效输入。")
        elif choice == "4":
            print("感谢使用，再见！")
            break
        else:
            print("无效选择，请重新输入。")

#作者：南鸾之巅·零柒柒