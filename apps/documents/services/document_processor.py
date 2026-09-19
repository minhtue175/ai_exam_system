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
    
    # File magic bytes (signatures)
    MAGIC_SIGNATURES = {
        '.pdf': [b'%PDF-'],
        '.docx': [b'PK\x03\x04'],
        '.doc': [b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'],
    }

    @classmethod
    def validate_file(cls, file: UploadedFile) -> None:
        """Validate uploaded file with extension, MIME, size and Magic Bytes signature"""
        if not file:
            raise ValidationError("Vui lòng chọn file!")
        
        # 1. Chống path traversal và ký tự điều khiển trong tên file
        clean_name = os.path.basename(file.name).replace('\x00', '')
        if not clean_name or clean_name.startswith('.'):
            raise ValidationError("Tên file không hợp lệ!")
        
        # 2. Check extension & double extensions
        parts = clean_name.split('.')
        if len(parts) < 2:
            raise ValidationError("File không có phần mở rộng hợp lệ!")
        
        file_ext = f".{parts[-1].lower()}"
        if file_ext not in cls.ALLOWED_EXTENSIONS:
            raise ValidationError(
                f"Định dạng không hợp lệ! Chỉ chấp nhận: {', '.join(cls.ALLOWED_EXTENSIONS)}"
            )
        
        # Kiểm tra double extension nguy hiểm (vd: file.php.pdf, file.exe.docx)
        dangerous_exts = {'php', 'exe', 'sh', 'py', 'bat', 'cmd', 'js', 'vbs', 'jsp', 'cgi', 'pl'}
        for part in parts[1:-1]:
            if part.lower() in dangerous_exts:
                raise ValidationError("Tên file chứa phần mở rộng nguy hiểm không được phép tải lên!")
        
        # 3. Check size
        if file.size > cls.MAX_FILE_SIZE:
            max_mb = cls.MAX_FILE_SIZE / (1024 * 1024)
            file_mb = file.size / (1024 * 1024)
            raise ValidationError(
                f"File quá lớn! ({file_mb:.2f}MB). Tối đa: {max_mb:.0f}MB"
            )
        
        # 4. Check Magic Bytes (Chữ ký thực tế của file - chống file giả dạng)
        try:
            current_pos = file.tell()
            header = file.read(8)
            file.seek(current_pos)
            
            expected_signatures = cls.MAGIC_SIGNATURES.get(file_ext, [])
            valid_signature = any(header.startswith(sig) for sig in expected_signatures)
            
            if not valid_signature:
                raise ValidationError(
                    f"Nội dung file không đúng với định dạng {file_ext.upper()}. Vui lòng kiểm tra lại file của bạn!"
                )
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(f"Không thể kiểm tra tính toàn vẹn của file: {str(e)}")
    
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