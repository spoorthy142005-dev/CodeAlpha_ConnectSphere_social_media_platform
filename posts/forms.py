from django import forms
from django.core.exceptions import ValidationError
from .models import Post, Comment, Community, validate_post_image, validate_community_icon
from django.utils.text import slugify


TOPIC_CHOICES = [
    ('', '— No Topic —'),
    ('technology', 'Technology & AI'),
    ('design', 'Design & UI/UX'),
    ('science', 'Science & Research'),
    ('art', 'Art & Photography'),
    ('business', 'Business & Startups'),
    ('culture', 'Culture & Society'),
    ('career', 'Career & Engineering'),
]


class PostCreateForm(forms.ModelForm):
    topic = forms.ChoiceField(
        choices=TOPIC_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control post-topic-select'})
    )

    class Meta:
        model = Post
        fields = ['content', 'image', 'topic', 'community', 'audience']
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
            'community': forms.Select(attrs={
                'class': 'form-control post-community-select',
            }),
            'audience': forms.Select(attrs={
                'class': 'form-control post-audience-select',
            }),
        }

    def __init__(self, *args, user=None, community=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if 'audience' in self.fields:
            self.fields['audience'].required = False

        if community:
            self.fields['community'].initial = community
            self.fields['community'].widget = forms.HiddenInput()
            self.fields['audience'].initial = 'community'
        elif user and user.is_authenticated:
            # Show communities user has joined
            joined_community_ids = user.community_memberships.values_list('community_id', flat=True)
            self.fields['community'].queryset = Community.objects.filter(id__in=joined_community_ids)
            self.fields['community'].empty_label = "— Public Sphere (No Community) —"
            self.fields['community'].required = False
            default_aud = getattr(user.profile, 'default_post_audience', 'public')
            self.fields['audience'].initial = default_aud
        else:
            self.fields['community'].queryset = Community.objects.none()
            self.fields['community'].required = False

    def clean(self):
        cleaned_data = super().clean()
        content = (cleaned_data.get('content') or '').strip()
        image = cleaned_data.get('image')
        audience = cleaned_data.get('audience')
        community = cleaned_data.get('community')

        if not audience:
            default_aud = 'public'
            if self.user and hasattr(self.user, 'profile'):
                default_aud = getattr(self.user.profile, 'default_post_audience', 'public')
            cleaned_data['audience'] = default_aud
            audience = default_aud

        if not content and not image:
            raise ValidationError("Please write some text or attach an image to publish a post.")
        if audience == 'community' and not community:
            # If community was not selected, default audience to public
            cleaned_data['audience'] = 'public'
        return cleaned_data


class PostEditForm(forms.ModelForm):
    topic = forms.ChoiceField(
        choices=TOPIC_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Post
        fields = ['content', 'image', 'topic', 'audience']
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
            'audience': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'audience' in self.fields:
            self.fields['audience'].required = False

    def clean(self):
        cleaned_data = super().clean()
        content = (cleaned_data.get('content') or '').strip()
        image = cleaned_data.get('image')
        audience = cleaned_data.get('audience')

        if not audience and self.instance:
            cleaned_data['audience'] = self.instance.audience or 'public'

        # If editing and clearing existing content without an image
        if not content and not image and not self.instance.image:
            raise ValidationError("Your post must have either text content or an image.")
        return cleaned_data


class CommunityForm(forms.ModelForm):
    topic = forms.ChoiceField(
        choices=[(c[0], c[1]) for c in TOPIC_CHOICES if c[0]],
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Community
        fields = ['name', 'slug', 'description', 'topic', 'icon']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g., Python Architects', 'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'placeholder': 'e.g., python-architects', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'placeholder': 'Describe purpose, discussion guidelines, and rules...', 'rows': 4, 'class': 'form-control'}),
            'icon': forms.FileInput(attrs={'class': 'form-control-file', 'accept': 'image/*'}),
        }
        help_texts = {
            'slug': 'Unique URL identifier: lowercase letters, numbers, and hyphens only.',
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if len(name) < 3:
            raise ValidationError("Community name must be at least 3 characters long.")
        qs = Community.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("A community with this name already exists. Please choose another name.")
        return name

    def clean_slug(self):
        slug = self.cleaned_data.get('slug', '').strip()
        name = self.cleaned_data.get('name', '').strip()
        if not slug and name:
            slug = slugify(name)
        else:
            slug = slugify(slug)

        if not slug:
            raise ValidationError("A valid slug is required.")

        qs = Community.objects.filter(slug__iexact=slug)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("This community slug is already taken. Please choose another.")
        return slug



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
