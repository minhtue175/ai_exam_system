"""
Service để xử lý upload và validate documents
"""
from django.core.files.uploadedfile import UploadedFile
from django.core.exceptions import ValidationError
import os


class DocumentProcessor:
    """Process and validate document uploads"""
    
    ALLOWED_EXTENSIONS = ['.pdf', '.doc', '.docx']
    ALLOWED_MIME_TYPES = [
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ]
    MAX_FILE_SIZE = 20 * 1024 * 1024 
    
    @classmethod
    def validate_file(cls, file: UploadedFile) -> None:
        """Validate uploaded file"""
        if not file:
            raise ValidationError("Vui lòng chọn file!")
        
        # Check extension
        file_ext = os.path.splitext(file.name)[1].lower()
        if file_ext not in cls.ALLOWED_EXTENSIONS:
            raise ValidationError(
                f"Định dạng không hợp lệ! Chỉ chấp nhận: {', '.join(cls.ALLOWED_EXTENSIONS)}"
            )
        
        # Check MIME type
        if file.content_type not in cls.ALLOWED_MIME_TYPES:
            raise ValidationError(f"Loại file không hợp lệ!")
        
        # Check size
        if file.size > cls.MAX_FILE_SIZE:
            max_mb = cls.MAX_FILE_SIZE / (1024 * 1024)
            file_mb = file.size / (1024 * 1024)
            raise ValidationError(
                f"File quá lớn! ({file_mb:.2f}MB). Tối đa: {max_mb:.0f}MB"
            )
    
    @staticmethod
    def get_file_info(file: UploadedFile) -> dict:
        """Get file information"""
        return {
            'filename': file.name,
            'size': file.size,
            'size_mb': round(file.size / (1024 * 1024), 2),
            'content_type': file.content_type,
            'extension': os.path.splitext(file.name)[1].lower()
        }