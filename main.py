from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.provider import ProviderRequest
import json
import os
import re
from typing import Dict, Any
from datetime import datetime

@register("AzusaImp", 
          "有栖日和", 
          "梓的用户信息和印象插件", 
          "0.0.3", 
          "https://github.com/Angus-YZH/astrbot_plugin_AzusaImp")

class AzusaImp(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.user_info_file = "data/plugin_data/AzusaImp/user_info.json"
        self.group_info_file = "data/plugin_data/AzusaImp/group_info.json"  # 新增群信息文件
        self.ensure_data_directory()
        self.placeholder_pattern = re.compile(r'\[User ID: (\d+), Nickname: ([^\]]+)\]')

    def ensure_data_directory(self):
        """确保data目录存在"""
        os.makedirs(os.path.dirname(self.user_info_file), exist_ok=True)
        os.makedirs(os.path.dirname(self.group_info_file), exist_ok=True)  # 确保群信息目录也存在

    def load_user_info(self) -> Dict[str, Any]:
        """加载用户信息文件"""
        try:
            if os.path.exists(self.user_info_file):
                with open(self.user_info_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"加载用户信息文件失败: {e}")
        return {}

    def load_group_info(self) -> Dict[str, Any]:
        """加载群信息文件"""
        try:
            if os.path.exists(self.group_info_file):
                with open(self.group_info_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"加载群信息文件失败: {e}")
        return {}

    def save_user_info(self, user_info: Dict[str, Any]):
        """保存用户信息到文件"""
        try:
            with open(self.user_info_file, 'w', encoding='utf-8') as f:
                json.dump(user_info, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存用户信息文件失败: {e}")

    def save_group_info(self, group_info: Dict[str, Any]):
        """保存群信息到文件"""
        try:
            with open(self.group_info_file, 'w', encoding='utf-8') as f:
                json.dump(group_info, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存群信息文件失败: {e}")

    async def get_qq_user_info(self, event: AstrMessageEvent, qq_number: str, update_user_info: bool = True) -> Dict[str, Any]:
        """获取QQ用户详细信息
        
        Args:
            update_user_info: 是否更新用户信息，False时只获取群信息
        """
        user_info = {
            "qq_number": qq_number,
            "timestamp": event.message_obj.timestamp
        }
        
        # 只有在需要更新用户信息时才设置昵称
        if update_user_info:
            user_info["nickname"] = event.get_sender_name()
    
        try:
            # 检查是否为QQ平台
            if event.get_platform_name() != "aiocqhttp":
                return user_info
    
            # 调用QQ协议端API获取用户信息
            from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
            if isinstance(event, AiocqhttpMessageEvent):
                client = event.bot
                
                # 只在需要更新用户信息时获取基础用户信息
                if update_user_info:
                    # 获取基础用户信息
                    payloads = {
                        "user_id": int(qq_number),
                        "no_cache": True
                    }
                    
                    stranger_info = await client.api.call_action('get_stranger_info', **payloads)
                    
                    # 尝试获取生日信息
                    birthday = self.parse_birthday(stranger_info)
                    
                    user_info.update({
                        "gender": self.get_gender_text(stranger_info.get('sex', 'unknown')),
                        "birthday": birthday
                    })
    
                # 如果是群聊消息，获取群成员信息（每次都获取）
                group_id = event.get_group_id()
                if group_id:
                    group_member_payloads = {
                        "group_id": int(group_id),
                        "user_id": int(qq_number),
                        "no_cache": True
                    }
                    
                    try:
                        group_member_info = await client.api.call_action('get_group_member_info', **group_member_payloads)
                        
                        # 获取群身份和头衔
                        role = group_member_info.get('role', 'member')
                        title = group_member_info.get('title', '') or '无'
                        
                        user_info.update({
                            "group_role": role,
                            "group_title": title
                        })
                        
                        logger.info(f"成功获取用户 {qq_number} 在群 {group_id} 的成员信息")
                    except Exception as e:
                        logger.error(f"获取群成员信息失败: {e}")
                
                logger.info(f"成功获取用户 {qq_number} 的信息")
                
        except Exception as e:
            logger.error(f"获取用户 {qq_number} 信息时出错: {e}")
    
        return user_info

    def get_group_role_text(self, role: str) -> str:
        """将群身份代码转换为中文文本"""
        role_map = {'owner': '群主', 'admin': '管理员', 'member': '成员'}
        return role_map.get(role, '成员')

    def parse_birthday(self, stranger_info: Dict[str, Any]) -> str:
        """从用户信息中解析生日"""
        if (
            stranger_info.get("birthday_year")
            and stranger_info.get("birthday_month")
            and stranger_info.get("birthday_day")
        ):
            return f"{stranger_info['birthday_year']}-{stranger_info['birthday_month']}-{stranger_info['birthday_day']}"
        return "未知"

    def calculate_age(self, birthday: str) -> int:
        """根据生日计算年龄"""
        if birthday == "未知":
            return 0
            
        try:
            # 解析生日字符串
            parts = birthday.split('-')
            if len(parts) != 3:
                return 0
                
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
            
            # 获取当前日期
            today = datetime.now()
            
            # 计算年龄
            age = today.year - year
            
            # 如果今年生日还没过，年龄减1
            if (today.month, today.day) < (month, day):
                age -= 1
                
            return age
        except Exception as e:
            logger.error(f"计算年龄时出错: {e}")
            return 0

    def get_gender_text(self, gender: str) -> str:
        """将性别代码转换为中文文本"""
        gender_map = {
            'male': '男',
            'female': '女',
            'unknown': '未知'
        }
        return gender_map.get(gender, '未知')

    def format_user_info_for_prompt(self, user_info: Dict[str, Any], is_group: bool = False) -> str:
        """将用户信息格式化为提示词文本"""
        prompt_parts = []
        
        # 基础信息
        prompt_parts.append(f"用户QQ号: {user_info.get('qq_number', '未知')}")
        prompt_parts.append(f"昵称: {user_info.get('nickname', '未知')}")
        
        # 个人信息
        if user_info.get('gender') != '未知':
            prompt_parts.append(f"性别: {user_info.get('gender')}")
        
        # 生日信息 - 总是显示
        birthday = user_info.get('birthday', '未知')
        prompt_parts.append(f"生日: {birthday}")
        
        # 年龄信息
        if birthday != '未知':
            age = self.calculate_age(birthday)
            if age > 0:
                prompt_parts.append(f"年龄: {age}岁")
        
        # 群聊额外信息
        if is_group:
            group_role = user_info.get('group_role')
            if group_role:
                prompt_parts.append(f"群身份: {self.get_group_role_text(group_role)}")
            
            group_title = user_info.get('group_title', '')
            if group_title and group_title != '无':
                prompt_parts.append(f"群头衔: {group_title}")
    
        return "，".join(prompt_parts)
        
    def replace_nickname_in_context(self, all_user_info: Dict[str, Any], pre_text: str) -> str:
        """更安全的昵称替换方案：解析-替换-重建"""
        if not all_user_info or not pre_text:
            return pre_text
        
        # 查找所有用户占位符
        placeholder_pattern = r'\[User ID: (\d+), Nickname: ([^\]]+)\]'
        
        def replace_callback(match):
            qq_number = match.group(1)
            old_nickname = match.group(2)
            
            # 精确查找用户信息
            user_info = all_user_info.get(qq_number)
            if user_info:
                new_nickname = user_info.get('nickname', '')
                
                # 如果新昵称与原昵称相同，跳过替换
                if new_nickname == old_nickname:
                    return match.group(0)
                
                # 如果新昵称存在且与原昵称不同，进行替换
                if new_nickname:
                    return f'[User ID: {qq_number}, Nickname: {new_nickname}]'
            
            # 如果没有找到用户信息或新昵称为空，保持原样
            return match.group(0)
        
        try:
            return re.sub(placeholder_pattern, replace_callback, pre_text)
        except Exception as e:
            logger.error(f"替换昵称时发生错误: {e}")
            return pre_text
    
    @filter.on_llm_request()
    async def on_llm_request_hook(self, event: AstrMessageEvent, req: ProviderRequest):
        """LLM请求时的钩子，用于记录用户信息并添加到提示词"""
        try:
            # 只处理QQ平台的消息
            if event.get_platform_name() != "aiocqhttp":
                return
    
            qq_number = event.get_sender_id()
            group_id = event.get_group_id()
            is_group = bool(group_id)
            
            # 加载现有信息
            all_user_info = self.load_user_info()
            all_group_info = self.load_group_info()
            
            # 如果用户信息不存在，则获取并保存
            if qq_number not in all_user_info:
                user_info = await self.get_qq_user_info(event, qq_number, update_user_info=True)
                all_user_info[qq_number] = user_info
                self.save_user_info(all_user_info)
                logger.info(f"已记录新用户基本信息: QQ{qq_number}")
            
            # 如果是群聊，保存群成员信息到群信息文件（每次都更新）
            if is_group:
                # 确保群ID键存在
                if group_id not in all_group_info:
                    all_group_info[group_id] = {}
                    
                user_info = all_user_info[qq_number]
                group_info = {
                    "qq_number": qq_number,
                    "group_id": group_id,
                    "group_role": user_info.get('group_role', 'member'),
                    "group_title": user_info.get('group_title', '无'),
                    "nickname": user_info.get('nickname', '未知'),
                    "timestamp": datetime.now().isoformat()
                }
                all_group_info[group_id][qq_number] = group_info
                self.save_group_info(all_group_info)
                logger.info(f"已更新用户 {qq_number} 在群 {group_id} 的群成员信息")
            
            # 将用户信息添加到系统提示词
            user_prompt = self.format_user_info_for_prompt(all_user_info[qq_number], is_group)
            req.context = self.replace_nickname_in_context(all_user_info, req.context)
            
            if user_prompt:
                # 在现有系统提示词前添加用户信息，并明确要求使用昵称称呼用户
                original_system_prompt = req.system_prompt or ""
                nickname = all_user_info[qq_number].get('nickname', '用户')
                req.system_prompt = f"当前对话用户信息: {user_prompt}。请称呼用户为{nickname}。{original_system_prompt}"
                    
                logger.debug(f"已将用户信息添加到提示词: {user_prompt}")
    
        except Exception as e:
            logger.error(f"在处理LLM请求钩子时出错: {e}")
    
    @filter.command_group("修改信息", alias={'update_info', 'set_info'})
    async def update_info_group(self):
        """修改用户信息命令组"""
        pass
    
    @update_info_group.command("昵称", alias={'nickname', 'name'})
    async def update_nickname(self, event: AstrMessageEvent, new_nickname: str):
        """修改昵称
        
        Args:
            new_nickname(string): 新的昵称
        """
        try:
            qq_number = event.get_sender_id()
            all_user_info = self.load_user_info()
            
            if qq_number not in all_user_info:
                yield event.plain_result("您的用户信息不存在，请先发送一条消息触发信息记录")
                return
            
            # 更新昵称
            old_nickname = all_user_info[qq_number].get('nickname', '')
            all_user_info[qq_number]['nickname'] = new_nickname
            
            self.save_user_info(all_user_info)
            
            logger.info(f"用户 {qq_number} 更新昵称: {old_nickname} -> {new_nickname}")
            yield event.plain_result(f"已更新您的昵称: {new_nickname}")
            
        except Exception as e:
            logger.error(f"更新昵称时出错: {e}")
            yield event.plain_result(f"更新昵称失败: {str(e)}")
    
    @update_info_group.command("生日", alias={'birthday', 'birth'})
    async def update_birthday(self, event: AstrMessageEvent, new_birthday: str):
        """修改生日
        
        Args:
            new_birthday(string): 新的生日 (YYYY-MM-DD格式)
        """
        try:
            qq_number = event.get_sender_id()
            all_user_info = self.load_user_info()
            
            if qq_number not in all_user_info:
                yield event.plain_result("您的用户信息不存在，请先发送一条消息触发信息记录")
                return
            
            # 验证生日格式 YYYY-MM-DD
            try:
                parts = new_birthday.split('-')
                if len(parts) != 3:
                    raise ValueError("生日格式不正确")
                year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                # 简单验证日期合理性
                if not (1900 <= year <= datetime.now().year):
                    raise ValueError("年份不合理")
                if not (1 <= month <= 12):
                    raise ValueError("月份不合理")
                if not (1 <= day <= 31):
                    raise ValueError("日期不合理")
            except Exception as e:
                yield event.plain_result(f"生日格式不正确，请使用 YYYY-MM-DD 格式: {e}")
                return
            
            # 更新生日
            old_birthday = all_user_info[qq_number].get('birthday', '')
            all_user_info[qq_number]['birthday'] = new_birthday
            
            self.save_user_info(all_user_info)
            
            logger.info(f"用户 {qq_number} 更新生日: {old_birthday} -> {new_birthday}")
            yield event.plain_result(f"已更新您的生日: {new_birthday}")
            
        except Exception as e:
            logger.error(f"更新生日时出错: {e}")
            yield event.plain_result(f"更新生日失败: {str(e)}")
    
    @update_info_group.command("性别", alias={'gender', 'sex'})
    async def update_gender(self, event: AstrMessageEvent, new_gender: str):
        """修改性别
        
        Args:
            new_gender(string): 新的性别 (男/女/未知)
        """
        try:
            qq_number = event.get_sender_id()
            all_user_info = self.load_user_info()
            
            if qq_number not in all_user_info:
                yield event.plain_result("您的用户信息不存在，请先发送一条消息触发信息记录")
                return
            
            # 验证性别值
            valid_genders = ['男', '女']
            if new_gender not in valid_genders:
                yield event.plain_result(f"性别必须是: {', '.join(valid_genders)}")
                return
            
            # 更新性别
            old_gender = all_user_info[qq_number].get('gender', '')
            all_user_info[qq_number]['gender'] = new_gender
            
            self.save_user_info(all_user_info)
            
            logger.info(f"用户 {qq_number} 更新性别: {old_gender} -> {new_gender}")
            yield event.plain_result(f"已更新您的性别: {new_gender}")
        
        except Exception as e:
            logger.error(f"更新性别时出错: {e}")
            yield event.plain_result(f"更新性别失败: {str(e)}")

    @filter.command("my_info", alias={'我的信息', '查看信息'})
    async def show_my_info(self, event: AstrMessageEvent):
        """查看当前用户信息"""
        try:
            qq_number = event.get_sender_id()
            all_user_info = self.load_user_info()
            
            if qq_number not in all_user_info:
                yield event.plain_result("您的用户信息不存在，请先发送一条消息触发信息记录")
                return
            
            user_info = all_user_info[qq_number]
            info_text = f"您的信息:\nQQ: {user_info.get('qq_number', '未知')}\n昵称: {user_info.get('nickname', '未知')}\n性别: {user_info.get('gender', '未知')}\n生日: {user_info.get('birthday', '未知')}"
            
            # 计算并显示年龄
            birthday = user_info.get('birthday', '未知')
            if birthday != '未知':
                age = self.calculate_age(birthday)
                if age > 0:
                    info_text += f"\n年龄: {age}岁"
            
            yield event.plain_result(info_text)
            
        except Exception as e:
            logger.error(f"查看用户信息时出错: {e}")
            yield event.plain_result(f"获取信息失败: {str(e)}")

    async def terminate(self):
        """插件卸载时的清理工作"""
        logger.info("QQ用户信息记录器插件已卸载")