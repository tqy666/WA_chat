import os
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

# 1. 初始化客户端（请确保你的环境变量中已配置 DASHSCOPE_API_KEY）
client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)


def translate_text(text, source_lang, target_lang, terms=None, domain_hint=None):
    """
    通用翻译函数
    :param text: 待翻译文本
    :param source_lang: 源语言 (如 "Chinese", "English", "auto")
    :param target_lang: 目标语言 (如 "English", "Japanese")
    :param terms: 术语干预字典 (如 {"千问": "Qwen"})
    :param domain_hint: 领域提示 (如 "严谨的医疗报告风格")
    :return: 翻译后的文本
    """
    # 构建翻译配置
    translation_options = {
        "source_lang": "auto",
        "target_lang": target_lang,
    }

    # 动态添加高级定制参数
    if terms:
        translation_options["terms"] = [
                            {"source": src, "target": tgt} for src, tgt in terms.items()
]
    if domain_hint:
        translation_options["domain_hint"] = domain_hint

    try:
        completion = client.chat.completions.create(
            model="qwen-mt-flash",  # 推荐使用 flash 版本，平衡速度与质量
            messages=[
                {"role": "user", "content": text}
            ],
            extra_body={
                "translation_options": translation_options
            },
        )
        return completion.choices[0].message.content

    except Exception as e:
        return f"翻译出错: {str(e)}"


# ================= 测试运行 =================
if __name__ == "__main__":
    # 场景 1：基础客服自动翻译
    user_input_1 = "Когда будет возвращено деньги"
    result_1 = translate_text(user_input_1, "Chinese", "Chinese")
    print(f"原始语言：{user_input_1}")
    print(f"基础翻译: {result_1}")

    # 场景 2：带术语干预的翻译（确保品牌名不被乱翻）
    user_input_2 = "请问 Qwen-MT 模型的 API 怎么调用？"
    custom_terms = {"Qwen-MT": "通义千问翻译模型"}
    result_2 = translate_text(user_input_2, "Chinese", "Chinese", terms=custom_terms)
    print(f"术语干预: {result_2}")

    # 场景 3：带领域提示的翻译（调整语气风格）
    user_input_3 = "服务器连不上，急！"
    result_3 = translate_text(
        user_input_3,
        "Chinese",
        "Chinese",
        domain_hint="专业的IT技术支持语气，礼貌且安抚用户情绪"
    )
    print(f"领域提示: {result_3}")