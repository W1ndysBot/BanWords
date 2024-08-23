import logging
import re
import os
import sys
import asyncio
import datetime

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


from app.api import *
from app.config import owner_id
from app.switch import load_switch, save_switch

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
def load_BanWords(group_id):
    try:
        with open(
            os.path.join(DATA_DIR, f"{group_id}.json"), "r", encoding="utf-8"
        ) as f:
            return json.load(f)
    except FileNotFoundError:
        return []


# 保存违禁词列表
def save_BanWords(group_id, BanWords):
    with open(os.path.join(DATA_DIR, f"{group_id}.json"), "w", encoding="utf-8") as f:
        json.dump(BanWords, f, ensure_ascii=False, indent=4)


# 查看违禁词开关状态
def load_BanWords_switch(group_id):
    return load_switch(group_id, "违禁词监控")


# 保存违禁词开关状态
def save_BanWords_switch(group_id, switch):
    save_switch(group_id, "违禁词监控", switch)


# 查看违禁词列表
async def list_BanWords(websocket, group_id, user_id):
    BanWords = load_BanWords(group_id)
    if BanWords:
        BanWords_message = "违禁词列表:\n" + "\n".join(BanWords)
    else:
        BanWords_message = "违禁词列表为空。"
    await send_group_msg(
        websocket,
        group_id,
        f"[CQ:at,id={user_id}]违禁词列表已私发，请注意查收。",
    )
    await send_private_msg(websocket, user_id, BanWords_message)


# 检查违禁词的主函数
async def check_BanWords(websocket, group_id, msg):
    if not load_BanWords_switch(group_id) or is_authorized(
        msg["sender"]["role"], msg["sender"]["user_id"]
    ):
        return False

    # 视频监控
    if load_switch(group_id, "视频监控"):
        message_id = int(msg["message_id"])
        if "[CQ:video," in msg["raw_message"]:
            await delete_msg(websocket, message_id)
            warning_message = "为防止广告，本群禁止发送视频。"
            await send_group_msg(websocket, group_id, warning_message)
            return

    # 使用正则表达式检测文本中是否包含任何不可见字符
    if re.search(r"[\u200b\u200c\u200d\u200e\u200f\ufeff]", msg.get("raw_message")):
        warning_message = "检测到消息中有不可见字符，已撤回"
        await send_group_msg(websocket, group_id, warning_message)
        message_id = int(msg["message_id"])
        await delete_msg(websocket, message_id)
        return

    # 违禁词检测
    BanWords = load_BanWords(group_id)
    raw_message = msg.get("raw_message")

    for word in BanWords:

        # 检查是否为违禁词，在re.search中，违禁词内容可以是字符串或正则表达式
        if re.search(word, raw_message):
            message_id = msg.get("message_id")
            user_id = msg.get("sender").get("user_id")
            await set_group_ban(websocket, group_id, user_id, 60)
            await delete_msg(websocket, message_id)
            warning_message = (
                f"警告：请不要发送违禁词，误封请联系管理员处理 [CQ:at,qq={owner_id[0]}]"
            )
            await send_group_msg(websocket, group_id, warning_message)

            await send_private_msg(
                websocket,
                owner_id,
                f"""群 {group_id}

成员 {user_id}

在 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

发送了违禁词 {word}

原消息内容为 {raw_message}""",
            )
            return True

    return False


# 视频检测管理
async def manage_video_check(
    websocket, group_id, raw_message, message_id, is_authorized
):
    if not is_authorized:
        return

    command_actions = {
        "vc-on": (True, "已开启视频监控。", "视频监控已经开启了，无需重复开启。"),
        "vc-off": (False, "已关闭视频监控。", "视频监控已经关闭了，无需重复关闭。"),
    }

    action = command_actions.get(raw_message)
    if action:
        current_status, success_message, fail_message = action
        if load_switch(group_id, "视频监控") == current_status:
            await send_group_msg(
                websocket,
                group_id,
                f"[CQ:reply,id={message_id}]{fail_message}",
            )
        else:
            save_switch(group_id, "视频监控", current_status)
            await send_group_msg(
                websocket,
                group_id,
                f"[CQ:reply,id={message_id}]{success_message}",
            )


