from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError

from .models import Document
from .forms import DocumentUploadForm
from .services.document_service import DocumentService


@login_required
def upload_view(request):
    """Xử lý Upload tài liệu và trích xuất văn bản"""
    if request.method == 'POST':
        form = DocumentUploadForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                # Gọi service để xử lý upload
                service = DocumentService()
                document = service.upload_and_process(
                    file=request.FILES['file_path'],
                    user=request.user,
                    extract_immediately=True
                )
                
                messages.success(
                    request, 
                    f'✅ Upload thành công! File "{document.filename}" đã được xử lý.'
                )
                return redirect('documents:detail', pk=document.pk)
                
            except ValidationError as e:
                messages.error(request, f'❌ {str(e)}')
            except Exception as e:
                messages.error(request, f'❌ Lỗi hệ thống: {str(e)}')
        
        else: 
            # Bắt toàn bộ lỗi từ form (như lỗi vượt quá 20MB) và đẩy ra màn hình
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'❌ Lỗi Tải Lên: {error}')
    else:
        form = DocumentUploadForm()
    
    return render(request, 'documents/upload.html', {'form': form})


@login_required
def document_list_view(request):
    """Hiển thị danh sách tất cả tài liệu của user"""
    documents = Document.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'documents/list.html', {'documents': documents})


@login_required
def document_detail_view(request, pk):
    """Xem chi tiết thông tin và nội dung đã trích xuất của tài liệu"""
    document = get_object_or_404(Document, pk=pk, user=request.user)
    
    # Tính toán số từ và số dòng để hiển thị ra UI
    word_count = len(document.extracted_text.split()) if document.extracted_text else 0
    line_count = document.extracted_text.count('\n') + 1 if document.extracted_text else 0
    
    context = {
        'document': document,
        'word_count': word_count,
        'line_count': line_count,
    }
    return render(request, 'documents/detail.html', context)


@login_required
def document_delete_view(request, pk):
    """Xóa tài liệu"""
    document = get_object_or_404(Document, pk=pk, user=request.user)
    
    if request.method == 'POST':
        try:
            service = DocumentService()
            service.delete_document(document)
            messages.success(request, f'✅ Đã xóa file "{document.filename}"!')
            return redirect('core:dashboard')
        except Exception as e:
            messages.error(request, f'❌ Lỗi khi xóa: {str(e)}')
    
    return render(request, 'documents/delete_confirm.html', {'document': document})


@login_required
def extract_text_view(request, pk):
    """Chức năng trích xuất lại văn bản (Dùng khi quá trình tự động bị lỗi)"""
    document = get_object_or_404(Document, pk=pk, user=request.user)
    
    try:
        service = DocumentService()
        service.extract_text(document)
        messages.success(request, '✅ Đã trích xuất lại văn bản thành công!')
    except Exception as e:
        messages.error(request, f'❌ Lỗi trích xuất: {str(e)}')
    
    return redirect('documents:detail', pk=pk)