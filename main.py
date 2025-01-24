import logging
import re
import os
import sys
import asyncio
from datetime import datetime

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


from app.api import *
from app.config import *
from app.switch import load_switch, save_switch
from app.scripts.InviteChain.main import get_invited_users

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
    user_id = str(user_id)
    try:
        BanWords = load_BanWords(group_id)
        if BanWords:
            BanWords_message = "群" + group_id + "的违禁词列表:\n" + "\n".join(BanWords)
            await send_private_msg(
                websocket, user_id, BanWords_message
            )  # 私发违禁词列表
            await send_group_msg(
                websocket,
                group_id,
                f"[CQ:at,qq={user_id}] 违禁词列表已私发，请注意查收。如果未收到请先私聊我一条消息。",  # 在群里艾特回复已私发
            )
        else:
            BanWords_message = "群" + group_id + "的违禁词列表为空。"
            await send_group_msg(
                websocket,
                group_id,
                f"[CQ:at,qq={user_id}] 违禁词列表为空。",  # 在群里艾特回复已私发
            )
    except Exception as e:
        logging.error(f"查看违禁词列表时发生错误: {e}")
        await send_group_msg(
            websocket,
            group_id,
            f"[CQ:at,qq={user_id}] 查看违禁词列表时发生错误，请稍后再试。",
        )


# 检查违禁词的主函数
async def check_BanWords(websocket, group_id, msg):
    try:
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

        # 违禁词检测
        BanWords = load_BanWords(group_id)
        raw_message = msg.get("raw_message")

        for word in BanWords:
            # 检查是否为违禁词，在re.search中，违禁词内容可以是字符串或正则表达式
            if re.search(word, raw_message):
                message_id = msg.get("message_id")
                user_id = str(msg.get("sender").get("user_id"))
                await set_group_ban(
                    websocket, group_id, user_id, 60 * 60 * 24 * 30
                )  # 禁言30天
                await delete_msg(websocket, message_id)

                # 初始化警告消息
                warning_message = (
                    f"[CQ:at,qq={user_id}]\n"
                    + "警告：请不要发送违禁词，误封请联系管理员处理\n"
                )

                # 获取群成员列表, 艾特管理员
                group_member = await get_group_member_list(websocket, group_id)
                for member in group_member:
                    if member.get("role") == "owner":
                        warning_message += f"[CQ:at,qq={member.get('user_id')}] "

                warning_message += "\n"
                warning_message += f"违规QQ是【{user_id}】\n"
                warning_message += f"快捷命令：t踢出bladd踢出并拉黑"
                await send_group_msg(websocket, group_id, warning_message)

                # 分离命令便于复制
                await send_group_msg(websocket, group_id, f"t{user_id}")

                await send_group_msg(websocket, group_id, f"bladd{user_id}")
                for group_id in report_group_ids:
                    await send_group_msg(
                        websocket,
                        group_id,
                        f"------------------------------------------",
                    )

                # 检查邀请链
                invited_users = get_invited_users(group_id, user_id)
                if invited_users:
                    await send_group_msg(
                        websocket,
                        group_id,
                        f"[+]检测到违规QQ[{user_id}]邀请了[{invited_users}]，请注意甄别相关用户身份",
                    )

                for group_id in report_group_ids:
                    await send_group_msg(
                        websocket,
                        group_id,
                        f"群【{group_id}】\n成员【{user_id}】\n在【{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}】发送了违禁词【{word}】\n原消息内容见下条消息",
                    )
                    await send_group_msg(websocket, group_id, f"{raw_message}")

                # 发出获取历史记录的申请
                await get_group_msg_history(websocket, group_id, 10, user_id)

                return True
    except Exception as e:
        logging.error(f"检查违禁词时发生错误: {e}")
        await send_group_msg(
            websocket,
            group_id,
            f"检查违禁词时发生错误，请稍后再试。错误信息: {e}",
        )
    return False


