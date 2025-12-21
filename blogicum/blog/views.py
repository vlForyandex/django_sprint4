from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Count
from django.urls import reverse
from django.views.generic import (
    CreateView,
    UpdateView,
    DeleteView
)
from django.contrib.auth.mixins import LoginRequiredMixin

from .models import Post, Category, Comment
from .forms import PostForm, CommentForm, UserEditForm

User = get_user_model()

POSTS_PER_PAGE = 10


def get_published_posts(queryset=None):
    """Возвращает queryset с опубликованными постами.

    Args:
        queryset: Опциональный базовый queryset. Если None, использует Post.objects.all()
    """
    if queryset is None:
        queryset = Post.objects.all()

    return (
        queryset
        .filter(
            pub_date__lte=timezone.now(),
            is_published=True,
            category__is_published=True,
        )
        .select_related("author", "location", "category")
    )


def annotate_comment_count(queryset):
    """Добавляет аннотацию с количеством комментариев."""
    return queryset.annotate(comment_count=Count("comments"))


def paginate_queryset(request, queryset, per_page=POSTS_PER_PAGE):
    """Создает пагинацию для queryset.

    Args:
        request: HTTP request объект
        queryset: Queryset для пагинации
        per_page: Количество объектов на странице

    Returns:
        Page object
    """
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get("page")
    return paginator.get_page(page_number)


def index(request):
    """Главная страница."""
    post_list = (
        annotate_comment_count(get_published_posts())
        .order_by(*Post._meta.ordering)
    )
    page_obj = paginate_queryset(request, post_list)
    context = {"page_obj": page_obj}
    return render(request, "blog/index.html", context)


def post_detail(request, post_id):
    """Детальная страница поста."""
    post = get_object_or_404(Post, pk=post_id)

    # Если пост не опубликован, проверяем, является ли пользователь автором
    if not (
        post.pub_date <= timezone.now()
        and post.is_published
        and post.category.is_published
    ):
        if request.user != post.author:
            # Если пользователь не автор, показываем 404
            post = get_object_or_404(
                Post,
                pk=post_id,
                pub_date__lte=timezone.now(),
                is_published=True,
                category__is_published=True,
            )

    comments = post.comments.select_related("author").all()
    form = CommentForm()
    context = {"post": post, "form": form, "comments": comments}
    return render(request, "blog/detail.html", context)


def category_posts(request, category_slug):
    """Страница категории."""
    category = get_object_or_404(
        Category, slug=category_slug, is_published=True
    )
    post_list = (
        annotate_comment_count(
            get_published_posts(category.posts.all())
        )
        .order_by(*Post._meta.ordering)
    )
    page_obj = paginate_queryset(request, post_list)
    context = {"category": category, "page_obj": page_obj}
    return render(request, "blog/category.html", context)


def profile(request, username):
    """Страница профиля пользователя."""
    profile_user = get_object_or_404(User, username=username)

    if request.user == profile_user:
        # Автор видит все свои посты
        post_list = (
            annotate_comment_count(
                profile_user.posts
                .select_related("author", "location", "category")
            )
            .order_by(*Post._meta.ordering)
        )
    else:
        # Остальные видят только опубликованные посты
        post_list = (
            annotate_comment_count(
                get_published_posts(profile_user.posts.all())
            )
            .order_by(*Post._meta.ordering)
        )

    page_obj = paginate_queryset(request, post_list)
    context = {"profile": profile_user, "page_obj": page_obj}
    return render(request, "blog/profile.html", context)


@login_required
def edit_profile(request):
    """Редактирование профиля пользователя."""
    form = UserEditForm(request.POST or None, instance=request.user)
    if form.is_valid():
        form.save()
        return redirect("blog:profile", username=request.user.username)
    context = {"form": form}
    return render(request, "blog/user.html", context)


class PostCreateView(LoginRequiredMixin, CreateView):
    """Создание нового поста."""

    model = Post
    form_class = PostForm
    template_name = "blog/create.html"

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "blog:profile", kwargs={"username": self.request.user.username}
        )


class PostUpdateView(LoginRequiredMixin, UpdateView):
    """Редактирование поста."""

    model = Post
    form_class = PostForm
    template_name = "blog/create.html"
    pk_url_kwarg = "post_id"

    def dispatch(self, request, *args, **kwargs):
        post = self.get_object()
        if post.author != request.user:
            return redirect("blog:post_detail", post_id=post.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse("blog:post_detail", kwargs={"post_id": self.object.pk})


class PostDeleteView(LoginRequiredMixin, DeleteView):
    """Удаление поста."""

    model = Post
    template_name = "blog/create.html"
    pk_url_kwarg = "post_id"

    def dispatch(self, request, *args, **kwargs):
        post = self.get_object()
        if post.author != request.user:
            return redirect("blog:post_detail", post_id=post.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse(
            "blog:profile", kwargs={"username": self.request.user.username}
        )


@login_required
def add_comment(request, post_id):
    """Добавление комментария."""
    post = get_object_or_404(Post, pk=post_id)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.author = request.user
        comment.post = post
        comment.save()
    return redirect("blog:post_detail", post_id=post_id)


class CommentUpdateView(LoginRequiredMixin, UpdateView):
    """Редактирование комментария."""

    model = Comment
    form_class = CommentForm
    template_name = "blog/comment.html"
    pk_url_kwarg = "comment_id"

    def dispatch(self, request, *args, **kwargs):
        comment = self.get_object()
        if comment.author != request.user:
            return redirect("blog:post_detail", post_id=comment.post.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse("blog:post_detail", kwargs={"post_id": self.object.post.pk})


class CommentDeleteView(LoginRequiredMixin, DeleteView):
    """Удаление комментария."""

    model = Comment
    template_name = "blog/comment.html"
    pk_url_kwarg = "comment_id"

    def dispatch(self, request, *args, **kwargs):
        comment = self.get_object()
        if comment.author != request.user:
            return redirect("blog:post_detail", post_id=comment.post.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse("blog:post_detail", kwargs={"post_id": self.object.post.pk})