# 违禁词管理
async def manage_BanWords(
    websocket, message_id, group_id, user_id, raw_message, is_authorized
):
    if not is_authorized:
        return

    command_actions = {
        "bw-on": (True, "已开启违禁词检测。", "违禁词检测已经开启了，无需重复开启。"),
        "bw-off": (
            False,
            "已关闭违禁词检测。",
            "违禁词检测已经关闭了，无需重复关闭。",
        ),
        "bw-list": ("list", None, None),
    }

    if raw_message.startswith("bw-add"):
        new_word = raw_message[6:].strip()  # 从命令字符串中直接提取违禁词
        if not new_word:
            await send_group_msg(
                websocket,
                group_id,
                f"[CQ:reply,id={message_id}] 命令格式错误，请使用: bw-add违禁词",
            )
            return
        BanWords = load_BanWords(group_id)
        if new_word not in BanWords:
            BanWords.append(new_word)
            save_BanWords(group_id, BanWords)
            await send_group_msg(
                websocket,
                group_id,
                f"[CQ:reply,id={message_id}] 已添加违禁词: {new_word}",
            )
        else:
            await send_group_msg(
                websocket,
                group_id,
                f"[CQ:reply,id={message_id}] 违禁词已存在，无需重复添加。",
            )
    elif raw_message.startswith("bw-rm"):
        remove_word = raw_message[6:].strip()  # 从命令字符串中直接提取违禁词
        if not remove_word:
            await send_group_msg(
                websocket,
                group_id,
                f"[CQ:reply,id={message_id}] 命令格式错误，请使用: bw-rm违禁词",
            )
            return
        BanWords = load_BanWords(group_id)
        if remove_word in BanWords:
            BanWords.remove(remove_word)
            save_BanWords(group_id, BanWords)
            await send_group_msg(
                websocket,
                group_id,
                f"[CQ:reply,id={message_id}] 已删除违禁词: {remove_word}",
            )
        else:
            await send_group_msg(
                websocket,
                group_id,
                f"[CQ:reply,id={message_id}] 违禁词不存在，无需删除。",
            )
    else:
        action = command_actions.get(raw_message)
        if action:
            current_status, success_message, fail_message = action
            if action[0] == "list":
                await list_BanWords(websocket, group_id, user_id)
            elif load_BanWords_switch(group_id) == current_status:
                await send_group_msg(
                    websocket,
                    group_id,
                    f"[CQ:reply,id={message_id}]{fail_message}",
                )
            else:
                save_BanWords_switch(group_id, current_status)
                await send_group_msg(
                    websocket,
                    group_id,
                    f"[CQ:reply,id={message_id}]{success_message}",
                )


# 处理违禁词消息事件
async def handle_BanWords_group_message(websocket, msg):
    try:
        # 确保数据目录存在
        os.makedirs(DATA_DIR, exist_ok=True)

        user_id = str(msg.get("sender", {}).get("user_id"))
        group_id = str(msg.get("group_id"))
        raw_message = str(msg.get("raw_message"))
        role = str(msg.get("sender", {}).get("role"))
        message_id = int(msg.get("message_id"))

        is_admin = is_group_admin(role)  # 是否是群管理员
        is_owner = is_group_owner(role)  # 是否是群主
        is_authorized = (is_admin or is_owner) or (
            user_id in owner_id
        )  # 是否是群主或管理员或root管理员

        # 并发执行管理和违禁词检测函数和视频检测函数
        await asyncio.gather(
            manage_BanWords(
                websocket, message_id, group_id, user_id, raw_message, is_authorized
            ),
            check_BanWords(websocket, group_id, msg),
            manage_video_check(
                websocket, group_id, raw_message, message_id, is_authorized
            ),
        )

    except Exception as e:
        logging.error(f"处理违禁词系统时发生错误: {e}")
        return