# 视频检测管理
async def manage_video_check(
    websocket, group_id, raw_message, message_id, is_authorized
):
    if not is_authorized:
        return

    command_actions = {
        "vcon": (True, "已开启视频监控。", "视频监控已经开启了，无需重复开启。"),
        "vcoff": (False, "已关闭视频监控。", "视频监控已经关闭了，无需重复关闭。"),
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

    try:
        if raw_message.startswith("bwadd"):
            match = re.search(r"bwadd(.*)", raw_message)
            if not match:
                await send_group_msg(
                    websocket,
                    group_id,
                    f"[CQ:reply,id={message_id}]命令格式错误，请使用: bwadd违禁词",
                )
                return
            new_word = match.group(1).strip()
            BanWords = load_BanWords(group_id)
            if new_word not in BanWords:
                BanWords.append(new_word)
                save_BanWords(group_id, BanWords)
                await send_group_msg(
                    websocket,
                    group_id,
                    f"[CQ:reply,id={message_id}]已添加违禁词: {new_word}",
                )
            else:
                await send_group_msg(
                    websocket,
                    group_id,
                    f"[CQ:reply,id={message_id}]违禁词已存在，无需重复添加。",
                )
        elif raw_message.startswith("bwrm"):
            match = re.search(r"bwrm(.*)", raw_message)
            if not match:
                await send_group_msg(
                    websocket,
                    group_id,
                    f"[CQ:reply,id={message_id}]命令格式错误，请使用: bwrm违禁词",
                )
                return
            remove_word = match.group(1).strip()
            BanWords = load_BanWords(group_id)
            if remove_word in BanWords:
                BanWords.remove(remove_word)
                save_BanWords(group_id, BanWords)
                await send_group_msg(
                    websocket,
                    group_id,
                    f"[CQ:reply,id={message_id}]已删除违禁词: {remove_word}",
                )
            else:
                await send_group_msg(
                    websocket,
                    group_id,
                    f"[CQ:reply,id={message_id}]违禁词不存在，无需删除。",
                )

        elif raw_message.startswith("bwlist"):
            await list_BanWords(websocket, group_id, user_id)

        elif raw_message.startswith("bwon"):
            save_BanWords_switch(group_id, True)
            await send_group_msg(
                websocket,
                group_id,
                f"[CQ:reply,id={message_id}]已开启违禁词检测。",
            )
        elif raw_message.startswith("bwoff"):
            save_BanWords_switch(group_id, False)
            await send_group_msg(
                websocket,
                group_id,
                f"[CQ:reply,id={message_id}]已关闭违禁词检测。",
            )

    except Exception as e:
        logging.error(f"管理违禁词时发生错误: {e}")


# 违禁词系统菜单
async def BanWords(websocket, group_id, message_id):
    message = (
        f"[CQ:reply,id={message_id}]\n"
        + """违禁词系统

bwon 开启违禁词监控
bwoff 关闭违禁词监控
bwlist 查看违禁词列表
bwadd+违禁词 添加违禁词
bwrm+违禁词 删除违禁词
"""
    )
    await send_group_msg(websocket, group_id, message)


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

        if raw_message == "banwords":
            await BanWords(websocket, group_id, message_id)

        # 先执行管理，都不属于之后再执行检查违禁词
        await manage_BanWords(
            websocket, message_id, group_id, user_id, raw_message, is_authorized
        )

        await manage_video_check(
            websocket, group_id, raw_message, message_id, is_authorized
        )

        # 如果不是管理员或群主或root管理员，检查违禁词
        if not is_authorized:
            await check_BanWords(websocket, group_id, msg)

    except Exception as e:
        logging.error(f"处理违禁词系统时发生错误: {e}")
        return


# 处理违禁词回应事件
async def handle_BanWords_response_message(websocket, message):
    try:
        msg = json.loads(message)

        if msg.get("status") == "ok":
            echo = msg.get("echo")

            if echo and echo.startswith("get_group_msg_history_"):
                parts = echo.split("_")
                if len(parts) > 3:
                    group_id = parts[4]
                    user_id = parts[5]
                    history_msg = msg.get("data", {})
                    messages = history_msg.get("messages", [])
                    for msg in messages:
                        if str(msg.get("user_id")) == user_id:
                            if "[CQ:video," in msg.get("raw_message"):
                                await delete_msg(websocket, msg.get("message_id"))
                                await send_group_msg(
                                    websocket,
                                    group_id,
                                    "卷卷递归发现违规QQ之前的消息中有视频，已进行撤回",
                                )
    except Exception as e:
        logging.error(f"处理违禁词回应事件时发生错误: {e}")
