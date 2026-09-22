# backend/app/services/build_state.py
import json
import os
import time
from typing import List, Optional
from pathlib import Path


class BuildState:
    """构建状态管理类，支持中断和继续功能"""
    
    def __init__(self, state_file_path: str):
        self.state_file_path = state_file_path
        self.state = {
            "checkpoint_version": "1.0",
            "last_updated": None,
            "processed_documents": [],
            "processed_chunks": 0,
            "total_chunks": 0,
            "embeddings_path": None,
            "index_path": None,
            "current_batch": 0,
            "total_batches": 0,
            "completed": False
        }
        self._load_state()
    
    def _load_state(self):
        """从文件加载状态"""
        if os.path.exists(self.state_file_path):
            try:
                with open(self.state_file_path, 'r', encoding='utf-8') as f:
                    saved_state = json.load(f)
                    # 合并状态，保留新字段的默认值
                    self.state = {**self.state, **saved_state}
                print(f"从检查点文件加载状态: {self.state_file_path}")
            except Exception as e:
                print(f"加载状态文件时出错: {e}")
    
    def _save_state(self):
        """保存状态到文件"""
        self.state["last_updated"] = time.time()
        try:
            # 确保目录存在
            Path(self.state_file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存状态文件时出错: {e}")
    
    def is_resumable(self) -> bool:
        """检查是否存在可恢复的检查点"""
        # 如果存在状态文件且有已处理的文本块，则可以恢复
        return (os.path.exists(self.state_file_path) and 
                self.state.get("processed_chunks", 0) > 0 and
                not self.state.get("completed", False))
    
    def mark_document_processed(self, doc_id: str):
        """标记文档已处理"""
        if doc_id not in self.state["processed_documents"]:
            self.state["processed_documents"].append(doc_id)
    
    def update_progress(self, processed_chunks: int, total_chunks: int, 
                       current_batch: int, total_batches: int):
        """更新处理进度"""
        self.state["processed_chunks"] = processed_chunks
        self.state["total_chunks"] = total_chunks
        self.state["current_batch"] = current_batch
        self.state["total_batches"] = total_batches
        self._save_state()
    
    def set_paths(self, embeddings_path: str, index_path: str):
        """设置embeddings和索引路径"""
        self.state["embeddings_path"] = embeddings_path
        self.state["index_path"] = index_path
    
    def mark_build_completed(self):
        """标记构建完成"""
        self.state["completed"] = True
        self._save_state()
    
    def get_processed_documents(self) -> List[str]:
        """获取已处理的文档ID列表"""
        return self.state["processed_documents"].copy()
    
    def get_progress(self) -> dict:
        """获取当前进度信息"""
        return {
            "processed_chunks": self.state["processed_chunks"],
            "total_chunks": self.state["total_chunks"],
            "current_batch": self.state["current_batch"],
            "total_batches": self.state["total_batches"],
            "completed": self.state.get("completed", False)
        }
    
    def reset(self):
        """重置状态"""
        self.state = {
            "checkpoint_version": "1.0",
            "last_updated": None,
            "processed_documents": [],
            "processed_chunks": 0,
            "total_chunks": 0,
            "embeddings_path": None,
            "index_path": None,
            "current_batch": 0,
            "total_batches": 0,
            "completed": False
        }
        if os.path.exists(self.state_file_path):
            os.remove(self.state_file_path)