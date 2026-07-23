import os
from app.config.MysqlConfig import check_content_repeat,insert_chunk_data,get_file_list,del_file_data
import hashlib
from pathlib import Path
from uuid import uuid4
import aiofiles
import asyncio
from langchain_mineru import MinerULoader
from concurrent.futures import ThreadPoolExecutor
from langchain_text_splitters import CharacterTextSplitter
from pymilvus import MilvusClient, DataType
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
import json
from datetime import datetime

class UploadRepository:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)
        #self.client = MilvusClient(uri="http://localhost:19530")
        self.embeddings = OllamaEmbeddings(model="nomic-embed-text")  # 电脑内存太小了，1024分配不到内存，默认用nomic768
        #self.COLLECTION_NAME = "rag_knowledge_base"
        #self.DIMENSION = 768
        #self.collection_name = "nomic_embeddings_v3"
        self.persist_dir = Path(__file__).resolve().parent.parent / "chroma_dir"
        self.persist_dir.mkdir(exist_ok=True)  # 确保目录存在
        self.collection_name = "openwa_webhook"
        self.vector_db = Chroma(
            persist_directory=str(self.persist_dir),
            embedding_function=self.embeddings,
            collection_name=self.collection_name
        )
        self.hash_mad5=None


    async def check_upload_file(self,file):
        try:
            file_type= {".docx",".xlsx"}
            _, ext = os.path.splitext(file.filename)
            ext_lower = ext.lower()
            if  ext_lower not in file_type:
                return {"code":400,"message":f"您上传的文件类型是：{ext_lower}，文件上传类型必须是{file_type}"}
            MAX_SIZE = 10 * 1024 * 1024
            if file.size>MAX_SIZE:
                return {"code":400,"message":f"您上传的文件大于10M，请重新上传"}
            content = await file.read()
            if len(content)==0:
                return {"code": 400, "message": f"您上传的文件是空文件，请重新上传新文件"}
            hash_md5 = hashlib.md5(content).hexdigest()
            self.hash_mad5=hash_md5
            check_data = check_content_repeat(hash_md5)

            if check_data:
                return {"code":400,"message":f"你的文件之前已经上传过了，请重新上传新文件"}
        except Exception as e:
            return  {"code": 500, "message": f"系统内部错误，请稍后重试{e}"}

    async def _safe_upload_path(self,filename: str) -> Path:
        """生成安全的上传路径，防止路径穿越攻击"""

        suffix = Path(filename).suffix

        safe_name = f"{uuid4().hex}{suffix}"
        upload_dir = Path(__file__).resolve().parent.parent / "uploads"
        upload_dir.mkdir(exist_ok=True)  # 确保上传目录存在
        return upload_dir / safe_name

    async def _save_upload_file(self,file,dest: Path,chunk_size: int = 4 * 1024 * 1024,) -> int:
        """流式写入上传文件，避免整文件读入内存。"""

        total = 0
        async with aiofiles.open(dest, "wb") as f:
            while chunk := await file.read(chunk_size):
                await f.write(chunk)
                total += len(chunk)
            await f.flush()
        return total

    async def file_chunk_insert(self,file):
        file_paths = await self._safe_upload_path(file.filename)
        print(file_paths)
        loop = asyncio.get_running_loop()
        try:
            await file.seek(0)
            file_size = await self._save_upload_file(file, file_paths)
            if file_size == 0:
                return {
                    "message": "文件读取失败，内容为空，请检查上传的文件是否有效。",
                    "error": "empty_file",
                    "chunks": 0,
                }

            print(f"文件写入成功: {file_paths}, 大小: {file_size} 字节")

            def _load_docs():
                try:
                    loader = MinerULoader(source=[str(file_paths)], mode="flash")
                    return loader.load()
                except Exception as e:
                    print(f"MinerU 内部加载错误: {e}")
                    return None

            raw_docs = await loop.run_in_executor(self.executor, _load_docs)
            if not raw_docs or not isinstance(raw_docs, list) or len(raw_docs) == 0:
                # 如果 MinerU 返回空列表或 None，尝试检查文件是否存在且非零
                if file_size == 0:
                    return {"message": "文件写入失败", "error": "文件大小为0字节"}
                else:
                    return {
                        "message": "文档解析失败",
                        "error": "MinerU 未能提取内容",
                        "detail": "文件格式可能不受支持或已损坏，请检查是否为标准 Word/PDF 文件。"
                    }

            print(f"成功解析出 {len(raw_docs)} 个文档片段")
            text_splitter = CharacterTextSplitter(
                separator="\n",
                chunk_size=1000,
                chunk_overlap=200,
            )
            chunks = text_splitter.split_documents(raw_docs)
            len_chunks = len(chunks)
            print(f"成功切分出 {len_chunks} 个文本块")

            filename = os.path.basename(file_paths)
            ids = [f"{filename}_chunk_{i}" for i in range(len(chunks))]
            print(f"ids打印：{ids}")

            #-------------------------Chroma-------------------------
            # 4. 存进向量库
            def _add_to_vector_db():
                self.vector_db.add_documents(documents=chunks, ids=ids)

            await loop.run_in_executor(self.executor, _add_to_vector_db)

            insert_chunk = insert_chunk_data(
                self.hash_mad5,
                self.collection_name,
                file.filename,
                f"{file_size / (1024 * 1024):.2f}M",
                len_chunks,
                str(file_paths),
                json.dumps(ids, ensure_ascii=False),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )

            if insert_chunk:
                return {"code": 200, "message": "输出上传成功"}
            else:
                return {"code": 400, "message": "上传失败"}
            #---------------------------miluvs-------------------------------------
            # if not self.client.has_collection(collection_name=self.COLLECTION_NAME):
            #     self.client.create_collection(
            #         collection_name=self.COLLECTION_NAME,
            #         dimension=self.DIMENSION,
            #         metric_type="COSINE",  # 余弦相似度
            #         auto_id=True,  # 自动生成主键
            #         enable_dynamic_field=True  # 允许存储文件名等元数据
            #     )
            #     print(f"集合 '{self.COLLECTION_NAME}' 创建成功")

            # chunk_texts = [chunk.page_content for chunk in chunks]
            # vectors = self.embeddings.embed_documents(chunk_texts)

            # data_to_insert = []
            # for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
            #     data_to_insert.append({
            #         # 如果 auto_id=True，则不需要提供 id 字段，Milvus 会自动生成
            #         # "id": i,
            #         "vector": vector,  # 字段名必须是 'vector' (或你创建集合时指定的向量字段名)
            #         "text": chunk.page_content,  # 动态字段，存储文本内容
            #         "source_file": f"{file.filename}",  # 动态字段，存储来源
            #         "chunk_id": f"chunk_{i}"  # 动态字段，存储块ID
            #     })

                # 4. 存进向量库
                # def _add_to_vector_db():
                #     self.client.insert(collection_name=self.COLLECTION_NAME, data=data_to_insert)
                #
                # await loop.run_in_executor(self.executor, _add_to_vector_db)
                # print("miluvs填充完成")
            # try:
            #     res = self.client.insert(collection_name=self.COLLECTION_NAME, data=data_to_insert)
            #     print(f"成功插入 {res['insert_count']} 条数据")
            # except Exception as e:
            #     print(f"插入失败: {e}")


        except Exception as e:
            param = {
                "message": "文件处理失败",
                "error": str(e),
                "detail": "上传或入库过程中发生异常，请稍后重试。",
            }
            print(param)
            # return {
            #     "message": "文件处理失败",
            #     "error": str(e),
            #     "detail": "上传或入库过程中发生异常，请稍后重试。",
            # }


    def del_file_data(self,id):

        seach_file  = get_file_list(id)
        print(seach_file)
        ids = json.loads(seach_file[1])
        print(f"删除前总共的条数{self.vector_db._collection.count()}")
        # 删除向量库里的数据
        self.vector_db.delete(ids=ids)
        print(f"删除后总共的条数{self.vector_db._collection.count()}")

        # 删除本地文件f
        file_path = seach_file[0]
        print(f"要删除的本地文件：{file_path}")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"物理文件 {file_path} 已成功删除")
            except Exception as e:
                print(f"删除物理文件失败: {e}")
        else:
            print("该文件在磁盘上不存在")

        result = del_file_data(id)
        print(f"打印输出删除结果：{result}")
        if result:
            return {
                "message": "删除成功",
                "detail": f"{seach_file[0]}已经删除",
                "status": "success"
            }
        else:
            return {
                "message": "删除失败",
                "detail": f"{len(seach_file[0])}删除失败",
                "status": "error"
            }







uploadRepository=  UploadRepository()