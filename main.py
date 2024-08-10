import logging
import re
import os
import sys
import asyncio

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


from app.api import *
from app.config import owner_id
from app.scripts.GroupSwitch.main import *

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "BanWords",
)


# 是否是群主
def is_group_owner(role):
    return role == "owner"


# 是否是管理员
def is_group_admin(role):
    return role == "admin"


# 是否是管理员或群主或root管理员
def is_authorized(role, user_id):
    is_admin = is_group_admin(role)
    is_owner = is_group_owner(role)
    return (is_admin or is_owner) or (user_id in owner_id)


# 加载违禁词列表
def load_banned_words(group_id):
    try:
        with open(
            os.path.join(DATA_DIR, f"{group_id}.json"), "r", encoding="utf-8"
        ) as f:
            return json.load(f)
    except FileNotFoundError:
        return []


# 保存违禁词列表
def save_banned_words(group_id, banned_words):
    with open(os.path.join(DATA_DIR, f"{group_id}.json"), "w", encoding="utf-8") as f:
        json.dump(banned_words, f, ensure_ascii=False, indent=4)


# 查看违禁词开关状态
def load_banned_words_status(group_id):
    return load_switch(group_id, "banned_words_status")


# 保存违禁词开关状态
def save_banned_words_status(group_id, status):
    save_switch(group_id, "banned_words_status", status)


# 查看违禁词列表
async def list_banned_words(websocket, group_id):
    banned_words = load_banned_words(group_id)
    if banned_words:
        banned_words_message = "违禁词列表:\n" + "\n".join(banned_words)
    else:
        banned_words_message = "违禁词列表为空。"
    await send_group_msg(websocket, group_id, banned_words_message)


# 检查违禁词的主函数
async def check_banned_words(websocket, group_id, msg):
    if not load_banned_words_status(group_id) or is_authorized(
        msg["sender"]["role"], msg["sender"]["user_id"]
    ):
        return False

    # 使用正则表达式检测文本中是否包含任何不可见字符
    if re.search(r"[\u200b\u200c\u200d\u200e\u200f\ufeff]", msg.get("raw_message")):
        warning_message = "检测到消息中有不可见字符，已撤回"
        await send_group_msg(websocket, group_id, warning_message)
        message_id = int(msg["message_id"])
        await delete_msg(websocket, message_id)
        return True

    banned_words = load_banned_words(group_id)
    raw_message = msg["raw_message"]

    for word in banned_words:

        # 检查是否为违禁词，在re.search中，违禁词内容可以是字符串或正则表达式
        if re.search(word, raw_message):
            message_id = int(msg["message_id"])
            await delete_msg(websocket, message_id)
            warning_message = f"""警告：请不要发送违禁词！
如有误删是发的内容触发了违禁词，请及时联系管理员处理。

有新的事件被处理了，请查看是否正常处理[CQ:at,qq=2769731875]"""
            await send_group_msg(websocket, group_id, warning_message)
            user_id = msg["sender"]["user_id"]
            await set_group_ban(websocket, group_id, user_id, 60)
            return True

    return False


async def handle_BanWords_group_message(websocket, msg):
    try:
        user_id = msg["user_id"]
        group_id = msg["group_id"]
        raw_message = msg["raw_message"]
        role = msg["sender"]["role"]
        message_id = int(msg["message_id"])
        self_id = str(msg.get("self_id", ""))  # 机器人QQ，转为字符串方便操作

        is_admin = is_group_admin(role)  # 是否是群管理员
        is_owner = is_group_owner(role)  # 是否是群主
        is_authorized = (is_admin or is_owner) or (
            user_id in owner_id
        )  # 是否是群主或管理员或root管理员

        if is_authorized:
            if raw_message == "on ban words" or raw_message == "开启违禁词检测":
                if load_banned_words_status(group_id):
                    asyncio.create_task(
                        send_group_msg(
                            websocket, group_id, "违禁词检测已经开启了，无需重复开启。"
                        )
                    )
                else:
                    save_banned_words_status(group_id, True)
                    asyncio.create_task(
                        send_group_msg(websocket, group_id, "已开启违禁词检测。")
                    )
            elif raw_message == "off ban words" or raw_message == "关闭违禁词检测":
                if not load_banned_words_status(group_id):
                    asyncio.create_task(
                        send_group_msg(
                            websocket, group_id, "违禁词检测已经关闭了，无需重复关闭。"
                        )
                    )
                else:
                    save_banned_words_status(group_id, False)
                    asyncio.create_task(
                        send_group_msg(websocket, group_id, "已关闭违禁词检测。")
                    )

        if is_authorized:
            if raw_message.startswith("add ban word ") or raw_message.startswith(
                "添加违禁词 "
            ):
                new_word = raw_message.split(" ", 1)[1].strip()
                banned_words = load_banned_words(group_id)
                if new_word not in banned_words:
                    banned_words.append(new_word)
                    save_banned_words(group_id, banned_words)
                    asyncio.create_task(
                        send_group_msg(websocket, group_id, f"已添加违禁词: {new_word}")
                    )
            elif raw_message.startswith("rm ban word ") or raw_message.startswith(
                "删除违禁词 "
            ):
                remove_word = raw_message.split(" ", 1)[1].strip()
                banned_words = load_banned_words(group_id)
                if remove_word in banned_words:
                    banned_words.remove(remove_word)
                    save_banned_words(group_id, banned_words)
                    asyncio.create_task(
                        send_group_msg(
                            websocket, group_id, f"已删除违禁词: {remove_word}"
                        )
                    )
            elif raw_message == "list ban words" or raw_message == "查看违禁词":
                asyncio.create_task(list_banned_words(websocket, group_id))

        # 前面执行完所有命令之后，检查违禁词
        asyncio.create_task(check_banned_words(websocket, group_id, msg))

    except Exception as e:
        logging.error(f"处理违禁词系统时发生错误: {e}")
        return
