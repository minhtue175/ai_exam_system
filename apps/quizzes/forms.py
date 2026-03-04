from django import forms
from .models import Quiz


class QuizGenerationForm(forms.Form):
    """Form để tạo quiz từ document"""
    
    DIFFICULTY_CHOICES = [
        ('easy', 'Dễ'),
        ('medium', 'Trung bình'),
        ('hard', 'Khó'),
    ]
    
    num_questions = forms.IntegerField(
        label='Số câu hỏi',
        min_value=1,
        max_value=40,
        initial=10,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nhập số câu (1-40)'
        })
    )
    
    difficulty = forms.ChoiceField(
        label='Độ khó',
        choices=DIFFICULTY_CHOICES,
        initial='medium',
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    def clean_num_questions(self):
        num = self.cleaned_data['num_questions']
        if num < 1 or num > 40:
            raise forms.ValidationError('Số câu hỏi phải từ 1 đến 40')
        return num


class QuizAnswerForm(forms.Form):
    """Form để trả lời quiz (dynamic form)"""
    
    def __init__(self, *args, questions=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        if questions:
            for question in questions:
                choices = [(i, opt) for i, opt in enumerate(question.options)]
                self.fields[f'question_{question.id}'] = forms.ChoiceField(
                    label=question.question_text,
                    choices=choices,
                    widget=forms.RadioSelect,
                    required=False
                )