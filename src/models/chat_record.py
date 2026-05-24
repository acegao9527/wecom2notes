from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class AttachmentInfo(BaseModel):
    """
    统一附件模型
    """
    file_name: Optional[str] = Field(None, description="原始文件名")
    local_path: Optional[str] = Field(None, description="本地文件路径")
    content_type: Optional[str] = Field(None, description="MIME 类型")
    size: Optional[int] = Field(None, description="文件大小")
    sha256: Optional[str] = Field(None, description="文件 sha256")
    url: Optional[str] = Field(None, description="外部访问 URL")

    class Config:
        extra = "ignore"

class UnifiedMessage(BaseModel):
    """
    统一消息模型
    """
    msg_id: str = Field(..., description="原始平台的消息ID")
    source: str = Field(..., description="消息来源: wecom")
    msg_type: str = Field(..., description="消息类型: text, image, link, voice, video, file")
    content: str = Field(..., description="文本内容 或 媒体文件的本地绝对路径")
    from_user: str = Field(..., description="发送者用户名或ID")
    create_time: int = Field(..., description="消息创建时间戳(秒)")
    raw_data: Dict[str, Any] = Field(default_factory=dict, description="原始数据备份")
    chat_id: Optional[str] = Field(None, description="会话或群聊ID")
    to_user: Optional[str] = Field(None, description="接收者用户ID")
    sender_name: Optional[str] = Field(None, description="发送者显示名")
    attachments: List[AttachmentInfo] = Field(default_factory=list, description="附件列表")

    class Config:
        extra = "ignore"
