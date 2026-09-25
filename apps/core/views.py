from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db import connection

from apps.documents.models import Document
from apps.quizzes.models import UserQuizAttempt, Quiz


def home_view(request):
    """Trang chủ dành cho khách chưa đăng nhập"""
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    return render(request, 'core/home.html')


@login_required
def dashboard_view(request):
    """
    Dashboard trung tâm: Tìm kiếm tối ưu với PostgreSQL Trigram & Full-Text Search
    (GIN Indexing, chống gõ nhầm chính tả và xếp hạng độ liên quan)
    """
    search_query = request.GET.get('search', '').strip()

    documents = Document.objects.filter(user=request.user)
    recent_attempts = UserQuizAttempt.objects.filter(user=request.user).select_related('quiz')

    if search_query:
        if connection.vendor == 'postgresql':
            from django.contrib.postgres.search import TrigramSimilarity, SearchVector, SearchQuery, SearchRank

            # 1. Tìm trong tài liệu: Tận dụng GIN Trigram Index trên filename và Full-Text trên extracted_text
            doc_vector = SearchVector('extracted_text', config='simple')
            doc_query = SearchQuery(search_query, config='simple')

            documents = documents.annotate(
                similarity=TrigramSimilarity('filename', search_query),
                rank=SearchRank(doc_vector, doc_query)
            ).filter(
                Q(similarity__gt=0.15) | Q(rank__gt=0.01) | Q(filename__icontains=search_query) | Q(extracted_text__icontains=search_query)
            ).order_by('-similarity', '-rank', '-created_at')

            # 2. Tìm trong lịch sử thi: Tận dụng GIN Trigram Index trên Quiz title
            recent_attempts = recent_attempts.annotate(
                similarity=TrigramSimilarity('quiz__title', search_query)
            ).filter(
                Q(similarity__gt=0.15) | Q(quiz__title__icontains=search_query)
            ).order_by('-similarity', '-completed_at')[:5]

        else:
            # Fallback an toàn cho môi trường test SQLite
            documents = documents.filter(
                Q(filename__icontains=search_query) |
                Q(extracted_text__icontains=search_query)
            ).order_by('-created_at')

            recent_attempts = recent_attempts.filter(
                Q(quiz__title__icontains=search_query)
            ).order_by('-completed_at')[:5]
    else:
        documents = documents.order_by('-created_at')
        recent_attempts = recent_attempts.order_by('-completed_at')[:5]

    context = {
        'documents': documents,
        'total_documents': documents.count(),
        'search_query': search_query,
        'recent_attempts': recent_attempts,
    }
    return render(request, 'core/dashboard.html', context)