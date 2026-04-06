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
            # Kiểm tra extension
            ext = file.name.split('.')[-1].lower()
            if ext not in ['pdf', 'doc', 'docx']:
                raise forms.ValidationError('Chỉ chấp nhận file PDF hoặc Word!')
            
            # Kiểm tra kích thước (max 10MB)
            if file.size > 20 * 1024 * 1024:
                raise forms.ValidationError('File không được vượt quá 20MB!')
        
        return file