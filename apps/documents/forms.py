from django import forms
from .models import Document

class DocumentUploadForm(forms.ModelForm):
    """Form upload document"""
    
    class Meta:
        model = Document
        fields = ['file_path']
        widgets = {
            'file_path': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx'
            })
        }
        labels = {
            'file_path': 'Chọn file (PDF hoặc Word)'
        }
    
    def clean_file_path(self):
        file = self.cleaned_data.get('file_path')
        if file:
            from .services.document_processor import DocumentProcessor
            try:
                DocumentProcessor.validate_file(file)
            except forms.ValidationError:
                raise
            except Exception as e:
                raise forms.ValidationError(f"Lỗi kiểm tra file: {str(e)}")
        return file