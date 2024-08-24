# BanWords

违禁词监控系统

## 命令

bw-on 开启违禁词监控

bw-off 关闭违禁词监控

bw-list 查看违禁词列表

bw-add+违禁词 添加违禁词

bw-rm+违禁词 删除违禁词

## 更新日志

[重大更新]2024 年 8 月 24 日，增加违禁词检测到视频消息后，撤回视频消息的逻辑，检测到违禁词之后，遍历消息列表，撤回违禁词消息前 10 条消息，被检测者的视频消息

2024 年 8 月 23 日，去掉指令中的空格，修改查看违禁词改为私发

2024 年 8 月 23 日，修复由于 qq 号获取没转成字符串导致的判断错误

2024 年 8 月 18 日，修复私聊汇报携带的 cq 码无法解析导致 cq 码部分没显示发 bug

2024 年 8 月 13 日，优化违禁词机制，检测到违禁词之后私聊 root 管理员相关群，群员，原消息，违禁词。

2024 年 8 月 12 日，重构代码，精简命令
