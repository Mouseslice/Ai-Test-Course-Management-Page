# backend/app/services/markdown_loader.py
import os
import re
from typing import List, Iterator
from app.core.document import Document
from app.core.document_loader import DocumentLoader

class MarkdownLoader(DocumentLoader):
    """Markdown文档加载器实现"""
    
    def load(self, file_path: str) -> Document:
        """加载单个Markdown文档"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        if not file_path.endswith('.md'):
            raise ValueError(f"File is not a Markdown file: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取标题（通常是第一个#标题）
        title = self._extract_title(content)
        
        # 提取元数据（---之间的内容）
        metadata = self._extract_metadata(content)
        
        # 移除元数据部分和标题行，获取纯内容
        clean_content = self._clean_content(content)
        
        # 生成文档ID（使用相对路径）
        doc_id = self._generate_id(file_path)
        
        return Document(
            id=doc_id,
            title=title,
            content=clean_content,
            file_path=file_path,
            file_type='md',
            metadata=metadata
        )
    
    def load_batch(self, file_paths: List[str]) -> List[Document]:
        """批量加载Markdown文档"""
        documents = []
        for file_path in file_paths:
            if file_path.endswith('.md'):
                try:
                    doc = self.load(file_path)
                    if doc.is_valid:
                        documents.append(doc)
                except Exception as e:
                    print(f"Warning: Failed to load {file_path}: {e}")
        return documents
    
    def load_from_directory(self, directory_path: str, recursive: bool = True) -> Iterator[Document]:
        """从目录加载Markdown文档"""
        if not os.path.exists(directory_path):
            raise FileNotFoundError(f"Directory not found: {directory_path}")
        
        file_count = 0
        if recursive:
            for root, _, files in os.walk(directory_path):
                for file in files:
                    if file.endswith('.md'):
                        file_count += 1
                        if file_count % 100 == 0:
                            print(f"  已扫描 {file_count} 个Markdown文件...")
                        file_path = os.path.join(root, file)
                        try:
                            doc = self.load(file_path)
                            if doc.is_valid:
                                yield doc
                        except Exception as e:
                            print(f"Warning: Failed to load {file_path}: {e}")
        else:
            for file in os.listdir(directory_path):
                file_path = os.path.join(directory_path, file)
                if os.path.isfile(file_path) and file.endswith('.md'):
                    file_count += 1
                    if file_count % 100 == 0:
                            print(f"  已扫描 {file_count} 个Markdown文件...")
                    try:
                        doc = self.load(file_path)
                        if doc.is_valid:
                            yield doc
                    except Exception as e:
                        print(f"Warning: Failed to load {file_path}: {e}")
    
    def _extract_title(self, content: str) -> str:
        """从Markdown内容中提取标题"""
        # 查找第一个H1标题
        lines = content.split('\n')
        for line in lines:
            if line.startswith('# '):
                return line[2:].strip()
        
        # 如果没有找到H1标题，返回文件名
        return "Untitled Document"
    
    def _extract_metadata(self, content: str) -> dict:
        """从Markdown内容中提取元数据"""
        metadata = {}
        # 匹配---之间的元数据
        metadata_pattern = r'^---\s*\n(.*?)\n---\s*\n'
        match = re.search(metadata_pattern, content, re.DOTALL)
        if match:
            metadata_lines = match.group(1).strip().split('\n')
            for line in metadata_lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    metadata[key.strip()] = value.strip()
        return metadata
    
    def _clean_content(self, content: str) -> str:
        """清理Markdown内容，移除元数据和标题"""
        # 移除元数据部分
        metadata_pattern = r'^---\s*\n.*?\n---\s*\n'
        content = re.sub(metadata_pattern, '', content, flags=re.DOTALL)
        
        # 移除第一个H1标题行
        content = re.sub(r'^# .*\n', '', content)
        
        return content.strip()
    
    def _generate_id(self, file_path: str) -> str:
        """生成文档ID"""
        # 使用相对路径作为ID
        return os.path.relpath(file_path, os.path.dirname(os.path.dirname(os.path.dirname(file_path))))