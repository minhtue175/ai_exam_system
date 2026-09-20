from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import UserRegistrationForm, UserLoginForm
from apps.core.security import RateLimiter, get_client_ip

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
    """User Login với bảo vệ chống Brute-force mật khẩu"""
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
                messages.error(request, 'Tên đăng nhập hoặc mật khẩu không đúng!')
    else:
        form = UserLoginForm()
    
    return render(request, 'users/login.html', {'form': form})

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
    from django.db.models import Avg, Count

    user = request.user

    # Stats
    total_quizzes = UserQuizAttempt.objects.filter(user=user).count()
    avg_score = UserQuizAttempt.objects.filter(user=user).aggregate(avg=Avg('score'))['avg'] or 0
    total_documents = Document.objects.filter(user=user).count()
    recent_attempts = UserQuizAttempt.objects.filter(user=user).select_related('quiz').order_by('-completed_at')[:5]

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