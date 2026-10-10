from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.http import JsonResponse
import json
import logging

from .forms import UserRegistrationForm, UserLoginForm, ForgotPasswordForm, ResetPasswordConfirmForm
from apps.core.security import RateLimiter, get_client_ip
from .tasks import send_password_reset_email_task

logger = logging.getLogger(__name__)
User = get_user_model()

def register_view(request):
    """User Registration với bảo vệ chống Spam bằng Rate Limiter"""
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    
    ip = get_client_ip(request)
    reg_key = f"reg_ip_{ip}"

    # Giới hạn 5 lần đăng ký trong 15 phút trên mỗi IP
    is_limited, remaining = RateLimiter.is_rate_limited(reg_key, max_attempts=5, lock_seconds=900)
    if is_limited:
        messages.error(request, f"Bạn đã đăng ký quá nhiều lần từ địa chỉ này. Vui lòng thử lại sau {remaining} giây.")
        return render(request, 'users/register.html', {'form': UserRegistrationForm()})

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            RateLimiter.record_failure(reg_key, max_attempts=5, lock_seconds=900)
            login(request, user)
            messages.success(request, 'Đăng ký thành công!')
            return redirect('core:dashboard')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'users/register.html', {'form': form})

def login_view(request):
    """User Login với bảo vệ chống Brute-force mật khẩu & Phát hiện tài khoản Google"""
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    
    ip = get_client_ip(request)
    ip_key = f"login_ip_{ip}"

    # Kiểm tra IP có đang bị khóa không (tối đa 5 lần sai trong 5 phút)
    is_ip_limited, ip_remaining = RateLimiter.is_rate_limited(ip_key, max_attempts=5, lock_seconds=300)
    if is_ip_limited:
        messages.error(request, f"Địa chỉ IP này đã thử đăng nhập sai quá nhiều lần. Vui lòng thử lại sau {ip_remaining} giây.")
        return render(request, 'users/login.html', {'form': UserLoginForm()})

    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username'].strip()
            password = form.cleaned_data['password']
            user_key = f"login_user_{username.lower()}"

            # Kiểm tra tài khoản có đang bị khóa do thử sai liên tiếp không
            is_user_limited, user_remaining = RateLimiter.is_rate_limited(user_key, max_attempts=5, lock_seconds=300)
            if is_user_limited:
                messages.error(request, f"Tài khoản '{username}' đang bị tạm khóa do nhập sai mật khẩu nhiều lần. Vui lòng chờ {user_remaining} giây.")
                return render(request, 'users/login.html', {'form': form})

            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                # Đăng nhập thành công: xóa lịch sử thất bại của IP và Username
                RateLimiter.reset(ip_key)
                RateLimiter.reset(user_key)
                login(request, user)
                messages.success(request, f'Chào mừng {user.username}!')
                return redirect('core:dashboard')
            else:
                # Thử sai: ghi nhận thất bại
                RateLimiter.record_failure(ip_key, max_attempts=5, lock_seconds=300)
                RateLimiter.record_failure(user_key, max_attempts=5, lock_seconds=300)
                
                # Kiểm tra tài khoản đã liên kết Google nhưng chưa tạo mật khẩu riêng
                existing_user = User.objects.filter(username__iexact=username).first() or \
                                User.objects.filter(email__iexact=username).first()
                if existing_user and not existing_user.has_usable_password():
                    messages.warning(
                        request,
                        '⚠️ Tài khoản này được đăng ký qua Google và chưa thiết lập mật khẩu riêng. '
                        'Vui lòng nhấn "Đăng nhập với Google" hoặc nhấn "Quên mật khẩu" bên dưới để tạo mật khẩu độc lập.'
                    )
                else:
                    messages.error(request, 'Tên đăng nhập hoặc mật khẩu không đúng!')
    else:
        form = UserLoginForm()
    
    return render(request, 'users/login.html', {'form': form})

