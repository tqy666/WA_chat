from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Request

from app.whatsWA.Authorization import get_current_user
#from app.whatsWA.RagRepository import ragRepository
from app.whatsWA.ChatRepository import chatRepository
from app.whatsWA.UploadRepository import uploadRepository
from app.config.MysqlConfig import get_file_list
router = APIRouter()


#----------------接口路由------------------
@router.post("/rag/upload_file",summary="上传文档")
async def upload_file(file: UploadFile = File(...), user=Depends(get_current_user)):

    check_file = await uploadRepository.check_upload_file(file)
    if check_file:
        return check_file

    file_chunk = await uploadRepository.file_chunk_insert(file)
    return file_chunk

@router.get("/rag/upload_file_list",summary="文档列表")
async def upload_file_list( user=Depends(get_current_user)):

    file_list = get_file_list()
    return file_list

@router.delete("/rag/file_del/{id}",summary="删除文档")
async def file_del(id,user=Depends(get_current_user)):

    del_file = uploadRepository.del_file_data(id)
    return del_file

@router.post("/rag/chat",summary="会话")
async def chat_send(request: Request):

    body = await request.json()
    print(f"打印：{body}")
    chat_data = await chatRepository.chat_stream("5f875c42-16be-4415-84b3-6a6fa382ecd9", body)
    return chat_data






