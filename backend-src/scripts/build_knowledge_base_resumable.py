# backend/scripts/build_knowledge_base_resumable.py
import os
import sys
import json
import signal
import argparse
from pathlib import Path

# Add the backend directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# 找到项目根目录并设置环境变量
project_root = Path(__file__).parent.parent.parent
os.chdir(project_root)

from app.core.config import settings
from app.services.rag_knowledge_builder_impl import KnowledgeBaseBuilderImpl


class ResumableKnowledgeBaseBuilder:
    """支持中断和继续的知识库构建器"""
    
    def __init__(self, checkpoint_dir: str = None):
        self.checkpoint_dir = checkpoint_dir or os.path.join(project_root, "backend", "app", "data", "checkpoints")
        self.state_file_path = os.path.join(self.checkpoint_dir, "build_state.json")
        self.builder = KnowledgeBaseBuilderImpl(self.state_file_path)

    def build(self, documents_dir: str = None, force_restart: bool = False):
        """构建知识库"""
        # 如果强制重新开始，删除现有的检查点文件
        if force_restart and os.path.exists(self.state_file_path):
            print("强制重新开始，删除现有检查点文件...")
            # 使用 self.builder.state 来调用 reset 方法
            if self.builder.state:
                self.builder.state.reset()
            
            # 删除embeddings文件
            embeddings_path = os.path.join(self.checkpoint_dir, "embeddings.json")
            if os.path.exists(embeddings_path):
                os.remove(embeddings_path)
        
        # 确保检查点目录存在
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        
        # 从配置或参数获取文档目录
        if not documents_dir:
            documents_dir = settings.DOCUMENTS_DIR
        
        print(f"开始构建知识库...")
        print(f"文档目录: {documents_dir}")
        print(f"检查点文件: {self.state_file_path}")
        
        try:
            # 从文档目录构建知识库
            print(f"从目录加载文档: {documents_dir}")
            self.builder.build_from_directory(documents_dir, recursive=True)
            
            # 保存知识库
            print(f"保存知识库到: {settings.VECTOR_STORE_DIR}")
            self.builder.save(settings.VECTOR_STORE_DIR)
            
            print("知识库构建完成!")
            return True
            
        except KeyboardInterrupt:
            print("\n构建过程被中断，进度已自动保存。")
            print("要继续构建，请重新运行此脚本（不要使用--force-restart参数）。")
            return False
        except Exception as e:
            print(f"构建过程中发生错误: {e}")
            raise e


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="构建知识库（支持中断和继续）")
    parser.add_argument(
        "--documents-dir",
        help="文档目录路径（默认使用配置中的DOCUMENTS_DIR）",
        default=None
    )
    parser.add_argument(
        "--force-restart",
        action="store_true",
        help="强制重新开始构建（删除现有检查点）"
    )
    parser.add_argument(
        "--checkpoint-dir",
        help="检查点目录路径（默认为项目根目录下的checkpoints目录）",
        default=None
    )
    
    args = parser.parse_args()
    
    # 创建构建器并开始构建
    builder = ResumableKnowledgeBaseBuilder(checkpoint_dir=args.checkpoint_dir)
    builder.build(
        documents_dir=args.documents_dir,
        force_restart=args.force_restart
    )


if __name__ == "__main__":
    main()