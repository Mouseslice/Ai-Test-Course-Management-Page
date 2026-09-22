# backend/app/services/translation_service.py
from openai import OpenAI
from app.core.config import settings
import time

class TranslationService:
    def __init__(self):
        # 使用独立的翻译API配置
        self.client = OpenAI(
            api_key=settings.TUTOR_TRANSLATION_API_KEY,
            base_url=settings.TUTOR_TRANSLATION_API_BASE,
            timeout=30.0  # 设置30秒超时
        )
        self.translation_model = settings.TUTOR_TRANSLATION_MODEL

    def translate(self, text: str, source_lang: str = "zh", target_lang: str = "en") -> str:
        """
        使用LLM将文本从源语言翻译成目标语言
        """
        # 处理空查询
        if not text or not text.strip():
            return ""
            
        try:
            # 添加重试机制
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    prompt = f"请将以下{source_lang}文本翻译成{target_lang}，只返回翻译结果，不要添加任何其他内容：\n\n{text}"
                    
                    response = self.client.chat.completions.create(
                        model=self.translation_model,
                        messages=[
                            {"role": "system", "content": f"你是一个专业的翻译员，专门负责将{source_lang}翻译成{target_lang}。"},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=1000,
                        temperature=0.3
                    )
                    
                    if response.choices and len(response.choices) > 0 and response.choices[0].message.content:
                        return response.choices[0].message.content.strip()
                    else:
                        raise ValueError("Empty translation received from API")
                except Exception as e:
                    if attempt < max_retries - 1:
                        # 等待后重试
                        time.sleep(1 * (attempt + 1))  # 指数退避
                        continue
                    else:
                        raise e
        except Exception as e:
            print(f"Error calling translation API: {e}")
            raise ValueError(f"Failed to get translation from API: {str(e)}")

# 后面使用DI，而非使用单例
# translation_service = TranslationService()