def forgot_password_view(request):
    """Xử lý yêu cầu quên mật khẩu: Gửi email reset link qua queue_high (Celery)"""
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].strip().lower()
            user = User.objects.filter(email__iexact=email).first()

            if user:
                # Tạo token an toàn
                token = default_token_generator.make_token(user)
                uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
                reset_link = request.build_absolute_uri(
                    reverse('users:reset_password_confirm', kwargs={'uidb64': uidb64, 'token': token})
                )
                
                # Gửi email bất đồng bộ qua queue_high (phản hồi web ngay tức thì < 0.1s)
                try:
                    send_password_reset_email_task.delay(user.id, reset_link, user.email)
                except Exception as celery_err:
                    logger.warning(f"Celery offline, gửi email trực tiếp: {celery_err}")
                    from django.core.mail import send_mail
                    from django.conf import settings
                    send_mail(
                        subject="[AI Exam System] Yêu cầu đặt lại mật khẩu của bạn",
                        message=f"Vui lòng nhấn vào liên kết sau để đặt lại mật khẩu: {reset_link}",
                        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@aiexam.local'),
                        recipient_list=[user.email],
                        fail_silently=True
                    )

            # Luôn thông báo thành công dù email có tồn tại hay không để chống quét tài khoản (Security Best Practice)
            messages.success(
                request,
                'Nếu địa chỉ email tồn tại trong hệ thống, chúng tôi đã gửi liên kết đặt lại mật khẩu đến hộp thư của bạn. '
                'Vui lòng kiểm tra hộp thư (kể cả mục Spam).'
            )
            return redirect('users:login')
    else:
        form = ForgotPasswordForm()

    return render(request, 'users/forgot_password.html', {'form': form})

def reset_password_confirm_view(request, uidb64, token):
    """Đặt mật khẩu mới sau khi nhấn liên kết trong email"""
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        messages.error(request, 'Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn!')
        return redirect('users:forgot_password')

    if request.method == 'POST':
        form = ResetPasswordConfirmForm(request.POST)
        if form.is_valid():
            new_password = form.cleaned_data['new_password1']
            user.set_password(new_password)
            user.save()
            messages.success(
                request,
                '🎉 Đặt lại mật khẩu thành công! Giờ bạn có thể đăng nhập bằng mật khẩu mới này '
                '(và vẫn có thể đăng nhập bằng Google nếu cùng email).'
            )
            return redirect('users:login')
    else:
        form = ResetPasswordConfirmForm()

    return render(request, 'users/reset_password_confirm.html', {'form': form, 'validlink': True})

