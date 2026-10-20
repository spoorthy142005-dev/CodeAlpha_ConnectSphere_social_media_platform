from django import forms
from django.core.exceptions import ValidationError
from .models import Post, Comment, validate_post_image


class PostCreateForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['content', 'image']
        widgets = {
            'content': forms.Textarea(attrs={
                'placeholder': "What's happening in your sphere? Share thoughts, links, or ideas...",
                'rows': 3,
                'class': 'form-control composer-textarea',
                'maxlength': '2000',
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control-file post-image-input',
                'accept': 'image/*',
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        content = (cleaned_data.get('content') or '').strip()
        image = cleaned_data.get('image')

        if not content and not image:
            raise ValidationError("Please write some text or attach an image to publish a post.")
        return cleaned_data


class PostEditForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['content', 'image']
        widgets = {
            'content': forms.Textarea(attrs={
                'placeholder': "Update your post content...",
                'rows': 4,
                'class': 'form-control',
                'maxlength': '2000',
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control-file',
                'accept': 'image/*',
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        content = (cleaned_data.get('content') or '').strip()
        image = cleaned_data.get('image')

        # If editing and clearing existing content without an image
        if not content and not image and not self.instance.image:
            raise ValidationError("Your post must have either text content or an image.")
        return cleaned_data


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.TextInput(attrs={
                'placeholder': 'Add a constructive comment...',
                'class': 'form-control comment-input',
                'maxlength': '1000',
                'autocomplete': 'off',
            }),
        }
        labels = {
            'content': '',
        }

    def clean_content(self):
        content = self.cleaned_data.get('content', '').strip()
        if not content:
            raise ValidationError("Comment cannot be empty.")
        if len(content) > 1000:
            raise ValidationError("Comment cannot exceed 1000 characters.")
        return content
