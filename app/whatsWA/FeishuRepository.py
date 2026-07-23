import requests


class FeishuReposirory:

    async def send_feishu_alert(self,send_from, pushName,send_content):

        """
            向飞书群发送转人工告警
            :param send_from: 客户ID
            :param pushName: 客户名称
            :param send_content: 问题简述
            """

        # 1. 替换为你在飞书后台获取的 Webhook 地址
        webhook_url = "https://open.feishu.cn/open-apis/bot/v2/hook/248fa32f-54fa-4c3d-b3ce-b0aba07240c3"

        # 2. 构造消息体 (Text 类型)
        # 注意：content 字段的内容必须包含你在后台设置的关键词 "转人工"
        # 进阶版：卡片消息结构
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": "🚨 WhatsApp 转人工申请"  # 标题包含关键词
                    },
                    "template": "red"  # 红色警示风格
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"**客户 ID**: {send_from}\n**客户名称**: {pushName}\n**原因**: {send_content}"
                        }
                    }
                ]
            }
        }

        # 3. 发送 POST 请求
        try:
            response = requests.post(webhook_url, json=payload)
            result = response.json()

            # 4. 检查返回结果
            if result.get("code") == 0:
                print("✅ 消息发送成功！")
                return {"code":200,"message":"已经转发给了人工客服"}
            else:
                print(f"❌ 发送失败，错误码: {result.get('code')}, 信息: {result.get('msg')}")
                return {"code": result.get('code'), "message": result.get('msg')}
        except Exception as e:
            print(f"❌ 请求发生异常: {str(e)}")
            return {"code": 400, "message": str(e)}