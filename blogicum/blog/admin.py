from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth import get_user_model
from .models import Category, Location, Post, Comment

User = get_user_model()

admin.site.register(Category)
admin.site.register(Location)
admin.site.register(Post)
admin.site.register(Comment)

# Разрегистрируем и регистрируем User с UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