def google_login_view(request):
    """
    Xử lý Đăng nhập Google (OAuth2 / Google Identity Services):
    - Tự động liên kết tài khoản (Account Linking) nếu email đã tồn tại.
    - Tự động đăng ký mới (với unusable password) nếu người dùng lần đầu đăng nhập bằng Google.
    - Khi dùng chức năng quên mật khẩu, tài khoản sẽ có thêm mật khẩu độc lập mà không mất liên kết Google!
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Chỉ chấp nhận phương thức POST'}, status=405)

    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip().lower()
        full_name = data.get('name', '').strip()
        google_id = data.get('google_id', '')

        if not email:
            return JsonResponse({'status': 'error', 'message': 'Không tìm thấy thông tin email từ Google'}, status=400)

        # 1. Tìm kiếm User theo email
        user = User.objects.filter(email__iexact=email).first()

        if user:
            # Case A: Tài khoản đã có sẵn -> Thực hiện Account Linking & Đăng nhập ngay
            logger.info(f"Đăng nhập thành công qua Google cho tài khoản hiện có: {user.username} ({email})")
            login(request, user)
            messages.success(request, f'Chào mừng bạn trở lại, {user.username}!')
            return JsonResponse({'status': 'success', 'redirect_url': reverse('core:dashboard')})
        else:
            # Case B: Chưa có tài khoản -> Tự động tạo mới
            base_username = email.split('@')[0]
            username = base_username
            counter = 1
            while User.objects.filter(username__iexact=username).exists():
                username = f"{base_username}_{counter}"
                counter += 1

            new_user = User.objects.create_user(
                username=username,
                email=email,
                first_name=full_name[:30] if full_name else ''
            )
            # Đặt unusable password vì tài khoản tạo bằng Google
            new_user.set_unusable_password()
            new_user.save()

            login(request, new_user)
            logger.info(f"Tạo mới tài khoản qua Google thành công: {new_user.username} ({email})")
            messages.success(request, f'Chào mừng bạn đến với AI Exam System, {new_user.username}!')
            return JsonResponse({'status': 'success', 'redirect_url': reverse('core:dashboard')})

    except Exception as e:
        logger.error(f"Lỗi xử lý đăng nhập Google: {e}")
        return JsonResponse({'status': 'error', 'message': f'Lỗi hệ thống: {str(e)}'}, status=500)

@login_required
def logout_view(request):
    """User Logout"""
    logout(request)
    messages.info(request, 'Đã đăng xuất thành công!')
    return redirect('users:login')

@login_required
def profile_view(request):
    """User Profile — Xem và chỉnh sửa thông tin cá nhân"""
    from apps.documents.models import Document
    from apps.quizzes.models import UserQuizAttempt
    from apps.core.cache_utils import CacheManager
    from django.db.models import Avg, Count

    user = request.user

    # A2: Cache-Aside Pipeline — Kiểm tra Cache (TTL = 300s / 5 phút)
    cached_stats = CacheManager.get_profile_stats(user.id)
    if cached_stats is not None:
        total_quizzes = cached_stats.get('total_quizzes', 0)
        avg_score = cached_stats.get('avg_score', 0)
        total_documents = cached_stats.get('total_documents', 0)
    else:
        # Gộp Aggregation: Count và Avg thành 1 query duy nhất, tiết kiệm round-trip DB
        stats = UserQuizAttempt.objects.filter(user=user).aggregate(
            total_quizzes=Count('id'),
            avg_score=Avg('score')
        )
        total_quizzes = stats['total_quizzes'] or 0
        avg_score = stats['avg_score'] or 0
        total_documents = Document.objects.filter(user=user).count()

        CacheManager.set_profile_stats(user.id, {
            'total_quizzes': total_quizzes,
            'avg_score': avg_score,
            'total_documents': total_documents,
        })

    recent_attempts = UserQuizAttempt.objects.filter(user=user).select_related('quiz', 'quiz__document').order_by('-completed_at')[:5]

    if request.method == 'POST':
        action = request.POST.get('action', 'update_profile')

        if action == 'update_profile':
            new_username = request.POST.get('username', '').strip()
            new_email = request.POST.get('email', '').strip().lower()
            new_phone = request.POST.get('phone', '').strip()

            # Validate username
            if new_username and new_username != user.username:
                from .models import User
                if User.objects.filter(username__iexact=new_username).exclude(pk=user.pk).exists():
                    messages.error(request, 'Tên đăng nhập đã tồn tại!')
                    return redirect('users:profile')
                user.username = new_username

            # Validate email
            if new_email and new_email != user.email:
                from .models import User
                if User.objects.filter(email__iexact=new_email).exclude(pk=user.pk).exists():
                    messages.error(request, 'Email đã được sử dụng!')
                    return redirect('users:profile')
                user.email = new_email

            user.phone = new_phone

            # Avatar upload
            if 'avatar' in request.FILES:
                user.avatar = request.FILES['avatar']

            user.save()
            messages.success(request, '✅ Cập nhật thông tin thành công!')
            return redirect('users:profile')

        elif action == 'change_password':
            from django.contrib.auth import update_session_auth_hash
            old_password = request.POST.get('old_password', '')
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')

            if not user.check_password(old_password):
                messages.error(request, 'Mật khẩu hiện tại không đúng!')
            elif len(new_password) < 8:
                messages.error(request, 'Mật khẩu mới phải có ít nhất 8 ký tự!')
            elif new_password != confirm_password:
                messages.error(request, 'Mật khẩu xác nhận không khớp!')
            else:
                user.set_password(new_password)
                user.save()
                update_session_auth_hash(request, user)
                messages.success(request, '✅ Đổi mật khẩu thành công!')
            return redirect('users:profile')

    context = {
        'total_quizzes': total_quizzes,
        'avg_score': round(avg_score, 1),
        'total_documents': total_documents,
        'recent_attempts': recent_attempts,
    }
    return render(request, 'users/profile.html', context)