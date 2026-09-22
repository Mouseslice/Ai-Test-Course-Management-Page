# backend/app/services/rag_service.py
import json
import os
import time
from openai import OpenAI
from annoy import AnnoyIndex
from app.core.config import settings
# 导入翻译服务类（不是实例）
from app.services.translation_service import TranslationService

class RAGService:
	def __init__(self, translation_service: TranslationService = None):
		# 在应用启动时加载索引和数据
		self.embedding_dimension = 2560 # for Qwen/Qwen3-Embedding-4B-GGUF
		self.index = AnnoyIndex(self.embedding_dimension, 'angular')
		
		# 使用配置中的路径
		kb_ann_path = os.path.join(settings.VECTOR_STORE_DIR, settings.KB_ANN_FILENAME)
		kb_chunks_path = os.path.join(settings.VECTOR_STORE_DIR, settings.KB_CHUNKS_FILENAME)
		
		# 使用内存映射加载索引，非常高效
		self.index.load(kb_ann_path, prefault=False) 
	  
		with open(kb_chunks_path, "r", encoding="utf-8") as f:
			self.chunks = json.load(f)
	  
		# 使用OpenAI客户端连接ModelScope API
		self.client = OpenAI(
			api_key=settings.TUTOR_EMBEDDING_API_KEY,
			base_url=settings.TUTOR_EMBEDDING_API_BASE,
			timeout=30.0  # 设置30秒超时
		)
		self.embedding_model = settings.TUTOR_EMBEDDING_MODEL
		
		# 使用DI方式注入翻译服务
		self.translation_service = translation_service

	def _is_chinese(self, text: str) -> bool:
		"""检测文本是否包含中文字符"""
		for ch in text:
			if '\u4e00' <= ch <= '\u9fff':
				return True
		return False

	def _get_embedding(self, text: str) -> list[float]:
		"""使用OpenAI客户端获取单个文本的embedding"""
		# 处理空查询
		if not text or not text.strip():
			# 对于空查询，返回零向量
			return [0.0] * self.embedding_dimension
			
		try:
			# 添加重试机制
			max_retries = 3
			for attempt in range(max_retries):
				try:
					response = self.client.embeddings.create(
						input=text,  # ModelScope API期望字符串而不是列表
						model=self.embedding_model
					)
					if response.data and len(response.data) > 0 and response.data[0].embedding:
						return response.data[0].embedding
					else:
						raise ValueError("Empty embedding received from API")
				except Exception as e:
					if attempt < max_retries - 1:
						# 等待后重试
						time.sleep(1 * (attempt + 1))  # 指数退避
						continue
					else:
						raise e
		except Exception as e:
			print(f"Error calling embedding API: {e}")
			raise ValueError(f"Failed to get embedding from API: {str(e)}")

	def retrieve(self, query_text: str, k: int = 3) -> list[str]:
		try:
			# 如果翻译服务可用且查询包含中文，则先翻译成英文
			if self.translation_service and self._is_chinese(query_text):
				translated_query = self.translation_service.translate(query_text, "zh", "en")
				print(f"Translated query: {query_text} -> {translated_query}")
				query_text = translated_query
			
			query_vector = self._get_embedding(query_text)
			
			if not query_vector:
				raise ValueError("Empty embedding vector received")
			
			# 在Annoy中搜索
			indices = self.index.get_nns_by_vector(query_vector, k)
	  
			return [self.chunks[i] for i in indices]
		except Exception as e:
			# 记录详细的错误信息
			print(f"Error in retrieve: {e}")
			raise

# 后面使用DI，而非使用单例
# rag_service = RAGService()
